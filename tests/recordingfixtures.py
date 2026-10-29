'''Helpers for the tests of the tasks that record video.'''
import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock

import numpy as np
from pyqtgraph.Qt import QtCore, QtTest, QtWidgets

from QVideo.dvr import QDVRWidget, formats

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class FakeSource(QtCore.QObject):

    '''The part of a camera that a recorder needs.'''

    newFrame = QtCore.Signal(np.ndarray, object)
    shapeChanged = QtCore.Signal(QtCore.QSize)
    fps = 30.

    def emit(self, n: int) -> None:
        for i in range(n):
            self.newFrame.emit(np.full((6, 8), i, np.uint8), None)
        QtTest.QTest.qWait(200)


def make_dvr(filename: str = 'out.mkv', nframes: int = 10_000) -> MagicMock:
    '''Return a mock DVR widget that is not playing.'''
    dvr = MagicMock()
    dvr.filename = filename
    dvr.nframes.value.return_value = nframes
    dvr.isPlaying.return_value = False
    return dvr


class RealDVRCase(unittest.TestCase):

    '''A real DVR widget on a fake camera, and a directory to write to.'''

    def setUp(self) -> None:
        self.source = FakeSource()
        self.dvr = QDVRWidget(source=self.source)
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory, True)
        self.addCleanup(self.dvr.recorder.stop)

    def path(self, name: str = 'run.h5') -> str:
        return os.path.join(self.directory, name)

    @staticmethod
    def frames(path: str) -> int:
        '''Return the number of frames in the video at *path*.'''
        return len(formats.openVideo(path))
