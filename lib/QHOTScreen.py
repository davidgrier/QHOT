from qtpy import QtCore, QtGui, QtWidgets
from QVideo.lib import QVideoScreen
from QHOT.lib.traps.QTrapOverlay import QTrapOverlay
import numpy as np
import logging


logger = logging.getLogger(__name__)


class QHOTScreen(QVideoScreen):

    '''Video screen with overlay for interacting with optical traps.

    Extends QVideoScreen by adding a QTrapOverlay that intercepts mouse
    and wheel events and translates them into trap operations.

    Parameters
    ----------
    *args :
        Positional arguments forwarded to QVideoScreen.
    **kwargs :
        Keyword arguments forwarded to QVideoScreen.

    Attributes
    ----------
    overlay : QTrapOverlay
        Graphical overlay for creating, moving, and grouping traps.

    Signals
    -------
    status : str
        Emitted with a human-readable message after user actions such
        as clearing all traps.
    rendered : signal
        Emitted each time a video frame is actually drawn, at the rate
        set by ``framerate``.  Suitable for driving computations that
        should be synchronized with the display cadence.
    '''

    #: Emitted with a status message string for display in the UI.
    status = QtCore.Signal(str)
    #: Emitted after each video frame is rendered to the screen.
    rendered = QtCore.Signal()

    def _setupUi(self) -> None:
        '''Add the trap overlay to the inherited video view.'''
        super()._setupUi()
        self.overlay = QTrapOverlay()
        self.addOverlay(self.overlay)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                           QtWidgets.QSizePolicy.Policy.Expanding)

    def _overlayPos(self, event: QtGui.QInputEvent) -> QtCore.QPointF:
        '''Map a widget event position to overlay item coordinates.

        Parameters
        ----------
        event : QtGui.QInputEvent
            A mouse or wheel event carrying a position in widget
            (viewport) coordinates.

        Returns
        -------
        QtCore.QPointF
            The corresponding position in the overlay item's local
            coordinate system.
        '''
        pt = (event.position().toPoint()
              if hasattr(event, 'position')
              else event.pos())
        return self.overlay.mapFromScene(self.mapToScene(pt))

    @QtCore.Slot(np.ndarray)
    def setImage(self, image: np.ndarray) -> None:
        '''Render a frame and emit ``rendered`` if the display rate
        allows it.'''
        was_ready = self._ready
        super().setImage(image)
        if was_ready:
            self.rendered.emit()

    @QtCore.Slot()
    def clearTraps(self) -> None:
        '''Remove all traps from the overlay and emit a status message.'''
        self.overlay.clearTraps()
        self.status.emit('Cleared all traps')

    # Pass mouse events to the trap overlay

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        '''Forward press to overlay; fall back to video screen handler.'''
        if self.overlay.mousePress(event, self._overlayPos(event)):
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        '''Forward move to overlay; fall back to video screen handler.'''
        if self.overlay.mouseMove(event, self._overlayPos(event)):
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        '''Forward release to overlay; fall back to video screen handler.'''
        if self.overlay.mouseRelease(event):
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        '''Forward wheel to overlay; fall back to video screen handler.'''
        if self.overlay.wheel(event, self._overlayPos(event)):
            event.accept()
        else:
            super().wheelEvent(event)


if __name__ == '__main__':  # pragma: no cover
    QHOTScreen.example()
