'''The pattern of an overlay describes the traps as they are.

Whatever is done to the traps, as the user does it, ``overlay.pattern()``
must be the traps as they are afterwards.  The expected pattern is
described here through the public interface of the traps, independently
of ``QTrap.spec()``, and the hologram made from the pattern must be the
hologram of the traps put where they are.
'''
import unittest
from unittest.mock import patch

import numpy as np
from pyqtgraph.Qt import QtCore, QtWidgets

from QHOT.lib.holograms import NumpyBackend
from QHOT.lib.holograms import reference as ref
from QHOT.lib.traps import QTrapGroup, QTrapOverlay, TrapSpec
from QHOT.traps import QRingTrap, QTweezer, QVortex

try:
    from patterns import SHAPE, group, levels, optics, tweezer
except ImportError:  # run from the root of the repository
    from tests.patterns import SHAPE, group, levels, optics, tweezer

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def describe(trap) -> TrapSpec:
    '''Describe a trap through its public interface.'''
    params = tuple(sorted((name, getattr(trap, name))
                          for name in trap.structureParams))
    if isinstance(trap, QTrapGroup):
        weight = (dict(amplitude=trap.amplitude, phase=trap.phase)
                  if trap.composite else {})
        return TrapSpec(kind=type(trap).__name__,
                        r=(trap.x, trap.y, trap.z),
                        children=tuple(describe(c) for c in trap),
                        isGroup=True, **weight)
    return TrapSpec(kind=type(trap).__name__, r=(trap.x, trap.y, trap.z),
                    amplitude=trap.amplitude, phase=trap.phase,
                    params=params)


def make_group():
    return group(tweezer(20, 20), tweezer(40, 20),
                 QVortex(r=(30, 30, 0), ell=3, phase=0.7),
                 QRingTrap(r=(30, 15, 0), radius=5., ell=2, phase=0.2),
                 r=(30., 24., 0.))


class PatternCase(unittest.TestCase):

    def setUp(self):
        self.overlay = QTrapOverlay()
        self.backend = NumpyBackend()

    def check(self):
        '''The pattern is the traps, and makes the hologram of the traps.'''
        pattern = self.overlay.pattern()
        expected = tuple(describe(t) for t in self.overlay)
        self.assertEqual(pattern, expected)
        o = optics()
        self.assertLessEqual(
            levels(self.backend.hologram(pattern, o),
                   ref.hologram(expected, o)).max(), 1)

    def breakAt(self, leaf):
        '''Detach a trap from its group, as a click on it would.'''
        with patch.object(self.overlay, 'trapAt', return_value=leaf):
            return self.overlay.breakGroup(QtCore.QPointF(leaf.x, leaf.y))


class TestSingleTraps(PatternCase):

    def test_empty(self):
        self.check()

    def test_add_and_change(self):
        a = tweezer(10, 12)
        self.overlay.addTrap(a)
        self.check()
        a.r = (20, 5, 3)
        self.check()
        a.x = 30
        self.check()
        a.amplitude = 0.4
        self.check()
        a.phase = 2.
        self.check()

    def test_the_pattern_is_a_snapshot(self):
        a = tweezer(10, 12)
        self.overlay.addTrap(a)
        before = self.overlay.pattern()
        a.r = (50., 40., 2.)
        self.assertEqual(before[0].r, (10., 12., 0.))
        self.assertNotEqual(self.overlay.pattern(), before)

    def test_several_traps(self):
        for n in range(5):
            self.overlay.addTrap(tweezer(5 + 8 * n, 10 + 3 * n, n))
        self.check()

    def test_remove(self):
        a, b = tweezer(10, 12), tweezer(30, 20)
        self.overlay.addTrap([a, b])
        self.overlay.removeTrap(a)
        self.check()
        self.assertEqual(len(self.overlay.pattern()), 1)

    def test_clear(self):
        self.overlay.addTrap([tweezer(10, 12), tweezer(30, 20)])
        self.overlay.clearTraps()
        self.assertEqual(self.overlay.pattern(), ())
        self.check()

    def test_undo_and_redo(self):
        self.overlay.addTrap(QtCore.QPointF(20., 15.))
        self.overlay.addTrap(QtCore.QPointF(40., 25.))
        self.check()
        self.overlay._undoStack.undo()
        self.check()
        self.assertEqual(len(self.overlay.pattern()), 1)
        self.overlay._undoStack.redo()
        self.check()
        self.assertEqual(len(self.overlay.pattern()), 2)

    def test_structure_follows_the_parameters(self):
        v = QVortex(r=(20, 20, 0), ell=3, phase=0.3)
        ring = QRingTrap(r=(40, 28, 0), radius=6., ell=2, phase=0.1)
        self.overlay.addTrap([v, ring])
        self.check()
        v.ell = 7
        ring.radius = 9.
        ring.ell = 4
        self.check()
        self.assertEqual(self.overlay.pattern()[0].parameters(), {'ell': 7})


class TestGroups(PatternCase):

    def setUp(self):
        super().setUp()
        self.group = make_group()
        self.overlay.addTrap(self.group)

    def test_group(self):
        self.check()

    def test_translate(self):
        self.group.r = (35., 28., 1.)
        self.check()
        self.group.r = (10., 10., 0.)
        self.check()

    def test_the_members_move_with_the_group(self):
        before = [s.r for s in self.overlay.pattern()[0].leaves()]
        self.group.r = (40., 34., 0.)
        after = [s.r for s in self.overlay.pattern()[0].leaves()]
        for old, new in zip(before, after):
            self.assertAlmostEqual(new[0] - old[0], 10.)
            self.assertAlmostEqual(new[1] - old[1], 10.)

    def test_member_moved(self):
        self.group.traps[0].x = 25.
        self.check()
        self.group.r = (35., 28., 0.)
        self.group.traps[1].y = 11.
        self.check()

    def test_member_structure_changed(self):
        self.group.traps[2].ell = 6
        self.group.traps[3].radius = 8.
        self.check()

    def test_rotate(self):
        snapshot = self.group._snapshot()
        for angle in (0.3, 0.6, 1.1):
            self.group.rotate(angle, snapshot)
            self.check()

    def test_rotation_turns_the_members_about_the_group(self):
        snapshot = self.group._snapshot()
        self.group.rotate(np.pi / 2, snapshot)
        leaf = next(s for s in self.overlay.pattern()[0].leaves()
                    if s.kind == 'QTweezer')
        self.assertAlmostEqual(leaf.r[0], 30. + (24. - 20.), places=5)

    def test_remove_group(self):
        self.overlay.removeTrap(self.group)
        self.assertEqual(self.overlay.pattern(), ())

    def test_nested(self):
        inner = group(tweezer(8, 36), tweezer(12, 38), r=(10., 37., 0.))
        outer = group(inner, tweezer(55, 20, 0., 1.4), r=(40., 28., 0.))
        self.overlay.addTrap(outer)
        self.check()
        outer.r = (45., 28., 0.)
        self.check()
        inner.r = (12., 30., 0.)
        self.check()
        inner.traps[0].x = 5.
        self.check()

    def test_break_a_trap_out_of_a_group(self):
        leaf = self.group.traps[0]
        self.assertTrue(self.breakAt(leaf))
        self.assertNotIsInstance(leaf.parent(), QTrapGroup)
        self.check()
        leaf.x = 22.
        self.group.r = (33., 26., 0.)
        self.check()

    def test_break_a_subgroup_out_of_a_nested_group(self):
        self.overlay.removeTrap(self.group)
        inner = group(tweezer(8, 36), tweezer(12, 38), r=(10., 37., 0.))
        outer = group(inner, tweezer(55, 20, 0., 1.4),
                      tweezer(58, 24, 0., 0.9), r=(50., 30., 0.))
        self.overlay.addTrap(outer)
        self.check()
        self.assertTrue(self.breakAt(inner.traps[0]))
        self.assertIs(inner.parent(), self.overlay)
        self.check()
        outer.r = (40., 20., 0.)
        self.check()

    def test_break_three_levels(self):
        self.overlay.removeTrap(self.group)
        inner = group(tweezer(8, 36), tweezer(12, 38), r=(10., 37., 0.))
        middle = group(inner, tweezer(30, 40, 0., 0.8), r=(25., 38., 0.))
        top = group(middle, tweezer(55, 20, 0., 1.4), r=(50., 30., 0.))
        self.overlay.addTrap(top)
        self.check()
        self.assertTrue(self.breakAt(inner.traps[0]))
        self.assertIs(middle.parent(), top)
        self.check()
        top.r = (44., 26., 0.)
        self.check()


if __name__ == '__main__':
    unittest.main()
