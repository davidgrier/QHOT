from pyqtgraph.Qt import QtCore, QtWidgets
from pyqtgraph import ImageItem
from pyqtgraph.exporters import ImageExporter
import pyqtgraph as pg
from pathlib import Path
from datetime import datetime
import numpy as np
import numpy.typing as npt
import tomlkit
import logging


logger = logging.getLogger(__name__)


class QSaveFile(QtCore.QObject):

    '''Utility for saving images and TOML configuration files.

    Automatically creates a timestamped data directory (``~/data``) and
    a hidden configuration directory (``~/.{parent_classname}``) on
    construction.

    Parameters
    ----------
    parent : QtWidgets.QMainWindow
        The application main window.  Its class name is used to derive
        the configuration directory.
    '''

    formats: str = ('PNG Image (*.png);;'
                    'JPEG Image (*.jpg *.jpeg);;'
                    'TIFF Image (*.tif *.tiff)')

    trap_format: str = 'Trap Configuration (*.json)'

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
            ``~/data/{prefix}_{timestamp}{suffix}``.
        '''
        prefix = prefix or self.classname
        path = self.datadir / f'{prefix}_{self.timestamp()}{suffix}'
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
              prefix: str = 'pyfab') -> str:
        '''Save image data to a file.

        Accepts either a pyqtgraph ``ImageItem`` (exported via
        ``ImageExporter``) or a raw numpy array (saved via
        ``pg.makeQImage``).

        Parameters
        ----------
        data : ImageItem or numpy.ndarray
            Image to save.
        filename : str or None
            Destination path.  If ``None``, a timestamped ``.png`` file
            is created in the data directory.
        prefix : str
            Prefix for the auto-generated filename.  Default: ``'pyfab'``.

        Returns
        -------
        str
            Path of the file that was written.
        '''
        filename = filename or self.filename(prefix=prefix, suffix='.png')
        if isinstance(data, ImageItem):
            ImageExporter(data).export(filename)
        else:
            pg.makeQImage(np.asarray(data)).save(filename)
        return filename

    def imageAs(self,
                data: ImageItem | npt.NDArray,
                prefix: str = 'pyfab') -> str:
        '''Save image data to a user-chosen file via a Save As dialog.

        Parameters
        ----------
        data : ImageItem or numpy.ndarray
            Image to save.
        prefix : str
            Prefix for the default filename suggestion.  Default: ``'pyfab'``.

        Returns
        -------
        str
            Path of the file that was written, or empty string if canceled.
        '''
        default = self.filename(prefix=prefix, suffix='.png')
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self.parent(), 'Save As', default, self.formats)
        if filename:
            return self.image(data, filename=filename)
        return ''

    def traps(self, overlay, filename: str | None = None) -> str:
        '''Save a trap overlay to a JSON file.

        Parameters
        ----------
        overlay : QTrapOverlay
            Overlay whose traps will be saved.
        filename : str or None
            Destination path.  If ``None``, a timestamped ``.json`` file
            is created in the data directory.

        Returns
        -------
        str
            Path of the file that was written.
        '''
        filename = filename or self.filename(prefix='traps', suffix='.json')
        overlay.save(filename)
        return filename

    def trapsAs(self, overlay) -> str:
        '''Save a trap overlay to a user-chosen JSON file via a Save As dialog.

        Parameters
        ----------
        overlay : QTrapOverlay
            Overlay whose traps will be saved.

        Returns
        -------
        str
            Path of the file that was written, or empty string if canceled.
        '''
        default = self.filename(prefix='traps', suffix='.json')
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self.parent(), 'Save Traps As', default, self.trap_format)
        if filename:
            return self.traps(overlay, filename)
        return ''

    def openTraps(self, overlay) -> str:
        '''Load traps from a user-chosen JSON file via an Open dialog.

        Parameters
        ----------
        overlay : QTrapOverlay
            Overlay to populate with the loaded traps.

        Returns
        -------
        str
            Path of the file that was read, or empty string if canceled.
        '''
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self.parent(), 'Open Traps', str(self.datadir), self.trap_format)
        if filename:
            overlay.load(filename)
            return filename
        return ''

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
