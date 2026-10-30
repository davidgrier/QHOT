from __future__ import annotations

from collections.abc import Callable

from qtpy import QtCore, QtWidgets

from QHOT.lib.QFileAction import QFileAction
from QHOT.lib.QSaveFile import QSaveFile


__all__ = ['QImageFile']


class QImageFile(QFileAction):

    '''An image that the program shows, saved to a file: the video, the SLM.

    The image is whatever it is at the moment that it is saved.  ``save``
    writes a file with a timestamped name in the data directory, and
    ``saveAs`` asks for one.

    Parameters
    ----------
    name : str
        What the image shows, as the messages say it: ``'image'``.
    prefix : str
        The start of the timestamped names of the files.
    source : Callable[[], ImageItem or ndarray]
        Returns the image to save, as it is now.
    files : QSaveFile
        The file helper.
    parent : QWidget
        The window that the dialogs belong to.
    '''

    #: The file types of the dialogs.
    FORMATS = ('PNG Image (*.png);;'
               'JPEG Image (*.jpg *.jpeg);;'
               'TIFF Image (*.tif *.tiff)')

    def __init__(self,
                 name: str,
                 *,
                 prefix: str,
                 source: Callable[[], object],
                 files: QSaveFile,
                 parent: QtWidgets.QWidget) -> None:
        super().__init__(name, self.FORMATS, files=files, parent=parent)
        self.prefix = prefix
        self._source = source

    @QtCore.Slot()
    def save(self) -> None:
        '''Save the image to a file with a timestamped name.'''
        self._write(None)

    @QtCore.Slot()
    def saveAs(self) -> None:
        '''Ask for a file, and save the image to it.'''
        default = self.files.filename(prefix=self.prefix, suffix='.png')
        path = self.chooseToSave(default)
        if not path:
            self.status.emit(f'Save {self.name} canceled')
            return
        self._write(path)

    def _write(self, path: str | None) -> None:
        try:                # the exporter reports a plain Exception
            path = self.files.image(self._source(), path, prefix=self.prefix)
        except Exception as error:
            self.failed('save', path, error)
            return
        self.status.emit(f'Saved {self.name} as {path}')
