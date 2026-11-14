'''Unit tests for QTrapOverlay.'''
import unittest
from unittest.mock import MagicMock, patch

import numpy as np
from qtpy import QtCore, QtWidgets, QtTest

from QHOT.lib.traps.QTrap import QTrap
from QHOT.lib.traps.QTrapGroup import QTrapGroup
from QHOT.lib.traps.QTrapOverlay import QTrapOverlay
from QHOT.lib.traps.commands import RemoveTrapCommand
from QHOT.traps.QTweezer import QTweezer


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def make_overlay():
    return QTrapOverlay()


class TestAddTrapSingle(unittest.TestCase):

    def setUp(self):
        self.overlay = make_overlay()
        self.trap = QTrap(r=(1., 2., 0.), phase=0.)
        self.overlay.addTrap(self.trap)

    def test_sets_parent(self):
        self.assertIs(self.trap.parent(), self.overlay)

    def test_registers_in_traps(self):
        self.assertIn(self.trap, self.overlay._traps)

    def test_index(self):
        self.assertEqual(self.trap._index, 0)

    def test_spot_created(self):
        self.assertEqual(len(self.overlay.points()), 1)

    def test_spot_position(self):
        spot = self.overlay.points()[0]
        self.assertAlmostEqual(spot._data['x'], 1.)
        self.assertAlmostEqual(spot._data['y'], 2.)


class TestAddTrapGroup(unittest.TestCase):

    def setUp(self):
        self.overlay = make_overlay()
        self.t1 = QTrap(r=(4., 4., 0.), phase=0.)
        self.t2 = QTrap(r=(6., 6., 0.), phase=0.)
        self.grp = QTrapGroup(r=(5., 5., 0.))
        self.grp.addTrap([self.t1, self.t2])
        self.overlay.addTrap(self.grp)

    def test_group_parent_is_overlay(self):
        self.assertIs(self.grp.parent(), self.overlay)

    def test_leaf_traps_registered(self):
        self.assertIn(self.t1, self.overlay._traps)
        self.assertIn(self.t2, self.overlay._traps)

    def test_spot_count(self):
        self.assertEqual(len(self.overlay.points()), 2)

    def test_iter_yields_group(self):
        self.assertEqual(list(self.overlay), [self.grp])


class TestAddTweezer(unittest.TestCase):

    '''A tweezer that is added at a position can be undone.'''

    def setUp(self):
        self.overlay = make_overlay()
        self.overlay.addTweezer(3., 7.)

    def test_a_tweezer_is_at_the_position(self):
        (trap,) = list(self.overlay)
        self.assertIsInstance(trap, QTweezer)
        self.assertAlmostEqual(trap.x, 3.)
        self.assertAlmostEqual(trap.y, 7.)

    def test_it_can_be_undone_and_done_again(self):
        self.overlay.undoStack.undo()
        self.assertEqual(list(self.overlay), [])
        self.overlay.undoStack.redo()
        self.assertEqual(len(list(self.overlay)), 1)


class TestAddTrapList(unittest.TestCase):

    def setUp(self):
        self.overlay = make_overlay()
        self.traps = [QTrap(r=(float(i), 0., 0.), phase=0.) for i in range(3)]
        self.overlay.addTrap(self.traps)

    def test_all_registered(self):
        self.assertEqual(len(self.overlay._traps), 3)

    def test_all_parents_set(self):
        self.assertTrue(all(t.parent() is self.overlay for t in self.traps))

    def test_spot_indices_sequential(self):
        self.assertEqual([t._index for t in self.traps], [0, 1, 2])


class TestGroupOf(unittest.TestCase):

    def test_ungrouped_returns_self(self):
        trap = QTrap(phase=0.)
        self.assertIs(QTrapOverlay.groupOf(trap), trap)

    def test_grouped_returns_group(self):
        trap = QTrap(phase=0.)
        grp = QTrapGroup(r=(0., 0., 0.))
        grp.addTrap(trap)
        self.assertIs(QTrapOverlay.groupOf(trap), grp)

    def test_nested_returns_topmost(self):
        trap = QTrap(phase=0.)
        inner = QTrapGroup(r=(0., 0., 0.))
        outer = QTrapGroup(r=(0., 0., 0.))
        inner.addTrap(trap)
        inner.setParent(outer)
        self.assertIs(QTrapOverlay.groupOf(trap), outer)


class TestIter(unittest.TestCase):

    def setUp(self):
        self.overlay = make_overlay()

    def test_yields_ungrouped_traps(self):
        traps = [QTrap(r=(float(i), 0., 0.), phase=0.) for i in range(3)]
        self.overlay.addTrap(traps)
        self.assertEqual(list(self.overlay), traps)

    def test_yields_group_not_leaves(self):
        grp = QTrapGroup(r=(5., 5., 0.))
        grp.addTrap([QTrap(r=(4., 4., 0.), phase=0.),
                     QTrap(r=(6., 6., 0.), phase=0.)])
        self.overlay.addTrap(grp)
        self.assertEqual(list(self.overlay), [grp])

    def test_mixed_traps_and_groups(self):
        t = QTrap(r=(1., 1., 0.), phase=0.)
        grp = QTrapGroup(r=(5., 5., 0.))
        grp.addTrap(QTrap(r=(5., 5., 0.), phase=0.))
        self.overlay.addTrap(t)
        self.overlay.addTrap(grp)
        self.assertEqual(list(self.overlay), [t, grp])


class TestRemoveTrapSingle(unittest.TestCase):

    def setUp(self):
        self.overlay = make_overlay()
        self.trap = QTrap(r=(1., 2., 0.), phase=0.)
        self.overlay.addTrap(self.trap)
        self.overlay.removeTrap(self.trap)

    def test_unregistered(self):
        self.assertNotIn(self.trap, self.overlay._traps)

    def test_parent_cleared(self):
        self.assertIsNone(self.trap.parent())

    def test_spot_removed(self):
        self.assertEqual(len(self.overlay.points()), 0)

    def test_index_cleared(self):
        self.assertIsNone(self.trap._index)


class TestRemoveTrapGroup(unittest.TestCase):
    '''Removing any leaf trap from a group removes the entire group.'''

    def setUp(self):
        self.overlay = make_overlay()
        self.t1 = QTrap(r=(4., 4., 0.), phase=0.)
        self.t2 = QTrap(r=(6., 6., 0.), phase=0.)
        self.grp = QTrapGroup(r=(5., 5., 0.))
        self.grp.addTrap([self.t1, self.t2])
        self.overlay.addTrap(self.grp)
        self.overlay.removeTrap(self.t1)

    def test_all_leaves_unregistered(self):
        self.assertNotIn(self.t1, self.overlay._traps)
        self.assertNotIn(self.t2, self.overlay._traps)

    def test_group_parent_cleared(self):
        self.assertIsNone(self.grp.parent())

    def test_no_spots_remain(self):
        self.assertEqual(len(self.overlay.points()), 0)


class TestRemovedGroupKeepsItsMembers(unittest.TestCase):
    '''A group that is removed is still a group, so that undo restores it.'''

    def setUp(self):
        self.overlay = make_overlay()
        self.inner = QTrapGroup(r=(7., 7., 0.))
        self.leaf = QTrap(r=(7., 7., 0.), phase=0.)
        self.inner.addTrap(self.leaf)
        self.t1 = QTrap(r=(4., 4., 0.), phase=0.)
        self.grp = QTrapGroup(r=(5., 5., 0.))
        self.grp.addTrap([self.t1, self.inner])
        self.overlay.addTrap(self.grp)

    def test_members_stay_in_the_group(self):
        self.overlay.removeTrap(self.t1)
        self.assertEqual(self.grp.traps, [self.t1, self.inner])
        self.assertEqual(self.inner.traps, [self.leaf])
        self.assertIs(self.t1.parent(), self.grp)
        self.assertIsNone(self.grp.parent())

    def test_undo_restores_the_whole_group(self):
        self.overlay.undoStack.push(RemoveTrapCommand(self.overlay, self.grp))
        self.assertEqual(len(self.overlay._traps), 0)
        self.overlay.undoStack.undo()
        self.assertEqual(len(self.overlay._traps), 2)
        self.assertEqual(len(self.grp.traps), 2)
        self.assertIs(self.grp.parent(), self.overlay)

    def test_redo_removes_it_again(self):
        self.overlay.undoStack.push(RemoveTrapCommand(self.overlay, self.grp))
        self.overlay.undoStack.undo()
        self.overlay.undoStack.redo()
        self.assertEqual(len(self.overlay._traps), 0)
        self.assertEqual(len(self.grp.traps), 2)


class TestRemoveTrapLargerGroup(unittest.TestCase):
    '''Removing any leaf from a three-member group removes the entire group.'''

    def setUp(self):
        self.overlay = make_overlay()
        self.traps = [QTrap(r=(float(i), 0., 0.), phase=0.) for i in range(3)]
        self.grp = QTrapGroup(r=(1., 0., 0.))
        self.grp.addTrap(self.traps)
        self.overlay.addTrap(self.grp)
        self.overlay.removeTrap(self.traps[0])

    def test_all_leaves_unregistered(self):
        for trap in self.traps:
            self.assertNotIn(trap, self.overlay._traps)

    def test_group_parent_cleared(self):
        self.assertIsNone(self.grp.parent())

    def test_no_spots_remain(self):
        self.assertEqual(len(self.overlay.points()), 0)


class TestRemoveTrapSignalOrdering(unittest.TestCase):
    '''trapRemoved must fire while group leaves are still attached.

    QTrapWidget.unregisterTrap iterates group.leaves() to remove leaf
    rows.  If leaves are orphaned before the signal fires, unregisterTrap
    sees an empty iterator and leaf rows are leaked.
    '''

    def setUp(self):
        self.overlay = make_overlay()
        self.t1 = QTrap(r=(1., 0., 0.), phase=0.)
        self.t2 = QTrap(r=(2., 0., 0.), phase=0.)
        self.grp = QTrapGroup(r=(1.5, 0., 0.))
        self.grp.addTrap([self.t1, self.t2])
        self.overlay.addTrap(self.grp)

    def test_leaves_still_attached_when_trap_removed_fires(self):
        leaf_count_at_signal = []
        self.overlay.trapRemoved.connect(
            lambda g: leaf_count_at_signal.append(len(list(g.leaves()))))
        self.overlay.removeTrap(self.t1)
        self.assertEqual(leaf_count_at_signal, [2])

    def test_leaves_stay_in_the_group_after_remove(self):
        self.overlay.removeTrap(self.t1)
        self.assertIs(self.t1.parent(), self.grp)
        self.assertIs(self.t2.parent(), self.grp)


class TestClearTraps(unittest.TestCase):

    def setUp(self):
        self.overlay = make_overlay()
        grp = QTrapGroup(r=(5., 5., 0.))
        grp.addTrap([QTrap(r=(4., 4., 0.), phase=0.),
                     QTrap(r=(6., 6., 0.), phase=0.)])
        self.overlay.addTrap([QTrap(r=(1., 1., 0.), phase=0.),
                               QTrap(r=(2., 2., 0.), phase=0.)])
        self.overlay.addTrap(grp)
        self.overlay.clearTraps()

    def test_traps_list_empty(self):
        self.assertEqual(self.overlay._traps, [])

    def test_no_spots(self):
        self.assertEqual(len(self.overlay.points()), 0)

    def test_no_top_level_children(self):
        self.assertEqual(list(self.overlay), [])


class TestRebuildSpots(unittest.TestCase):

    def test_indices_resequenced_after_removal(self):
        overlay = make_overlay()
        traps = [QTrap(r=(float(i), 0., 0.), phase=0.) for i in range(3)]
        overlay.addTrap(traps)
        overlay.removeTrap(traps[1])
        self.assertEqual(traps[0]._index, 0)
        self.assertEqual(traps[2]._index, 1)


class TestOnTrapChanged(unittest.TestCase):

    def test_spot_position_updated(self):
        overlay = make_overlay()
        trap = QTrap(r=(1., 2., 0.), phase=0.)
        overlay.addTrap(trap)
        trap.r = (5., 6., 0.)
        spot = overlay.points()[0]
        self.assertAlmostEqual(spot._data['x'], 5.)
        self.assertAlmostEqual(spot._data['y'], 6.)

    def test_spot_position_unchanged_for_z(self):
        overlay = make_overlay()
        trap = QTrap(r=(1., 2., 0.), phase=0.)
        overlay.addTrap(trap)
        trap.z = 99.
        spot = overlay.points()[0]
        self.assertAlmostEqual(spot._data['x'], 1.)
        self.assertAlmostEqual(spot._data['y'], 2.)


class TestSetGroupBrush(unittest.TestCase):

    def setUp(self):
        self.overlay = make_overlay()
        self.t1 = QTrap(r=(1., 1., 0.), phase=0.)
        self.t2 = QTrap(r=(2., 2., 0.), phase=0.)
        grp = QTrapGroup(r=(1.5, 1.5, 0.))
        grp.addTrap([self.t1, self.t2])
        self.overlay.addTrap(grp)

    def test_sets_all_leaf_spots(self):
        self.overlay.setGroupBrush(self.overlay._traps[0].parent(),
                                    self.overlay.State.ACTIVE)
        for trap in [self.t1, self.t2]:
            spot = self.overlay.points()[trap._index]
            self.assertEqual(spot.brush(),
                             self.overlay.brush[self.overlay.State.ACTIVE])

    def test_resets_to_normal(self):
        self.overlay.setGroupBrush(self.overlay._traps[0].parent(),
                                    self.overlay.State.ACTIVE)
        self.overlay.setGroupBrush(self.overlay._traps[0].parent(),
                                    self.overlay.State.NORMAL)
        for trap in [self.t1, self.t2]:
            spot = self.overlay.points()[trap._index]
            self.assertEqual(spot.brush(),
                             self.overlay.brush[self.overlay.State.NORMAL])


class TestTrapSignals(unittest.TestCase):

    def setUp(self):
        self.overlay = QTrapOverlay()

    def tearDown(self):
        self.overlay.clearTraps()

    def test_trap_added_emitted_on_add_single(self):
        trap = QTrap(r=(1., 2., 0.), phase=0.)
        spy = QtTest.QSignalSpy(self.overlay.trapAdded)
        self.overlay.addTrap(trap)
        self.assertEqual(len(spy), 1)

    def test_trap_added_carries_correct_trap(self):
        trap = QTrap(r=(1., 2., 0.), phase=0.)
        spy = QtTest.QSignalSpy(self.overlay.trapAdded)
        self.overlay.addTrap(trap)
        self.assertIs(spy[0][0], trap)

    def test_trap_added_emitted_once_per_list_item(self):
        traps = [QTrap(r=(float(i), 0., 0.), phase=0.) for i in range(3)]
        spy = QtTest.QSignalSpy(self.overlay.trapAdded)
        self.overlay.addTrap(traps)
        self.assertEqual(len(spy), 3)

    def test_trap_added_emitted_for_group(self):
        group = QTrapGroup(r=(5., 5., 0.))
        group.addTrap([QTrap(r=(4., 5., 0.), phase=0.),
                       QTrap(r=(6., 5., 0.), phase=0.)])
        spy = QtTest.QSignalSpy(self.overlay.trapAdded)
        self.overlay.addTrap(group)
        self.assertEqual(len(spy), 1)
        self.assertIs(spy[0][0], group)

    def test_trap_removed_emitted_on_remove(self):
        trap = QTrap(r=(1., 2., 0.), phase=0.)
        self.overlay.addTrap(trap)
        spy = QtTest.QSignalSpy(self.overlay.trapRemoved)
        self.overlay.removeTrap(trap)
        self.assertEqual(len(spy), 1)

    def test_trap_removed_carries_correct_trap(self):
        trap = QTrap(r=(1., 2., 0.), phase=0.)
        self.overlay.addTrap(trap)
        spy = QtTest.QSignalSpy(self.overlay.trapRemoved)
        self.overlay.removeTrap(trap)
        self.assertIs(spy[0][0], trap)

    def test_trap_removed_emitted_for_each_on_clear(self):
        traps = [QTrap(r=(float(i), 0., 0.), phase=0.) for i in range(3)]
        self.overlay.addTrap(traps)
        spy = QtTest.QSignalSpy(self.overlay.trapRemoved)
        self.overlay.clearTraps()
        self.assertEqual(len(spy), 3)


class TestTrapAt(unittest.TestCase):

    def setUp(self):
        self.overlay = make_overlay()
        self.trap = QTrap(r=(5., 5., 0.), phase=0.)
        self.overlay.addTrap(self.trap)

    def test_returns_trap_at_position(self):
        spot = self.overlay.points()[0]
        with patch.object(self.overlay, 'pointsAt', return_value=[spot]):
            result = self.overlay.trapAt(QtCore.QPointF(5., 5.))
        self.assertIs(result, self.trap)

    def test_returns_none_when_no_trap(self):
        with patch.object(self.overlay, 'pointsAt', return_value=[]):
            result = self.overlay.trapAt(QtCore.QPointF(99., 99.))
        self.assertIsNone(result)


class TestGroupAt(unittest.TestCase):

    def setUp(self):
        self.overlay = make_overlay()
        self.t1 = QTrap(r=(4., 4., 0.), phase=0.)
        self.t2 = QTrap(r=(6., 6., 0.), phase=0.)
        self.grp = QTrapGroup(r=(5., 5., 0.))
        self.grp.addTrap([self.t1, self.t2])
        self.overlay.addTrap(self.grp)

    def test_returns_group_at_position(self):
        with patch.object(self.overlay, 'trapAt', return_value=self.t1):
            result = self.overlay.groupAt(QtCore.QPointF(4., 4.))
        self.assertIs(result, self.grp)

    def test_returns_ungrouped_trap_itself(self):
        overlay = make_overlay()
        trap = QTrap(r=(5., 5., 0.), phase=0.)
        overlay.addTrap(trap)
        with patch.object(overlay, 'trapAt', return_value=trap):
            result = overlay.groupAt(QtCore.QPointF(5., 5.))
        self.assertIs(result, trap)

    def test_returns_none_when_no_trap(self):
        with patch.object(self.overlay, 'trapAt', return_value=None):
            result = self.overlay.groupAt(QtCore.QPointF(99., 99.))
        self.assertIsNone(result)


class TestReshapeSignals(unittest.TestCase):
    '''Cover _connectGroup, _onGroupReshaping, _onGroupReshaped.'''

    def setUp(self):
        from QHOT.traps.QTrapArray import QTrapArray
        self.overlay = make_overlay()
        self.array = QTrapArray(shape=(2, 2), separation=10.)
        self.overlay.addTrap(self.array)

    def tearDown(self):
        self.overlay.clearTraps()

    def test_array_leaves_registered_on_add(self):
        self.assertEqual(len(self.overlay._traps), 4)

    def test_reshaping_signal_connected(self):
        # Changing nx triggers reshaping/reshaped; trap count should update.
        self.array.nx = 3
        self.assertEqual(len(self.overlay._traps), 6)

    def test_shrink_updates_trap_count(self):
        self.array.nx = 1
        self.assertEqual(len(self.overlay._traps), 2)

    def test_spot_count_matches_traps_after_reshape(self):
        self.array.ny = 3
        self.assertEqual(len(self.overlay._traps), len(self.overlay.points()))

    def test_trap_removed_signal_emitted_on_reshape(self):
        spy = QtTest.QSignalSpy(self.overlay.trapRemoved)
        self.array.nx = 3
        self.assertEqual(len(spy), 1)

    def test_trap_added_signal_emitted_on_reshape(self):
        spy = QtTest.QSignalSpy(self.overlay.trapAdded)
        self.array.nx = 3
        self.assertEqual(len(spy), 1)

    def test_all_new_leaves_have_changed_connected(self):
        self.array.nx = 3
        spy = QtTest.QSignalSpy(self.overlay.trapAdded)
        # Changing a trap's position should not raise — signals are connected.
        try:
            for t in self.array.leaves():
                t.x = t.x + 1.
        except Exception as e:
            self.fail(f'Unexpected exception after reshape: {e}')

    def test_old_leaves_disconnected_after_reshape(self):
        old_leaves = list(self.array.leaves())
        self.array.nx = 3
        # Old leaves are no longer in _traps
        for leaf in old_leaves:
            self.assertNotIn(leaf, self.overlay._traps)


class TestSaveLoad(unittest.TestCase):

    def setUp(self):
        self.overlay = make_overlay()

    def test_roundtrip_tweezer_count(self):
        for x in (10., 50., 90.):
            self.overlay.addTrap(QTweezer(r=(x, 30., 0.), phase=0.))
        data = self.overlay.toList()
        self.overlay.fromList(data)
        self.assertEqual(len(self.overlay._traps), 3)

    def test_roundtrip_tweezer_position(self):
        self.overlay.addTrap(QTweezer(r=(123., 456., 7.), phase=0.))
        self.overlay.fromList(self.overlay.toList())
        trap = self.overlay._traps[0]
        self.assertAlmostEqual(trap.x, 123.)
        self.assertAlmostEqual(trap.y, 456.)
        self.assertAlmostEqual(trap.z, 7.)

    def test_roundtrip_group(self):
        from QHOT.lib.traps.QTrapGroup import QTrapGroup
        grp = QTrapGroup(r=(0., 0., 0.), phase=0.)
        grp.addTrap(QTweezer(r=(10., 10., 0.), phase=0.))
        grp.addTrap(QTweezer(r=(20., 20., 0.), phase=0.))
        self.overlay.addTrap(grp)
        self.overlay.fromList(self.overlay.toList())
        self.assertEqual(len(self.overlay._traps), 2)

    def test_roundtrip_trap_array(self):
        from QHOT.traps.QTrapArray import QTrapArray
        arr = QTrapArray(shape=(3, 2), separation=30., r=(100., 100., 0.))
        self.overlay.addTrap(arr)
        self.overlay.fromList(self.overlay.toList())
        self.assertEqual(len(self.overlay._traps), 6)

    def test_from_list_replaces_existing(self):
        self.overlay.addTrap(QTweezer(r=(1., 1., 0.), phase=0.))
        data = self.overlay.toList()
        for x in (10., 20., 30., 40.):
            self.overlay.addTrap(QTweezer(r=(x, 0., 0.), phase=0.))
        self.overlay.fromList(data)
        self.assertEqual(len(self.overlay._traps), 1)


class TestLockedTrapIgnored(unittest.TestCase):
    '''A locked trap is shown with the static brush (the gestures that it
    ignores are tested with the gestures).'''

    def setUp(self):
        self.overlay = make_overlay()
        self.trap = QTrap(r=(5., 5., 0.), phase=0.)
        self.overlay.addTrap(self.trap)
        self.trap.locked = True

    def test_add_locked_uses_static_brush(self):
        overlay = make_overlay()
        trap = QTrap(r=(3., 3., 0.), phase=0., locked=True)
        overlay.addTrap(trap)
        spot = overlay.points()[0]
        self.assertEqual(
            spot.brush().color(),
            overlay.brush[overlay.State.STATIC].color())


class TestLockedSerialization(unittest.TestCase):

    def test_locked_survives_roundtrip(self):
        overlay = make_overlay()
        overlay.addTrap(QTweezer(r=(2., 3., 0.), locked=True))
        overlay2 = make_overlay()
        overlay2.fromList(overlay.toList())
        self.assertEqual(len(overlay2._traps), 1)
        self.assertTrue(overlay2._traps[0].locked)

    def test_unlocked_not_in_dict(self):
        overlay = make_overlay()
        overlay.addTrap(QTweezer(r=(1., 1., 0.)))
        data = overlay.toList()
        self.assertNotIn('locked', data[0])


class TestMarkerSize(unittest.TestCase):

    '''A marker is as large as the defocus of its trap: bigger with |z|.'''

    def setUp(self):
        self.overlay = QTrapOverlay()
        self.base = self.overlay.opts['size']

    def size(self, trap):
        return self.overlay.points()[trap._index].size()

    def test_a_trap_in_the_focal_plane_has_the_size_of_the_overlay(self):
        trap = QTweezer(r=(50., 60., 0.))
        self.overlay.addTrap(trap)
        self.assertAlmostEqual(self.size(trap), self.base)

    def test_a_trap_at_the_scale_height_is_twice_as_large(self):
        trap = QTweezer(r=(50., 60., self.overlay.ZSCALE))
        self.overlay.addTrap(trap)
        self.assertAlmostEqual(self.size(trap), 2. * self.base)

    def test_above_and_below_the_focal_plane_are_alike(self):
        above = QTweezer(r=(50., 60., 70.))
        below = QTweezer(r=(80., 60., -70.))
        self.overlay.addTrap([above, below])
        self.assertAlmostEqual(self.size(above), self.size(below))

    def test_the_marker_follows_the_z_of_the_trap(self):
        trap = QTweezer(r=(50., 60., 0.))
        self.overlay.addTrap(trap)
        trap.z = self.overlay.ZSCALE
        self.assertAlmostEqual(self.size(trap), 2. * self.base)

    def test_the_markers_of_a_group_follow_a_move_of_the_group(self):
        traps = [QTweezer(r=(50., 60., 0.)), QTweezer(r=(80., 60., 0.))]
        group = QTrapGroup(r=(65., 60., 0.))
        group.addTrap(traps)
        self.overlay.addTrap(group)
        group.r = (65., 60., self.overlay.ZSCALE)
        for trap in traps:
            self.assertAlmostEqual(self.size(trap), 2. * self.base)

    def test_the_markers_are_kept_when_the_spots_are_rebuilt(self):
        gone = QTweezer(r=(20., 30., 0.))
        kept = QTweezer(r=(50., 60., self.overlay.ZSCALE))
        self.overlay.addTrap([gone, kept])
        self.overlay.removeTrap(gone)
        self.assertAlmostEqual(self.size(kept), 2. * self.base)


class TestMarkedGroups(unittest.TestCase):

    def setUp(self):
        self.overlay = make_overlay()

    def test_none_at_first(self):
        self.assertEqual(self.overlay.markedGroups, [])

    def test_a_single_trap(self):
        trap = QTrap(r=(1., 1., 0.), phase=0.)
        self.overlay.addTrap(trap)
        self.overlay.mark(trap)
        self.assertEqual(self.overlay.markedGroups, [trap])

    def test_a_group_is_marked_as_a_whole(self):
        g = QTrapGroup()
        t1 = QTrap(r=(1., 1., 0.), phase=0.)
        t2 = QTrap(r=(2., 2., 0.), phase=0.)
        g.addTrap([t1, t2])
        self.overlay.addTrap(g)
        self.overlay.mark(g)
        self.assertEqual(self.overlay.markedGroups, [g])

    def test_unmarked_traps_are_not_in_it(self):
        t1 = QTrap(r=(1., 1., 0.), phase=0.)
        t2 = QTrap(r=(2., 2., 0.), phase=0.)
        self.overlay.addTrap([t1, t2])
        self.overlay.mark(t1)
        self.assertEqual(self.overlay.markedGroups, [t1])


class TestAMarkedGroupStaysMarkedInTheEyesOfTheUser(unittest.TestCase):

    '''A marked group is blue at rest.  Dragging it, rotating it, enclosing
    it in a rubber band, removing another trap and locking it do not make it
    look like a group that is not marked: the user would think that a task
    skips it, and ``selected_only`` would move it.'''

    def setUp(self):
        self.overlay = make_overlay()
        self.state = self.overlay.State
        self.t1 = QTrap(r=(3., 3., 0.), phase=0.)
        self.t2 = QTrap(r=(30., 30., 0.), phase=0.)
        self.overlay.addTrap(self.t1)
        self.overlay.addTrap(self.t2)
        self.overlay.mark(self.t1)

    def shows(self, trap, state):
        return (self.overlay.points()[trap._index].brush()
                == self.overlay.brush[state])

    def test_a_mark_and_an_active_group_are_not_alike(self):
        brush = self.overlay.brush
        self.assertNotEqual(brush[self.state.MARKED].color().getRgb()[:3],
                            brush[self.state.ACTIVE].color().getRgb()[:3])

    def test_marked(self):
        self.assertTrue(self.shows(self.t1, self.state.MARKED))

    def test_while_it_is_dragged_it_is_active(self):
        with patch.object(self.overlay, 'trapAt', return_value=self.t1):
            self.overlay.gestures.grab(QtCore.QPointF(3., 3.))
        self.assertTrue(self.shows(self.t1, self.state.ACTIVE))

    def test_after_a_drag(self):
        self.overlay.setGroupBrush(self.t1, self.state.ACTIVE)
        self.overlay.gestures.dragged = self.t1
        self.overlay.gestures.release(None)
        self.assertTrue(self.shows(self.t1, self.state.MARKED))

    def test_after_a_rubber_band_that_does_not_group_it(self):
        gestures = self.overlay.gestures
        gestures.startSelection(QtCore.QPointF(0., 0.))
        gestures.growSelection(QtCore.QPointF(5., 5.))
        self.assertTrue(self.shows(self.t2, self.state.NORMAL))
        gestures.endSelection()
        self.assertTrue(self.shows(self.t1, self.state.MARKED))

    def test_while_a_rubber_band_encloses_it_it_shows_the_grouping(self):
        gestures = self.overlay.gestures
        gestures.startSelection(QtCore.QPointF(0., 0.))
        gestures.growSelection(QtCore.QPointF(5., 5.))
        self.assertTrue(self.shows(self.t1, self.state.GROUPING))

    def test_after_another_trap_is_removed(self):
        self.overlay.removeTrap(self.t2)
        self.assertTrue(self.shows(self.t1, self.state.MARKED))

    def test_a_trap_that_is_added_is_not_marked(self):
        t3 = QTrap(r=(60., 60., 0.), phase=0.)
        self.overlay.addTrap(t3)
        self.assertTrue(self.shows(t3, self.state.NORMAL))
        self.assertTrue(self.shows(self.t1, self.state.MARKED))

    def test_locking_a_marked_group_keeps_it_marked(self):
        self.t1.locked = True
        self.overlay.rest(self.t1)
        self.assertTrue(self.shows(self.t1, self.state.MARKED))

    def test_unmarking_a_locked_group_shows_that_it_is_locked(self):
        self.t1.locked = True
        self.overlay.unmark(self.t1)
        self.assertTrue(self.shows(self.t1, self.state.STATIC))

    def test_unmarking_shows_the_normal_color(self):
        self.overlay.unmark(self.t1)
        self.assertTrue(self.shows(self.t1, self.state.NORMAL))


class TestClearingTheTrapsClearsTheMarks(unittest.TestCase):

    '''A task that moves the marked groups must not find traps that are gone
    (clearing, and loading a file, which clears first).'''

    def setUp(self):
        self.overlay = make_overlay()
        self.trap = QTrap(r=(1., 1., 0.), phase=0.)
        self.overlay.addTrap(self.trap)
        self.overlay.mark(self.trap)

    def test_clear_traps(self):
        self.overlay.clearTraps()
        self.assertEqual(self.overlay.markedGroups, [])

    def test_load_traps(self):
        self.overlay.fromList([])
        self.assertEqual(self.overlay.markedGroups, [])

    def test_a_trap_that_comes_after_is_not_marked(self):
        self.overlay.clearTraps()
        self.overlay.addTrap(self.trap)
        self.assertEqual(self.overlay.markedGroups, [])


class TestRemovingATrapClearsItsMark(unittest.TestCase):

    def setUp(self):
        self.overlay = make_overlay()
        self.t1 = QTrap(r=(1., 1., 0.), phase=0.)
        self.t2 = QTrap(r=(2., 2., 0.), phase=0.)
        self.overlay.addTrap(self.t1)
        self.overlay.addTrap(self.t2)

    def test_remove_trap_clears_from_marked(self):
        self.overlay.mark(self.t1)
        self.overlay.removeTrap(self.t1)
        self.assertEqual(self.overlay.markedGroups, [])


if __name__ == '__main__':
    unittest.main()
