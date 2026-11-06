'''The QHOT window: the parts of the system, wired together.

A real window is built, with the camera that makes noise, and whatever
the user does to the traps must show up in the hologram that is made for
the SLM, which is compared here with the algorithm in ``reference``.
'''
import importlib
import json
import os
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
from qtpy import QtCore, QtGui, QtTest, QtWidgets
from QVideo.cameras import chooser

from QHOT.lib import QSLM
from QHOT.lib.holograms import CGH
from QHOT.lib.holograms import reference as ref
from QHOT.traps import QTweezer

qhot = importlib.import_module('QHOT.qhot')

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def wait_for(condition, timeout=5000):
    '''Run the event loop until the condition holds.'''
    waited = 0
    while not condition() and waited < timeout:
        QtTest.QTest.qWait(10)
        waited += 10
    return condition()


class Window:

    '''A window that is built once, without touching the user's files.'''

    window = None
    tree = None
    camera = None
    home = None

    @classmethod
    def build(cls) -> None:
        # Saving and restoring the settings would read and write the
        # configuration of the user, and the file helper makes its
        # directories in the home of the user.
        cls.home = tempfile.TemporaryDirectory()
        with patch.object(qhot.QHOT, 'saveSettings'), \
                patch.object(qhot.QHOT, 'restoreSettings'), \
                patch.object(Path, 'home', return_value=Path(cls.home.name)), \
                patch.object(sys, 'argv', ['qhot']):   # not pytest's flags
            key, cls.camera = chooser.open_camera()
            cls.tree = chooser.make_tree(key, cls.camera).start()   # as main()
            slm = QSLM()
            cls.window = qhot.QHOT(cls.tree, slm=slm, cgh=CGH(shape=slm.shape))
            cls.window.ready = QtTest.QSignalSpy(cls.window.cgh.hologramReady)
        wait_for(lambda: cls.window.screen.image.image is not None)

    @classmethod
    def close(cls) -> None:
        with patch.object(qhot.QHOT, 'saveSettings'):
            cls.window.close()
        cls.tree.stop()               # before the camera goes away
        cls.camera.close()
        cls.home.cleanup()


def setUpModule():
    Window.build()


def tearDownModule():
    Window.close()


class WindowCase(unittest.TestCase):

    def setUp(self):
        self.window = Window.window
        self.cgh = self.window.cgh
        self.overlay = self.window.screen.overlay
        self.overlay.clearTraps()
        self.settle()

    def tearDown(self):
        self.overlay.clearTraps()

    @property
    def ready(self):
        return self.window.ready

    def settle(self):
        '''Wait until holograms stop arriving.'''
        count = -1
        while count != len(self.ready):
            count = len(self.ready)
            QtTest.QTest.qWait(60)
        self.seen = len(self.ready)

    def after(self, change):
        '''Make a change; wait for the hologram that follows it.'''
        count = len(self.ready)
        change()
        self.assertTrue(wait_for(lambda: len(self.ready) > count),
                        'no hologram followed the change')
        self.settle()

    def assertHologramOfTheTraps(self):
        shown = np.array(self.ready[len(self.ready) - 1][0]).astype(int)
        expected = ref.hologram(self.overlay.pattern(),
                                self.cgh.optics).astype(int)
        difference = np.abs(shown - expected)
        difference = np.minimum(difference, 256 - difference)   # it wraps
        # Where fields nearly cancel, float32 and float64 may disagree.
        self.assertLess((difference > 2).mean(), 1e-3)


class TestTheHologramFollowsTheTraps(WindowCase):

    def test_adding_a_trap(self):
        self.after(lambda: self.overlay.addTrap(QtCore.QPointF(60., 40.)))
        self.assertHologramOfTheTraps()

    def test_moving_a_trap(self):
        self.after(lambda: self.overlay.addTrap(QtCore.QPointF(60., 40.)))
        trap = next(iter(self.overlay))
        self.after(lambda: setattr(trap, 'r', (30., 50., 2.)))
        self.assertHologramOfTheTraps()

    def test_removing_a_trap(self):
        self.after(lambda: self.overlay.addTrap(QtCore.QPointF(60., 40.)))
        self.after(lambda: self.overlay.addTrap(QtCore.QPointF(20., 70.)))
        self.after(lambda: self.overlay.removeTrap(next(iter(self.overlay))))
        self.assertEqual(len(self.overlay.pattern()), 1)
        self.assertHologramOfTheTraps()

    def test_undo_and_redo(self):
        self.after(lambda: self.overlay.addTrap(QtCore.QPointF(60., 40.)))
        self.after(lambda: self.overlay.addTrap(QtCore.QPointF(20., 70.)))
        self.after(self.overlay.undoStack.undo)
        self.assertEqual(len(self.overlay.pattern()), 1)
        self.assertHologramOfTheTraps()
        self.after(self.overlay.undoStack.redo)
        self.assertEqual(len(self.overlay.pattern()), 2)
        self.assertHologramOfTheTraps()

    def test_clearing_the_traps(self):
        self.after(lambda: self.overlay.addTrap(QtCore.QPointF(60., 40.)))
        self.after(self.overlay.clearTraps)
        self.assertHologramOfTheTraps()

    def test_a_trap_with_structure(self):
        from QHOT.traps import QVortex
        vortex = QVortex(r=(50., 40., 0.), phase=0., ell=3)
        self.after(lambda: self.overlay.addTrap(vortex))
        self.assertHologramOfTheTraps()
        self.after(lambda: setattr(vortex, 'ell', 5))
        self.assertHologramOfTheTraps()

    def test_a_group_that_moves(self):
        from QHOT.lib.traps import QTrapGroup
        from QHOT.traps import QTweezer
        members = [QTweezer(r=(40., 30., 0.), phase=0.),
                   QTweezer(r=(60., 50., 0.), phase=1.)]
        group = QTrapGroup(r=(50., 40., 0.))
        group.addTrap(members)
        self.after(lambda: self.overlay.addTrap(group))
        self.after(lambda: setattr(group, 'r', (70., 45., 0.)))
        self.assertHologramOfTheTraps()

    def test_a_change_of_the_calibration(self):
        self.after(lambda: self.overlay.addTrap(QtCore.QPointF(60., 40.)))
        self.after(lambda: setattr(self.cgh, 'wavelength', 0.9))
        self.assertHologramOfTheTraps()

    def test_nothing_is_computed_when_nothing_changes(self):
        self.after(lambda: self.overlay.addTrap(QtCore.QPointF(60., 40.)))
        count = len(self.ready)
        QtTest.QTest.qWait(200)
        self.assertEqual(len(self.ready), count)

    def test_the_hologram_reaches_the_slm(self):
        self.after(lambda: self.overlay.addTrap(QtCore.QPointF(60., 40.)))
        made = np.array(self.ready[len(self.ready) - 1][0])
        self.assertEqual(self.window.slm.shape, made.shape)
        self.assertTrue(np.array_equal(self.window.slm.data, made))

    def test_the_hologram_reaches_the_view_of_the_slm(self):
        self.after(lambda: self.overlay.addTrap(QtCore.QPointF(60., 40.)))
        made = np.array(self.ready[len(self.ready) - 1][0])
        # The preview draws nothing while its tab is hidden, but keeps
        # the newest hologram for when it is shown.
        self.assertTrue(np.array_equal(self.window.slmView._hologram, made))


class TestTheWindow(WindowCase):

    def test_a_failed_hologram_is_reported(self):
        self.cgh.computeFailed.emit('nothing today')
        self.assertIn('nothing today',
                      self.window.statusBar().currentMessage())

    def test_the_task_manager_is_wired_to_the_system(self):
        manager = self.window.manager
        self.assertIs(manager.overlay, self.overlay)
        self.assertIs(manager.cgh, self.cgh)
        self.assertIs(manager.dvr, self.window.dvr)
        self.assertIs(manager.save, self.window.save)

    def test_a_frame_of_the_screen_steps_the_tasks(self):
        from QHOT.tasks import Delay
        manager = self.window.manager
        manager.clear()
        manager.register(Delay(frames=5))
        self.assertIsNone(manager.active)
        self.window.screen.newFrame.emit(np.zeros((4, 4), np.uint8), None)
        self.assertIsInstance(manager.active, Delay)
        manager.clear()

    def test_the_trap_tab_follows_the_overlay(self):
        traps = self.window.traps
        self.assertEqual(len(traps._trapWidgets), 0)
        trap = QTweezer(r=(60., 40., 0.), phase=0.)
        self.overlay.addTrap(trap)
        self.assertIn(trap, traps._trapWidgets)
        self.overlay.removeTrap(trap)
        self.assertNotIn(trap, traps._trapWidgets)


class TestTheAspectRatioDoesNotChaseItself(WindowCase):

    '''If the width of the screen depends on the height of the window, the
    correction of the height never settles; it must still stop.'''

    def setUp(self):
        super().setUp()
        self.window._resetCorrections()

    def tearDown(self):
        self.window._resetCorrections()
        super().tearDown()

    def chase(self, times, widths):
        # The window never gets the height that it asks for, as when the
        # layout moves the screen again; the screen is as wide as the
        # next of widths.
        # The display is big enough that no height is cut to fit it: the
        # test is about the requests, not about the size of a screen.
        screen = self.window.screen
        frame = MagicMock(return_value=QtCore.QRect(0, 0, 1, 1))
        QApplication = qhot.QtWidgets.QApplication
        display = MagicMock()
        display.availableGeometry.return_value = QtCore.QRect(0, 0, 4000, 3000)
        primary = MagicMock(return_value=display)
        with patch.object(self.window, 'height', return_value=1), \
                patch.object(self.window, 'frameGeometry', frame), \
                patch.object(self.window, 'resize') as resize, \
                patch.object(QApplication, 'primaryScreen', primary), \
                patch.object(screen, 'width', side_effect=widths * times):
            for _ in range(times * len(widths)):
                self.window._constrainAspectRatio()
        return resize.call_count

    def test_the_same_request_is_made_once_in_a_burst(self):
        self.assertEqual(self.chase(20, [900]), 1)

    def test_two_heights_that_alternate_are_asked_for_once_each(self):
        self.assertEqual(self.chase(20, [900, 880]), 2)

    def resized(self, w, h):
        self.window.resizeEvent(QtGui.QResizeEvent(QtCore.QSize(w, h),
                                                   QtCore.QSize(1, 1)))

    def test_a_resize_by_the_user_allows_the_request_again(self):
        self.chase(5, [900])
        self.window._expected = (1000, 700)
        self.resized(1200, 800)             # not what the correction asked
        self.assertEqual(self.window._requested, set())

    def test_the_resize_that_a_correction_causes_is_not_the_user(self):
        self.chase(5, [900])
        asked = set(self.window._requested)
        self.window._expected = (1000, 700)
        self.resized(1000, 700)
        self.assertEqual(self.window._requested, asked)

    def test_a_pause_allows_the_request_again(self):
        self.chase(5, [900])
        self.assertTrue(wait_for(lambda: not self.window._requested))
        self.assertEqual(self.chase(5, [900]), 1)


class TestTheConfigurationThatCannotBeSaved(WindowCase):

    '''A window closes even if the file system will not take its settings.'''

    def save(self, error):
        # Neither the settings nor the configuration of the user.
        with patch.object(qhot.QtCore, 'QSettings'), \
                patch.object(self.window.save, 'toToml', side_effect=error):
            self.window.saveSettings()

    def test_it_is_reported(self):
        self.save(PermissionError('read-only file system'))
        message = self.window.statusBar().currentMessage()
        self.assertIn('Could not save the configuration', message)
        self.assertIn('read-only file system', message)

    def test_it_is_logged_with_its_traceback(self):
        with self.assertLogs(qhot.logger, 'ERROR') as logged:
            self.save(OSError('disk full'))
        self.assertIsNotNone(logged.records[0].exc_info)

    def test_a_saved_configuration_is_reported_with_its_name(self):
        name = '/somewhere/QHOT.toml'
        with patch.object(qhot.QtCore, 'QSettings'), \
                patch.object(self.window.save, 'toToml', return_value=name):
            self.window.saveSettings()
        self.assertIn(name, self.window.statusBar().currentMessage())


class TestTheFileMenu(WindowCase):

    '''The actions of the File menu write and read the files that they name.'''

    def setUp(self):
        super().setUp()
        self.data = Path(Window.home.name) / 'data'
        for path in self.data.glob('*'):
            path.unlink()
        self.after(lambda: self.overlay.addTrap(QtCore.QPointF(60., 40.)))
        self.after(lambda: self.overlay.addTrap(QtCore.QPointF(90., 70.)))

    def files(self):
        return sorted(self.data.glob('*'))

    def trigger(self, action, dialog=None, name=None):
        '''Trigger an action, answering the file dialog with ``name``.'''
        before = set(self.files())
        answer = (str(self.data / name), '') if name else ('', '')
        dialog = dialog or 'getSaveFileName'
        with patch.object(QtWidgets.QFileDialog, dialog, return_value=answer):
            getattr(self.window, action).trigger()
        QtTest.QTest.qWait(50)
        return sorted(set(self.files()) - before)

    def pixels(self, path) -> np.ndarray:
        image = QtGui.QImage(str(path))
        rows = range(image.height())
        columns = range(image.width())
        return np.array([[QtGui.qGray(image.pixel(x, y)) for x in columns]
                         for y in rows])

    def test_save_traps(self):
        (path,) = self.trigger('actionSaveTraps')
        self.assertEqual(path.suffix, '.json')
        self.assertEqual(json.loads(path.read_text()), self.overlay.toList())
        self.assertIn(path.name, self.window.statusBar().currentMessage())

    def test_save_traps_again_goes_to_the_same_file(self):
        (path,) = self.trigger('actionSaveTrapsAs', name='mine.json')
        self.overlay.clearTraps()
        self.assertEqual(self.trigger('actionSaveTraps'), [])    # no new file
        self.assertEqual(json.loads(path.read_text()), [])

    def test_save_traps_as(self):
        (path,) = self.trigger('actionSaveTrapsAs', name='chosen.json')
        self.assertEqual(path.name, 'chosen.json')
        self.assertEqual(len(json.loads(path.read_text())), 2)

    def test_open_traps(self):
        (path,) = self.trigger('actionSaveTrapsAs', name='chosen.json')
        saved = self.overlay.toList()
        self.overlay.clearTraps()
        self.assertEqual(self.overlay.pattern(), ())
        self.trigger('actionOpenTraps', 'getOpenFileName', 'chosen.json')
        self.assertEqual(self.overlay.toList(), saved)
        self.assertIn('chosen.json', self.window.statusBar().currentMessage())

    def test_a_canceled_dialog_changes_nothing(self):
        self.assertEqual(self.trigger('actionSaveTrapsAs'), [])
        self.assertIn('canceled', self.window.statusBar().currentMessage())
        before = self.overlay.toList()
        self.trigger('actionOpenTraps', 'getOpenFileName')
        self.assertEqual(self.overlay.toList(), before)

    def test_save_the_queue_and_open_it_again(self):
        self.window.manager.clear()
        self.window.menuQueue._onTaskSelected('Delay')
        self.window.menuQueue._onTaskSelected('ClearTraps')
        (path,) = self.trigger('actionSaveQueueAs', name='queue.toml')
        saved = tomllib.loads(path.read_text())['tasks']
        self.assertEqual([d['type'] for d in saved], ['Delay', 'ClearTraps'])
        self.window.manager.clear()
        self.trigger('actionOpenQueue', 'getOpenFileName', 'queue.toml')
        self.assertEqual(self.window.manager.toList(), saved)
        self.assertTrue(self.window.manager.paused)  # look before it runs
        self.window.manager.clear()

    def test_a_queue_is_a_toml_file_that_says_what_it_is(self):
        self.window.manager.clear()
        self.window.menuQueue._onTaskSelected('Delay')
        (path,) = self.trigger('actionSaveQueue')
        self.assertEqual(path.suffix, '.toml')
        text = path.read_text()
        self.assertTrue(text.startswith('# A queue of tasks for QHOT.'))
        self.assertIn('[[tasks]]', text)
        self.window.manager.clear()

    def open_by_hand(self, text: str):
        '''Open a queue file that a person wrote.'''
        (self.data / 'by_hand.toml').write_text(text)
        self.window.manager.clear()
        self.trigger('actionOpenQueue', 'getOpenFileName', 'by_hand.toml')

    def message(self) -> str:
        return self.window.statusBar().currentMessage()

    def test_a_queue_that_is_written_by_hand_runs_as_written(self):
        self.open_by_hand('''
# a short experiment
[[tasks]]
type = "Delay"
frames = 12              # settle

[[tasks]]
type = "Move"
x = 100
y = 50.5
step = 2

[[tasks]]
type = "ClearTraps"
''')
        tasks = self.window.manager.scheduled
        self.assertEqual([type(t).__name__ for t in tasks],
                         ['Delay', 'Move', 'ClearTraps'])
        self.assertEqual(tasks[0].frames, 12)
        self.assertEqual((tasks[1].x, tasks[1].y, tasks[1].step),
                         (100, 50.5, 2))
        self.assertIn('Opened queue', self.message())
        self.window.manager.clear()

    def test_a_task_that_leaves_out_its_parameters_has_the_defaults(self):
        self.open_by_hand('[[tasks]]\ntype = "Delay"\n')
        (task,) = self.window.manager.scheduled
        self.assertEqual(task.frames, 30)
        self.window.manager.clear()

    def test_a_mistake_in_the_name_of_a_task_names_it(self):
        with self.assertLogs('QHOT.lib.QFileAction', level='ERROR'):
            self.open_by_hand('[[tasks]]\ntype = "Dely"\n')
        self.assertIn("unknown task type: 'Dely'", self.message())
        self.assertEqual(self.window.manager.scheduled, [])

    def test_a_mistake_in_the_name_of_a_parameter_names_it(self):
        with self.assertLogs('QHOT.lib.QFileAction', level='ERROR'):
            self.open_by_hand('[[tasks]]\ntype = "Delay"\nframe = 5\n')
        self.assertIn("'frame'", self.message())
        self.assertEqual(self.window.manager.scheduled, [])

    def test_a_task_with_no_type_says_so(self):
        with self.assertLogs('QHOT.lib.QFileAction', level='ERROR'):
            self.open_by_hand('[[tasks]]\nframes = 5\n')
        self.assertIn("needs a 'type'", self.message())

    def test_a_fault_in_the_toml_says_where(self):
        with self.assertLogs('QHOT.lib.QFileAction', level='ERROR'):
            self.open_by_hand('[[tasks]]\ntype = Delay\n')
        self.assertIn('line 2', self.message())

    def test_save_the_image(self):
        (path,) = self.trigger('actionSaveImage')
        self.assertEqual(path.suffix, '.png')
        image = QtGui.QImage(str(path))
        self.assertEqual((image.width(), image.height()),
                         self.window.screen.image.image.shape[:2][::-1])

    def test_save_the_image_as(self):
        (path,) = self.trigger('actionSaveImageAs', name='frame.png')
        self.assertEqual(path.name, 'frame.png')
        self.assertFalse(QtGui.QImage(str(path)).isNull())

    def test_save_the_hologram(self):
        (path,) = self.trigger('actionSaveHologram')
        self.assertIn('hologram', path.name)
        np.testing.assert_array_equal(self.pixels(path),
                                      self.window.slm.data)

    def test_save_the_hologram_as(self):
        (path,) = self.trigger('actionSaveHologramAs', name='holo.png')
        self.assertEqual(path.name, 'holo.png')
        np.testing.assert_array_equal(self.pixels(path),
                                      self.window.slm.data)


class TestTheWindowFollowsTheCamera(unittest.TestCase):

    '''The screen has the shape of the image, so the image has no bars.

    The panels of controls scroll, so that they never ask for more height
    than the image has.
    '''

    @classmethod
    def setUpClass(cls):
        cls.window = Window.window
        cls.window.show()
        QtTest.QTest.qWait(100)

    @classmethod
    def tearDownClass(cls):
        cls.window.hide()

    def camera(self):
        size = self.window.screen.sizeHint()
        return size.width(), size.height()

    def test_the_screen_has_the_shape_of_the_camera_at_any_width(self):
        width, height = self.camera()
        for w in (560, 620, 680, 740, 800):
            with self.subTest(width=w):
                self.window.resize(w, 700)
                QtTest.QTest.qWait(150)
                screen = self.window.screen
                self.assertAlmostEqual(
                    screen.height(),
                    screen.width() * height // width,
                    delta=2,
                    msg='the image has bars',
                )

    def test_the_panels_scroll(self):
        tabs = self.window.tabWidget
        self.assertEqual(tabs.count(), 6)
        for n in range(tabs.count()):
            with self.subTest(tabs.tabText(n)):
                page = tabs.widget(n)
                self.assertIsInstance(page, QtWidgets.QScrollArea)
                self.assertTrue(page.widgetResizable())

    def test_the_panels_do_not_ask_for_more_height_than_the_image_has(self):
        _, height = self.camera()
        self.assertLess(self.window.tabWidget.minimumSizeHint().height(),
                        height)
        self.assertLess(self.window.minimumSizeHint().height(), height)

    def test_the_contents_of_a_panel_are_where_the_program_puts_them(self):
        # the pages are still named, and the widgets are in them
        self.assertIs(self.window.cameraTree.parent(), self.window.videoTab)
        self.assertIsNotNone(self.window.videoTab.layout())
        viewport = self.window.videoTab.parent()
        self.assertIs(viewport.parent(), self.window.videoScroll)


class TestTheCommandLine(unittest.TestCase):
    '''The command line is read before there is a window or a thread.

    ``-h`` once aborted the program (a thread was running when
    ``SystemExit`` left ``main``), and a bad value crashed it.
    '''

    def run_qhot(self, *args: str) -> subprocess.CompletedProcess:
        script = 'from QHOT.qhot import main; main()'
        env = dict(os.environ, QT_QPA_PLATFORM='offscreen')
        return subprocess.run([sys.executable, '-c', script, *args],
                              capture_output=True,
                              text=True,
                              timeout=120,
                              env=env)

    def test_help_prints_and_ends(self):
        done = self.run_qhot('-h')
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn('camera backend', done.stdout)
        self.assertIn('CGH backend', done.stdout)

    def test_a_bad_value_ends_with_a_message(self):
        done = self.run_qhot('-c', 'abc')
        self.assertEqual(done.returncode, 2, done.stderr)
        self.assertIn('invalid int value', done.stderr)


class TestTheTasksMenu(WindowCase):

    def test_add_tweezer_comes_before_clear_traps(self):
        actions = self.window.menuTasks.actions()
        names = [a.text() for a in actions]
        self.assertLess(names.index('Add &Tweezer'),
                        actions.index(self.window.actionClearTraps))


class TestTheAddTrapMenu(WindowCase):
    '''A trap that the menu adds is on the optical axis, as calibrated.'''

    def setUp(self):
        super().setUp()
        self.axis = (self.cgh.xc, self.cgh.yc)
        self.addCleanup(self.restoreAxis)

    def restoreAxis(self):
        self.cgh.xc, self.cgh.yc = self.axis

    def add(self, name):
        menu = self.window.menuAddTrap
        menu.aboutToShow.emit()             # as the menu does when it opens
        action = next(a for a in menu.actions() if a.text() == name)
        action.trigger()

    def test_the_trap_is_where_the_axis_was_calibrated(self):
        self.cgh.xc, self.cgh.yc = 123., 77.
        self.add('QTweezer')
        (trap,) = list(self.overlay.groupOf(t) for t in self.overlay._traps)
        np.testing.assert_allclose(trap.r[:2], [123., 77.])


class TestStartingUp(unittest.TestCase):
    '''What main() and the window do when something is missing.'''

    def test_no_saved_configuration_is_not_a_warning(self):
        # The first launch on a machine has no configuration file.
        window = MagicMock()
        window.save.fromToml.return_value = ''
        window.SETTINGS = qhot.QHOT.SETTINGS
        with patch.object(qhot.QtCore, 'QSettings') as settings, \
                patch.object(qhot.QtCore.QTimer, 'singleShot'):
            settings.return_value.value.return_value = None
            with self.assertNoLogs(qhot.logger, 'WARNING'):
                qhot.QHOT.restoreSettings(window)
        message = window.setStatus.call_args.args[0]
        self.assertIn('defaults', message)

    def test_a_failure_to_make_the_slm_stops_the_camera_thread(self):
        opener = MagicMock()
        screen = MagicMock()
        failing = MagicMock(side_effect=RuntimeError('no SLM'))
        with patch.object(qhot.pg, 'mkQApp'), \
                patch.object(qhot, 'build_parser'), \
                patch.object(qhot, 'splash', return_value=screen), \
                patch.object(qhot, 'say'), \
                patch.object(qhot, 'QCameraOpener', return_value=opener), \
                patch.object(qhot, 'choose_slm', failing):
            with self.assertRaises(SystemExit) as raised:
                qhot.main()
        opener.stop.assert_called_once()
        screen.close.assert_called_once()
        self.assertIn('no SLM', str(raised.exception))

    def test_a_failure_to_make_the_engine_stops_the_camera_thread(self):
        opener = MagicMock()
        failing = MagicMock(side_effect=RuntimeError('no engine'))
        with patch.object(qhot.pg, 'mkQApp'), \
                patch.object(qhot, 'build_parser'), \
                patch.object(qhot, 'splash'), \
                patch.object(qhot, 'say'), \
                patch.object(qhot, 'QCameraOpener', return_value=opener), \
                patch.object(qhot, 'choose_slm'), \
                patch.object(qhot, 'choose_cgh', failing):
            with self.assertRaises(SystemExit):
                qhot.main()
        opener.stop.assert_called_once()


if __name__ == '__main__':
    unittest.main()
