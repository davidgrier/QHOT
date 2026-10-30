'''A file helper that works in a temporary home, and dialogs that answer.'''
import contextlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pyqtgraph.Qt import QtWidgets

from QHOT.lib.QSaveFile import QSaveFile

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class FileCase(unittest.TestCase):

    '''A window, a ``QSaveFile`` in a temporary home, and its data directory.'''

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.window = QtWidgets.QMainWindow()
        with patch.object(Path, 'home', return_value=self.home):
            self.files = QSaveFile(self.window)
        self.data = self.files.datadir

    def tearDown(self):
        self.window.close()
        self._tmp.cleanup()

    def written(self):
        '''The files in the data directory.'''
        return sorted(self.data.glob('*'))

    @contextlib.contextmanager
    def answering(self, dialog: str, path=None):
        '''Answer the file dialog ``dialog`` with ``path``, or cancel it.'''
        answer = (str(path), '') if path else ('', '')
        with patch.object(
            QtWidgets.QFileDialog,
            dialog,
            return_value=answer,
        ) as mock:
            yield mock
