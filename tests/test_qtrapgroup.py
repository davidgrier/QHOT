'''Unit tests for QTrapGroup.'''
import unittest
import numpy as np
from pyqtgraph.Qt import QtCore, QtWidgets, QtTest
from QFab.lib.traps.QTrap import QTrap
from QFab.lib.traps.QTrapGroup import QTrapGroup

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


class TestRepr(unittest.TestCase):

    def test_repr(self):
        group = QTrapGroup(r=(0., 0., 0.))
        s = repr(group)
        self.assertTrue(s.startswith('QTrapGroup('))
        self.assertIn('ntraps=', s)


class TestGroupMoved(unittest.TestCase):

    def setUp(self):
        self.group = QTrapGroup(r=(0., 0., 0.))
        self.t1 = QTrap(r=(1., 0., 0.), phase=0.)
        self.t2 = QTrap(r=(2., 0., 0.), phase=0.)
        self.group.addTrap([self.t1, self.t2])

    def test_group_moved_emitted_on_translation(self):
        spy = QtTest.QSignalSpy(self.group.groupMoved)
        self.group.r = (3., 0., 0.)
        self.assertEqual(len(spy), 1)

    def test_group_moved_carries_leaves(self):
        spy = QtTest.QSignalSpy(self.group.groupMoved)
        self.group.r = (3., 0., 0.)
        leaves, _ = spy[0]
        self.assertIn(self.t1, leaves)
        self.assertIn(self.t2, leaves)

    def test_group_moved_carries_delta(self):
        spy = QtTest.QSignalSpy(self.group.groupMoved)
        self.group.r = (3., 0., 0.)
        _, delta = spy[0]
        np.testing.assert_array_almost_equal(delta, [3., 0., 0.])

    def test_leaf_changed_emitted_after_group_move(self):
        spy1 = QtTest.QSignalSpy(self.t1.changed)
        spy2 = QtTest.QSignalSpy(self.t2.changed)
        self.group.r = (3., 0., 0.)
        self.assertEqual(len(spy1), 1)
        self.assertEqual(len(spy2), 1)

    def test_group_changed_emitted_once(self):
        spy = QtTest.QSignalSpy(self.group.changed)
        self.group.r = (3., 0., 0.)
        self.assertEqual(len(spy), 1)

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


class TestToDict(unittest.TestCase):

    def setUp(self):
        self.group = QTrapGroup(r=(0., 0., 0.), phase=0.)
        self.child_a = QTrap(r=(1., 2., 0.), phase=0.)
        self.child_b = QTrap(r=(3., 4., 0.), phase=0.)
        self.group.addTrap([self.child_a, self.child_b])

    def test_type_key(self):
        self.assertEqual(self.group.to_dict()['type'], 'QTrapGroup')

    def test_children_present(self):
        self.assertIn('children', self.group.to_dict())

    def test_children_count(self):
        self.assertEqual(len(self.group.to_dict()['children']), 2)

    def test_children_have_type(self):
        for child in self.group.to_dict()['children']:
            self.assertIn('type', child)

    def test_empty_group(self):
        empty = QTrapGroup(r=(0., 0., 0.), phase=0.)
        self.assertEqual(empty.to_dict()['children'], [])


if __name__ == '__main__':
    unittest.main()
