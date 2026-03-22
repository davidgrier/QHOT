import logging
from pathlib import Path

import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets, QtGui, uic

from QVideo.lib import choose_camera, QCameraTree
from QHOT.lib import QSLM, QSLMWidget, QSaveFile, build_parser, choose_cgh  # noqa: F401
from QHOT.lib.holograms import CGH, QCGHTree      # noqa: F401
from QHOT.lib.traps import QTrap, QTrapGroup, QTrapMenu  # noqa: F401


logger = logging.getLogger(__name__)


class QHOT(QtWidgets.QMainWindow):

    '''Main application window for the QHOT optical trapping system.

    Integrates a live camera view (``QHOTScreen``) with an SLM display
    (``QSLM``), a hologram computation engine (``CGH``), a parameter
    tree (``QCGHTree``), and a DVR for recording.  The UI layout is
    defined in ``QHOT.ui``.

    Parameters
    ----------
    cameraTree : QCameraTree
        Configured camera tree providing the live video source.
    slm : QSLM or None
        SLM display window.  Created automatically if not provided.
    cgh : CGH or None
        Hologram computation engine.  If not provided, a default
        ``CGH`` is created using ``slm.shape``.
    *args, **kwargs
        Forwarded to ``QMainWindow``.
    '''

    UIFILE = Path(__file__).parent / 'QHOT.ui'
    HELPDIR = Path(__file__).parent / 'help'
    SETTINGS = ('QHOT', 'QHOT')

    _computeRequested = QtCore.pyqtSignal(list)

    def __init__(self, cameraTree: QCameraTree,
                 *args,
                 slm: QSLM | None = None,
                 cgh: CGH | None = None,
                 **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.cameraTree = cameraTree
        self.source = self.cameraTree.source
        self.slm = slm or QSLM()
        self.cgh = cgh or CGH(shape=self.slm.shape)
        self._cghThread = QtCore.QThread(self)
        self.cgh.moveToThread(self._cghThread)
        self._trapsChanged: bool = False
        self._computePending: bool = False
        self._setupUi()
        self._connectSignals()
        self._addFilters()
        self.save = QSaveFile(self)
        self._trapFile: str | None = None
        self.restoreSettings()
        self._cghThread.start()

    def _setupUi(self) -> None:
        '''Load the UI file and configure child widgets.'''
        uic.loadUi(self.UIFILE, self)
        self.videoTab.layout().addWidget(self.cameraTree)
        self.videoTab.layout().addWidget(self.screen.filter)
        self.screen.filter.setVisible(True)
        self.screen.framerate = 30
        self.screen.source = self.source
        self.dvr.source = self.source
        self.cghTree.cgh = self.cgh
        self.menuAddTrap.pos = QtCore.QPointF(self.cgh.xc, self.cgh.yc)
        self.helpBrowser.setSearchPaths([str(self.HELPDIR)])
        self.helpBrowser.setSource(QtCore.QUrl('index.html'))
        self._setupEditMenu()

    def _setupEditMenu(self) -> None:
        '''Insert an Edit menu with Undo/Redo between File and Tasks.'''
        stack = self.screen.overlay._undoStack
        undoAction = stack.createUndoAction(self, '&Undo')
        undoAction.setShortcut(QtGui.QKeySequence.StandardKey.Undo)
        redoAction = stack.createRedoAction(self, '&Redo')
        redoAction.setShortcut(QtGui.QKeySequence.StandardKey.Redo)
        editMenu = QtWidgets.QMenu('&Edit', self.menubar)
        editMenu.addAction(undoAction)
        editMenu.addAction(redoAction)
        self.menubar.insertMenu(self.menuTasks.menuAction(), editMenu)

    def _connectSignals(self) -> None:
        '''Wire signals and slots between subsystems.'''
        self.dvr.playing.connect(self.dvrPlayback)
        self.dvr.recording.connect(self.cameraTree.setDisabled)
        self.cgh.hologramReady.connect(self.slm.setData)
        self.cgh.hologramReady.connect(self.slmView.setData)
        self.cgh.hologramReady.connect(self._onHologramReady)
        self._computeRequested.connect(self.cgh.compute)
        self.screen.rendered.connect(self._onFrame)
        self.screen.status.connect(self.setStatus)
        overlay = self.screen.overlay
        overlay.trapAdded.connect(self.traps.registerTrap)
        overlay.trapRemoved.connect(self.traps.unregisterTrap)
        overlay.trapAdded.connect(self._onTrapAdded)
        overlay.trapRemoved.connect(self._onTrapRemoved)
        self.cgh.recalculate.connect(self._scheduleCompute)
        self.menuAddTrap.trapRequested.connect(self._onTrapRequested)

    def _addFilters(self) -> None:
        '''Register display filters with the video screen.'''
        for f in 'QRGBFilter QBlurFilter QSampleHold QEdgeFilter'.split():
            self.screen.filter.registerByName(f)

    @QtCore.pyqtSlot(QTrap)
    def _onTrapAdded(self, trap: QTrap) -> None:
        '''Connect each new trap's changed signals and schedule a compute.

        For groups, the group's own ``changed`` is connected to handle
        translation (individual leaves do not emit ``changed`` on group
        moves).  Each leaf's ``changed`` and ``structureChanged`` are
        also connected to handle independent leaf changes.
        '''
        if isinstance(trap, QTrapGroup):
            trap.changed.connect(self._scheduleCompute)
        for leaf in trap.leaves():
            leaf.changed.connect(self._scheduleCompute)
            if hasattr(leaf, 'structureChanged'):
                leaf.structureChanged.connect(self._scheduleCompute)
        self._scheduleCompute()

    @QtCore.pyqtSlot(QTrap)
    def _onTrapRemoved(self, trap: QTrap) -> None:
        '''Disconnect compute signals and schedule a hologram recompute.

        Disconnects signals connected in ``_onTrapAdded`` so that
        undo/redo cycles do not accumulate duplicate connections.
        '''
        if isinstance(trap, QTrapGroup):
            try:
                trap.changed.disconnect(self._scheduleCompute)
            except (TypeError, RuntimeError):
                pass
        for leaf in trap.leaves():
            try:
                leaf.changed.disconnect(self._scheduleCompute)
            except (TypeError, RuntimeError):
                pass
            if hasattr(leaf, 'structureChanged'):
                try:
                    leaf.structureChanged.disconnect(self._scheduleCompute)
                except (TypeError, RuntimeError):
                    pass
        self._scheduleCompute()

    @QtCore.pyqtSlot(QtCore.QPointF, QTrap)
    def _onTrapRequested(self, pos: QtCore.QPointF, trap: QTrap) -> None:
        '''Add a trap from the menu at the requested position.'''
        trap.r = (pos.x(), pos.y(), 0.)
        self.screen.overlay.addTrap(trap)

    @QtCore.pyqtSlot()
    def _scheduleCompute(self) -> None:
        '''Mark traps as changed; the next frame will trigger recomputation.'''
        self._trapsChanged = True

    @QtCore.pyqtSlot()
    def _onFrame(self) -> None:
        '''On each video frame, dispatch a compute if traps have changed.'''
        if self._trapsChanged and not self._computePending:
            self._trapsChanged = False
            self._computePending = True
            self._computeRequested.emit(list(self.screen.overlay._traps))

    @QtCore.pyqtSlot(object)
    def _onHologramReady(self, _phase) -> None:
        '''Clear the pending flag so the next frame may trigger a compute.'''
        self._computePending = False

    @QtCore.pyqtSlot(bool)
    def dvrPlayback(self, playback: bool) -> None:
        '''Switch the screen source between live camera and DVR playback.'''
        if playback:
            self.source.newFrame.disconnect(self.screen.setImage)
            self.dvr.newFrame.connect(self.screen.setImage)
        else:
            self.dvr.newFrame.disconnect(self.screen.setImage)
            self.source.newFrame.connect(self.screen.setImage)
        self.cameraTree.setDisabled(playback)

    @QtCore.pyqtSlot()
    def openTraps(self) -> None:
        '''Prompt for a JSON file and load traps from it.'''
        filename = self.save.openTraps(self.screen.overlay)
        if filename:
            self._trapFile = filename
            self.setStatus(f'Opened traps from {filename}')
        else:
            self.setStatus('Open traps canceled')

    @QtCore.pyqtSlot()
    def saveTraps(self) -> None:
        '''Save traps to the current file, or prompt if none is set.'''
        filename = self.save.traps(self.screen.overlay, self._trapFile)
        self._trapFile = filename
        self.setStatus(f'Saved traps to {filename}')

    @QtCore.pyqtSlot()
    def saveTrapsAs(self) -> None:
        '''Prompt for a filename and save traps to it.'''
        filename = self.save.trapsAs(self.screen.overlay)
        if filename:
            self._trapFile = filename
            self.setStatus(f'Saved traps to {filename}')
        else:
            self.setStatus('Save traps canceled')

    @QtCore.pyqtSlot()
    def saveImage(self) -> None:
        '''Save the current camera frame to disk.'''
        filename = self.save.image(self.screen.image)
        self.setStatus(f'Saved image as {filename}')

    @QtCore.pyqtSlot()
    def saveImageAs(self) -> None:
        '''Prompt for a filename and save the current camera frame.'''
        filename = self.save.imageAs(self.screen.image)
        if filename:
            self.setStatus(f'Saved image as {filename}')
        else:
            self.setStatus('Save image canceled')

    @QtCore.pyqtSlot()
    def saveHologram(self) -> None:
        '''Save the current SLM phase pattern to disk.'''
        filename = self.save.image(self.slm.data, prefix='hologram')
        self.setStatus(f'Saved hologram as {filename}')

    @QtCore.pyqtSlot()
    def saveHologramAs(self) -> None:
        '''Prompt for a filename and save the current SLM phase pattern.'''
        filename = self.save.imageAs(self.slm.data, prefix='hologram')
        if filename:
            self.setStatus(f'Saved hologram as {filename}')
        else:
            self.setStatus('Save hologram canceled')

    @QtCore.pyqtSlot()
    def saveSettings(self) -> None:
        '''Save window geometry and CGH calibration settings.'''
        settings = QtCore.QSettings(*self.SETTINGS)
        settings.setValue('geometry', self.saveGeometry())
        filename = self.save.toToml(self.cghTree)
        self.setStatus(f'Configuration saved to {filename}')

    @QtCore.pyqtSlot()
    def restoreSettings(self) -> None:
        '''Restore window geometry and CGH calibration settings.'''
        geometry = QtCore.QSettings(*self.SETTINGS).value('geometry')
        if geometry:
            self.restoreGeometry(geometry)
        else:
            QtCore.QTimer.singleShot(0, self._fitToCamera)
        if (filename := self.save.fromToml(self.cghTree)):
            self.setStatus(f'Configuration restored from {filename}')
        else:
            self.setStatus('Configuration file not found or invalid')

    @property
    def _chromeHeight(self) -> int:
        '''Height of window chrome (menu bar, status bar) in pixels.

        Measured from actual geometry rather than widget height reports,
        which are unreliable on macOS with native menus.
        '''
        return self.height() - self.centralWidget().height()

    def _fitToCamera(self) -> None:
        '''Size the window so the screen shows the camera frame with no bars.

        Sets the splitter so the screen gets exactly the camera's native
        width, then resizes the window height to the larger of the camera
        height and the panel's preferred height, plus chrome.  The result
        is clamped to the available display geometry.  Only called on
        first launch when no saved geometry exists.
        '''
        cam = self.screen.sizeHint()
        if not cam.isValid():
            return
        panel_w = self.tabWidget.sizeHint().width()
        panel_h = self.tabWidget.sizeHint().height()
        self.splitter.setSizes([cam.width(), panel_w])
        available = QtWidgets.QApplication.primaryScreen().availableGeometry()
        total_w = min(cam.width() + panel_w + self.splitter.handleWidth(),
                      available.width())
        total_h = min(max(cam.height(), panel_h) + self._chromeHeight,
                      available.height())
        self.resize(total_w, total_h)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        '''Schedule an aspect-ratio correction after every resize.'''
        super().resizeEvent(event)
        QtCore.QTimer.singleShot(0, self._constrainAspectRatio)

    def _constrainAspectRatio(self) -> None:
        '''Snap the window height so the screen matches the camera
        aspect ratio.

        Reads the screen widget's actual width after the layout has
        settled, computes the ideal height, and resizes the window if
        they differ.  The height is floored at the panel's minimum size
        hint so that the controls are never squished when the window is
        narrow.  The correction is a no-op when the height is already
        correct, so the resulting second resize event terminates the loop.
        '''
        cam = self.screen.sizeHint()
        if not cam.isValid() or cam.width() == 0:
            return
        screen_w = self.screen.width()
        if screen_w <= 0:
            return
        ideal_h = screen_w * cam.height() // cam.width()
        min_panel_h = self.tabWidget.minimumSizeHint().height()
        available_h = (QtWidgets.QApplication.primaryScreen()
                       .availableGeometry().height())
        desired_h = min(max(ideal_h, min_panel_h) + self._chromeHeight,
                        available_h)
        if self.height() != desired_h:
            self.resize(self.width(), desired_h)

    @QtCore.pyqtSlot(str)
    def setStatus(self, message: str) -> None:
        '''Display a transient status message in the status bar.'''
        self.statusBar().showMessage(message, 5000)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        '''Save settings, shut down CGH thread, and close the SLM on exit.'''
        self.saveSettings()
        self._cghThread.quit()
        self._cghThread.wait()
        self.slm.close()
        super().closeEvent(event)


def main() -> None:
    '''Launch the QHOT application.

    Parses command-line arguments for both the camera backend (QVideo
    flags) and the CGH backend (QHOT flags) from a shared parser, so
    that ``-h`` shows all options together.  The CGH backend is
    auto-selected (TorchCGH → cupyCGH → CGH) when no flag is given.
    '''
    app = pg.mkQApp('QHOT')
    parser = build_parser()
    slm = QSLM()
    cgh = choose_cgh(parser, shape=slm.shape)
    cameraTree = choose_camera(parser).start()
    hot = QHOT(cameraTree, slm=slm, cgh=cgh)
    hot.show()
    pg.exec()


if __name__ == '__main__':
    main()
