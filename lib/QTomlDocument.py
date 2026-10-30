from __future__ import annotations

from collections.abc import Callable

from qtpy import QtWidgets

from QHOT.lib.QDocument import QDocument
from QHOT.lib.QSaveFile import QSaveFile


__all__ = ['QTomlDocument']


class QTomlDocument(QDocument):

    '''A document kept in a TOML file, for what a person writes or edits.

    TOML has comments and reads like a form, so a person can write the
    file by hand.  The document is a list of tables, written as
    ``[[root]]`` tables, one for each item::

        [[tasks]]
        type = "Delay"
        frames = 30

    A file that is not written correctly is reported with the line where
    TOML found the fault.

    Parameters
    ----------
    root : str
        The name of the tables: ``'tasks'``.
    header : str
        Comment lines at the top of the files that are written, to tell
        whoever opens one what it is.

    See :class:`~QHOT.lib.QDocument.QDocument` for the others.
    '''

    SUFFIX = '.toml'

    def __init__(self,
                 name: str,
                 kind: str,
                 *,
                 root: str,
                 header: str,
                 dump: Callable[[], list],
                 load: Callable[[list], None],
                 files: QSaveFile,
                 parent: QtWidgets.QWidget) -> None:
        super().__init__(
            name,
            kind,
            dump=dump,
            load=load,
            files=files,
            parent=parent,
        )
        self.root = root
        self.header = header

    def _read(self, path: str) -> list:
        table = self.files.readToml(path)
        if self.root not in table:
            raise ValueError(f'the file has no [[{self.root}]] tables')
        return table[self.root]

    def _write(self, data: list, path: str | None) -> str:
        return self.files.writeToml(
            {self.root: data},
            path,
            prefix=self.name,
            header=self.header,
        )
