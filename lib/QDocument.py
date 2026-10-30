from __future__ import annotations

from collections.abc import Callable

from qtpy import QtCore, QtWidgets

from QHOT.lib.QFileAction import QFileAction
from QHOT.lib.QSaveFile import QSaveFile


__all__ = ['QDocument']


class QDocument(QFileAction):

    '''A document of the program, kept in a file: its traps, its queue.

    The document is opened from a file, and saved to the file that it was
    opened from or last saved to.  ``save`` before there is a file writes
    one with a timestamped name in the data directory.

    This is what is the same for every format.  A subclass says how the
    data is read from a file and written to one: see
    :class:`~QHOT.lib.QJsonDocument.QJsonDocument` and
    :class:`~QHOT.lib.QTomlDocument.QTomlDocument`.

    Parameters
    ----------
    name : str
        What the document holds, as the messages say it: ``'traps'``.
    kind : str
        What the dialogs call it: ``'Trap Configuration'``.
    dump : Callable[[], object]
        Returns what to write.
    load : Callable[[object], None]
        Takes what was read, and makes it part of the program.
    files : QSaveFile
        The file helper.
    parent : QWidget
        The window that the dialogs belong to.

    Attributes
    ----------
    SUFFIX : str
        The extension of the files, with its dot.
    filename : str or None
        The file that the document is kept in, once there is one.
    '''

    SUFFIX = ''

    def __init__(self,
                 name: str,
                 kind: str,
                 *,
                 dump: Callable[[], object],
                 load: Callable[[object], None],
                 files: QSaveFile,
                 parent: QtWidgets.QWidget) -> None:
        super().__init__(
            name,
            f'{kind} (*{self.SUFFIX})',
            files=files,
            parent=parent,
        )
        self._dump = dump
        self._load = load
        self.filename: str | None = None

    def _read(self, path: str) -> object:
        '''Return the data in the file at ``path``.'''
        raise NotImplementedError

    def _write(self, data: object, path: str | None) -> str:
        '''Write the data to ``path`` (a new file if ``None``); return it.'''
        raise NotImplementedError

    @QtCore.Slot()
    def open(self) -> None:
        '''Ask for a file, and load the document from it.'''
        path = self.chooseToOpen()
        if not path:
            self.status.emit(f'Open {self.name} canceled')
            return
        try:                    # what a user chose may be anything
            self._load(self._read(path))
        except Exception as error:
            self.failed('open', path, error)
            return
        self.filename = path
        self.status.emit(f'Opened {self.name} from {path}')

    @QtCore.Slot()
    def save(self) -> None:
        '''Save the document to its file, or to a new one if it has none.'''
        self._saveTo(self.filename)

    @QtCore.Slot()
    def saveAs(self) -> None:
        '''Ask for a file, and save the document to it.'''
        default = self.files.filename(prefix=self.name, suffix=self.SUFFIX)
        path = self.chooseToSave(default)
        if not path:
            self.status.emit(f'Save {self.name} canceled')
            return
        self._saveTo(path)

    def _saveTo(self, path: str | None) -> None:
        try:
            path = self._write(self._dump(), path)
        except OSError as error:
            self.failed('save', path, error)
            return
        self.filename = path
        self.status.emit(f'Saved {self.name} to {path}')
