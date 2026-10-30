from __future__ import annotations

from QHOT.lib.QDocument import QDocument


__all__ = ['QJsonDocument']


class QJsonDocument(QDocument):

    '''A document kept in a JSON file, for what the program writes.

    JSON holds lists and nested dicts of any depth, and every program can
    read it, which suits data that the program writes and other programs
    read.  See :class:`~QHOT.lib.QDocument.QDocument` for the parameters.
    '''

    SUFFIX = '.json'

    def _read(self, path: str) -> object:
        return self.files.readJson(path)

    def _write(self, data: object, path: str | None) -> str:
        return self.files.writeJson(data, path, prefix=self.name)
