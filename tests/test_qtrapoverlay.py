'''Unit tests for QTrapOverlay.'''
import unittest
import numpy as np
from unittest.mock import MagicMock, patch
from pyqtgraph.Qt import QtCore, QtWidgets, QtTest
from QFab.lib.traps.QTrap import QTrap
from QFab.lib.traps.QTrapGroup import QTrapGroup
from QFab.lib.traps.QTrapOverlay import QTrapOverlay
from QFab.traps.QTweezer import QTweezer


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
        self.overlay._setGroupBrush(self.overlay._traps[0].parent(),
                                    self.overlay.State.SELECTED)
        for trap in [self.t1, self.t2]:
            spot = self.overlay.points()[trap._index]
            self.assertEqual(spot.brush(),
                             self.overlay.brush[self.overlay.State.SELECTED])

    def test_resets_to_normal(self):
        self.overlay._setGroupBrush(self.overlay._traps[0].parent(),
                                    self.overlay.State.SELECTED)
        self.overlay._setGroupBrush(self.overlay._traps[0].parent(),
                                    self.overlay.State.NORMAL)
        for trap in [self.t1, self.t2]:
            spot = self.overlay.points()[trap._index]
            self.assertEqual(spot.brush(),
                             self.overlay.brush[self.overlay.State.NORMAL])


class TestFinalizeSelection(unittest.TestCase):

    def setUp(self):
        self.overlay = make_overlay()
        self.rect = QtCore.QRectF(0., 0., 10., 10.)

    def test_groups_two_traps_inside_rect(self):
        self.overlay.addTrap([QTrap(r=(3., 3., 0.), phase=0.),
                              QTrap(r=(7., 7., 0.), phase=0.)])
        self.overlay._finalizeSelection(self.rect)
        top_items = list(self.overlay)
        self.assertEqual(len(top_items), 1)
        self.assertIsInstance(top_items[0], QTrapGroup)

    def test_new_group_is_child_of_overlay(self):
        self.overlay.addTrap([QTrap(r=(3., 3., 0.), phase=0.),
                              QTrap(r=(7., 7., 0.), phase=0.)])
        self.overlay._finalizeSelection(self.rect)
        grp = list(self.overlay)[0]
        self.assertIs(grp.parent(), self.overlay)

    def test_fewer_than_two_no_group_created(self):
        self.overlay.addTrap(QTrap(r=(3., 3., 0.), phase=0.))
        self.overlay._finalizeSelection(self.rect)
        self.assertNotIsInstance(list(self.overlay)[0], QTrapGroup)

    def test_outside_trap_excluded(self):
        t_in = QTrap(r=(3., 3., 0.), phase=0.)
        t_out = QTrap(r=(15., 5., 0.), phase=0.)
        self.overlay.addTrap([t_in, t_out])
        self.overlay._finalizeSelection(self.rect)
        # only 1 inside → no group; both items remain top-level
        self.assertEqual(len(list(self.overlay)), 2)

    def test_straddling_group_excluded(self):
        t_inside = QTrap(r=(3., 3., 0.), phase=0.)
        t_outside = QTrap(r=(15., 3., 0.), phase=0.)
        straddler = QTrapGroup(r=(9., 3., 0.))
        straddler.addTrap([t_inside, t_outside])
        lone = QTrap(r=(5., 5., 0.), phase=0.)
        self.overlay.addTrap(straddler)
        self.overlay.addTrap(lone)
        self.overlay._finalizeSelection(self.rect)
        # straddler is not fully inside → no new group
        self.assertEqual(len(list(self.overlay)), 2)

    def test_centroid_of_new_group(self):
        self.overlay.addTrap([QTrap(r=(2., 2., 0.), phase=0.),
                              QTrap(r=(8., 8., 0.), phase=0.)])
        self.overlay._finalizeSelection(self.rect)
        grp = list(self.overlay)[0]
        np.testing.assert_array_almost_equal(grp._r, [5., 5., 0.])


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


class TestAddTrapFromPosition(unittest.TestCase):

    def test_creates_trap_at_position(self):
        overlay = make_overlay()
        overlay.addTrap(QtCore.QPointF(3., 7.))
        self.assertEqual(len(overlay._traps), 1)

    def test_trap_is_tweezer(self):
        overlay = make_overlay()
        overlay.addTrap(QtCore.QPointF(1., 1.))
        self.assertIsInstance(overlay._traps[0], QTweezer)

    def test_tweezer_position_matches(self):
        overlay = make_overlay()
        overlay.addTrap(QtCore.QPointF(3., 7.))
        trap = overlay._traps[0]
        self.assertAlmostEqual(trap.x, 3.)
        self.assertAlmostEqual(trap.y, 7.)

    def test_returns_true(self):
        overlay = make_overlay()
        self.assertTrue(overlay.addTrap(QtCore.QPointF(1., 1.)))


class TestRemoveTrapFromPosition(unittest.TestCase):

    def setUp(self):
        self.overlay = make_overlay()
        self.trap = QTrap(r=(5., 5., 0.), phase=0.)
        self.overlay.addTrap(self.trap)

    def test_removes_nearest_trap(self):
        spot = self.overlay.points()[0]
        with patch.object(self.overlay, 'pointsAt', return_value=[spot]):
            self.overlay.removeTrap(QtCore.QPointF(5., 5.))
        self.assertNotIn(self.trap, self.overlay._traps)

    def test_returns_true_when_trap_found(self):
        spot = self.overlay.points()[0]
        with patch.object(self.overlay, 'pointsAt', return_value=[spot]):
            result = self.overlay.removeTrap(QtCore.QPointF(5., 5.))
        self.assertTrue(result)

    def test_returns_false_when_no_trap(self):
        with patch.object(self.overlay, 'pointsAt', return_value=[]):
            result = self.overlay.removeTrap(QtCore.QPointF(99., 99.))
        self.assertFalse(result)


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


class TestTrapsIn(unittest.TestCase):

    def setUp(self):
        self.overlay = make_overlay()
        self.t1 = QTrap(r=(2., 2., 0.), phase=0.)
        self.t2 = QTrap(r=(7., 7., 0.), phase=0.)
        self.overlay.addTrap([self.t1, self.t2])

    def test_returns_traps_in_rect(self):
        spots = list(self.overlay.points())
        with patch.object(self.overlay, 'pointsAt', return_value=spots):
            result = self.overlay.trapsIn(QtCore.QRectF(0., 0., 10., 10.))
        self.assertIn(self.t1, result)
        self.assertIn(self.t2, result)

    def test_returns_empty_when_none_in_rect(self):
        with patch.object(self.overlay, 'pointsAt', return_value=[]):
            result = self.overlay.trapsIn(QtCore.QRectF(50., 50., 10., 10.))
        self.assertEqual(result, [])


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


class TestFinalizeSelectionSignals(unittest.TestCase):

    def setUp(self):
        self.overlay = QTrapOverlay()
        self.t1 = QTrap(r=(2., 2., 0.), phase=0.)
        self.t2 = QTrap(r=(8., 8., 0.), phase=0.)
        self.overlay.addTrap([self.t1, self.t2])
        self.rect = QtCore.QRectF(0., 0., 10., 10.)

    def test_emits_trap_removed_for_each_candidate(self):
        spy = QtTest.QSignalSpy(self.overlay.trapRemoved)
        self.overlay._finalizeSelection(self.rect)
        self.assertEqual(len(spy), 2)

    def test_trap_removed_carries_individual_traps(self):
        spy = QtTest.QSignalSpy(self.overlay.trapRemoved)
        self.overlay._finalizeSelection(self.rect)
        self.assertEqual({spy[0][0], spy[1][0]}, {self.t1, self.t2})

    def test_emits_trap_added_once_for_new_group(self):
        spy = QtTest.QSignalSpy(self.overlay.trapAdded)
        self.overlay._finalizeSelection(self.rect)
        self.assertEqual(len(spy), 1)

    def test_trap_added_carries_new_group(self):
        spy = QtTest.QSignalSpy(self.overlay.trapAdded)
        self.overlay._finalizeSelection(self.rect)
        self.assertIsInstance(spy[0][0], QTrapGroup)

    def test_no_signals_when_fewer_than_two_candidates(self):
        overlay = QTrapOverlay()
        overlay.addTrap(QTrap(r=(3., 3., 0.), phase=0.))
        spy_removed = QtTest.QSignalSpy(overlay.trapRemoved)
        spy_added = QtTest.QSignalSpy(overlay.trapAdded)
        overlay._finalizeSelection(self.rect)
        self.assertEqual(len(spy_removed), 0)
        self.assertEqual(len(spy_added), 0)


class TestBreakGroup(unittest.TestCase):

    def test_returns_false_when_no_trap(self):
        overlay = make_overlay()
        with patch.object(overlay, 'trapAt', return_value=None):
            self.assertFalse(overlay.breakGroup(QtCore.QPointF(0., 0.)))

    def test_returns_false_for_ungrouped_trap(self):
        overlay = make_overlay()
        trap = QTrap(r=(1., 1., 0.), phase=0.)
        overlay.addTrap(trap)
        with patch.object(overlay, 'trapAt', return_value=trap):
            self.assertFalse(overlay.breakGroup(QtCore.QPointF(1., 1.)))

    def test_detaches_leaf_from_group(self):
        overlay = make_overlay()
        t1 = QTrap(r=(1., 1., 0.), phase=0.)
        t2 = QTrap(r=(2., 2., 0.), phase=0.)
        grp = QTrapGroup(r=(1.5, 1.5, 0.))
        grp.addTrap([t1, t2])
        overlay.addTrap(grp)
        with patch.object(overlay, 'trapAt', return_value=t1):
            result = overlay.breakGroup(QtCore.QPointF(1., 1.))
        self.assertTrue(result)
        self.assertIs(t1.parent(), overlay)

    def test_empty_group_detached_after_last_leaf_broken(self):
        overlay = make_overlay()
        t1 = QTrap(r=(1., 1., 0.), phase=0.)
        t2 = QTrap(r=(2., 2., 0.), phase=0.)
        grp = QTrapGroup(r=(1.5, 1.5, 0.))
        grp.addTrap([t1, t2])
        overlay.addTrap(grp)
        with patch.object(overlay, 'trapAt', return_value=t1):
            overlay.breakGroup(QtCore.QPointF(1., 1.))
        with patch.object(overlay, 'trapAt', return_value=t2):
            overlay.breakGroup(QtCore.QPointF(2., 2.))
        self.assertIsNone(grp.parent())

    def test_detaches_subgroup_from_nested_group(self):
        overlay = make_overlay()
        inner_t1 = QTrap(r=(1., 1., 0.), phase=0.)
        inner_t2 = QTrap(r=(2., 2., 0.), phase=0.)
        inner_grp = QTrapGroup(r=(1.5, 1.5, 0.))
        inner_grp.addTrap([inner_t1, inner_t2])
        singleton = QTrap(r=(5., 5., 0.), phase=0.)
        outer_grp = QTrapGroup(r=(3., 3., 0.))
        outer_grp.addTrap([inner_grp, singleton])
        overlay.addTrap(outer_grp)
        with patch.object(overlay, 'trapAt', return_value=inner_t1):
            result = overlay.breakGroup(QtCore.QPointF(1., 1.))
        self.assertTrue(result)
        self.assertIs(inner_grp.parent(), overlay)

    def test_empty_outer_group_detached_after_subgroup_broken(self):
        '''Breaking the only subgroup from a nested group removes the outer.'''
        overlay = make_overlay()
        inner_t1 = QTrap(r=(1., 1., 0.), phase=0.)
        inner_grp = QTrapGroup(r=(1., 1., 0.))
        inner_grp.addTrap(inner_t1)
        outer_grp = QTrapGroup(r=(1., 1., 0.))
        outer_grp.addTrap(inner_grp)
        overlay.addTrap(outer_grp)
        with patch.object(overlay, 'trapAt', return_value=inner_t1):
            overlay.breakGroup(QtCore.QPointF(1., 1.))
        self.assertIsNone(outer_grp.parent())

    def test_emits_trap_added_for_detached_leaf(self):
        overlay = make_overlay()
        t1 = QTrap(r=(1., 1., 0.), phase=0.)
        t2 = QTrap(r=(2., 2., 0.), phase=0.)
        grp = QTrapGroup(r=(1.5, 1.5, 0.))
        grp.addTrap([t1, t2])
        overlay.addTrap(grp)
        spy = QtTest.QSignalSpy(overlay.trapAdded)
        with patch.object(overlay, 'trapAt', return_value=t1):
            overlay.breakGroup(QtCore.QPointF(1., 1.))
        self.assertEqual(len(spy), 1)
        self.assertIs(spy[0][0], t1)

    def test_emits_trap_removed_when_group_becomes_empty(self):
        overlay = make_overlay()
        t1 = QTrap(r=(1., 1., 0.), phase=0.)
        t2 = QTrap(r=(2., 2., 0.), phase=0.)
        grp = QTrapGroup(r=(1.5, 1.5, 0.))
        grp.addTrap([t1, t2])
        overlay.addTrap(grp)
        with patch.object(overlay, 'trapAt', return_value=t1):
            overlay.breakGroup(QtCore.QPointF(1., 1.))
        spy = QtTest.QSignalSpy(overlay.trapRemoved)
        with patch.object(overlay, 'trapAt', return_value=t2):
            overlay.breakGroup(QtCore.QPointF(2., 2.))
        self.assertEqual(len(spy), 1)
        self.assertIs(spy[0][0], grp)

    def test_no_trap_removed_when_group_still_has_members(self):
        overlay = make_overlay()
        t1 = QTrap(r=(1., 1., 0.), phase=0.)
        t2 = QTrap(r=(2., 2., 0.), phase=0.)
        grp = QTrapGroup(r=(1.5, 1.5, 0.))
        grp.addTrap([t1, t2])
        overlay.addTrap(grp)
        spy = QtTest.QSignalSpy(overlay.trapRemoved)
        with patch.object(overlay, 'trapAt', return_value=t1):
            overlay.breakGroup(QtCore.QPointF(1., 1.))
        self.assertEqual(len(spy), 0)

    def test_nested_emits_trap_removed_for_outer(self):
        overlay = make_overlay()
        inner_t1 = QTrap(r=(1., 1., 0.), phase=0.)
        inner_grp = QTrapGroup(r=(1., 1., 0.))
        inner_grp.addTrap([inner_t1, QTrap(r=(2., 2., 0.), phase=0.)])
        outer_grp = QTrapGroup(r=(3., 3., 0.))
        outer_grp.addTrap([inner_grp, QTrap(r=(5., 5., 0.), phase=0.)])
        overlay.addTrap(outer_grp)
        spy = QtTest.QSignalSpy(overlay.trapRemoved)
        with patch.object(overlay, 'trapAt', return_value=inner_t1):
            overlay.breakGroup(QtCore.QPointF(1., 1.))
        self.assertEqual(len(spy), 1)
        self.assertIs(spy[0][0], outer_grp)

    def test_nested_emits_trap_added_for_outer_and_subgroup(self):
        overlay = make_overlay()
        inner_t1 = QTrap(r=(1., 1., 0.), phase=0.)
        inner_grp = QTrapGroup(r=(1., 1., 0.))
        inner_grp.addTrap([inner_t1, QTrap(r=(2., 2., 0.), phase=0.)])
        outer_grp = QTrapGroup(r=(3., 3., 0.))
        outer_grp.addTrap([inner_grp, QTrap(r=(5., 5., 0.), phase=0.)])
        overlay.addTrap(outer_grp)
        spy = QtTest.QSignalSpy(overlay.trapAdded)
        with patch.object(overlay, 'trapAt', return_value=inner_t1):
            overlay.breakGroup(QtCore.QPointF(1., 1.))
        added = {spy[i][0] for i in range(len(spy))}
        self.assertIn(outer_grp, added)
        self.assertIn(inner_grp, added)


class TestSelectGroup(unittest.TestCase):

    def test_returns_false_when_no_trap(self):
        overlay = make_overlay()
        with patch.object(overlay, 'pointsAt', return_value=[]):
            self.assertFalse(overlay.selectGroup(QtCore.QPointF(0., 0.)))

    def test_returns_true_when_trap_found(self):
        overlay = make_overlay()
        trap = QTrap(r=(5., 5., 0.), phase=0.)
        overlay.addTrap(trap)
        spot = overlay.points()[0]
        with patch.object(overlay, 'pointsAt', return_value=[spot]):
            self.assertTrue(overlay.selectGroup(QtCore.QPointF(5., 5.)))

    def test_selected_is_set(self):
        overlay = make_overlay()
        trap = QTrap(r=(5., 5., 0.), phase=0.)
        overlay.addTrap(trap)
        spot = overlay.points()[0]
        with patch.object(overlay, 'pointsAt', return_value=[spot]):
            overlay.selectGroup(QtCore.QPointF(5., 5.))
        self.assertIs(overlay._selected, trap)

    def test_brush_changes_to_selected(self):
        overlay = make_overlay()
        trap = QTrap(r=(5., 5., 0.), phase=0.)
        overlay.addTrap(trap)
        spot = overlay.points()[0]
        with patch.object(overlay, 'pointsAt', return_value=[spot]):
            overlay.selectGroup(QtCore.QPointF(5., 5.))
        self.assertEqual(overlay.points()[0].brush(),
                         overlay.brush[overlay.State.SELECTED])


class TestRubberBandSelection(unittest.TestCase):

    def setUp(self):
        self.overlay = make_overlay()

    def test_start_selection_sets_origin(self):
        pos = QtCore.QPointF(5., 5.)
        self.overlay.startSelection(pos)
        self.assertEqual(self.overlay._selection_origin, pos)

    def test_start_selection_shows_rect(self):
        self.overlay.startSelection(QtCore.QPointF(2., 2.))
        self.assertTrue(self.overlay._selection.isVisible())

    def test_grow_selection_updates_rect(self):
        self.overlay.startSelection(QtCore.QPointF(0., 0.))
        self.overlay.growSelection(QtCore.QPointF(5., 5.))
        rect = self.overlay._selection.rect()
        self.assertAlmostEqual(rect.width(), 5.)
        self.assertAlmostEqual(rect.height(), 5.)

    def test_grow_selection_highlights_traps_inside(self):
        trap = QTrap(r=(3., 3., 0.), phase=0.)
        self.overlay.addTrap(trap)
        self.overlay.startSelection(QtCore.QPointF(0., 0.))
        self.overlay.growSelection(QtCore.QPointF(10., 10.))
        self.assertEqual(self.overlay.points()[0].brush(),
                         self.overlay.brush[self.overlay.State.GROUPING])

    def test_end_selection_hides_rect(self):
        self.overlay.startSelection(QtCore.QPointF(0., 0.))
        self.overlay.growSelection(QtCore.QPointF(5., 5.))
        self.overlay.endSelection()
        self.assertFalse(self.overlay._selection.isVisible())

    def test_end_selection_clears_origin(self):
        self.overlay.startSelection(QtCore.QPointF(0., 0.))
        self.overlay.endSelection()
        self.assertIsNone(self.overlay._selection_origin)

    def test_end_selection_resets_brushes(self):
        trap = QTrap(r=(3., 3., 0.), phase=0.)
        self.overlay.addTrap(trap)
        self.overlay.startSelection(QtCore.QPointF(0., 0.))
        self.overlay.growSelection(QtCore.QPointF(10., 10.))
        self.overlay.endSelection()
        self.assertEqual(self.overlay.points()[0].brush(),
                         self.overlay.brush[self.overlay.State.NORMAL])


class TestMousePressEvent(unittest.TestCase):
    '''Tests for the QGraphicsItem standalone event path.'''

    def _make_event(self, button, modifiers, pos):
        event = MagicMock()
        event.button.return_value = button
        event.modifiers.return_value = modifiers
        event.pos.return_value = pos
        return event

    def test_shift_left_creates_trap_and_sets_drag_last(self):
        overlay = make_overlay()
        pos = QtCore.QPointF(5., 5.)
        event = self._make_event(QtCore.Qt.MouseButton.LeftButton,
                                 QtCore.Qt.KeyboardModifier.ShiftModifier,
                                 pos)
        overlay.mousePressEvent(event)
        self.assertEqual(len(overlay._traps), 1)
        self.assertEqual(overlay._drag_last, pos)

    def test_left_no_trap_starts_selection(self):
        overlay = make_overlay()
        pos = QtCore.QPointF(5., 5.)
        event = self._make_event(QtCore.Qt.MouseButton.LeftButton,
                                 QtCore.Qt.KeyboardModifier.NoModifier,
                                 pos)
        overlay.mousePressEvent(event)
        self.assertTrue(overlay._selection.isVisible())

    def test_event_accepted(self):
        overlay = make_overlay()
        pos = QtCore.QPointF(5., 5.)
        event = self._make_event(QtCore.Qt.MouseButton.LeftButton,
                                 QtCore.Qt.KeyboardModifier.NoModifier,
                                 pos)
        overlay.mousePressEvent(event)
        event.accept.assert_called_once()


class TestMouseMoveEvent(unittest.TestCase):
    '''Tests for the QGraphicsItem standalone event path.'''

    def _make_event(self, pos):
        event = MagicMock()
        event.pos.return_value = pos
        return event

    def test_moves_selected_group(self):
        overlay = make_overlay()
        trap = QTrap(r=(5., 5., 0.), phase=0.)
        overlay.addTrap(trap)
        overlay._selected = trap
        overlay._drag_last = QtCore.QPointF(5., 5.)
        overlay.mouseMoveEvent(self._make_event(QtCore.QPointF(8., 9.)))
        self.assertAlmostEqual(trap.x, 8.)
        self.assertAlmostEqual(trap.y, 9.)

    def test_updates_drag_last(self):
        overlay = make_overlay()
        trap = QTrap(r=(5., 5., 0.), phase=0.)
        overlay.addTrap(trap)
        overlay._selected = trap
        overlay._drag_last = QtCore.QPointF(5., 5.)
        new_pos = QtCore.QPointF(8., 9.)
        overlay.mouseMoveEvent(self._make_event(new_pos))
        self.assertEqual(overlay._drag_last, new_pos)

    def test_grows_selection_when_active(self):
        overlay = make_overlay()
        overlay.startSelection(QtCore.QPointF(0., 0.))
        pos = QtCore.QPointF(5., 5.)
        with patch.object(overlay, 'growSelection') as mock_grow:
            overlay.mouseMoveEvent(self._make_event(pos))
        mock_grow.assert_called_once_with(pos)

    def test_event_accepted(self):
        overlay = make_overlay()
        event = self._make_event(QtCore.QPointF(0., 0.))
        overlay.mouseMoveEvent(event)
        event.accept.assert_called_once()


class TestMouseReleaseEvent(unittest.TestCase):
    '''Tests for the QGraphicsItem standalone event path.'''

    def _make_event(self):
        return MagicMock()

    def test_ends_selection_when_active(self):
        overlay = make_overlay()
        overlay.startSelection(QtCore.QPointF(0., 0.))
        with patch.object(overlay, 'endSelection') as mock_end:
            overlay.mouseReleaseEvent(self._make_event())
        mock_end.assert_called_once()

    def test_clears_selected(self):
        overlay = make_overlay()
        trap = QTrap(r=(5., 5., 0.), phase=0.)
        overlay.addTrap(trap)
        overlay._selected = trap
        overlay.mouseReleaseEvent(self._make_event())
        self.assertIsNone(overlay._selected)

    def test_clears_drag_last(self):
        overlay = make_overlay()
        overlay._drag_last = QtCore.QPointF(1., 1.)
        overlay.mouseReleaseEvent(self._make_event())
        self.assertIsNone(overlay._drag_last)

    def test_resets_selected_brush(self):
        overlay = make_overlay()
        trap = QTrap(r=(5., 5., 0.), phase=0.)
        overlay.addTrap(trap)
        overlay._selected = trap
        overlay._setGroupBrush(trap, overlay.State.SELECTED)
        overlay.mouseReleaseEvent(self._make_event())
        self.assertEqual(overlay.points()[0].brush(),
                         overlay.brush[overlay.State.NORMAL])

    def test_event_accepted(self):
        overlay = make_overlay()
        event = self._make_event()
        overlay.mouseReleaseEvent(event)
        event.accept.assert_called_once()


class TestMousePress(unittest.TestCase):
    '''Tests for the QFabScreen hosted event path.'''

    def _make_event(self, buttons, modifiers):
        event = MagicMock()
        event.buttons.return_value = buttons
        event.modifiers.return_value = modifiers
        return event

    def test_returns_true(self):
        overlay = make_overlay()
        event = self._make_event(QtCore.Qt.MouseButton.LeftButton,
                                 QtCore.Qt.KeyboardModifier.NoModifier)
        with patch.object(overlay, 'selectGroup', return_value=False):
            result = overlay.mousePress(event, QtCore.QPointF(0., 0.))
        self.assertTrue(result)

    def test_shift_left_creates_trap_and_sets_drag_last(self):
        overlay = make_overlay()
        pos = QtCore.QPointF(5., 5.)
        event = self._make_event(QtCore.Qt.MouseButton.LeftButton,
                                 QtCore.Qt.KeyboardModifier.ShiftModifier)
        overlay.mousePress(event, pos)
        self.assertEqual(len(overlay._traps), 1)
        self.assertEqual(overlay._drag_last, pos)

    def test_left_no_trap_starts_selection(self):
        overlay = make_overlay()
        pos = QtCore.QPointF(5., 5.)
        event = self._make_event(QtCore.Qt.MouseButton.LeftButton,
                                 QtCore.Qt.KeyboardModifier.NoModifier)
        with patch.object(overlay, 'selectGroup', return_value=False):
            overlay.mousePress(event, pos)
        self.assertTrue(overlay._selection.isVisible())


class TestMouseMove(unittest.TestCase):
    '''Tests for the QFabScreen hosted event path.'''

    def _make_event(self, buttons):
        event = MagicMock()
        event.buttons.return_value = buttons
        return event

    def test_returns_false_for_non_left_button(self):
        overlay = make_overlay()
        event = self._make_event(QtCore.Qt.MouseButton.RightButton)
        self.assertFalse(overlay.mouseMove(event, QtCore.QPointF(0., 0.)))

    def test_moves_selected_group_on_left_drag(self):
        overlay = make_overlay()
        trap = QTrap(r=(5., 5., 0.), phase=0.)
        overlay.addTrap(trap)
        overlay._selected = trap
        overlay._drag_last = QtCore.QPointF(5., 5.)
        event = self._make_event(QtCore.Qt.MouseButton.LeftButton)
        overlay.mouseMove(event, QtCore.QPointF(8., 9.))
        self.assertAlmostEqual(trap.x, 8.)
        self.assertAlmostEqual(trap.y, 9.)

    def test_returns_true_on_left_drag(self):
        overlay = make_overlay()
        trap = QTrap(r=(5., 5., 0.), phase=0.)
        overlay.addTrap(trap)
        overlay._selected = trap
        overlay._drag_last = QtCore.QPointF(5., 5.)
        event = self._make_event(QtCore.Qt.MouseButton.LeftButton)
        self.assertTrue(overlay.mouseMove(event, QtCore.QPointF(6., 6.)))

    def test_grows_selection_when_active(self):
        overlay = make_overlay()
        overlay.startSelection(QtCore.QPointF(0., 0.))
        pos = QtCore.QPointF(5., 5.)
        event = self._make_event(QtCore.Qt.MouseButton.LeftButton)
        with patch.object(overlay, 'growSelection') as mock_grow:
            overlay.mouseMove(event, pos)
        mock_grow.assert_called_once_with(pos)


class TestMouseRelease(unittest.TestCase):
    '''Tests for the QFabScreen hosted event path.'''

    def _make_event(self):
        return MagicMock()

    def test_returns_true(self):
        overlay = make_overlay()
        self.assertTrue(overlay.mouseRelease(self._make_event()))

    def test_ends_selection_when_active(self):
        overlay = make_overlay()
        overlay.startSelection(QtCore.QPointF(0., 0.))
        with patch.object(overlay, 'endSelection') as mock_end:
            overlay.mouseRelease(self._make_event())
        mock_end.assert_called_once()

    def test_clears_selected(self):
        overlay = make_overlay()
        trap = QTrap(r=(5., 5., 0.), phase=0.)
        overlay.addTrap(trap)
        overlay._selected = trap
        overlay.mouseRelease(self._make_event())
        self.assertIsNone(overlay._selected)

    def test_clears_drag_last(self):
        overlay = make_overlay()
        overlay._drag_last = QtCore.QPointF(1., 1.)
        overlay.mouseRelease(self._make_event())
        self.assertIsNone(overlay._drag_last)

    def test_resets_selected_brush(self):
        overlay = make_overlay()
        trap = QTrap(r=(5., 5., 0.), phase=0.)
        overlay.addTrap(trap)
        overlay._selected = trap
        overlay._setGroupBrush(trap, overlay.State.SELECTED)
        overlay.mouseRelease(self._make_event())
        self.assertEqual(overlay.points()[0].brush(),
                         overlay.brush[overlay.State.NORMAL])


class TestWheel(unittest.TestCase):

    def _make_event(self, delta_y):
        event = MagicMock()
        event.angleDelta.return_value = QtCore.QPoint(0, delta_y)
        return event

    def test_returns_false_when_no_trap(self):
        overlay = make_overlay()
        with patch.object(overlay, 'groupAt', return_value=None):
            self.assertFalse(overlay.wheel(self._make_event(120),
                                           QtCore.QPointF(0., 0.)))

    def test_returns_true_when_trap_found(self):
        overlay = make_overlay()
        trap = QTrap(r=(5., 5., 0.), phase=0.)
        overlay.addTrap(trap)
        with patch.object(overlay, 'groupAt', return_value=trap):
            self.assertTrue(overlay.wheel(self._make_event(120),
                                          QtCore.QPointF(5., 5.)))

    def test_adjusts_z_by_one_notch_up(self):
        overlay = make_overlay()
        trap = QTrap(r=(5., 5., 10.), phase=0.)
        overlay.addTrap(trap)
        with patch.object(overlay, 'groupAt', return_value=trap):
            overlay.wheel(self._make_event(120), QtCore.QPointF(5., 5.))
        self.assertAlmostEqual(trap.z, 11.)

    def test_adjusts_z_by_one_notch_down(self):
        overlay = make_overlay()
        trap = QTrap(r=(5., 5., 10.), phase=0.)
        overlay.addTrap(trap)
        with patch.object(overlay, 'groupAt', return_value=trap):
            overlay.wheel(self._make_event(-120), QtCore.QPointF(5., 5.))
        self.assertAlmostEqual(trap.z, 9.)


if __name__ == '__main__':
    unittest.main()
