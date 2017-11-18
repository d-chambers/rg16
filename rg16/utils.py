"""
Utilities for fanopy
"""
import collections
import copy
import functools
import struct

import numpy as np
from obspy import Trace

BITMAP = np.array([1, 2, 4, 8])[::-1].reshape(4, 1)

TENS = np.power(10, range(12))[::-1]


def open_file(func):
    """
    Decorator to ensure a file buffer is passed as first argument to the
    decorated function.

    :param func:
        callable that takes at least one argument; the first argument must
        be treated as a buffer.
    :return: callable
    """

    @functools.wraps(func)
    def _wrap(*args, **kwargs):
        first_arg = args[0]
        try:
            with open(first_arg, 'rb') as fi:
                args = tuple([fi] + list(args[1:]))
                return func(*args, **kwargs)
        except TypeError:  # assume we have been passed a buffer
            if not hasattr(args[0], 'read') or args[0].closed:
                raise  # type error was in function call, not in opening file
            return func(*args, **kwargs)

    return _wrap


# -------------------- functions for byte chunk reads


READ_FUNCS = {}


def register_read_func(dtype):
    def _wrap(func):
        READ_FUNCS[dtype] = func
        return func

    return _wrap


def read_block(fi, spec, start_bit=0):
    out = {}
    for name, start, length, fmt in spec:
        out[name] = read(fi, start_bit + np.array(start), length, fmt)
    return out


def read(fi, position, length, dtype):
    """
    Read one or more bytes using provided datatype.

    :param fi: A buffer containing the bytes to read.
    :param position: Byte position to start reading.
    :type position: int
    :param length: Length, in bytes, of data to read.
    :type length: int
    :param dtype:
        The data type, all numpy data types are supported plus the following:
            bcd - binary coded decimal
            <i3 - little endian 3 byte int
            >i3 - big endian 3 byte int
            >i. - 4 bit int, left four bits
    :type dtype: str
    :return:
    """
    # if a list is passed as parameters then recurse through each
    if isinstance(position, (collections.Sequence, np.ndarray)):
        assert len(position) == len(length) == len(dtype)
        for pos, leng, dty in zip(position, length, dtype):
            try:
                return read(fi, pos, leng, dty)
            except ValueError:
                pass
        else:
            msg = 'failed to read chunk'
            raise ValueError(msg)
    # non recursive case
    fi.seek(position)
    if dtype in READ_FUNCS:
        return READ_FUNCS[dtype](fi, length)
    else:
        data = np.fromstring(fi.read(int(length)), dtype)
        return data[0] if len(data) == 1 else data


@register_read_func('bcd')
def read_bcd(fi, length):
    """
    Interprets a byte string as binary coded decimals. See:
    https://en.wikipedia.org/wiki/Binary-coded_decimal#Basics

    Raises a ValueError if any any invalid values are found.
    """
    byte_values = fi.read(length)
    ints = np.fromstring(byte_values, dtype='<u1', count=length)
    bits = np.dot(np.unpackbits(ints).reshape(-1, 4), BITMAP)
    if np.any(bits > 9):
        raise ValueError('%s are not valid bcd values' % byte_values)
    return np.dot(TENS[-len(bits):], bits)[0]


@register_read_func(None)
def read_bytes(fi, length):
    """ simply read raw bytes """
    return fi.read(length)


@register_read_func('<i3')
def read_24_bit_little(fi, length):
    """ read a 3 byte int, little endian """
    chunk = fi.read(length)
    return struct.unpack('<I', chunk + b'\x00')[0]


@register_read_func('>i3')
def read_24_bit_big(fi, length):
    """ read a 3 byte int, big endian """
    chunk = fi.read(length)
    return struct.unpack('>I', b'\x00' + chunk)[0]


@register_read_func('>i.')
def read_4_bit_left(fi, length):
    """ read the four bits on the left """
    assert length == 1, 'half byte reads only support 1 byte length'
    ints = np.fromstring(fi.read(length), dtype='<u1')[0]
    return np.bitwise_and(ints >> 4, 0x0f)


@register_read_func('<i.')
def read_4_bit_right(fi, length):
    """ read the four bits on the right """
    assert length == 1, 'half byte reads only support 1 byte length'
    ints = np.fromstring(fi.read(length), dtype='<u1')[0]
    return np.bitwise_and(ints, 0x0f)


# ---------------------- stream manipulation stuff


def quick_merge(traces, small_number=.000001):
    """
    Specialized function for merging traces found in rg16 file.

    Requires that are of the same datatype, have the same sampling_rate,
    and dont have data overlaps. For streams with large numbers of traces
    this can be many orders of magnitude faster than obspy.Stream.merge.

    :param traces: list of ObsPy :class:`~obspy.core.trace.Trace` objects.
    :param small_number:
        A small number for determining if traces should be merged. Should be
        much less than one sample spacing.
    :return: list of ObsPy :class:`~obspy.core.trace.Trace` objects.
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


def _trace_list_to_rec_array(traces):
    """
    return a recarray from the trace list. These are seperated into
    two arrays due to a weird issue with numpy.sort returning and error
    set.
    """
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
