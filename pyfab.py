from pyqtgraph.Qt import QtCore, QtWidgets, QtGui, uic
import pyqtgraph as pg
from pathlib import Path
from QVideo.lib import choose_camera, QCameraTree
from QFab.lib.QSLM import QSLM
from QFab.lib.holograms.CGH import CGH
from QFab.lib.holograms.QCGHTree import QCGHTree  # noqa: F401 — needed for uic
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

    def __init__(self, cameraTree: QCameraTree,
                 *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.cameraTree = cameraTree
        self.source = self.cameraTree.source
        self.slm = QSLM()
        self.cgh = CGH(shape=self.slm.shape)
        self._setupUi()
        self._connectSignals()
        self._addFilters()
        self.save = QSaveFile(self)
        self.restoreSettings()

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
        self.helpBrowser.setSearchPaths([str(self.HELPDIR)])
        self.helpBrowser.setSource(QtCore.QUrl('index.html'))
        self.splitter.setStretchFactor(0, 3)  # screen gets 3 parts
        self.splitter.setStretchFactor(1, 1)  # control panel gets 1 part

    def _connectSignals(self) -> None:
        '''Wire signals and slots between subsystems.'''
        self.dvr.playing.connect(self.dvrPlayback)
        self.dvr.recording.connect(self.cameraTree.setDisabled)
        self.cgh.hologramReady.connect(self.slm.setData)
        self.screen.status.connect(self.setStatus)
        overlay = self.screen.overlay
        overlay.trapAdded.connect(self.traps.registerTrap)
        overlay.trapRemoved.connect(self.traps.unregisterTrap)
        # TODO: connect trap-tree changes to CGH computation once the
        # aggregate "traps changed" signal is designed (see QTrapOverlay).
        # TODO: connect CGH.recalculate to overlay once an overlay
        # recalculate slot is implemented.
        # TODO: connect menuAddTrap once QTrapMenu integration is finalised.

    def _addFilters(self) -> None:
        '''Register display filters with the video screen.'''
        for f in 'QRGBFilter QBlurFilter QSampleHold QEdgeFilter'.split():
            self.screen.filter.registerByName(f)

    @QtCore.pyqtSlot(bool)
    def dvrPlayback(self, playback: bool) -> None:
        '''Switch the screen source between live camera and DVR playback.'''
        if playback:
            self.source.newFrame.disconnect(self.screen.setImage)
            self.dvr.newFrame.connect(self.screen.setImage)
        else:
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
        QtCore.QSettings('QFab', 'PyFab').setValue(
            'geometry', self.saveGeometry())
        filename = self.save.toToml(self.cghTree)
        self.setStatus(f'Configuration saved to {filename}')

    @QtCore.pyqtSlot()
    def restoreSettings(self) -> None:
        '''Restore window geometry and CGH calibration settings.'''
        geometry = QtCore.QSettings('QFab', 'PyFab').value('geometry')
        if geometry:
            self.restoreGeometry(geometry)
        else:
            self.adjustSize()
        if (filename := self.save.fromToml(self.cghTree)):
            self.setStatus(f'Configuration restored from {filename}')
        else:
            self.setStatus('Configuration file not found or invalid')

    @QtCore.pyqtSlot(str)
    def setStatus(self, message: str) -> None:
        '''Display a transient status message in the status bar.'''
        self.statusBar().showMessage(message, 5000)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        '''Save settings and close the SLM on exit.'''
        self.saveSettings()
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
