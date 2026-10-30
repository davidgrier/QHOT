from __future__ import annotations

from collections.abc import Callable

from qtpy import QtCore, QtWidgets

from QHOT.lib.QFileAction import QFileAction
from QHOT.lib.QSaveFile import QSaveFile


__all__ = ['QDocument']


class QDocument(QFileAction):

    '''A document of the program, kept in a JSON file: its traps, its queue.

    The document is opened from a file, and saved to the file that it was
    opened from or last saved to.  ``save`` before there is a file writes
    one with a timestamped name in the data directory.

    Parameters
    ----------
    name : str
        What the document holds, as the messages say it: ``'traps'``.
    kind : str
        What the dialogs call it: ``'Trap Configuration'``.
    dump : Callable[[], object]
        Returns what to write: lists, dicts, strings and numbers.
    load : Callable[[object], None]
        Takes what was read, and makes it part of the program.
    files : QSaveFile
        The file helper.
    parent : QWidget
        The window that the dialogs belong to.

    Attributes
    ----------
    filename : str or None
        The file that the document is kept in, once there is one.
    '''

    def __init__(self,
                 name: str,
                 kind: str,
                 *,
                 dump: Callable[[], object],
                 load: Callable[[object], None],
                 files: QSaveFile,
                 parent: QtWidgets.QWidget) -> None:
        super().__init__(name, f'{kind} (*.json)', files=files, parent=parent)
        self._dump = dump
        self._load = load
        self.filename: str | None = None

    @QtCore.Slot()
    def open(self) -> None:
        '''Ask for a file, and load the document from it.'''
        path = self.chooseToOpen()
        if not path:
            self.status.emit(f'Open {self.name} canceled')
            return
        try:                    # what a user chose may be anything
            self._load(self.files.fromJson(path))
        except Exception as error:
            self.failed('open', path, error)
            return
        self.filename = path
        self.status.emit(f'Opened {self.name} from {path}')

    @QtCore.Slot()
    def save(self) -> None:
        '''Save the document to its file, or to a new one if it has none.'''
        self._write(self.filename)

    @QtCore.Slot()
    def saveAs(self) -> None:
        '''Ask for a file, and save the document to it.'''
        default = self.files.filename(prefix=self.name, suffix='.json')
        path = self.chooseToSave(default)
        if not path:
            self.status.emit(f'Save {self.name} canceled')
            return
        self._write(path)

    def _write(self, path: str | None) -> None:
        try:
            path = self.files.toJson(self._dump(), path, prefix=self.name)
        except OSError as error:
            self.failed('save', path, error)
            return
        self.filename = path
        self.status.emit(f'Saved {self.name} to {path}')
