# rg16


Obspy read support for Fairfield Nodal Receiver Gather format 1.6-1

Quickstart
---------

I will be working on integrating this into obspy, but it make it into obspy
until version 1.2.0 at the earliest (around April 2018 perhaps).
Until then, just pip install this package using its git url
and obspy should be able to detect and read the rg1.6 format automatically.

```bash
>>> pip install git+https://github.com/d-chambers/rg16
```

Now obspy.read should recognize and read Receiver Gather format 1.6-1.

```python
import obspy

path_to_rg16 = 'somefile.fcnt'
st = obspy.read(path_to_rg16)
```

Write support is not planned.
