"""
tests for the Utilities of rg16
"""
import unittest
from io import BytesIO

from rg16.utils import read


def byte_io(byte_str):
    """ write byte_str to BytesIO object, seek back to 0, return """
    return BytesIO(byte_str)


class TestRead(unittest.TestCase):
    """
    Tests for the read function, which should read all the weird binary
    formats used in this file format.
    """

    # --- tests bcd

    bcd = [
        (b'\x99', 1, 99),
        (b'\x99\x01', 2, 9901),
    ]

    def test_read_bcd(self):
        """ ensure bcd encoding returns expected values """
        for byte, length, answer in self.bcd:
            out = read(byte_io(byte), 0, length, 'bcd')
            self.assertEqual(out, answer)

    def test_ff_raises(self):
        """ ensure FF raises. BCD values for any half byte past 9 should
        raise """
        with self.assertRaises(ValueError) as e:
            read(byte_io(b'\xFF'), 0, 1, 'bcd')
        assert 'are not valid bcd' in str(e.exception)

    # --- test half byte reads

    halfsies = [
        (b'\x45', '>i.', 4),
        (b'\x45', '<i.', 5),
        (b'\xfa', '>i.', 15),
        (b'\xfa', '<i.', 10),
    ]

    def test_read_half_bit(self):
        """ ensure reading half bytes (4 bit) works """
        for byte, format, answer in self.halfsies:
            self.assertEqual(read(byte_io(byte), 0, 1, format), answer)

    # --- test 24 bit (3 byte) reads

    why_use_3_bytes = [  # seriously, how expensive is one extra byte!?
        (b'\x00\x00\x00', '<i3', 0),
        (b'\x00\x00\x00', '>i3', 0),
        (b'\x00\x00\x01', '>i3', 1),
        (b'\x00\x00\x01', '<i3', 65536),
    ]

    def test_read_3_bytes(self):
        """ ensure 3 byte chunks are correctly read """
        for byte, format, answer in self.why_use_3_bytes:
            self.assertEqual(read(byte_io(byte), 0, 3, format), answer)

    # --- test backup

    def test_backup(self):
        """ if lists are passed it the second values should be used as
        backup if the first read attempt raises """
        fi = byte_io(b'\xff\x98')
        self.assertEqual(read(fi, [0, 1], [1, 1], ['bcd', 'bcd']), 98)

    def test_read_raises_when_all_fail(self):
        """ensure the backup function raises if it runs off the edge """
        fi = byte_io(b'\xff\xff')
        with self.assertRaises(ValueError):
            read(fi, [0, 1], [1, 1], ['bcd', 'bcd'])


if __name__ == '__main__':
    unittest.main()
