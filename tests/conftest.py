""" configure tests for fanopy """
import glob
import sys
from os.path import join, dirname, abspath

TEST_PATH = abspath(dirname(__file__))
PKG_PATH = dirname(TEST_PATH)
TEST_DATA_PATH = join(TEST_PATH, 'test_data')
KML_FILE_PATHS = glob.glob(join(TEST_DATA_PATH, 'kml', '*'))

# insert path into sys.path to allow for expected importing
sys.path.insert(0, PKG_PATH)


def pytest_namespace():
    """ add the expected files to the py.test namespace """
    odict = {'test_data_path': TEST_DATA_PATH,
             'test_path': TEST_PATH,
             'package_path': PKG_PATH,
             'kml_file_paths': KML_FILE_PATHS
             }
    return odict
