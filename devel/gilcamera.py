'''A noise camera that holds the interpreter lock while it waits.

The ``genicam`` binding under harvesters never releases the GIL: its wait for
a frame is a call into C that keeps it.  ``ctypes.PyDLL`` does the same, so
this camera waits as the Flir does, without the hardware: ``usleep`` in
slices of a millisecond, as harvesters polls.
'''
import ctypes
import os
import time

import numpy as np

from QVideo.cameras.Noise import QNoiseCamera

LIBC = ctypes.PyDLL(None)           # PyDLL does not release the GIL
SLICE = int(os.environ.get('GIL_SLICE_US', 1000))   # harvesters polls at 1000


class GilNoiseCamera(QNoiseCamera):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._width, self._height, self._fps = 1280, 1024, 60.

    def read(self):
        due = time.perf_counter() + 1. / self._fps
        while time.perf_counter() < due:
            LIBC.usleep(SLICE)
        image = self._rng.integers(self._blacklevel, self._whitelevel,
                                   (self._height, self._width), np.uint8)
        return True, image
