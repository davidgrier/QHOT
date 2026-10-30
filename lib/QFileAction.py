from __future__ import annotations

import logging

from qtpy import QtCore, QtWidgets

from QHOT.lib.QSaveFile import QSaveFile


__all__ = ['QFileAction']

logger = logging.getLogger(__name__)


class QFileAction(QtCore.QObject):

    '''What a menu does with one kind of file: open it, save it.

    This is the part that is the same for every kind of file: the file
    dialogs, and the message that says what happened.  A file that
    cannot be read or written is not an error of the program, so it is
    reported to the user in ``status`` and logged, and the program goes
    on.

    Parameters
    ----------
    name : str
        What the file holds, as the messages say it: ``'traps'``.
    filter : str
        The file types of the dialogs, as Qt writes them:
        ``'Trap Configuration (*.json)'``.
    files : QSaveFile
        The file helper, which names and writes the files.
    parent : QWidget
        The window that the dialogs belong to.

    Signals
    -------
    status : Signal(str)
        A message for the user about what was done.
    '''

    #: Emitted with a message about what was done, or could not be.
    status = QtCore.Signal(str)

    def __init__(self,
                 name: str,
                 filter: str,
                 *,
                 files: QSaveFile,
                 parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)
        self.name = name
        self.filter = filter
        self.files = files

    def chooseToSave(self, default: str) -> str:
        '''Ask for the file to write; return its path, or ``''``.'''
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self.parent(),
            f'Save {self.name.capitalize()} As',
            default,
            self.filter,
        )
        return path

    def chooseToOpen(self) -> str:
        '''Ask for the file to read; return its path, or ``''``.'''
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self.parent(),
            f'Open {self.name.capitalize()}',
            str(self.files.datadir),
            self.filter,
        )
        return path

    def failed(self, verb: str, path: str | None, error: Exception) -> None:
        '''Say that a file could not be ``verb``-ed, and why.'''
        where = f' {path}' if path else ''
        logger.exception(f'could not {verb} {self.name}{where}')
        self.status.emit(f'Could not {verb} {self.name}{where}: {error}')
