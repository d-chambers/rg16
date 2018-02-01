# rg16


Obspy read support for Fairfield Nodal Receiver Gather format 1.6-1

Quickstart
---------

I will be working on integrating this into obspy, but it wont make it into obspy
until at least version 1.2.0 (to be released around April 2018 perhaps).
Until then, just pip install this package using its git url
and obspy should be able to detect and read the rg1.6 format automatically.

```bash
>>> pip install git+https://github.com/d-chambers/rg16
```

Now obspy.read should recognize and read Receiver Gather 1.6-1 files.

```python
import obspy

path_to_rg16 = 'somefile.fcnt'
st = obspy.read(path_to_rg16)
```

Write support is not planned.

### Change Log:


Version 0.0.3
* Fixed bug where rg16 would only read first few traces of some larger files.

Vestion 0.0.4
* Fixed bug that caused an offset of one trace see issue #1