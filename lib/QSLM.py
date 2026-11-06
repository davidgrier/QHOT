'''The window that shows the hologram on the SLM.'''
import logging

import numpy as np
from qtpy import QtCore, QtGui
from pyqtgraph import GraphicsLayoutWidget, ImageItem

from QHOT.lib.types import Hologram, Shape


logger = logging.getLogger(__name__)


class QSLM(GraphicsLayoutWidget):

    '''Spatial Light Modulator interface

    QSLM displays 8-bit phase patterns on an SLM that is configured
    as the secondary display of the computer.
    If no secondary display is detected, a window of a fixed size is
    opened on the primary screen.  The shape of the hologram is the shape
    of the window, so that window cannot be resized.

    Parameters
    ----------
    fake : bool
        If True, open a window on the primary screen even when a
        secondary screen is present. Useful for testing without
        hardware. Default: False.
    *args, **kwargs
        Passed to ``GraphicsLayoutWidget``.

    Attributes
    ----------
    shape : tuple[int, int]
        The shape of the SLM in pixels (height, width).
    data : npt.NDArray[np.uint8]
        The current phase pattern displayed on the SLM.
    '''

    def __init__(self, *args, fake: bool = False, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._setupUi(fake)

    def _setupUi(self, fake: bool = False) -> None:
        '''Configure the display window and place it on the correct screen.

        If more than one screen is detected and ``fake`` is False, the
        window is moved to the secondary screen and maximized. Otherwise
        a fixed-size window is opened on the primary screen, so that the
        shape of the holograms cannot change under the engine that makes
        them.

        Parameters
        ----------
        fake : bool
            If True, always use the primary screen fallback.
        '''
        self.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint)
        self.ci.layout.setContentsMargins(0, 0, 0, 0)
        self.view = self.addViewBox(enableMenu=False,
                                    enableMouse=False)
        self.view.setDefaultPadding(0)
        self.image = ImageItem(axisOrder='row-major')
        self.view.addItem(self.image)

        screens = QtGui.QGuiApplication.screens()
        if len(screens) > 1 and not fake:
            logger.info('Opening SLM on secondary screen')
            screen = screens[1]
            geometry = screen.geometry()
            self.move(geometry.topLeft())
            self.showMaximized()
        else:
            if fake:
                logger.info('Opening SLM on primary screen (fake mode)')
            else:
                logger.warning('No secondary screen detected; '
                               'opening SLM on primary screen')
            x0, y0, w, h = 100, 100, 640, 480
            self.move(x0, y0)
            self.setFixedSize(w, h)
            self.show()
        self.setData(np.zeros(self.shape, dtype=np.uint8))

    @property
    def shape(self) -> Shape:
        '''Current dimensions of the SLM window.

        Returns
        -------
        Shape
            (height, width) in pixels.
        '''
        return (self.height(), self.width())

    @QtCore.Slot(np.ndarray)
    def setData(self, hologram: Hologram) -> None:
        '''Display a phase hologram on the SLM.

        Parameters
        ----------
        hologram : npt.NDArray[np.uint8]
            Phase pattern to display, encoded as 8-bit integers.

        Raises
        ------
        ValueError
            If ``hologram.shape`` does not match the SLM dimensions.  The
            holograms are made for the size of this window, so a different
            shape means that the display was reconfigured under the
            pipeline, which is a fault in the set-up to be seen and not
            to be worked around.
        '''
        if hologram.shape != self.shape:
            raise ValueError(
                f'hologram shape {hologram.shape} does not match '
                f'SLM shape {self.shape}')
        self.image.setImage(hologram, autoLevels=False)

    @property
    def data(self) -> Hologram:
        '''Return the phase pattern currently displayed on the SLM.

        Returns
        -------
        npt.NDArray[np.uint8]
            The current image data from the underlying ``ImageItem``.
        '''
        return self.image.image

    @classmethod
    def example(cls) -> None:  # pragma: no cover
        '''Display a test pattern on the SLM.

        Opens an SLM window in fake (primary screen) mode and displays
        a diagonal gradient pattern. Can be called on any subclass.
        '''
        import pyqtgraph as pg

        pg.mkQApp()
        slm = cls(fake=True)
        phase = np.indices(slm.shape).sum(axis=0) % 256
        slm.setData(phase.astype(np.uint8))
        pg.exec()


if __name__ == '__main__':  # pragma: no cover
    QSLM.example()
