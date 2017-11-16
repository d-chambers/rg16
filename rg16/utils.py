"""
Utilities for fanopy
"""
import collections
import functools
import struct

import numpy as np

BITMAP = np.array([1, 2, 4, 8])[::-1].reshape(4, 1)

TENS = np.power(10, range(12))[::-1]


def open_file(func):
    """ decorator to ensure a file buffer is passed as first argument """

    @functools.wraps(func)
    def _wrap(*args, **kwargs):
        first_arg = args[0]
        try:
            fi = open(first_arg, 'rb')
        except TypeError:  # assume we have been passed a buffer
            assert hasattr(args[0], 'read')
            return func(*args, **kwargs)
        else:
            args = tuple([fi] + list(args[1:]))
            out = func(*args, **kwargs)
            fi.close()
            return out

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

    Parameters
    ----------
    fi
        A file object
    position
        Start byte position
    length
        Length of bytes to read
    dtype
        The data type, all numpy data types are supported plus the following:
            bcd - binary coded decimal
            <i3 - little endian 3 byte int
            >i3 - big endian 3 byte int
            >i. - 4 bit int, left four bits
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
        # convert length to count arg in np.fromfile
        dtype_num = int([x for x in dtype if x.isdigit()][0])
        # make sure it goes into the length evenly
        count = length / dtype_num
        assert count % 1.0 == 0.0
        fromfi = np.fromfile(fi, dtype, count=int(count))
        return fromfi[0] if len(fromfi) == 1 else fromfi


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
