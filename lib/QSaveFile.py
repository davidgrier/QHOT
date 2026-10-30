from qtpy import QtCore, QtGui, QtWidgets
from pyqtgraph import ImageItem
from pyqtgraph.exporters import ImageExporter
from pathlib import Path
from datetime import datetime
import numpy as np
import numpy.typing as npt
import json
import tomllib
import tomlkit
import logging


logger = logging.getLogger(__name__)


class QSaveFile(QtCore.QObject):

    '''Utility for saving images, JSON files and TOML configuration files.

    Automatically creates a timestamped data directory (``~/data``) and
    a hidden configuration directory (``~/.{parent_classname}``) on
    construction.

    Parameters
    ----------
    parent : QtWidgets.QMainWindow
        The application main window.  Its class name is used to derive
        the configuration directory.
    '''

    def __init__(self, parent: QtWidgets.QMainWindow) -> None:
        super().__init__(parent)
        self._makeDirs()

    def _makeDirs(self) -> None:
        '''Create data and configuration directories if they do not exist.'''
        classname = type(self.parent()).__name__.lower()
        self.classname = classname
        self.datadir = Path.home() / 'data'
        self.configdir = Path.home() / f'.{classname}'
        self.datadir.mkdir(parents=True, exist_ok=True)
        self.configdir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def timestamp() -> str:
        '''Return the current date and time as a compact string.'''
        return datetime.now().strftime('%Y%m%d_%H%M%S')

    def filename(self,
                 prefix: str | None = None,
                 suffix: str = '') -> str:
        '''Build a timestamped filename in the data directory.

        Parameters
        ----------
        prefix : str or None
            Leading name component.  Defaults to the parent class name.
        suffix : str
            File extension including the leading dot (e.g. ``'.png'``).
            Default: ``''``.

        Returns
        -------
        str
            Absolute path string of the form
            ``~/data/{prefix}_{timestamp}{suffix}``.  The timestamp has a
            resolution of one second, so a name that is already taken has
            a counter, ``{prefix}_{timestamp}_{n}{suffix}``, and a file
            that is saved does not replace one that was saved a moment
            before.
        '''
        prefix = prefix or self.classname
        stem = f'{prefix}_{self.timestamp()}'
        path = self.datadir / f'{stem}{suffix}'
        n = 0
        while path.exists():
            n += 1
            path = self.datadir / f'{stem}_{n}{suffix}'
        return str(path)

    def configname(self, qobj: QtCore.QObject) -> str:
        '''Return the TOML configuration file path for a QObject.

        Parameters
        ----------
        qobj : QtCore.QObject
            Object whose class name determines the filename.

        Returns
        -------
        str
            Absolute path string of the form
            ``~/.{classname}/{QObjectClass}.toml``.
        '''
        path = self.configdir / f'{type(qobj).__name__}.toml'
        return str(path)

    def image(self,
              data: ImageItem | npt.NDArray,
              filename: str | None = None,
              prefix: str = 'qhot') -> str:
        '''Save image data to a file.

        Accepts either a pyqtgraph ``ImageItem`` (exported via
        ``ImageExporter``) or an array of 8-bit pixels in row-major
        order, such as a hologram: ``(height, width)`` for gray,
        ``(height, width, 3)`` for RGB or ``(height, width, 4)`` for
        RGBA.

        Parameters
        ----------
        data : ImageItem or numpy.ndarray
            Image to save.
        filename : str or None
            Destination path.  If ``None``, a timestamped ``.png`` file
            is created in the data directory.
        prefix : str
            Prefix for the auto-generated filename.  Default: ``'qhot'``.

        Returns
        -------
        str
            Path of the file that was written.

        Raises
        ------
        ValueError
            If an array is not ``uint8`` of one of the shapes above.
        OSError
            If the file cannot be written.
        '''
        filename = filename or self.filename(prefix=prefix, suffix='.png')
        if isinstance(data, ImageItem):
            ImageExporter(data).export(filename)
        elif not self._qimage(data).save(filename):
            raise OSError(f'could not write {filename}')
        return filename

    @staticmethod
    def _qimage(data: npt.NDArray) -> QtGui.QImage:
        '''Return a ``QImage`` of an array of 8-bit pixels (row-major).'''
        array = np.asarray(data)
        formats = QtGui.QImage.Format
        if array.dtype != np.uint8:
            raise ValueError(f'an image has 8-bit pixels, not {array.dtype}')
        if array.ndim == 2:
            fmt = formats.Format_Grayscale8
        elif array.ndim == 3 and array.shape[2] == 3:
            fmt = formats.Format_RGB888
        elif array.ndim == 3 and array.shape[2] == 4:
            fmt = formats.Format_RGBA8888
        else:
            raise ValueError(f'an image cannot have the shape {array.shape}')
        array = np.ascontiguousarray(array)
        height, width = array.shape[:2]
        image = QtGui.QImage(array.data, width, height, array.strides[0], fmt)
        return image.copy()             # the copy owns its pixels

    def writeJson(self,
                  data: object,
                  filename: str | None = None,
                  prefix: str = 'data') -> str:
        '''Write data to a JSON file.

        Parameters
        ----------
        data : object
            What to write: lists, dicts, strings and numbers.
        filename : str or None
            Destination path.  If ``None``, a timestamped ``.json`` file
            is created in the data directory.
        prefix : str
            Prefix for the auto-generated filename.  Default: ``'data'``.

        Returns
        -------
        str
            Path of the file that was written.

        Raises
        ------
        OSError
            If the file cannot be written.
        '''
        filename = filename or self.filename(prefix=prefix, suffix='.json')
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        return filename

    @staticmethod
    def readJson(filename: str) -> object:
        '''Read the data in a JSON file.

        Parameters
        ----------
        filename : str
            Path of the file.

        Returns
        -------
        object
            What the file holds.

        Raises
        ------
        OSError
            If the file cannot be read.
        ValueError
            If the file is not JSON.
        '''
        with open(filename) as f:
            return json.load(f)

    def writeToml(self,
                  data: dict,
                  filename: str | None = None,
                  prefix: str = 'data',
                  header: str = '') -> str:
        '''Write a table to a TOML file, which a person can edit.

        Parameters
        ----------
        data : dict
            What to write.  A list of dicts is written as ``[[key]]``
            tables.
        filename : str or None
            Destination path.  If ``None``, a timestamped ``.toml`` file
            is created in the data directory.
        prefix : str
            Prefix for the auto-generated filename.  Default: ``'data'``.
        header : str
            Comment lines at the top of the file, to tell whoever opens it
            what it is.

        Returns
        -------
        str
            Path of the file that was written.

        Raises
        ------
        OSError
            If the file cannot be written.
        '''
        filename = filename or self.filename(prefix=prefix, suffix='.toml')
        doc = tomlkit.document()
        for line in header.splitlines():
            doc.add(tomlkit.comment(line))
        if header:
            doc.add(tomlkit.nl())
        for key, value in data.items():
            doc[key] = value
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(tomlkit.dumps(doc))
        return filename

    @staticmethod
    def readToml(filename: str) -> dict:
        '''Read the table in a TOML file.

        Parameters
        ----------
        filename : str
            Path of the file.

        Returns
        -------
        dict
            What the file holds.

        Raises
        ------
        OSError
            If the file cannot be read.
        ValueError
            If the file is not TOML; the message says where.
        '''
        with open(filename, 'rb') as f:
            return tomllib.load(f)

    def toToml(self, qobj: QtCore.QObject) -> str:
        '''Save the settings of a QObject to a TOML configuration file.

        Parameters
        ----------
        qobj : QtCore.QObject
            Object whose ``settings`` property will be serialized.

        Returns
        -------
        str
            Path of the configuration file that was written.
        '''
        doc = tomlkit.document()
        doc['settings'] = qobj.settings
        filename = self.configname(qobj)
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(tomlkit.dumps(doc))
        return filename

    def fromToml(self, qobj: QtCore.QObject) -> str:
        '''Restore the settings of a QObject from a TOML configuration file.

        Parameters
        ----------
        qobj : QtCore.QObject
            Object whose ``settings`` property will be populated.

        Returns
        -------
        str
            Path of the configuration file that was read, or empty string
            if the file does not exist.
        '''
        filename = self.configname(qobj)
        if Path(filename).exists():
            with open(filename, 'r', encoding='utf-8') as f:
                doc = tomlkit.load(f)
            qobj.settings = doc['settings']
            return filename
        return ''
