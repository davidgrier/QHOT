from pyqtgraph.Qt import QtCore, QtWidgets, QtGui, uic
import pyqtgraph as pg
from pathlib import Path
from QVideo.lib import choose_camera, QCameraTree
from QFab.lib.QSLM import QSLM
from QFab.lib.holograms.CGH import CGH
from QFab.lib.holograms.QCGHTree import QCGHTree  # noqa: F401 — needed for uic
from QFab.lib.traps.QTrap import QTrap
from QFab.lib.traps.QTrapMenu import QTrapMenu  # noqa: F401 — needed for uic
from QFab.lib.QSLMWidget import QSLMWidget  # noqa: F401 — needed for uic
from QFab.lib.QSaveFile import QSaveFile
import logging


logger = logging.getLogger(__name__)


class PyFab(QtWidgets.QMainWindow):

    '''Main application window for the QFab optical trapping system.

    Integrates a live camera view (``QFabScreen``) with an SLM display
    (``QSLM``), a hologram computation engine (``CGH``), a parameter
    tree (``QCGHTree``), and a DVR for recording.  The UI layout is
    defined in ``PyFab.ui``.

    Parameters
    ----------
    cameraTree : QCameraTree
        Configured camera tree providing the live video source.
    *args, **kwargs
        Forwarded to ``QMainWindow``.
    '''

    UIFILE = Path(__file__).parent / 'PyFab.ui'
    HELPDIR = Path(__file__).parent / 'help'
    SETTINGS = ('QFab', 'PyFab')

    _computeRequested = QtCore.pyqtSignal(list)

    def __init__(self, cameraTree: QCameraTree,
                 *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.cameraTree = cameraTree
        self.source = self.cameraTree.source
        self.slm = QSLM()
        self.cgh = CGH(shape=self.slm.shape)
        self._cgh_thread = QtCore.QThread(self)
        self.cgh.moveToThread(self._cgh_thread)
        self._traps_changed: bool = False
        self._compute_pending: bool = False
        self._setupUi()
        self._connectSignals()
        self._addFilters()
        self.save = QSaveFile(self)
        self.restoreSettings()
        self._cgh_thread.start()

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
        '''Connect each new leaf trap's changed signal and schedule a compute.'''
        for leaf in trap.leaves():
            leaf.changed.connect(self._scheduleCompute)
            if hasattr(leaf, 'structureChanged'):
                leaf.structureChanged.connect(self._scheduleCompute)
        self._scheduleCompute()

    @QtCore.pyqtSlot(QTrap)
    def _onTrapRemoved(self, trap: QTrap) -> None:
        '''Schedule a hologram recompute after a trap is removed.'''
        self._scheduleCompute()

    @QtCore.pyqtSlot(QtCore.QPointF, QTrap)
    def _onTrapRequested(self, pos: QtCore.QPointF, trap: QTrap) -> None:
        '''Add a trap from the menu at the requested position.'''
        trap.r = (pos.x(), pos.y(), 0.)
        self.screen.overlay.addTrap(trap)

    @QtCore.pyqtSlot()
    def _scheduleCompute(self) -> None:
        '''Mark traps as changed; the next frame will trigger recomputation.'''
        self._traps_changed = True

    @QtCore.pyqtSlot()
    def _onFrame(self) -> None:
        '''On each video frame, dispatch a compute if traps have changed.'''
        if self._traps_changed and not self._compute_pending:
            self._traps_changed = False
            self._compute_pending = True
            self._computeRequested.emit(list(self.screen.overlay._traps))

    @QtCore.pyqtSlot(object)
    def _onHologramReady(self, _phase) -> None:
        '''Clear the pending flag so the next frame may trigger a compute.'''
        self._compute_pending = False

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
            self.setStatus('Save image cancelled')

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
            self.setStatus('Save hologram cancelled')

    @QtCore.pyqtSlot()
    def saveSettings(self) -> None:
        '''Save window geometry and CGH calibration settings.'''
        QtCore.QSettings(*self.SETTINGS).setValue('geometry', self.saveGeometry())
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
        width, then resizes the window height to match the camera height
        plus the menu bar and status bar.  Only called on first launch
        when no saved geometry exists.
        '''
        cam = self.screen.sizeHint()
        if not cam.isValid():
            return
        panel_w = self.tabWidget.sizeHint().width()
        self.splitter.setSizes([cam.width(), panel_w])
        self.resize(cam.width() + panel_w + self.splitter.handleWidth(),
                    cam.height() + self._chromeHeight)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        '''Schedule an aspect-ratio correction after every resize.'''
        super().resizeEvent(event)
        QtCore.QTimer.singleShot(0, self._constrainAspectRatio)

    def _constrainAspectRatio(self) -> None:
        '''Snap the window height so the screen matches the camera aspect ratio.

        Reads the screen widget's actual width after the layout has
        settled, computes the ideal height, and resizes the window if
        they differ.  The correction is a no-op when the ratio is already
        correct, so the resulting second resize event terminates the loop.
        '''
        cam = self.screen.sizeHint()
        if not cam.isValid() or cam.width() == 0:
            return
        screen_w = self.screen.width()
        if screen_w <= 0:
            return
        ideal_h = screen_w * cam.height() // cam.width()
        desired_h = ideal_h + self._chromeHeight
        if self.height() != desired_h:
            self.resize(self.width(), desired_h)

    @QtCore.pyqtSlot(str)
    def setStatus(self, message: str) -> None:
        '''Display a transient status message in the status bar.'''
        self.statusBar().showMessage(message, 5000)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        '''Save settings, shut down CGH thread, and close the SLM on exit.'''
        self.saveSettings()
        self._cgh_thread.quit()
        self._cgh_thread.wait()
        self.slm.close()
        super().closeEvent(event)


def main() -> None:
    '''Launch the PyFab application.'''
    app = pg.mkQApp('pyfab')
    cameraTree = choose_camera().start()
    fab = PyFab(cameraTree)
    fab.show()
    pg.exec()


if __name__ == '__main__':
    main()
