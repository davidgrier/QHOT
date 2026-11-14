'''Unit tests for grouping and breaking the groups of an overlay.'''
import unittest

import numpy as np
from qtpy import QtCore, QtWidgets, QtTest

from QHOT.lib.traps.QTrap import QTrap
from QHOT.lib.traps.QTrapGroup import QTrapGroup
from QHOT.lib.traps.QTrapOverlay import QTrapOverlay
from QHOT.lib.traps.grouping import break_group, group_within


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def make_overlay():
    return QTrapOverlay()


def pair(overlay):
    '''Add a group of two traps to the overlay; return it and them.'''
    t1 = QTrap(r=(1., 1., 0.), phase=0.)
    t2 = QTrap(r=(2., 2., 0.), phase=0.)
    group = QTrapGroup(r=(1.5, 1.5, 0.))
    group.addTrap([t1, t2])
    overlay.addTrap(group)
    return group, t1, t2


def brush_of(overlay, trap):
    return overlay.points()[trap._index].brush()


class TestGroupWithin(unittest.TestCase):

    def setUp(self):
        self.overlay = make_overlay()
        self.rect = QtCore.QRectF(0., 0., 10., 10.)

    def test_groups_two_traps_inside_rect(self):
        self.overlay.addTrap([QTrap(r=(3., 3., 0.), phase=0.),
                              QTrap(r=(7., 7., 0.), phase=0.)])
        group_within(self.overlay, self.rect)
        top_items = list(self.overlay)
        self.assertEqual(len(top_items), 1)
        self.assertIsInstance(top_items[0], QTrapGroup)

    def test_new_group_is_child_of_overlay(self):
        self.overlay.addTrap([QTrap(r=(3., 3., 0.), phase=0.),
                              QTrap(r=(7., 7., 0.), phase=0.)])
        group_within(self.overlay, self.rect)
        grp = next(iter(self.overlay))
        self.assertIs(grp.parent(), self.overlay)

    def test_fewer_than_two_no_group_created(self):
        self.overlay.addTrap(QTrap(r=(3., 3., 0.), phase=0.))
        group_within(self.overlay, self.rect)
        self.assertNotIsInstance(next(iter(self.overlay)), QTrapGroup)

    def test_outside_trap_excluded(self):
        t_in = QTrap(r=(3., 3., 0.), phase=0.)
        t_out = QTrap(r=(15., 5., 0.), phase=0.)
        self.overlay.addTrap([t_in, t_out])
        group_within(self.overlay, self.rect)
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
        group_within(self.overlay, self.rect)
        # straddler is not fully inside → no new group
        self.assertEqual(len(list(self.overlay)), 2)

    def test_centroid_of_new_group(self):
        self.overlay.addTrap([QTrap(r=(2., 2., 0.), phase=0.),
                              QTrap(r=(8., 8., 0.), phase=0.)])
        group_within(self.overlay, self.rect)
        grp = next(iter(self.overlay))
        np.testing.assert_array_almost_equal(grp._r, [5., 5., 0.])


class TestGroupWithinSignals(unittest.TestCase):

    def setUp(self):
        self.overlay = QTrapOverlay()
        self.t1 = QTrap(r=(2., 2., 0.), phase=0.)
        self.t2 = QTrap(r=(8., 8., 0.), phase=0.)
        self.overlay.addTrap([self.t1, self.t2])
        self.rect = QtCore.QRectF(0., 0., 10., 10.)

    def test_emits_trap_removed_for_each_candidate(self):
        spy = QtTest.QSignalSpy(self.overlay.trapRemoved)
        group_within(self.overlay, self.rect)
        self.assertEqual(len(spy), 2)

    def test_trap_removed_carries_individual_traps(self):
        spy = QtTest.QSignalSpy(self.overlay.trapRemoved)
        group_within(self.overlay, self.rect)
        self.assertEqual({spy[0][0], spy[1][0]}, {self.t1, self.t2})

    def test_emits_trap_added_once_for_new_group(self):
        spy = QtTest.QSignalSpy(self.overlay.trapAdded)
        group_within(self.overlay, self.rect)
        self.assertEqual(len(spy), 1)

    def test_trap_added_carries_new_group(self):
        spy = QtTest.QSignalSpy(self.overlay.trapAdded)
        group_within(self.overlay, self.rect)
        self.assertIsInstance(spy[0][0], QTrapGroup)

    def test_no_signals_when_fewer_than_two_candidates(self):
        overlay = QTrapOverlay()
        overlay.addTrap(QTrap(r=(3., 3., 0.), phase=0.))
        spy_removed = QtTest.QSignalSpy(overlay.trapRemoved)
        spy_added = QtTest.QSignalSpy(overlay.trapAdded)
        group_within(overlay, self.rect)
        self.assertEqual(len(spy_removed), 0)
        self.assertEqual(len(spy_added), 0)


class TestBreakGroup(unittest.TestCase):

    '''A trap, or its subgroup, leaves its group.'''

    def test_detaches_leaf_from_group(self):
        overlay = make_overlay()
        t1 = QTrap(r=(1., 1., 0.), phase=0.)
        t2 = QTrap(r=(2., 2., 0.), phase=0.)
        grp = QTrapGroup(r=(1.5, 1.5, 0.))
        grp.addTrap([t1, t2])
        overlay.addTrap(grp)
        result = break_group(overlay, t1)
        self.assertTrue(result)
        self.assertIs(t1.parent(), overlay)

    def test_empty_group_detached_after_last_leaf_broken(self):
        overlay = make_overlay()
        t1 = QTrap(r=(1., 1., 0.), phase=0.)
        t2 = QTrap(r=(2., 2., 0.), phase=0.)
        grp = QTrapGroup(r=(1.5, 1.5, 0.))
        grp.addTrap([t1, t2])
        overlay.addTrap(grp)
        break_group(overlay, t1)
        break_group(overlay, t2)
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
        result = break_group(overlay, inner_t1)
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
        break_group(overlay, inner_t1)
        self.assertIsNone(outer_grp.parent())

    def test_emits_trap_added_for_detached_leaf(self):
        overlay = make_overlay()
        t1 = QTrap(r=(1., 1., 0.), phase=0.)
        t2 = QTrap(r=(2., 2., 0.), phase=0.)
        grp = QTrapGroup(r=(1.5, 1.5, 0.))
        grp.addTrap([t1, t2])
        overlay.addTrap(grp)
        spy = QtTest.QSignalSpy(overlay.trapAdded)
        break_group(overlay, t1)
        # two trapAdded: t2 promoted (dissolution) then t1 (detached)
        self.assertEqual(len(spy), 2)
        self.assertIs(spy[0][0], t2)
        self.assertIs(spy[1][0], t1)

    def test_dissolve_promotes_sole_member_to_overlay(self):
        overlay = make_overlay()
        t1 = QTrap(r=(1., 1., 0.), phase=0.)
        t2 = QTrap(r=(2., 2., 0.), phase=0.)
        grp = QTrapGroup(r=(1.5, 1.5, 0.))
        grp.addTrap([t1, t2])
        overlay.addTrap(grp)
        break_group(overlay, t1)
        self.assertIs(t2.parent(), overlay)

    def test_dissolve_emits_trap_removed_for_group(self):
        overlay = make_overlay()
        t1 = QTrap(r=(1., 1., 0.), phase=0.)
        t2 = QTrap(r=(2., 2., 0.), phase=0.)
        grp = QTrapGroup(r=(1.5, 1.5, 0.))
        grp.addTrap([t1, t2])
        overlay.addTrap(grp)
        spy = QtTest.QSignalSpy(overlay.trapRemoved)
        break_group(overlay, t1)
        # one trapRemoved(grp) during dissolution
        self.assertEqual(len(spy), 1)
        self.assertIs(spy[0][0], grp)

    def test_emits_trap_removed_for_refresh_when_group_still_has_members(self):
        overlay = make_overlay()
        t1 = QTrap(r=(1., 1., 0.), phase=0.)
        t2 = QTrap(r=(2., 2., 0.), phase=0.)
        t3 = QTrap(r=(3., 3., 0.), phase=0.)
        grp = QTrapGroup(r=(2., 2., 0.))
        grp.addTrap([t1, t2, t3])
        overlay.addTrap(grp)
        spy = QtTest.QSignalSpy(overlay.trapRemoved)
        break_group(overlay, t1)
        # one trapRemoved(grp) for the refresh; group still has 2 members
        self.assertEqual(len(spy), 1)
        self.assertIs(spy[0][0], grp)

    def test_nested_emits_trap_removed_for_outer(self):
        overlay = make_overlay()
        inner_t1 = QTrap(r=(1., 1., 0.), phase=0.)
        inner_grp = QTrapGroup(r=(1., 1., 0.))
        inner_grp.addTrap([inner_t1, QTrap(r=(2., 2., 0.), phase=0.)])
        outer_grp = QTrapGroup(r=(3., 3., 0.))
        outer_grp.addTrap([inner_grp, QTrap(r=(5., 5., 0.), phase=0.)])
        overlay.addTrap(outer_grp)
        spy = QtTest.QSignalSpy(overlay.trapRemoved)
        break_group(overlay, inner_t1)
        self.assertEqual(len(spy), 1)
        self.assertIs(spy[0][0], outer_grp)

    def test_nested_dissolves_the_outer_group_that_is_left_with_one(self):
        overlay = make_overlay()
        inner_t1 = QTrap(r=(1., 1., 0.), phase=0.)
        inner_grp = QTrapGroup(r=(1., 1., 0.))
        inner_grp.addTrap([inner_t1, QTrap(r=(2., 2., 0.), phase=0.)])
        singleton = QTrap(r=(5., 5., 0.), phase=0.)
        outer_grp = QTrapGroup(r=(3., 3., 0.))
        outer_grp.addTrap([inner_grp, singleton])
        overlay.addTrap(outer_grp)
        spy = QtTest.QSignalSpy(overlay.trapAdded)
        break_group(overlay, inner_t1)
        added = [spy[i][0] for i in range(len(spy))]
        self.assertEqual(added, [singleton, inner_grp])   # the group is gone
        self.assertIsNone(outer_grp.parent())
        self.assertIs(singleton.parent(), overlay)
        self.assertIs(inner_grp.parent(), overlay)

    def test_nested_keeps_the_outer_group_that_has_two_left(self):
        overlay = make_overlay()
        inner_t1 = QTrap(r=(1., 1., 0.), phase=0.)
        inner_grp = QTrapGroup(r=(1., 1., 0.))
        inner_grp.addTrap([inner_t1, QTrap(r=(2., 2., 0.), phase=0.)])
        outer_grp = QTrapGroup(r=(3., 3., 0.))
        outer_grp.addTrap([inner_grp,
                           QTrap(r=(5., 5., 0.), phase=0.),
                           QTrap(r=(6., 6., 0.), phase=0.)])
        overlay.addTrap(outer_grp)
        spy = QtTest.QSignalSpy(overlay.trapAdded)
        break_group(overlay, inner_t1)
        added = [spy[i][0] for i in range(len(spy))]
        self.assertEqual(added, [outer_grp, inner_grp])
        self.assertEqual(len(list(outer_grp)), 2)


class TestAGroupOfOne(unittest.TestCase):

    '''A group may hold one trap (a file can say so, and so can breaking
    the subgroup of a group of two), and breaking its trap dissolves it.'''

    def setUp(self):
        self.overlay = make_overlay()
        self.trap = QTrap(r=(5., 5., 0.), phase=0.)
        self.group = QTrapGroup(r=(5., 5., 0.))
        self.group.addTrap(self.trap)
        self.overlay.addTrap(self.group)

    def test_the_trap_leaves_it(self):
        self.assertTrue(break_group(self.overlay, self.trap))
        self.assertIs(self.trap.parent(), self.overlay)

    def test_the_group_disappears(self):
        break_group(self.overlay, self.trap)
        self.assertIsNone(self.group.parent())
        self.assertEqual(list(self.overlay), [self.trap])

    def test_observers_see_the_group_go_and_the_trap_come(self):
        removed = QtTest.QSignalSpy(self.overlay.trapRemoved)
        added = QtTest.QSignalSpy(self.overlay.trapAdded)
        break_group(self.overlay, self.trap)
        self.assertEqual([removed[i][0] for i in range(len(removed))],
                         [self.group])
        self.assertEqual([added[i][0] for i in range(len(added))],
                         [self.trap])


class TestTheSpotsFollowAGroup(unittest.TestCase):

    '''The overlay keeps the spots of a top-level group where it is, and
    stops when the group is not at the top level any more.'''

    def setUp(self):
        self.overlay = make_overlay()
        self.t1 = QTrap(r=(2., 2., 0.), phase=0.)
        self.t2 = QTrap(r=(8., 8., 0.), phase=0.)
        self.overlay.addTrap([self.t1, self.t2])

    def x_of(self, trap):
        return self.overlay.points()[trap._index]._data['x']

    def test_a_new_group_moves_its_spots(self):
        group_within(self.overlay, QtCore.QRectF(0., 0., 10., 10.))
        group = next(iter(self.overlay))
        group.r = group.r + np.array([1., 0., 0.])
        self.assertAlmostEqual(self.x_of(self.t1), 3.)
        self.assertAlmostEqual(self.x_of(self.t2), 9.)

    def test_a_subgroup_that_leaves_moves_its_spots(self):
        a = QTrap(r=(1., 1., 0.), phase=0.)
        b = QTrap(r=(2., 2., 0.), phase=0.)
        inner = QTrapGroup(r=(1.5, 1.5, 0.))
        inner.addTrap([a, b])
        outer = QTrapGroup(r=(4., 4., 0.))
        outer.addTrap([inner, QTrap(r=(7., 7., 0.), phase=0.)])
        self.overlay.addTrap(outer)         # only the outer group is followed
        break_group(self.overlay, a)
        inner.r = inner.r + np.array([1., 0., 0.])
        self.assertAlmostEqual(self.x_of(a), 2.)
        self.assertAlmostEqual(self.x_of(b), 3.)

    def test_a_dissolved_group_is_not_followed(self):
        group, a, b = pair(self.overlay)
        break_group(self.overlay, a)
        spy = QtTest.QSignalSpy(self.overlay.patternChanged)
        group.changed.emit()
        self.assertEqual(len(spy), 0)


class TestStructureAndMarks(unittest.TestCase):

    '''A mark is on a top-level item, so a change of structure clears it.'''

    def setUp(self):
        self.overlay = make_overlay()
        self.t1 = QTrap(r=(3., 3., 0.), phase=0.)
        self.t2 = QTrap(r=(6., 6., 0.), phase=0.)
        self.overlay.addTrap([self.t1, self.t2])
        self.rect = QtCore.QRectF(0., 0., 10., 10.)

    def test_what_is_grouped_is_not_marked_any_more(self):
        self.overlay.mark(self.t1)
        self.overlay.mark(self.t2)
        group_within(self.overlay, self.rect)
        self.assertEqual(self.overlay.markedGroups, [])

    def test_what_is_grouped_is_in_its_own_color_again(self):
        self.overlay.mark(self.t1)
        group_within(self.overlay, self.rect)
        self.assertEqual(brush_of(self.overlay, self.t1),
                         self.overlay.brush[self.overlay.State.NORMAL])

    def test_what_is_not_grouped_keeps_its_mark(self):
        far = QTrap(r=(50., 50., 0.), phase=0.)
        self.overlay.addTrap(far)
        self.overlay.mark(far)
        group_within(self.overlay, self.rect)
        self.assertEqual(self.overlay.markedGroups, [far])

    def test_a_group_that_is_broken_is_not_marked_any_more(self):
        group, a, b = pair(self.overlay)
        self.overlay.mark(group)
        break_group(self.overlay, a)
        self.assertEqual(self.overlay.markedGroups, [])
        for trap in (a, b):
            self.assertEqual(brush_of(self.overlay, trap),
                             self.overlay.brush[self.overlay.State.NORMAL])

    def test_a_locked_group_that_is_broken_is_shown_as_locked(self):
        group, a, b = pair(self.overlay)
        group.locked = True
        self.overlay.mark(group)
        break_group(self.overlay, a)
        self.assertEqual(brush_of(self.overlay, b),
                         self.overlay.brush[self.overlay.State.STATIC])


if __name__ == '__main__':
    unittest.main()


class TestAGroupThatIsDeeper(unittest.TestCase):

    '''The top-level item is what observers know, however deep the change.'''

    def build(self):
        '''Return root{ middle{ inner{a, b}, c }, d } in an overlay.'''
        self.overlay = make_overlay()
        self.a, self.b, self.c, self.d = (
            QTrap(r=(float(n), float(n), 0.), phase=0.) for n in range(1, 5))
        self.inner = QTrapGroup(r=(1.5, 1.5, 0.))
        self.inner.addTrap([self.a, self.b])
        self.middle = QTrapGroup(r=(2., 2., 0.))
        self.middle.addTrap([self.inner, self.c])
        self.root = QTrapGroup(r=(3., 3., 0.))
        self.root.addTrap([self.middle, self.d])
        self.overlay.addTrap(self.root)

    def test_the_root_is_what_changes(self):
        self.build()
        removed = QtTest.QSignalSpy(self.overlay.trapRemoved)
        break_group(self.overlay, self.a)
        self.assertEqual([removed[i][0] for i in range(len(removed))],
                         [self.root])

    def test_a_group_that_is_left_with_one_gives_its_place_to_the_trap(self):
        self.build()
        break_group(self.overlay, self.a)     # inner leaves middle; c is left
        self.assertIs(self.c.parent(), self.root)
        self.assertIsNone(self.middle.parent())
        self.assertIs(self.inner.parent(), self.overlay)

    def test_the_root_stays_and_is_announced_again(self):
        self.build()
        added = QtTest.QSignalSpy(self.overlay.trapAdded)
        break_group(self.overlay, self.a)
        self.assertEqual([added[i][0] for i in range(len(added))],
                         [self.root, self.inner])

    def test_a_cascade_dissolves_every_group_that_is_left_with_one(self):
        self.build()
        break_group(self.overlay, self.a)     # middle dissolves: root{c, d}
        added = QtTest.QSignalSpy(self.overlay.trapAdded)
        break_group(self.overlay, self.c)     # root dissolves: d is at the top
        self.assertEqual([added[i][0] for i in range(len(added))],
                         [self.d, self.c])
        self.assertIsNone(self.root.parent())

    def test_a_group_that_is_left_with_none_goes_from_the_group_above(self):
        # root{ middle{ inner{a} }, d }: the groups of one come from a file
        overlay = make_overlay()
        a = QTrap(r=(1., 1., 0.), phase=0.)
        d = QTrap(r=(4., 4., 0.), phase=0.)
        inner = QTrapGroup(r=(1., 1., 0.))
        inner.addTrap(a)
        middle = QTrapGroup(r=(1., 1., 0.))
        middle.addTrap(inner)
        root = QTrapGroup(r=(3., 3., 0.))
        root.addTrap([middle, d])
        overlay.addTrap(root)
        added = QtTest.QSignalSpy(overlay.trapAdded)
        break_group(overlay, a)
        # inner leaves middle, which is empty and goes; root has d, and goes
        self.assertEqual({id(x) for x in overlay}, {id(d), id(inner)})
        self.assertIsNone(middle.parent())
        self.assertIsNone(root.parent())
        self.assertEqual([added[i][0] for i in range(len(added))],
                         [d, inner])


class TestTheStructureIsKeptWhateverIsBroken(unittest.TestCase):

    '''Break traps of random structures, one after another.  The top level
    that the observers have made of the signals is the top level of the
    overlay, and no group is left with fewer than two traps.'''

    def groups(self, overlay):
        found = []
        def visit(item):
            if isinstance(item, QTrapGroup):
                found.append(item)
                for child in item:
                    visit(child)
        for item in overlay:
            visit(item)
        return found

    def make(self, rng, depth=0):
        '''Return a trap, or a group of two to four items, at random.'''
        if depth >= 3 or rng.random() < .4:
            return QTrap(r=(rng.random() * 90., rng.random() * 90., 0.),
                         phase=0.)
        group = QTrapGroup(r=(0., 0., 0.))
        group.addTrap([self.make(rng, depth + 1)
                       for _ in range(rng.randint(2, 4))])
        return group

    def test_random_structures(self):
        import random
        for seed in range(30):
            rng = random.Random(seed)
            overlay = make_overlay()
            for _ in range(rng.randint(1, 3)):
                overlay.addTrap(self.make(rng))
            leaves = set(overlay._traps)
            seen = set(overlay)                 # what an observer knows
            overlay.trapAdded.connect(seen.add)
            overlay.trapRemoved.connect(seen.discard)
            for _ in range(20):
                leaves_now = [t for t in overlay._traps
                              if isinstance(t.parent(), QTrapGroup)]
                if not leaves_now:
                    break
                break_group(overlay, rng.choice(leaves_now))
                with self.subTest(seed=seed):
                    self.assertEqual(seen, set(overlay))
                    self.assertEqual(set(overlay._traps), leaves)
                    for group in self.groups(overlay):
                        self.assertGreaterEqual(len(list(group)), 2)
