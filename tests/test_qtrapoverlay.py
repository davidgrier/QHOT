'''Unit tests for QTrapOverlay.'''
import unittest
import numpy as np
from pyqtgraph.Qt import QtCore, QtWidgets, QtTest
from QFab.lib.traps.QTrap import QTrap
from QFab.lib.traps.QTrapGroup import QTrapGroup
from QFab.lib.traps.QTrapOverlay import QTrapOverlay


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


if __name__ == '__main__':
    unittest.main()
