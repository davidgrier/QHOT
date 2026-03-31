from qtpy import QtCore
from pyqtgraph import GraphicsLayoutWidget, ImageItem
from QHOT.lib.QSLM import Hologram
import numpy as np
import logging


logger = logging.getLogger(__name__)


class QSLMWidget(GraphicsLayoutWidget):

    '''Preview widget showing the hologram currently displayed on the SLM.

    Embeds a read-only image view of the phase pattern being sent to
    the physical SLM.  Connect ``QSLM.hologramReady`` (or any signal
    carrying a ``Hologram`` array) to :meth:`setData` to keep the
    preview in sync.

    The widget skips updates while hidden so that it imposes no
    rendering cost when it is not visible.

    Inherits
    --------
    pyqtgraph.GraphicsLayoutWidget

    Parameters
    ----------
    *args, **kwargs
        Forwarded to ``GraphicsLayoutWidget``.

    Attributes
    ----------
    data : Hologram or None
        The phase pattern currently shown, or ``None`` before the first
        call to :meth:`setData`.
    '''

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setBackground('w')
        self._setupUi()
        self._hologram: Hologram | None = None

    def _setupUi(self) -> None:
        self.ci.layout.setContentsMargins(0, 0, 0, 0)
        self.view = self.addViewBox(enableMenu=False)
        self.view.setDefaultPadding(0)
        self.view.setAspectLocked(True)
        self.image = ImageItem(axisOrder='row-major')
        self.view.addItem(self.image)

    @property
    def data(self) -> Hologram | None:
        '''Phase pattern currently shown, or ``None`` before first update.'''
        return self.image.image

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._hologram is not None:
            self.image.setImage(self._hologram, autoLevels=False)

    @QtCore.Slot(np.ndarray)
    def setData(self, hologram: Hologram) -> None:
        '''Display a phase hologram in the preview.

        Always caches the hologram so the display is current when the
        widget becomes visible.  Rendering is skipped while hidden.

        Parameters
        ----------
        hologram : Hologram
            Phase pattern to preview, encoded as 8-bit integers.
        '''
        self._hologram = hologram
        if self.isVisible():
            logger.debug('Updating SLM preview')
            self.image.setImage(hologram, autoLevels=False)

    @classmethod
    def example(cls) -> None:  # pragma: no cover
        '''Show the widget with a diagonal gradient test pattern.'''
        import pyqtgraph as pg

        pg.mkQApp()
        w = cls()
        w.setWindowTitle('QSLMWidget example')
        w.resize(640, 480)
        shape = (480, 640)
        phase = np.indices(shape).sum(axis=0) % 256
        w.setData(phase.astype(np.uint8))
        w.show()
        pg.exec()


if __name__ == '__main__':  # pragma: no cover
    QSLMWidget.example()
