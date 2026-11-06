'''Unit tests for lib/traps/commands.py.'''
import sys
import unittest
import numpy as np
from qtpy import QtWidgets
from QHOT.lib.traps.QTrap import QTrap
from QHOT.lib.traps.QTrapGroup import QTrapGroup
from QHOT.lib.traps.QTrapOverlay import QTrapOverlay
from QHOT.lib.traps.commands import (
    AddTrapCommand, RemoveTrapCommand,
    MoveCommand, RotateCommand, WheelCommand,
    LockCommand, PropertyCommand, QUndoStack)
from QHOT.traps.QTweezer import QTweezer


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)


def make_overlay():
    return QTrapOverlay()


class TestPropertyCommand(unittest.TestCase):

    def setUp(self):
        self.overlay = make_overlay()
        self.stack = self.overlay.undoStack
        self.trap = QTweezer(r=(10., 20., 0.))
        self.overlay.addTrap(self.trap)
        self.stack.clear()

    def test_an_edit_sets_the_property_and_undo_sets_it_back(self):
        self.overlay.editTrap(self.trap, 'x', 55.)
        self.assertEqual(self.trap.x, 55.)
        self.stack.undo()
        self.assertEqual(self.trap.x, 10.)
        self.stack.redo()
        self.assertEqual(self.trap.x, 55.)

    def test_the_undo_menu_says_what_was_edited(self):
        self.overlay.editTrap(self.trap, 'amplitude', 0.5)
        self.assertEqual(self.stack.undoText(), 'Edit amplitude')

    def test_an_edit_that_changes_nothing_is_not_a_step(self):
        self.overlay.editTrap(self.trap, 'x', 10.)
        self.assertEqual(self.stack.count(), 0)

    def test_editing_a_group_and_undoing_puts_the_members_back(self):
        group = QTrapGroup(r=(100., 100., 0.))
        group.addTrap([QTweezer(r=(90., 100., 0.)),
                       QTweezer(r=(110., 100., 0.))])
        self.overlay.addTrap(group)
        self.stack.clear()
        before = [leaf.r.copy() for leaf in group.leaves()]
        self.overlay.editTrap(group, 'x', 200.)
        self.assertEqual(next(group.leaves()).x, 190.)
        self.stack.undo()
        for leaf, r in zip(group.leaves(), before):
            np.testing.assert_allclose(leaf.r, r)

    def test_undoing_a_reshape_gives_the_mask_back(self):
        from QHOT.traps.QTrapArray import QTrapArray
        mask = np.array([[True, False, True], [True, True, False]])
        array = QTrapArray(r=(100., 100., 0.), shape=(2, 3), mask=mask)
        self.overlay.addTrap(array)
        self.stack.clear()
        self.overlay.editTrap(array, 'nx', 4.)
        self.assertIsNone(array.mask)
        self.stack.undo()
        self.assertEqual(array.shape, (2, 3))
        np.testing.assert_array_equal(array.mask, mask)
        self.assertEqual(len(list(array.leaves())), 4)

    def test_undoing_a_change_of_separation_keeps_the_mask(self):
        from QHOT.traps.QTrapArray import QTrapArray
        mask = np.array([[True, False], [True, True]])
        array = QTrapArray(r=(100., 100., 0.), shape=(2, 2), mask=mask)
        self.overlay.addTrap(array)
        self.stack.clear()
        self.overlay.editTrap(array, 'separation', 80.)
        self.stack.undo()
        self.assertEqual(array.separation, 50.)
        np.testing.assert_array_equal(array.mask, mask)


class TestAddTrapCommand(unittest.TestCase):

    def setUp(self):
        self.overlay = make_overlay()
        self.stack = self.overlay._undoStack
        self.stack.push(AddTrapCommand(self.overlay, 3., 7.))

    def test_redo_adds_trap(self):
        self.assertEqual(len(self.overlay._traps), 1)

    def test_trap_is_tweezer(self):
        self.assertIsInstance(self.overlay._traps[0], QTweezer)

    def test_trap_position(self):
        trap = self.overlay._traps[0]
        self.assertAlmostEqual(trap.x, 3.)
        self.assertAlmostEqual(trap.y, 7.)

    def test_trap_added_signal(self):
        overlay = make_overlay()
        received = []
        overlay.trapAdded.connect(received.append)
        overlay._undoStack.push(AddTrapCommand(overlay, 1., 2.))
        self.assertEqual(len(received), 1)

    def test_undo_removes_trap(self):
        self.stack.undo()
        self.assertEqual(len(self.overlay._traps), 0)

    def test_undo_emits_trap_removed(self):
        received = []
        self.overlay.trapRemoved.connect(received.append)
        self.stack.undo()
        self.assertEqual(len(received), 1)

    def test_redo_after_undo_restores_trap(self):
        self.stack.undo()
        self.stack.redo()
        self.assertEqual(len(self.overlay._traps), 1)

    def test_repeated_undo_redo_cycle(self):
        for _ in range(3):
            self.stack.undo()
            self.assertEqual(len(self.overlay._traps), 0)
            self.stack.redo()
            self.assertEqual(len(self.overlay._traps), 1)


class TestRemoveTrapCommand(unittest.TestCase):

    def setUp(self):
        self.overlay = make_overlay()
        self.stack = self.overlay._undoStack
        self.trap = QTrap(r=(5., 5., 0.), phase=0.)
        self.overlay._addTrap(self.trap)
        self.stack.push(RemoveTrapCommand(self.overlay, self.trap))

    def test_redo_removes_trap(self):
        self.assertNotIn(self.trap, self.overlay._traps)

    def test_trap_removed_signal_emitted(self):
        overlay = make_overlay()
        trap = QTrap(r=(1., 1., 0.), phase=0.)
        overlay._addTrap(trap)
        received = []
        overlay.trapRemoved.connect(received.append)
        overlay._undoStack.push(RemoveTrapCommand(overlay, trap))
        self.assertEqual(len(received), 1)

    def test_undo_adds_trap_back(self):
        self.stack.undo()
        self.assertIn(self.trap, self.overlay._traps)

    def test_undo_emits_trap_added(self):
        received = []
        self.overlay.trapAdded.connect(received.append)
        self.stack.undo()
        self.assertEqual(len(received), 1)

    def test_redo_after_undo_removes_again(self):
        self.stack.undo()
        self.stack.redo()
        self.assertNotIn(self.trap, self.overlay._traps)

    def test_repeated_undo_redo_cycle(self):
        for _ in range(3):
            self.stack.undo()
            self.assertIn(self.trap, self.overlay._traps)
            self.stack.redo()
            self.assertNotIn(self.trap, self.overlay._traps)


class TestMoveCommand(unittest.TestCase):

    def setUp(self):
        self.trap = QTrap(r=(1., 2., 0.), phase=0.)
        self.origin = self.trap._r.copy()
        self.trap.r = (4., 5., 0.)
        self.cmd = MoveCommand(self.trap, self.origin)
        self.stack = self.trap._undoStack = QUndoStack()
        self.stack.push(self.cmd)

    def test_first_redo_is_noop(self):
        np.testing.assert_array_almost_equal(self.trap._r, [4., 5., 0.])

    def test_undo_restores_origin(self):
        self.stack.undo()
        np.testing.assert_array_almost_equal(self.trap._r, [1., 2., 0.])

    def test_redo_after_undo_restores_destination(self):
        self.stack.undo()
        self.stack.redo()
        np.testing.assert_array_almost_equal(self.trap._r, [4., 5., 0.])

    def test_undo_emits_changed(self):
        received = []
        self.trap.changed.connect(lambda: received.append(1))
        self.stack.undo()
        self.assertTrue(len(received) > 0)

    def test_text(self):
        self.assertEqual(self.cmd.text(), 'Move trap')


class TestRotateCommand(unittest.TestCase):

    def setUp(self):
        self.t1 = QTweezer(r=(4., 0., 0.))
        self.t2 = QTweezer(r=(-4., 0., 0.))
        self.group = QTrapGroup(r=(0., 0., 0.))
        self.group.addTrap([self.t1, self.t2])
        self.snapshot_before = self.group._snapshot()
        self.group.rotate(np.pi / 2., self.snapshot_before)
        self.cmd = RotateCommand(self.group, self.snapshot_before)
        self.stack = QUndoStack()
        self.stack.push(self.cmd)

    def test_first_redo_is_noop(self):
        self.assertAlmostEqual(self.t1._r[0], 0., places=5)
        self.assertAlmostEqual(self.t1._r[1], 4., places=5)

    def test_undo_restores_original_positions(self):
        self.stack.undo()
        self.assertAlmostEqual(self.t1._r[0], 4., places=5)
        self.assertAlmostEqual(self.t1._r[1], 0., places=5)

    def test_redo_after_undo_restores_rotated_positions(self):
        self.stack.undo()
        self.stack.redo()
        self.assertAlmostEqual(self.t1._r[0], 0., places=5)
        self.assertAlmostEqual(self.t1._r[1], 4., places=5)

    def test_text(self):
        self.assertEqual(self.cmd.text(), 'Rotate group')


class TestWheelCommand(unittest.TestCase):

    def setUp(self):
        self.trap = QTrap(r=(0., 0., 10.), phase=0.)
        self.trap._r[2] += 1.
        self.cmd = WheelCommand(self.trap, 1.)
        self.stack = QUndoStack()
        self.stack.push(self.cmd)

    def test_first_redo_is_noop(self):
        self.assertAlmostEqual(self.trap.z, 11.)

    def test_undo_reverses_scroll(self):
        self.stack.undo()
        self.assertAlmostEqual(self.trap.z, 10.)

    def test_redo_after_undo_reapplies(self):
        self.stack.undo()
        self.stack.redo()
        self.assertAlmostEqual(self.trap.z, 11.)

    def test_text(self):
        self.assertEqual(self.cmd.text(), 'Scroll trap z')


class TestWheelCommandMerge(unittest.TestCase):

    def setUp(self):
        self.trap = QTrap(r=(0., 0., 0.), phase=0.)
        self.stack = QUndoStack()
        # Three wheel events each incrementing z by 1
        for _ in range(3):
            self.trap._r[2] += 1.
            self.stack.push(WheelCommand(self.trap, 1.))

    def test_commands_merged_into_one(self):
        self.assertEqual(self.stack.count(), 1)

    def test_merged_dz(self):
        cmd = self.stack.command(0)
        self.assertAlmostEqual(cmd._dz, 3.)

    def test_z_after_scroll(self):
        self.assertAlmostEqual(self.trap.z, 3.)

    def test_undo_reverses_all_scrolls(self):
        self.stack.undo()
        self.assertAlmostEqual(self.trap.z, 0.)

    def test_redo_reapplies_all_scrolls(self):
        self.stack.undo()
        self.stack.redo()
        self.assertAlmostEqual(self.trap.z, 3.)


class TestWheelCommandNoMergeAcrossGroups(unittest.TestCase):

    def test_different_groups_not_merged(self):
        trap_a = QTrap(r=(0., 0., 0.), phase=0.)
        trap_b = QTrap(r=(1., 1., 0.), phase=0.)
        stack = QUndoStack()
        trap_a._r[2] += 1.
        stack.push(WheelCommand(trap_a, 1.))
        trap_b._r[2] += 1.
        stack.push(WheelCommand(trap_b, 1.))
        self.assertEqual(stack.count(), 2)


class TestLockCommand(unittest.TestCase):

    def setUp(self):
        self.overlay = make_overlay()
        self.trap = QTrap(r=(5., 5., 0.), phase=0.)
        self.overlay._addTrap(self.trap)
        self.stack = self.overlay._undoStack

    def test_redo_locks_trap(self):
        self.stack.push(LockCommand(self.overlay, self.trap))
        self.assertTrue(self.trap.locked)

    def test_undo_unlocks_trap(self):
        self.stack.push(LockCommand(self.overlay, self.trap))
        self.stack.undo()
        self.assertFalse(self.trap.locked)

    def test_redo_after_undo_locks_again(self):
        self.stack.push(LockCommand(self.overlay, self.trap))
        self.stack.undo()
        self.stack.redo()
        self.assertTrue(self.trap.locked)

    def test_redo_unlocks_already_locked(self):
        self.trap.locked = True
        self.stack.push(LockCommand(self.overlay, self.trap))
        self.assertFalse(self.trap.locked)

    def test_undo_relocks_after_unlock(self):
        self.trap.locked = True
        self.stack.push(LockCommand(self.overlay, self.trap))
        self.stack.undo()
        self.assertTrue(self.trap.locked)

    def test_text_lock(self):
        cmd = LockCommand(self.overlay, self.trap)
        self.assertEqual(cmd.text(), 'Lock trap')

    def test_text_unlock(self):
        self.trap.locked = True
        cmd = LockCommand(self.overlay, self.trap)
        self.assertEqual(cmd.text(), 'Unlock trap')

    def test_redo_sets_static_brush(self):
        self.stack.push(LockCommand(self.overlay, self.trap))
        spot = self.overlay.points()[0]
        self.assertEqual(spot.brush().color(),
                         self.overlay.brush[self.overlay.State.STATIC].color())

    def test_undo_restores_normal_brush(self):
        self.stack.push(LockCommand(self.overlay, self.trap))
        self.stack.undo()
        spot = self.overlay.points()[0]
        self.assertEqual(spot.brush().color(),
                         self.overlay.brush[self.overlay.State.NORMAL].color())


class TestUndoStackIntegration(unittest.TestCase):
    '''Integration: add, move, and remove via overlay and undo.'''

    def setUp(self):
        from qtpy import QtCore
        self.overlay = make_overlay()
        self.stack = self.overlay._undoStack
        self.overlay.addTrap(QtCore.QPointF(5., 5.))

    def test_undo_add_empties_overlay(self):
        self.stack.undo()
        self.assertEqual(len(self.overlay._traps), 0)

    def test_redo_add_restores_overlay(self):
        self.stack.undo()
        self.stack.redo()
        self.assertEqual(len(self.overlay._traps), 1)

    def test_clear_traps_clears_stack(self):
        self.overlay.clearTraps()
        self.assertFalse(self.stack.canUndo())


if __name__ == '__main__':
    unittest.main()
