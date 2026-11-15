'''QHOT: holographic optical trapping, in one window.

The window shows the live video, with the traps that the user places on it,
and the controls of the camera, the recorder, the filters, the traps, the
tasks and the calibration.  A spatial light modulator, on a display of its
own, shows the hologram that makes the traps.  ``main`` is the program:
it is what the command ``qhot`` runs.
'''
import logging
import sys
from pathlib import Path
from typing import NoReturn, cast

from qtpy import QtCore, QtWidgets, QtGui, uic
import pyqtgraph as pg

from QVideo.cameras import chooser
from QVideo.dvr import QDVRWidget
from QVideo.lib import QCamera, QCameraOpener, QCameraTree, QFilterRack
from QHOT.lib import (QSLM, QSLMWidget, QSaveFile, build_parser, choose_cgh,
                      choose_slm, configure_logging)
from QHOT.lib.holograms import CGH
from QHOT.lib.holograms.QCGHTree import QCGHTree
from QHOT.lib.QHOTScreen import QHOTScreen
from QHOT.lib.QImageFile import QImageFile
from QHOT.lib.QJsonDocument import QJsonDocument
from QHOT.lib.QSidecar import QSidecar
from QHOT.lib.QTomlDocument import QTomlDocument
from QHOT.lib.splash import say, splash
from QHOT.lib.tasks import QTaskManager, QTaskManagerWidget, QueueMenu
from QHOT.lib.traps import QTrap, QTrapMenu
from QHOT.lib.traps.QTrapWidget import QTrapWidget


logger = logging.getLogger(__name__)

__all__ = 'QHOT QUEUE_HEADER main'.split()


#: What a queue file says about itself, at the top.
QUEUE_HEADER = (
    'A queue of tasks for QHOT.  Open it with File > Open Queue.\n'
    'Each [[tasks]] table is one task, and the tasks run in order.\n'
    'The "type" is the name of the task; the other keys are its parameters.'
)


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
    slm : QSLM
        The SLM display window.
    cgh : CGH
        The hologram computation engine, with the shape of the SLM.
    *args, **kwargs
        Forwarded to ``QMainWindow``.

    Attributes
    ----------
    manager : QTaskManager
        Frame-synchronized task scheduler.  Register tasks with
        ``self.manager.register(task)`` to queue them for execution.
    '''

    UIFILE = Path(__file__).parent / 'QHOT.ui'
    HELPDIR = Path(__file__).parent / 'help'
    SETTINGS = ('QHOT', 'QHOT')

    # The widgets that QHOT.ui makes (uic.loadUi sets them as attributes).
    videoScreen: QHOTScreen
    dvr: QDVRWidget
    traps: QTrapWidget
    cghTree: QCGHTree
    slmView: QSLMWidget
    taskManagerWidget: QTaskManagerWidget
    splitter: QtWidgets.QSplitter
    tabWidget: QtWidgets.QTabWidget
    videoTab: QtWidgets.QWidget
    helpBrowser: QtWidgets.QTextBrowser
    menubar: QtWidgets.QMenuBar
    menuTasks: QtWidgets.QMenu
    menuAddTrap: QTrapMenu
    menuQueue: QueueMenu
    actionOpenTraps: QtGui.QAction
    actionSaveTraps: QtGui.QAction
    actionSaveTrapsAs: QtGui.QAction
    actionClearTraps: QtGui.QAction
    actionOpenQueue: QtGui.QAction
    actionSaveQueue: QtGui.QAction
    actionSaveQueueAs: QtGui.QAction
    actionSaveImage: QtGui.QAction
    actionSaveImageAs: QtGui.QAction
    actionSaveHologram: QtGui.QAction
    actionSaveHologramAs: QtGui.QAction

    def __init__(self,
                 cameraTree: QCameraTree,
                 *args,
                 slm: QSLM,
                 cgh: CGH,
                 **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.cameraTree = cameraTree
        self.source = self.cameraTree.source
        self.slm = slm
        self.cgh = cgh
        self._videoName = ''        # the name that is offered for a video
        self._setupUi()
        self._connectSignals()
        self._addFilters()
        self.save = QSaveFile(self)
        self._offerVideoName()
        self.sidecar = QSidecar(self.dvr,
                                self.cameraTree,
                                self.cgh,
                                self.videoScreen.overlay,
                                self.save,
                                self)
        self.sidecar.status.connect(self.setStatus)
        self.manager = QTaskManager(
            overlay=self.videoScreen.overlay,
            cgh=self.cgh,
            dvr=self.dvr,
            save=self.save,
            image=self.videoScreen.image,
            parent=self)
        self.videoScreen.newFrame.connect(self.manager.step)
        # The manager reports that it has stopped, and the reason follows.
        self.source.lost.connect(self.manager.fail)
        self.source.lost.connect(self._onCameraLost)
        self.dvr.stopped.connect(self.manager.fail)
        self.dvr.stopped.connect(self._onRecordingStopped)
        self.taskManagerWidget.manager = self.manager
        self.menuQueue.manager = self.manager
        self._setupFiles()
        self.restoreSettings()
        self.cgh.start()

    def _setupUi(self) -> None:
        '''Load the UI file and configure child widgets.'''
        uic.loadUi(self.UIFILE, self)
        self.splitter.setStretchFactor(0, 1)    # the screen takes the width
        self.splitter.setStretchFactor(1, 0)    # that the panels do not use
        layout = cast(QtWidgets.QLayout, self.videoTab.layout())
        layout.addWidget(self.cameraTree)
        self.filter = QFilterRack(source=self.source)
        layout.addWidget(self.filter)
        self.videoScreen.framerate = 30
        self.videoScreen.source = self.filter.pipeline
        self.dvr.source = self.source
        self.cghTree.cgh = self.cgh
        self.helpBrowser.setSearchPaths([str(self.HELPDIR)])
        self.helpBrowser.setSource(QtCore.QUrl('index.html'))
        self._setupEditMenu()
        self._setupShortcuts()

    def _setupFiles(self) -> None:
        '''Make the files that the File menu opens and saves, and wire it.'''
        overlay = self.videoScreen.overlay
        self.trapFile = QJsonDocument(
            'traps',
            'Trap Configuration',
            dump=overlay.toList,
            load=overlay.fromList,
            files=self.save,
            parent=self,
        )
        self.queueFile = QTomlDocument(
            'queue',
            'Task Queue',
            root='tasks',
            header=QUEUE_HEADER,
            dump=self.manager.toList,
            load=self.manager.load,
            files=self.save,
            parent=self,
        )
        self.imageFile = QImageFile(
            'image',
            prefix='qhot',
            source=lambda: self.videoScreen.image,
            files=self.save,
            parent=self,
        )
        self.hologramFile = QImageFile(
            'hologram',
            prefix='hologram',
            source=lambda: self.slm.data,
            files=self.save,
            parent=self,
        )
        self.actionOpenTraps.triggered.connect(self.trapFile.open)
        self.actionSaveTraps.triggered.connect(self.trapFile.save)
        self.actionSaveTrapsAs.triggered.connect(self.trapFile.saveAs)
        self.actionOpenQueue.triggered.connect(self.queueFile.open)
        self.actionSaveQueue.triggered.connect(self.queueFile.save)
        self.actionSaveQueueAs.triggered.connect(self.queueFile.saveAs)
        self.actionSaveImage.triggered.connect(self.imageFile.save)
        self.actionSaveImageAs.triggered.connect(self.imageFile.saveAs)
        self.actionSaveHologram.triggered.connect(self.hologramFile.save)
        self.actionSaveHologramAs.triggered.connect(self.hologramFile.saveAs)
        for file in (self.trapFile, self.queueFile,
                     self.imageFile, self.hologramFile):
            file.status.connect(self.setStatus)

    def _setupEditMenu(self) -> None:
        '''Insert an Edit menu with Undo/Redo/Toggle Overlay between
        File and Tasks.'''
        stack = self.videoScreen.overlay.undoStack
        undoAction = cast(QtGui.QAction, stack.createUndoAction(self, '&Undo'))
        undoAction.setShortcut(QtGui.QKeySequence.StandardKey.Undo)
        redoAction = cast(QtGui.QAction, stack.createRedoAction(self, '&Redo'))
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
        self.menuTasks.insertSeparator(self.actionClearTraps)
        self.menuTasks.insertAction(self.actionClearTraps, addAction)

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
        self.dvr.recording.connect(self._onRecording)
        self.cgh.hologramReady.connect(self.slm.setData)
        self.cgh.hologramReady.connect(self.slmView.setData)
        self.cgh.computeFailed.connect(self._onComputeFailed)
        self.videoScreen.status.connect(self.setStatus)
        self.taskManagerWidget.status.connect(self.setStatus)
        overlay = self.videoScreen.overlay
        overlay.trapAdded.connect(self.traps.registerTrap)
        overlay.trapRemoved.connect(self.traps.unregisterTrap)
        self.traps.edited.connect(overlay.editTrap)
        self.cgh.follow(overlay)
        self.menuAddTrap.aboutToShow.connect(self._placeNewTraps)
        self.menuAddTrap.trapRequested.connect(self._onTrapRequested)

    def _addFilters(self) -> None:
        '''Register display filters with the filter rack.'''
        for f in ('Color Channel', 'Smoothing', 'Sample and Hold', 'Canny'):
            self.filter.addByName(f)

    @QtCore.Slot()
    def _placeNewTraps(self) -> None:
        '''Put the traps that the menu adds on the optical axis as it is now.

        The calibration can change at any time, so the place is read when
        the menu opens.
        '''
        self.menuAddTrap.pos = QtCore.QPointF(self.cgh.xc, self.cgh.yc)

    @QtCore.Slot(QtCore.QPointF, QTrap)
    def _onTrapRequested(self, pos: QtCore.QPointF, trap: QTrap) -> None:
        '''Add a trap from the menu at the requested position.'''
        trap.r = (pos.x(), pos.y(), 0.)
        self.videoScreen.overlay.addTrap(trap)

    @QtCore.Slot(str)
    def _onComputeFailed(self, reason: str) -> None:
        '''Say why there is no new hologram.

        The next change of the traps asks for another.
        '''
        self.setStatus(f'Hologram computation failed: {reason}')

    def _offerVideoName(self) -> None:
        '''Put a new name in the recorder: ``video_<time>.mkv`` in ``data``.

        A recording that is not given a name of its own (the record button,
        or a task whose file name is empty) is then written to a file of
        its own, and not over the last one.
        '''
        suffix = Path(self.dvr.FILENAME).suffix
        self._videoName = self.save.filename(prefix='video', suffix=suffix)
        self.dvr.filename = self._videoName

    @QtCore.Slot(bool)
    def _onRecording(self, recording: bool) -> None:
        '''Offer another name when a recording to the one offered is over.

        A name that the user chose, or that a task was given, is theirs, and
        is not changed.
        '''
        if not recording and self.dvr.filename == self._videoName:
            self._offerVideoName()

    @QtCore.Slot(str)
    def _onCameraLost(self, reason: str) -> None:
        '''Say that the camera is gone: the screen keeps its last frame.'''
        self._statusBar.showMessage(
            f'Camera lost: {reason}.  Restart the program to use it again.')

    @QtCore.Slot(str)
    def _onRecordingStopped(self, reason: str) -> None:
        '''Say why a recording stopped by itself.'''
        self._statusBar.showMessage(f'Recording stopped: {reason}')

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
        self.videoScreen.overlay.addTweezer(self.cgh.xc, self.cgh.yc)

    @QtCore.Slot()
    def toggleOverlay(self) -> None:
        '''Toggle the visibility of the trap overlay.'''
        self.videoScreen.overlaysVisible = not self.videoScreen.overlaysVisible

    @QtCore.Slot()
    def saveSettings(self) -> None:
        '''Save window geometry and CGH calibration settings.

        A configuration that cannot be written (a full disk, a file system
        that is read-only) is reported and logged.  The window closes with
        this, so an exception would leave the SLM window open and the
        thread of the CGH running.
        '''
        settings = QtCore.QSettings(*self.SETTINGS)
        settings.setValue('geometry', self.saveGeometry())
        try:
            filename = self.save.toToml(self.cghTree)
        except OSError as error:
            logger.exception('Could not save the configuration')
            self.setStatus(f'Could not save the configuration: {error}')
        else:
            self.setStatus(f'Configuration saved to {filename}')

    @QtCore.Slot()
    def restoreSettings(self) -> None:
        '''Restore window geometry and CGH calibration settings.'''
        geometry = QtCore.QSettings(*self.SETTINGS).value('geometry')
        if geometry:        # otherwise the screen fits the window to the video
            self.restoreGeometry(geometry)
        if (filename := self.save.fromToml(self.cghTree)):
            logger.info(f'Configuration restored from {filename}')
            self.setStatus(f'Configuration restored from {filename}')
        else:       # the first launch has none; a bad file was reported
            logger.info('No saved configuration; using the defaults')
            self.setStatus('No saved configuration; using the defaults')

    @property
    def _statusBar(self) -> QtWidgets.QStatusBar:
        '''The status bar, which a main window always has (Qt 6 says it may
        not).'''
        return cast(QtWidgets.QStatusBar, self.statusBar())

    @QtCore.Slot(str)
    def setStatus(self, message: str) -> None:
        '''Display a transient status message in the status bar.'''
        self._statusBar.showMessage(message, 5000)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        '''Save settings, shut down CGH thread, and close the SLM on exit.'''
        self.saveSettings()
        self.cgh.stop()
        self.slm.close()
        super().closeEvent(event)


def _quit(screen: QtWidgets.QWidget,
          opener: QCameraOpener,
          message: object) -> NoReturn:
    '''End the program with a message, before there is a window.

    The thread that opens the camera must not outlive the program, and the
    camera that it holds is closed with it.  ``SystemExit`` with a message
    prints it, and ends the program with a status of 1.
    '''
    opener.stop()
    screen.close()
    sys.exit(f'Error: {message}')


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

    The SLM, the hologram engine, the camera, or the controls of the
    camera, that cannot be made end the program with a message on a line
    and a status of 1, not with a traceback.
    '''
    parser = build_parser()
    # -h and a bad value end the program here, before there is a window or
    # a thread: argparse exits by raising SystemExit, which Qt turns into an
    # abort while the camera thread is running.
    args, _ = parser.parse_known_args()
    configure_logging(getattr(args, 'log_level', None))
    app = pg.mkQApp('QHOT')
    screen = splash()
    screen.show()
    screen.raise_()  # macOS shows a splash screen only if it is raised
    screen.activateWindow()
    say(screen, 'Opening the camera...')
    opener = QCameraOpener(parser)
    app.aboutToQuit.connect(opener.stop)
    opener.start()
    try:
        say(screen, 'Opening the SLM...')
        slm = choose_slm(parser)
        say(screen, 'Starting the hologram engine...')
        cgh = choose_cgh(parser, shape=slm.shape)
    except Exception as error:
        _quit(screen, opener, error)
    say(screen, 'Waiting for the camera...')
    if not opener.waitForCamera():
        _quit(screen, opener, opener.reason)
    say(screen, 'Building the interface...')
    try:
        # both are there once the opener has waited for the camera
        tree = chooser.make_tree(cast(str, opener.key),
                                 cast(QCamera, opener.camera)).start()
    except Exception as error:      # the camera opened, and will do no more
        _quit(screen, opener, error)
    opener.camera = None  # the interface has it now
    hot = QHOT(tree, slm=slm, cgh=cgh)
    hot.show()
    screen.finish(hot)
    pg.exec()


if __name__ == '__main__':
    main()
