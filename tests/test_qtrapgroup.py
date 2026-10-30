'''Unit tests for QTrapGroup.'''
import unittest
import numpy as np
from pyqtgraph.Qt import QtCore, QtWidgets, QtTest
from QHOT.lib.traps.QTrap import QTrap
from QHOT.lib.traps.QTrapGroup import QTrapGroup

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class TestAddTrap(unittest.TestCase):

    def setUp(self):
        self.group = QTrapGroup(r=(0., 0., 0.))

    def test_single_sets_parent(self):
        trap = QTrap(phase=0.)
        self.group.addTrap(trap)
        self.assertIs(trap.parent(), self.group)

    def test_single_increments_len(self):
        self.group.addTrap(QTrap(phase=0.))
        self.assertEqual(len(self.group), 1)

    def test_list_sets_parents(self):
        traps = [QTrap(phase=0.) for _ in range(3)]
        self.group.addTrap(traps)
        self.assertTrue(all(t.parent() is self.group for t in traps))

    def test_list_increments_len(self):
        traps = [QTrap(phase=0.) for _ in range(3)]
        self.group.addTrap(traps)
        self.assertEqual(len(self.group), 3)

    def test_iter_after_add(self):
        trap = QTrap(phase=0.)
        self.group.addTrap(trap)
        self.assertEqual(list(self.group), [trap])


class TestRemoveTrap(unittest.TestCase):

    def setUp(self):
        self.group = QTrapGroup(r=(0., 0., 0.))

    def test_removes_child(self):
        trap = QTrap(phase=0.)
        self.group.addTrap(trap)
        self.group.removeTrap(trap)
        self.assertEqual(len(self.group), 0)

    def test_clears_parent(self):
        trap = QTrap(phase=0.)
        self.group.addTrap(trap)
        self.group.removeTrap(trap)
        self.assertIsNot(trap.parent(), self.group)

    def test_noop_if_not_child(self):
        trap = QTrap(phase=0.)
        other = QTrapGroup(r=(5., 5., 0.))
        other.addTrap(trap)
        self.group.removeTrap(trap)
        self.assertIs(trap.parent(), other)


class TestTrapsAndIter(unittest.TestCase):

    def setUp(self):
        self.group = QTrapGroup(r=(0., 0., 0.))
        self.traps = [QTrap(phase=0.) for _ in range(3)]
        self.group.addTrap(self.traps)

    def test_traps_property(self):
        self.assertEqual(self.group.traps, self.traps)

    def test_iter_yields_children(self):
        self.assertEqual(list(self.group), self.traps)

    def test_empty_group_iter(self):
        self.assertEqual(list(QTrapGroup(r=(0., 0., 0.))), [])

    def test_len(self):
        self.assertEqual(len(self.group), 3)


class TestRSetter(unittest.TestCase):

    def test_group_position_updates(self):
        group = QTrapGroup(r=(0., 0., 0.))
        group.addTrap(QTrap(r=(1., 0., 0.), phase=0.))
        group.r = (3., 0., 0.)
        np.testing.assert_array_equal(group.r, [3., 0., 0.])

    def test_child_translates_by_delta(self):
        group = QTrapGroup(r=(0., 0., 0.))
        trap = QTrap(r=(1., 0., 0.), phase=0.)
        group.addTrap(trap)
        group.r = (3., 0., 0.)
        np.testing.assert_array_almost_equal(trap.r, [4., 0., 0.])

    def test_geometry_preserved(self):
        group = QTrapGroup(r=(0., 0., 0.))
        t1 = QTrap(r=(1., 0., 0.), phase=0.)
        t2 = QTrap(r=(-1., 0., 0.), phase=0.)
        group.addTrap([t1, t2])
        group.r = (5., 0., 0.)
        np.testing.assert_array_almost_equal(t1.r, [6., 0., 0.])
        np.testing.assert_array_almost_equal(t2.r, [4., 0., 0.])

    def test_emits_changed(self):
        group = QTrapGroup(r=(0., 0., 0.))
        group.addTrap(QTrap(r=(1., 0., 0.), phase=0.))
        spy = QtTest.QSignalSpy(group.changed)
        group.r = (3., 0., 0.)
        self.assertEqual(len(spy), 1)

    def test_nested_group_translates(self):
        outer = QTrapGroup(r=(0., 0., 0.))
        inner = QTrapGroup(r=(2., 0., 0.))
        trap = QTrap(r=(3., 0., 0.), phase=0.)
        inner.addTrap(trap)
        outer.addTrap(inner)
        outer.r = (1., 0., 0.)
        np.testing.assert_array_almost_equal(outer.r, [1., 0., 0.])
        np.testing.assert_array_almost_equal(inner.r, [3., 0., 0.])
        np.testing.assert_array_almost_equal(trap.r, [4., 0., 0.])


class TestIsWithin(unittest.TestCase):

    def setUp(self):
        self.rect = QtCore.QRectF(0., 0., 10., 10.)

    def test_all_inside(self):
        group = QTrapGroup(r=(5., 5., 0.))
        group.addTrap([QTrap(r=(3., 3., 0.), phase=0.),
                       QTrap(r=(7., 7., 0.), phase=0.)])
        self.assertTrue(group.isWithin(self.rect))

    def test_all_outside(self):
        group = QTrapGroup(r=(15., 5., 0.))
        group.addTrap([QTrap(r=(12., 3., 0.), phase=0.),
                       QTrap(r=(14., 7., 0.), phase=0.)])
        self.assertFalse(group.isWithin(self.rect))

    def test_straddles_boundary(self):
        group = QTrapGroup(r=(5., 5., 0.))
        group.addTrap([QTrap(r=(3., 3., 0.), phase=0.),
                       QTrap(r=(15., 7., 0.), phase=0.)])
        self.assertFalse(group.isWithin(self.rect))

    def test_nested_all_inside(self):
        outer = QTrapGroup(r=(5., 5., 0.))
        inner = QTrapGroup(r=(4., 4., 0.))
        inner.addTrap([QTrap(r=(3., 3., 0.), phase=0.),
                       QTrap(r=(5., 5., 0.), phase=0.)])
        outer.addTrap(inner)
        self.assertTrue(outer.isWithin(self.rect))

    def test_nested_straddles_boundary(self):
        outer = QTrapGroup(r=(5., 5., 0.))
        inner = QTrapGroup(r=(4., 4., 0.))
        inner.addTrap([QTrap(r=(3., 3., 0.), phase=0.),
                       QTrap(r=(15., 5., 0.), phase=0.)])
        outer.addTrap(inner)
        self.assertFalse(outer.isWithin(self.rect))


class TestLeaves(unittest.TestCase):

    def test_flat_group_yields_traps(self):
        group = QTrapGroup(r=(0., 0., 0.))
        traps = [QTrap(phase=0.) for _ in range(3)]
        group.addTrap(traps)
        self.assertEqual(list(group.leaves()), traps)

    def test_nested_group_yields_all_leaves(self):
        outer = QTrapGroup(r=(0., 0., 0.))
        inner = QTrapGroup(r=(1., 0., 0.))
        t1 = QTrap(r=(0., 0., 0.), phase=0.)
        t2 = QTrap(r=(2., 0., 0.), phase=0.)
        inner.addTrap([t1, t2])
        t3 = QTrap(r=(5., 0., 0.), phase=0.)
        outer.addTrap([inner, t3])
        self.assertEqual(set(outer.leaves()), {t1, t2, t3})

    def test_leaves_are_not_groups(self):
        outer = QTrapGroup(r=(0., 0., 0.))
        inner = QTrapGroup(r=(1., 0., 0.))
        inner.addTrap([QTrap(phase=0.), QTrap(phase=0.)])
        outer.addTrap(inner)
        for leaf in outer.leaves():
            self.assertNotIsInstance(leaf, QTrapGroup)

    def test_iter_yields_direct_children(self):
        outer = QTrapGroup(r=(0., 0., 0.))
        inner = QTrapGroup(r=(1., 0., 0.))
        trap = QTrap(phase=0.)
        inner.addTrap(trap)
        outer.addTrap(inner)
        self.assertEqual(list(outer), [inner])

    def test_len_counts_direct_children(self):
        outer = QTrapGroup(r=(0., 0., 0.))
        inner = QTrapGroup(r=(1., 0., 0.))
        inner.addTrap([QTrap(phase=0.), QTrap(phase=0.)])
        outer.addTrap(inner)
        self.assertEqual(len(outer), 1)


class TestSubgroupChanges(unittest.TestCase):

    '''A change of a subgroup is a change of the group above it.'''

    @staticmethod
    def make(*members, r=(0., 0., 0.)) -> QTrapGroup:
        group = QTrapGroup(r=r)
        group.addTrap(list(members))
        return group

    def setUp(self):
        self.inner = self.make(QTrap(r=(1., 1., 0.), phase=0.),
                               QTrap(r=(3., 1., 0.), phase=0.))
        self.outer = self.make(self.inner, QTrap(r=(9., 9., 0.), phase=0.))
        self.spy = QtTest.QSignalSpy(self.outer.changed)

    def test_a_subgroup_that_moves_changes_the_group(self):
        self.inner.r = (5., 5., 0.)
        self.assertGreaterEqual(len(self.spy), 1)

    def test_a_change_reaches_the_top_of_a_hierarchy(self):
        top = self.make(self.outer)
        spy = QtTest.QSignalSpy(top.changed)
        self.inner.r = (5., 5., 0.)
        self.assertGreaterEqual(len(spy), 1)

    def test_a_subgroup_that_is_removed_is_no_longer_forwarded(self):
        self.outer.removeTrap(self.inner)
        count = len(self.spy)
        self.inner.r = (5., 5., 0.)
        self.assertEqual(len(self.spy), count)

    def test_a_subgroup_that_is_added_is_forwarded_once(self):
        other = self.make(QTrap(r=(20., 20., 0.), phase=0.))
        self.outer.addTrap(other)
        count = len(self.spy)
        other.r = (25., 25., 0.)
        self.assertEqual(len(self.spy) - count, 1)

    def test_a_subgroup_that_changes_parent_is_forwarded_to_the_new_one(self):
        new = self.make(QTrap(r=(30., 30., 0.), phase=0.))
        new.addTrap(self.inner)       # Qt removes it from the old parent
        count, new_spy = len(self.spy), QtTest.QSignalSpy(new.changed)
        self.inner.r = (5., 5., 0.)
        self.assertEqual(len(self.spy), count)
        self.assertGreaterEqual(len(new_spy), 1)

    def test_a_trap_that_is_not_a_group_needs_no_forwarding(self):
        leaf = self.outer.traps[-1]
        count = len(self.spy)
        leaf.x = 12.
        self.assertEqual(len(self.spy), count)


class TestRepr(unittest.TestCase):

    def test_repr(self):
        group = QTrapGroup(r=(0., 0., 0.))
        s = repr(group)
        self.assertTrue(s.startswith('QTrapGroup('))
        self.assertIn('ntraps=', s)


class TestGroupTranslation(unittest.TestCase):

    def setUp(self):
        self.group = QTrapGroup(r=(0., 0., 0.))
        self.t1 = QTrap(r=(1., 0., 0.), phase=0.)
        self.t2 = QTrap(r=(2., 0., 0.), phase=0.)
        self.group.addTrap([self.t1, self.t2])

    def test_group_changed_emitted_once(self):
        spy = QtTest.QSignalSpy(self.group.changed)
        self.group.r = (3., 0., 0.)
        self.assertEqual(len(spy), 1)

    def test_leaf_changed_not_emitted_on_group_move(self):
        spy1 = QtTest.QSignalSpy(self.t1.changed)
        spy2 = QtTest.QSignalSpy(self.t2.changed)
        self.group.r = (3., 0., 0.)
        self.assertEqual(len(spy1), 0)
        self.assertEqual(len(spy2), 0)

    def test_leaf_positions_updated(self):
        self.group.r = (3., 0., 0.)
        np.testing.assert_array_almost_equal(self.t1.r, [4., 0., 0.])
        np.testing.assert_array_almost_equal(self.t2.r, [5., 0., 0.])

    def test_nested_group_positions_updated(self):
        inner = QTrapGroup(r=(5., 0., 0.))
        leaf = QTrap(r=(6., 0., 0.), phase=0.)
        inner.addTrap(leaf)
        outer = QTrapGroup(r=(0., 0., 0.))
        outer.addTrap(inner)
        outer.r = (2., 0., 0.)
        np.testing.assert_array_almost_equal(inner.r, [7., 0., 0.])
        np.testing.assert_array_almost_equal(leaf.r, [8., 0., 0.])


class TestTranslateSilently(unittest.TestCase):

    def test_updates_group_position(self):
        group = QTrapGroup(r=(1., 0., 0.))
        group._translateSilently(np.array([2., 0., 0.]))
        np.testing.assert_array_almost_equal(group.r, [3., 0., 0.])

    def test_updates_leaf_positions(self):
        group = QTrapGroup(r=(0., 0., 0.))
        t = QTrap(r=(1., 0., 0.), phase=0.)
        group.addTrap(t)
        group._translateSilently(np.array([5., 0., 0.]))
        np.testing.assert_array_almost_equal(t.r, [6., 0., 0.])

    def test_does_not_emit_leaf_changed(self):
        group = QTrapGroup(r=(0., 0., 0.))
        t = QTrap(r=(1., 0., 0.), phase=0.)
        group.addTrap(t)
        spy = QtTest.QSignalSpy(t.changed)
        group._translateSilently(np.array([1., 0., 0.]))
        self.assertEqual(len(spy), 0)

    def test_does_not_emit_group_changed(self):
        group = QTrapGroup(r=(0., 0., 0.))
        spy = QtTest.QSignalSpy(group.changed)
        group._translateSilently(np.array([1., 0., 0.]))
        self.assertEqual(len(spy), 0)


class TestSnapshot(unittest.TestCase):

    def setUp(self):
        self.group = QTrapGroup(r=(0., 0., 0.))
        self.t1 = QTrap(r=(1., 0., 0.), phase=0.)
        self.t2 = QTrap(r=(2., 0., 0.), phase=0.)
        self.group.addTrap([self.t1, self.t2])

    def test_contains_all_children(self):
        snap = self.group._snapshot()
        self.assertIn(id(self.t1), snap)
        self.assertIn(id(self.t2), snap)

    def test_values_are_copies(self):
        snap = self.group._snapshot()
        self.t1._r[0] = 99.
        np.testing.assert_array_almost_equal(snap[id(self.t1)], [1., 0., 0.])

    def test_nested_children_included(self):
        inner = QTrapGroup(r=(5., 0., 0.))
        leaf = QTrap(r=(6., 0., 0.), phase=0.)
        inner.addTrap(leaf)
        outer = QTrapGroup(r=(0., 0., 0.))
        outer.addTrap(inner)
        snap = outer._snapshot()
        self.assertIn(id(inner), snap)
        self.assertIn(id(leaf), snap)


class TestRotate(unittest.TestCase):

    def setUp(self):
        self.group = QTrapGroup(r=(0., 0., 0.))
        self.t1 = QTrap(r=(1., 0., 0.), phase=0.)
        self.t2 = QTrap(r=(-1., 0., 0.), phase=0.)
        self.group.addTrap([self.t1, self.t2])
        self.snap = self.group._snapshot()

    def test_90deg_rotation(self):
        self.group.rotate(np.pi / 2., self.snap)
        np.testing.assert_array_almost_equal(self.t1._r[:2], [0., 1.])
        np.testing.assert_array_almost_equal(self.t2._r[:2], [0., -1.])

    def test_180deg_rotation(self):
        self.group.rotate(np.pi, self.snap)
        np.testing.assert_array_almost_equal(self.t1._r[:2], [-1., 0.])
        np.testing.assert_array_almost_equal(self.t2._r[:2], [1., 0.])

    def test_group_center_unchanged(self):
        self.group.rotate(np.pi / 4., self.snap)
        np.testing.assert_array_almost_equal(self.group._r, [0., 0., 0.])

    def test_z_coordinate_unchanged(self):
        self.t1._r[2] = 5.
        snap = self.group._snapshot()
        self.group.rotate(np.pi / 2., snap)
        self.assertAlmostEqual(self.t1._r[2], 5.)

    def test_group_changed_emitted(self):
        spy = QtTest.QSignalSpy(self.group.changed)
        self.group.rotate(np.pi / 2., self.snap)
        self.assertGreaterEqual(len(spy), 1)

    def test_leaf_changed_emitted_for_cgh_invalidation(self):
        spy1 = QtTest.QSignalSpy(self.t1.changed)
        spy2 = QtTest.QSignalSpy(self.t2.changed)
        self.group.rotate(np.pi / 2., self.snap)
        self.assertGreaterEqual(len(spy1), 1)
        self.assertGreaterEqual(len(spy2), 1)

    def test_idempotent_with_same_snapshot(self):
        self.group.rotate(np.pi / 3., self.snap)
        r1a = self.t1._r.copy()
        self.group.rotate(np.pi / 3., self.snap)
        np.testing.assert_array_almost_equal(self.t1._r, r1a)

    def test_zero_angle_no_change(self):
        self.group.rotate(0., self.snap)
        np.testing.assert_array_almost_equal(self.t1._r, [1., 0., 0.])

    def test_non_zero_center(self):
        group = QTrapGroup(r=(2., 0., 0.))
        trap = QTrap(r=(3., 0., 0.), phase=0.)
        group.addTrap(trap)
        snap = group._snapshot()
        group.rotate(np.pi / 2., snap)
        np.testing.assert_array_almost_equal(trap._r[:2], [2., 1.])

    def test_nested_group_center_rotates(self):
        outer = QTrapGroup(r=(0., 0., 0.))
        inner = QTrapGroup(r=(2., 0., 0.))
        leaf = QTrap(r=(3., 0., 0.), phase=0.)
        inner.addTrap(leaf)
        outer.addTrap(inner)
        snap = outer._snapshot()
        outer.rotate(np.pi / 2., snap)
        np.testing.assert_array_almost_equal(inner._r[:2], [0., 2.])
        np.testing.assert_array_almost_equal(leaf._r[:2], [0., 3.])

    def test_inner_group_changed_emitted_for_cgh_invalidation(self):
        outer = QTrapGroup(r=(0., 0., 0.))
        inner = QTrapGroup(r=(2., 0., 0.))
        leaf = QTrap(r=(3., 0., 0.), phase=0.)
        inner.addTrap(leaf)
        outer.addTrap(inner)
        snap = outer._snapshot()
        spy_inner = QtTest.QSignalSpy(inner.changed)
        spy_leaf = QtTest.QSignalSpy(leaf.changed)
        outer.rotate(np.pi / 2., snap)
        self.assertGreaterEqual(len(spy_inner), 1)
        self.assertGreaterEqual(len(spy_leaf), 1)

    def test_nested_leaf_rotates_around_outer_center(self):
        outer = QTrapGroup(r=(0., 0., 0.))
        inner = QTrapGroup(r=(1., 0., 0.))
        leaf = QTrap(r=(2., 0., 0.), phase=0.)
        inner.addTrap(leaf)
        outer.addTrap(inner)
        snap = outer._snapshot()
        outer.rotate(np.pi / 2., snap)
        np.testing.assert_array_almost_equal(leaf._r[:2], [0., 2.])


class TestToDict(unittest.TestCase):

    def setUp(self):
        self.group = QTrapGroup(r=(0., 0., 0.), phase=0.)
        self.child_a = QTrap(r=(1., 2., 0.), phase=0.)
        self.child_b = QTrap(r=(3., 4., 0.), phase=0.)
        self.group.addTrap([self.child_a, self.child_b])

    def test_type_key(self):
        self.assertEqual(self.group.toDict()['type'], 'QTrapGroup')

    def test_children_present(self):
        self.assertIn('children', self.group.toDict())

    def test_children_count(self):
        self.assertEqual(len(self.group.toDict()['children']), 2)

    def test_children_have_type(self):
        for child in self.group.toDict()['children']:
            self.assertIn('type', child)

    def test_empty_group(self):
        empty = QTrapGroup(r=(0., 0., 0.), phase=0.)
        self.assertEqual(empty.toDict()['children'], [])


if __name__ == '__main__':
    unittest.main()
