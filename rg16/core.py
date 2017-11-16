"""
Functions to read waveform data from Receiver Gather 1.6-1 foramt.
This format is used for continuous data by Farfield's (fairfieldnodal.com)
Zland product line (http://fairfieldnodal.com/equipment/zland).

Inspired by a similar project by Thomas Lecocq
found here: https://github.com/iceseismic/Fairfield-Receiver-Gather

Some useful diagrams, provided by Faifield technical support, for
understanding Base Scan intervals, data format, and sensor type numbers
can be found here: https://imgur.com/a/4aneG
"""
import copy

import numpy as np
from obspy.core import Stream, Trace, Stats, UTCDateTime

from rg16.utils import read, open_file, read_block

# ------------------- define specs of various blocks

# blocks are specified as a list of tuples. Each tuple contains the following:
# (name, startbyte, length, format), explanation as follows:
# name - The name, these will be keys in a returned dict
# startbye - the byte position, relative to the block, to start reading
# length - the number of bytes to read
# format - format to interpret the data being read. see rg16.utils.read.

# header block, combines header block one and two
general_header_block = [
    ('channel_sets', 28, 1, 'bcd'),
    ('num_additional_headers', 11, 1, '>i.'),
    ('extended_headers', [30, 37], [1, 2], ['bcd', '>i2']),
    ('external_headers', [31, 39], [1, 3], ['bcd', '>i3']),
    ('record_length', 46, 3, '>i3'),
    ('base_scan', 22, 1, '>i1'),  # https://imgur.com/a/4aneG
]

# channel set header block
channel_header_block = [
    ('chan_num', 1, 1, 'bcd'),
    ('num_channels', 8, 2, 'bcd'),
    ('ru_channel_number', 30, 1, '>i1'),
]

# combines extended header 1, 2, and 3
extended_header_block = [
    ('num_records', 16 + 32, 4, '>i4'),
    ('collection_method', 32 + 15, 1, '>i1'),
    ('line_number', 64, 4, '>i4'),
    ('receiver_point', 68, 4, '>i4'),
    ('point_index', 69, 1, '>i1'),
]

# combines trace header blocks 0 (20 byte) and 1 to 10 (32 byte)
trace_header_block = [
    ('trace_number', 4, 2, 'bcd'),
    ('num_ext_blocks', 9, 1, '>i1'),
    ('line_number', 20 + 0, 3, '>i3'),
    ('point', 20 + 3, 3, '>i3'),
    ('index', 20 + 6, 1, '>i1'),
    ('samples', 20 + 7, 3, '>i3'),
    ('channel_code', 20 + 20, 1, '>i1'),  # https://imgur.com/a/4aneG
    ('trace_count', 20 + 21, 4, '>i4'),
    ('time', 20 + 2 * 32, 8, '>i8'),
]

# since UTCDateTime cannot be compared to np.inf in py27 get a large timestamp
# after which I will be dead (somebody else's problem)
BIG_TS = UTCDateTime('3000-01-01').timestamp


# ------------------- read and format check functions


@open_file
def read_rg16(fi, headonly=False, starttime=None, endtime=None, merge=False,
              **kwargs):
    """
    Read fairfield nodal's Receiver Gather File Format version 1.6-1.

    Parameters
    ----------
    fi: str or buffer
        A path to the file to read or a buffer of an opened file.
    headonly: bool
        If True don't read data, only header information.
    starttime: Optional, obspy.UTCDateTime
        If not None dont read traces that end before starttime.
    endtime: Optional, obspy.UTCDateTime
        If None None dont read traces that start after endtime.
    merge: bool
        If True merge contiguous data blocks as they are found. For
        continuous data files having 100,000+ traces this will create
        more manageable streams.

    Returns
    -------
    obspy.Stream
    """
    if not is_rg16(fi):
        raise ValueError('read_fcnt was not passed a Fairfield RG 1.6 file')
    # get timestamps
    time1 = UTCDateTime(starttime).timestamp if starttime else 0
    time2 = UTCDateTime(endtime).timestamp if endtime else BIG_TS
    # read general header information
    gheader = read_block(fi, general_header_block)
    # byte number channel sets start at in file
    chan_set_start = (gheader['num_additional_headers'] + 1) * 32
    # get the total number of traces from the channel sets
    num_traces = _get_num_traces(fi, chan_set_start, gheader['channel_sets'])
    # get the byte number the extended headers start
    eheader_start = (gheader['channel_sets']) * 32 + chan_set_start
    # read trace headers
    ex_headers = gheader['extended_headers'] + gheader['external_headers']
    # get byte number trace headers start
    theader_start = eheader_start + (ex_headers * 32)
    # get traces
    traces = _make_traces(fi, theader_start, gheader, num_traces,
                          head_only=headonly, starttime=time1, endtime=time2,
                          merge=merge)
    return Stream(traces=traces)


@open_file
def is_rg16(fi, **kwargs):
    """ reads key information from header to figure out if this is rg16
    from fairfield nodal """
    sample_format = read(fi, 2, 2, 'bcd')
    manufacturer_code = read(fi, 16, 1, 'bcd')
    version = read(fi, 42, 2, None)
    con1 = version == b'\x01\x06' and sample_format == 8058
    return con1 and manufacturer_code == 20


# ------------ helper functions for formatting specific blocks


def _trace_list_to_rec_array(traces):
    """ return a recarray from the trace list. These are seperated into
     two arrays due to a weird issue with numpy.sort returning and error
     set. """
    # get the id, starttime, endtime into a recarray
    dtype1 = [('id', object), ('starttime', float), ('endtime', float)]
    dtype2 = [('data', object), ('stats', object)]
    data1 = [(tr.id, tr.stats.starttime.timestamp, tr.stats.endtime.timestamp)
             for tr in traces]
    data2 = [(tr.data, tr.stats) for tr in traces]
    ar1 = np.array(data1, dtype=dtype1)  # array of id, starttime, endtime
    ar2 = np.array(data2, dtype=dtype2)  # array of data, stats objects
    #
    sort_index = np.argsort(ar1, order=['id', 'starttime'])
    return ar1[sort_index], ar2[sort_index]


def _get_trace_groups(ar, diff):
    """
    Return an array of ints where each element corresponds to a pre-merged
    trace row. All trace rows with the same group number can be merged.
    """
    # get a bool of if ids are the same as the next row down
    ids_different = np.ones(len(ar), dtype=bool)
    ids_different[1:] = ar['id'][1:] != ar['id'][:-1]
    # get bool of endtimes within one sample of starttime of next row
    disjoint = np.zeros(len(ar), dtype=bool)
    start_end_diffs = ar['starttime'][1:] - ar['endtime'][:-1]
    disjoint[:-1] = np.abs(start_end_diffs) <= diff
    # get groups (not disjoint, not different ids)
    return np.cumsum(ids_different & disjoint)


def _quick_merge(traces, small_number=.000001):
    """
    Quickly merge traces together that are of the same datatype and
    sampling_rate and dont have data overlaps.
    """
    # make sure sampling rates are all the same
    assert len({tr.stats.sampling_rate for tr in traces}) == 1
    assert len({tr.data.dtype for tr in traces}) == 1
    sampling_rate = traces[0].stats.sampling_rate
    diff = 1. / sampling_rate + small_number
    # get the array
    ar, trace_ar = _trace_list_to_rec_array(traces)
    # get groups of traces that can be merged together
    group = _get_trace_groups(ar, diff)
    group_numbers = np.unique(group)
    out = [None] * len(group_numbers)  # init output list
    for index, gnum in enumerate(group_numbers):
        # ar_to_merge = ar[group == gnum]
        trace_ar_to_merge = trace_ar[group == gnum]
        new_data = np.concatenate(trace_ar_to_merge['data'])
        # get updated stats object
        new_stats = copy.deepcopy(trace_ar_to_merge['stats'][0])
        new_stats.npts = len(new_data)
        out[index] = Trace(data=new_data, header=new_stats)
    return out


def _make_traces(fi, data_block_start, gheader, num_traces, head_only=False,
                 starttime=None, endtime=None, merge=False):
    """ make obspy traces from trace blocks and headers """
    traces = []  # list to store traces
    trace_position = data_block_start
    for _ in range(num_traces):
        theader = read_block(fi, trace_header_block, trace_position)
        stats = _make_stats(theader, gheader)
        if stats.endtime < starttime or stats.starttime > endtime:
            continue
        if head_only:
            data = np.array([])
        else:
            data_start = trace_position + 20 + theader['num_ext_blocks'] * 32
            data = read(fi, data_start, theader['samples'] * 4, '>f4')
        # update trace position
        trace_position += stats.npts * 4 + theader['num_ext_blocks'] * 32 + 20
        traces.append(Trace(data=data, header=stats))
    if merge:
        traces = _quick_merge(traces)
    return traces


def _get_num_traces(fi, byte_start, number_channel_sets):
    """
    Get the number of traces contained in this file by reading trace sets.

    Note: This function was created because multiplying channel_set in
    the general header by num_records in the general header doesn't work for
    larger files.
    """
    channel_sets = [read_block(fi, channel_header_block, byte_start + x * 32)
                    for x in range(number_channel_sets)]
    return np.sum([x['num_channels'] for x in channel_sets])


def _make_stats(theader, gheader):
    """ make Stats object """
    sampling_rate = int(1000. / (gheader['base_scan'] / 16.))

    statsdict = dict(
        starttime=UTCDateTime(theader['time'] / 1000000.),
        sampling_rate=sampling_rate,
        npts=theader['samples'],
        network=str(theader['line_number']),
        station=str(theader['point']),
        location=str(theader['index']),
        channel=str(theader['channel_code']),
    )
    return Stats(statsdict)
