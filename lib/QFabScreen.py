from QVideo.lib import QVideoScreen, QCamera
from QFab.lib.traps.QTrapOverlay import QTrapOverlay
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets
import logging


logger = logging.getLogger(__name__)


class QFabScreen(QVideoScreen):

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
    '''

    def _setupUi(self) -> None:
        '''Add the trap overlay to the inherited video view.'''
        super()._setupUi()
        self.overlay = QTrapOverlay()
        self.view.addItem(self.overlay)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                           QtWidgets.QSizePolicy.Policy.Expanding)

    def sizeHint(self) -> QtCore.QSize:
        '''Return the natural video frame size as the preferred widget size.'''
        rect = self.view.viewRect()
        if rect.isValid() and rect.width() > 0:
            return QtCore.QSize(int(rect.width()), int(rect.height()))
        return super().sizeHint()

    def hasHeightForWidth(self) -> bool:
        '''Return True when a valid video frame size is known.'''
        rect = self.view.viewRect()
        return rect.isValid() and rect.width() > 0

    def heightForWidth(self, width: int) -> int:
        '''Return the height that preserves the video aspect ratio.'''
        rect = self.view.viewRect()
        if rect.isValid() and rect.width() > 0:
            return int(width * rect.height() / rect.width())
        return super().heightForWidth(width)

    def _overlayPos(self, event: QtGui.QInputEvent) -> QtCore.QPointF:
        '''Map a widget event position to overlay item coordinates.

        Parameters
        ----------
        event : QtGui.QInputEvent
            A mouse or wheel event carrying a ``position()`` in widget
            (viewport) coordinates. The position is truncated to integer
            pixels by ``mapToScene``, which does not accept ``QPointF``.

        Returns
        -------
        QtCore.QPointF
            The corresponding position in the overlay item's local
            coordinate system.
        '''
        return self.overlay.mapFromScene(
            self.mapToScene(event.position().toPoint()))

    @QtCore.pyqtSlot()
    def clearTraps(self) -> None:
        '''Remove all traps from the overlay and emit a status message.'''
        self.overlay.clearTraps()
        self.status.emit('Cleared all traps')

    # Pass mouse events to the trap overlay

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if self.overlay.mousePress(event, self._overlayPos(event)):
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if self.overlay.mouseMove(event, self._overlayPos(event)):
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        if self.overlay.mouseRelease(event):
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        if self.overlay.wheel(event, self._overlayPos(event)):
            event.accept()
        else:
            super().wheelEvent(event)


if __name__ == '__main__':
    QFabScreen.example()
