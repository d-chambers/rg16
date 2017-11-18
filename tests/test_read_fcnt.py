"""
tests for reading fcnt files
"""
import glob
import io
import unittest
from os.path import join, dirname

import obspy

from rg16.core import read_rg16, is_rg16

TEST_FCNT_DIRECTORY = join(dirname(__file__), 'test_data', 'fcnt')
FCNT_FILES = glob.glob(join(TEST_FCNT_DIRECTORY, '*'))
FCNT_STREAMS = [read_rg16(x) for x in FCNT_FILES]

assert len(FCNT_FILES), 'No test files found'


class TestIsRG16(unittest.TestCase):
    def test_rg16_files_identified(self):
        """ ensure the rg16 files are correctly labeled as such """
        for fcnt_file in FCNT_FILES:
            self.assertTrue(is_rg16(fcnt_file))

    def test_empty_buffer(self):
        """ ensure an empty buffer returns false"""
        buff = io.BytesIO()
        self.assertFalse(is_rg16(buff))


class TestStream(unittest.TestCase):
    """ basic tests for stream """
    # these are the sample rates supported by manufacturer of Zland inst.
    supported_samps = {250, 500, 1000, 2000}
    supported_components = {1, 3}

    def test_supported_samps(self):
        """ ensure all the sampling rates are supported by inst. """
        for fcnt_stream in FCNT_STREAMS:
            for tr in fcnt_stream:
                self.assertIn(tr.stats.sampling_rate, self.supported_samps)

    def test_components(self):
        """ ensure there are either 1 type of channel or 3 """
        for fcnt_stream in FCNT_STREAMS:
            seed_ids = len({tr.id for tr in fcnt_stream})
            self.assertIn(seed_ids, self.supported_components)

    def test_can_write(self):
        """ ensure the resulting stream can be written as mseed """
        for fcnt_stream in FCNT_STREAMS:
            bytstr = io.BytesIO()
            # test passes if this doesn't raise
            try:
                fcnt_stream.write(bytstr, 'mseed')
            except Exception:
                self.fail('Failed to write to mseed!')

    def test_can_read_from_buffer(self):
        """ ensure each stream can be read from a buffer """
        for fcnt_file in FCNT_FILES:
            with open(fcnt_file, 'rb') as fi:
                buff = io.BytesIO(fi.read())
            buff.seek(0)
            try:
                read_rg16(buff, 'mseed')
            except Exception:
                self.fail('failed to read from bytesIO')


class TestReadHeadOnly(unittest.TestCase):
    def test_no_data(self):
        """ ensure no data is returned when the option is used """
        for fcnt_file in FCNT_FILES:
            st = read_rg16(fcnt_file, headonly=True)
            for tr in st:
                self.assertEqual(len(tr.data), 0)
                self.assertNotEqual(tr.stats.npts, 0)


class TestStartTimeEndTime(unittest.TestCase):
    def test_starttime_endtime(self):
        """ ensure starttimes and endtimes filter traces returned """
        for fcnt_file in FCNT_FILES:
            # get good times to filter on
            st = read_rg16(fcnt_file, headonly=True)
            stats = st[0].stats
            t1, t2 = stats.starttime.timestamp, stats.endtime.timestamp
            tpoint = obspy.UTCDateTime((t1 + t2) / 2.)
            # this should only return one trace for each channel
            st = read_rg16(fcnt_file, starttime=tpoint, endtime=tpoint)
            ids = {tr.id for tr in st}
            self.assertEqual(len(st), len(ids))
            # make sure tpoint is in the time range
            start = st[0].stats.starttime
            end = st[0].stats.endtime
            self.assertLess(start, tpoint)
            self.assertLess(tpoint, end)


class TestMerge(unittest.TestCase):
    def test_merge(self):
        """ ensure the merge option of read_rg16 merges all contiguous
        traces together """
        for fcnt_file in FCNT_FILES:
            st_merged = read_rg16(fcnt_file, merge=True)
            st = read_rg16(fcnt_file).merge()
            self.assertEqual(len(st), len(st_merged))
            self.assertEqual(st, st_merged)


if __name__ == '__main__':
    unittest.main()
