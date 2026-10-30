'''The QHOT window: the parts of the system, wired together.

A real window is built, with the camera that makes noise, and whatever
the user does to the traps must show up in the hologram that is made for
the SLM, which is compared here with the algorithm in ``reference``.
'''
import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from pyqtgraph.Qt import QtCore, QtTest, QtWidgets
from QVideo.cameras import chooser

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
            tree = chooser.make_tree(key, cls.camera)
            cls.window = qhot.QHOT(tree)       # its own SLM and CGH
            cls.window.ready = QtTest.QSignalSpy(cls.window.cgh.hologramReady)

    @classmethod
    def close(cls) -> None:
        with patch.object(qhot.QHOT, 'saveSettings'):
            cls.window.close()
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

    def test_the_trap_tab_follows_the_overlay(self):
        traps = self.window.traps
        self.assertEqual(len(traps._trapWidgets), 0)
        trap = QTweezer(r=(60., 40., 0.), phase=0.)
        self.overlay.addTrap(trap)
        self.assertIn(trap, traps._trapWidgets)
        self.overlay.removeTrap(trap)
        self.assertNotIn(trap, traps._trapWidgets)


if __name__ == '__main__':
    unittest.main()
