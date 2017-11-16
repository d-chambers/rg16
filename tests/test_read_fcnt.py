"""
tests for reading fcnt files
"""
import glob
import io
from os.path import join

import obspy
import pytest

import rg16
import rg16.core
from rg16.core import read_rg16

FCNT_FILES = glob.glob(join(pytest.test_data_path, 'fcnt', '*'))


@pytest.fixture(scope='module', params=FCNT_FILES)
def fcnt_file(request):
    return request.param


@pytest.fixture(scope='module')
def fcnt_stream(fcnt_file):
    """ read in the fcnt files and return """
    return read_rg16(fcnt_file)


class TestIsFairfieldRG16:
    @pytest.mark.parametrize('path', FCNT_FILES)
    def test_is_rg16(self, path):
        assert rg16.core.is_rg16(path)

    def test_non_rg16_files_raise(self):
        """ file that are not rg16 should raise """
        bad_file = io.BytesIO(b'clearly not a rg16 file')
        with pytest.raises(ValueError):
            read_rg16(bad_file)


class TestStream:
    """ basic tests for stream """
    # these are the sample rates supported by manufacturer of Zland inst.
    supported_samps = {250, 500, 1000, 2000}
    supported_components = {1, 3}

    def test_supported_samps(self, fcnt_stream):
        """ ensure all the sampling rates are supported by inst. """
        for tr in fcnt_stream:
            assert tr.stats.sampling_rate in self.supported_samps

    def test_components(self, fcnt_stream):
        """ ensure there are either 1 type of channel or 3 """
        seed_ids = len({tr.id for tr in fcnt_stream})
        assert seed_ids in self.supported_components

    def test_can_write(self, fcnt_stream):
        """ ensure the resulting stream can be written as mseed """
        bytstr = io.BytesIO()
        # test passes if this doesn't raise
        fcnt_stream.write(bytstr, 'mseed')


class TestReadNoData:
    def test_no_data(self, fcnt_file):
        """ ensure no data is returned when the option is used """
        st = read_rg16(fcnt_file, headonly=True)
        for tr in st:
            assert len(tr.data) == 0
            assert tr.stats.npts != 0


class TestStartTimeEndTime:
    def test_starttime_endtime(self, fcnt_file):
        """ ensure starttimes and endtimes filter traces returned """
        # get good times to filter on
        st = read_rg16(fcnt_file, headonly=True)
        stats = st[0].stats
        t1, t2 = stats.starttime.timestamp, stats.endtime.timestamp
        tpoint = obspy.UTCDateTime((t1 + t2) / 2.)
        # this should only return one trace for each channel
        st = read_rg16(fcnt_file, starttime=tpoint, endtime=tpoint)
        ids = {tr.id for tr in st}
        assert len(st) == len(ids)
        # make sure tpoint is in the time range
        start = st[0].stats.starttime
        end = st[0].stats.endtime
        assert start < tpoint < end


class TestMerge:
    def test_merge(self, fcnt_file):
        """ ensure the merge option of read_rg16 merges all contiguous
        traces together """
        st_merged = read_rg16(fcnt_file, merge=True)
        st = read_rg16(fcnt_file).merge()
        assert len(st) == len(st_merged)
        assert st == st_merged
