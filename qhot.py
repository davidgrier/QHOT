import logging
import sys
from pathlib import Path

from qtpy import QtCore, QtWidgets, QtGui, uic
import pyqtgraph as pg

from QVideo.cameras import chooser
from QVideo.lib import QCameraTree, QFilterRack
from QHOT.lib import (QSLM, QSLMWidget, QSaveFile,  # noqa: F401
                      build_parser, choose_cgh, choose_slm)
from QHOT.lib.holograms import CGH, QCGHTree  # noqa: F401
from QHOT.lib.QCameraOpener import QCameraOpener
from QHOT.lib.splash import say, splash
from QHOT.lib.tasks import QTaskManager
from QHOT.lib.traps import QTrap, QTrapMenu  # noqa: F401


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

    Attributes
    ----------
    manager : QTaskManager
        Frame-synchronised task scheduler.  Register tasks with
        ``self.manager.register(task)`` to queue them for execution.
    '''

    UIFILE = Path(__file__).parent / 'QHOT.ui'
    HELPDIR = Path(__file__).parent / 'help'
    SETTINGS = ('QHOT', 'QHOT')

    def __init__(self,
                 cameraTree: QCameraTree,
                 *args,
                 slm: QSLM | None = None,
                 cgh: CGH | None = None,
                 **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.cameraTree = cameraTree
        self.source = self.cameraTree.source
        self.slm = slm or QSLM()
        self.cgh = cgh or CGH(shape=self.slm.shape)
        self._setupUi()
        self._connectSignals()
        self._addFilters()
        self.save = QSaveFile(self)
        self.manager = QTaskManager(
            overlay=self.screen.overlay,
            cgh=self.cgh,
            dvr=self.dvr,
            save=self.save,
            image=self.screen.image,
            parent=self)
        self.screen.rendered.connect(self.manager.step)
        self.taskManagerWidget.manager = self.manager
        self.menuQueue.manager = self.manager
        self._trapFile:  str | None = None
        self._queueFile: str | None = None
        self.restoreSettings()
        self.cgh.start()

    def _setupUi(self) -> None:
        '''Load the UI file and configure child widgets.'''
        uic.loadUi(self.UIFILE, self)
        self.videoTab.layout().addWidget(self.cameraTree)
        self.filter = QFilterRack(source=self.source)
        self.videoTab.layout().addWidget(self.filter)
        self.screen.framerate = 30
        self.screen.source = self.filter.pipeline
        self.dvr.source = self.source
        self.cghTree.cgh = self.cgh
        self.menuAddTrap.pos = QtCore.QPointF(self.cgh.xc, self.cgh.yc)
        self.helpBrowser.setSearchPaths([str(self.HELPDIR)])
        self.helpBrowser.setSource(QtCore.QUrl('index.html'))
        self._setupEditMenu()
        self._setupShortcuts()

    def _setupEditMenu(self) -> None:
        '''Insert an Edit menu with Undo/Redo/Toggle Overlay between
        File and Tasks.'''
        stack = self.screen.overlay.undoStack
        undoAction = stack.createUndoAction(self, '&Undo')
        undoAction.setShortcut(QtGui.QKeySequence.StandardKey.Undo)
        redoAction = stack.createRedoAction(self, '&Redo')
        redoAction.setShortcut(QtGui.QKeySequence.StandardKey.Redo)
        toggleAction = QtGui.QAction('Toggle &Overlay', self)
        toggleAction.setShortcut(QtGui.QKeySequence('Ctrl+\\'))
        toggleAction.triggered.connect(self.toggleOverlay)
        editMenu = QtWidgets.QMenu('&Edit', self.menubar)
        editMenu.addAction(undoAction)
        editMenu.addAction(redoAction)
        editMenu.addSeparator()
        editMenu.addAction(toggleAction)
        self.menubar.insertMenu(self.menuTasks.menuAction(), editMenu)

    def _setupShortcuts(self) -> None:
        '''Assign platform-adaptive keyboard shortcuts to menu actions.

        Fixed shortcuts (e.g. Ctrl+Backspace for Clear Traps) are
        declared in QHOT.ui.  Only StandardKey shortcuts, which adapt
        per platform (Ctrl vs Cmd on macOS), are set here.
        '''
        self.actionOpenTraps.setShortcut(
            QtGui.QKeySequence.StandardKey.Open)
        self.actionSaveTraps.setShortcut(
            QtGui.QKeySequence.StandardKey.Save)
        self.actionSaveTrapsAs.setShortcut(
            QtGui.QKeySequence.StandardKey.SaveAs)
        addAction = QtGui.QAction('Add &Tweezer', self)
        addAction.setShortcut(QtGui.QKeySequence('Ctrl+T'))
        addAction.triggered.connect(self.addTweezerAtCenter)
        clearAction = self.menuTasks.actions()[1]
        self.menuTasks.insertSeparator(clearAction)
        self.menuTasks.insertAction(clearAction, addAction)

    def _connectSignals(self) -> None:
        '''Wire signals and slots between subsystems.

        PyQt6 uic only handles no-argument connections from .ui files;
        typed signals (str, bool) must be connected here.

        The CGH follows the overlay of traps: it asks for a hologram of
        the pattern whenever that changes, on a clock of its own and not
        the video's, so that it keeps up with the traps however slowly
        the camera delivers frames.
        '''
        self.dvr.playing.connect(self.dvrPlayback)
        self.dvr.recording.connect(self.cameraTree.setDisabled)
        self.cgh.hologramReady.connect(self.slm.setData)
        self.cgh.hologramReady.connect(self.slmView.setData)
        self.cgh.computeFailed.connect(self._onComputeFailed)
        self.screen.status.connect(self.setStatus)
        self.taskManagerWidget.status.connect(self.setStatus)
        overlay = self.screen.overlay
        overlay.trapAdded.connect(self.traps.registerTrap)
        overlay.trapRemoved.connect(self.traps.unregisterTrap)
        self.cgh.follow(overlay)
        self.menuAddTrap.trapRequested.connect(self._onTrapRequested)

    def _addFilters(self) -> None:
        '''Register display filters with the filter rack.'''
        for f in ('Color Channel', 'Smoothing', 'Sample and Hold', 'Canny'):
            self.filter.addByName(f)

    @QtCore.Slot(QtCore.QPointF, QTrap)
    def _onTrapRequested(self, pos: QtCore.QPointF, trap: QTrap) -> None:
        '''Add a trap from the menu at the requested position.'''
        trap.r = (pos.x(), pos.y(), 0.)
        self.screen.overlay.addTrap(trap)

    @QtCore.Slot(str)
    def _onComputeFailed(self, reason: str) -> None:
        '''Say why there is no new hologram.

        The next change of the traps asks for another.
        '''
        self.setStatus(f'Hologram computation failed: {reason}')

    @QtCore.Slot(bool)
    def dvrPlayback(self, playback: bool) -> None:
        '''Switch the screen source between live camera and DVR playback.'''
        if playback:
            self.filter.source = self.dvr.playback.source
        else:
            self.filter.source = self.source
        self.cameraTree.setDisabled(playback)

    @QtCore.Slot()
    def addTweezerAtCenter(self) -> None:
        '''Add a tweezer at the optical axis (CGH center).'''
        pos = QtCore.QPointF(self.cgh.xc, self.cgh.yc)
        self.screen.overlay.addTrap(pos)

    @QtCore.Slot()
    def toggleOverlay(self) -> None:
        '''Toggle the visibility of the trap overlay.'''
        self.screen.overlaysVisible = not self.screen.overlaysVisible

    @QtCore.Slot()
    def openTraps(self) -> None:
        '''Prompt for a JSON file and load traps from it.'''
        filename = self.save.openTraps(self.screen.overlay)
        if filename:
            self._trapFile = filename
            self.setStatus(f'Opened traps from {filename}')
        else:
            self.setStatus('Open traps canceled')

    @QtCore.Slot()
    def saveTraps(self) -> None:
        '''Save traps to the current file, or prompt if none is set.'''
        filename = self.save.traps(self.screen.overlay, self._trapFile)
        self._trapFile = filename
        self.setStatus(f'Saved traps to {filename}')

    @QtCore.Slot()
    def saveTrapsAs(self) -> None:
        '''Prompt for a filename and save traps to it.'''
        filename = self.save.trapsAs(self.screen.overlay)
        if filename:
            self._trapFile = filename
            self.setStatus(f'Saved traps to {filename}')
        else:
            self.setStatus('Save traps canceled')

    @QtCore.Slot()
    def openQueue(self) -> None:
        '''Prompt for a JSON queue file and append tasks from it.'''
        was_idle = (self.manager.active is None
                    and not self.manager.background)
        filename = self.save.openQueue(self.manager)
        if filename:
            if was_idle:
                self.manager.pause(True)
            self._queueFile = filename
            self.setStatus(f'Loaded queue from {filename}')
        else:
            self.setStatus('Open queue canceled')

    @QtCore.Slot()
    def saveQueue(self) -> None:
        '''Save the pending queue to the current file, or prompt for one.'''
        filename = self.save.queue(self.manager, self._queueFile)
        self._queueFile = filename
        self.setStatus(f'Saved queue to {filename}')

    @QtCore.Slot()
    def saveQueueAs(self) -> None:
        '''Prompt for a filename and save the pending queue to it.'''
        filename = self.save.queueAs(self.manager)
        if filename:
            self._queueFile = filename
            self.setStatus(f'Saved queue to {filename}')
        else:
            self.setStatus('Save queue canceled')

    @QtCore.Slot()
    def saveImage(self) -> None:
        '''Save the current camera frame to disk.'''
        filename = self.save.image(self.screen.image)
        self.setStatus(f'Saved image as {filename}')

    @QtCore.Slot()
    def saveImageAs(self) -> None:
        '''Prompt for a filename and save the current camera frame.'''
        filename = self.save.imageAs(self.screen.image)
        if filename:
            self.setStatus(f'Saved image as {filename}')
        else:
            self.setStatus('Save image canceled')

    @QtCore.Slot()
    def saveHologram(self) -> None:
        '''Save the current SLM phase pattern to disk.'''
        filename = self.save.image(self.slm.data, prefix='hologram')
        self.setStatus(f'Saved hologram as {filename}')

    @QtCore.Slot()
    def saveHologramAs(self) -> None:
        '''Prompt for a filename and save the current SLM phase pattern.'''
        filename = self.save.imageAs(self.slm.data, prefix='hologram')
        if filename:
            self.setStatus(f'Saved hologram as {filename}')
        else:
            self.setStatus('Save hologram canceled')

    @QtCore.Slot()
    def saveSettings(self) -> None:
        '''Save window geometry and CGH calibration settings.'''
        settings = QtCore.QSettings(*self.SETTINGS)
        settings.setValue('geometry', self.saveGeometry())
        filename = self.save.toToml(self.cghTree)
        self.setStatus(f'Configuration saved to {filename}')

    @QtCore.Slot()
    def restoreSettings(self) -> None:
        '''Restore window geometry and CGH calibration settings.'''
        geometry = QtCore.QSettings(*self.SETTINGS).value('geometry')
        if geometry:
            self.restoreGeometry(geometry)
        else:
            QtCore.QTimer.singleShot(0, self._fitToCamera)
        if (filename := self.save.fromToml(self.cghTree)):
            logger.info(f'Configuration restored from {filename}')
            self.setStatus(f'Configuration restored from {filename}')
        else:
            logger.warning('Configuration file not found or invalid')
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

    @QtCore.Slot(str)
    def setStatus(self, message: str) -> None:
        '''Display a transient status message in the status bar.'''
        self.statusBar().showMessage(message, 5000)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        '''Save settings, shut down CGH thread, and close the SLM on exit.'''
        self.saveSettings()
        self.cgh.stop()
        self.slm.close()
        super().closeEvent(event)


def main() -> None:
    '''Launch the QHOT application.

    A splash screen appears at once and says what is happening.  The
    camera opens in a thread of its own, so that a slow camera does not
    freeze the splash screen, while the SLM and the hologram backend are
    made in the meantime.

    Parses command-line arguments for both the camera backend (QVideo
    flags) and the CGH backend (QHOT flags) from a shared parser, so
    that ``-h`` shows all options together.  The CGH backend is
    auto-selected (PyTorch, then numba, then NumPy) when no flag is given.
    '''
    app = pg.mkQApp('QHOT')
    screen = splash()
    screen.show()
    screen.raise_()  # macOS shows a splash screen only if it is raised
    screen.activateWindow()
    parser = build_parser()
    say(screen, 'Opening the camera...')
    opener = QCameraOpener(parser)
    app.aboutToQuit.connect(opener.stop)
    opener.start()
    say(screen, 'Opening the SLM...')
    slm = choose_slm(parser)
    say(screen, 'Starting the hologram engine...')
    cgh = choose_cgh(parser, shape=slm.shape)
    say(screen, 'Waiting for the camera...')
    if not opener.waitForCamera():
        screen.close()
        sys.exit(f'Error: {opener.reason}')
    say(screen, 'Building the interface...')
    tree = chooser.make_tree(opener.key, opener.camera).start()
    opener.camera = None  # the interface has it now
    hot = QHOT(tree, slm=slm, cgh=cgh)
    hot.show()
    screen.finish(hot)
    pg.exec()


if __name__ == '__main__':
    main()
