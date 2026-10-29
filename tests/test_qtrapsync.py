'''Unit tests for QTrapSync and the replicas of the CGH engine.

The central property: the hologram that the engine computes from its
replicas equals the one that a fresh engine, with nothing cached, computes
from the traps of the overlay, whatever has been done to the traps.
A fresh engine is the standard because an engine that reads the traps
of the overlay and caches their fields can be stale: after a trap is
detached from a group it keeps the old structure of the group.
'''
import unittest
from unittest.mock import patch

import numpy as np
from pyqtgraph.Qt import QtCore, QtTest, QtWidgets

from QHOT.lib.holograms.CGH import CGH
from QHOT.lib.holograms.QTrapSync import QTrapSync
from QHOT.lib.traps.QTrap import QTrap
from QHOT.lib.traps.QTrapGroup import QTrapGroup
from QHOT.lib.traps.QTrapOverlay import QTrapOverlay
from QHOT.traps.QRingTrap import QRingTrap
from QHOT.traps.QTweezer import QTweezer
from QHOT.traps.QVortex import QVortex


try:
    from QHOT.lib.holograms.TorchCGH import TorchCGH
    import torch  # noqa: F401
except ImportError:
    TorchCGH = None

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

SHAPE = (48, 64)


def close(a: np.ndarray, b: np.ndarray) -> bool:
    '''Return True if two holograms differ by rounding only.

    A group that moves in one piece reuses what was cached for it, which
    sums the fields in another order than a fresh computation, so a few
    pixels may land one level of phase away across a quantization
    boundary.  A real error is many levels.
    '''
    difference = np.abs(a.astype(int) - b.astype(int))
    difference = np.minimum(difference, 256 - difference)
    return (difference.max() <= 1
            and np.count_nonzero(difference) < 0.01 * difference.size)


class Rig:

    '''An overlay and the engine that follows it.'''

    def __init__(self, threaded: bool = False, engine=CGH) -> None:
        self.overlay = QTrapOverlay()
        self.engine = engine(shape=SHAPE)
        self.reference = CGH(shape=SHAPE)  # holds the calibration only
        self.thread = None
        if threaded:
            self.thread = QtCore.QThread()
            self.engine.moveToThread(self.thread)
        self.sync = QTrapSync(self.engine)
        self.overlay.trapAdded.connect(self.sync.addTrap)
        self.overlay.trapRemoved.connect(self.sync.removeTrap)
        if threaded:
            self.thread.start()

    def close(self) -> None:
        if self.thread is not None:
            self.thread.quit()
            self.thread.wait()

    def replicated(self) -> np.ndarray:
        '''Hologram computed by the engine from its replicas.'''
        spy = QtTest.QSignalSpy(self.engine.hologramReady)
        keys = self.sync.keysOf(self.overlay._traps)
        if self.thread is None:
            self.engine.computeKeys(keys)
        else:
            QtCore.QMetaObject.invokeMethod(
                self.engine, 'computeKeys',
                QtCore.Qt.ConnectionType.QueuedConnection,
                QtCore.Q_ARG(list, keys))
            assert spy.wait(5000), 'no hologram'
        return np.array(spy[-1][0])

    def direct(self) -> np.ndarray:
        '''Hologram that a fresh engine computes from the overlay.'''
        fresh = CGH(shape=SHAPE)
        fresh.settings = self.reference.settings
        return fresh.compute(list(self.overlay._traps))

    def check(self, test: unittest.TestCase) -> None:
        '''Assert that the engine agrees with a fresh engine.'''
        test.assertTrue(close(self.replicated(), self.direct()))


def tweezer(x, y, z=0., phase=0.5, **kw):
    return QTweezer(r=(x, y, z), phase=phase, **kw)


class TestSimple(unittest.TestCase):

    def setUp(self):
        self.rig = Rig()

    def test_empty(self):
        self.rig.check(self)

    def test_add_and_move(self):
        a = tweezer(10, 12)
        self.rig.overlay.addTrap(a)
        self.rig.check(self)
        a.r = (20, 5, 3)
        self.rig.check(self)
        a.x = 30
        self.rig.check(self)
        a.amplitude = 0.4
        self.rig.check(self)
        a.phase = 2.
        self.rig.check(self)

    def test_several_traps(self):
        for n in range(5):
            self.rig.overlay.addTrap(tweezer(5 + 8 * n, 10 + 3 * n, n))
        self.rig.check(self)

    def test_remove(self):
        a, b = tweezer(10, 12), tweezer(30, 20)
        self.rig.overlay.addTrap([a, b])
        self.rig.check(self)
        self.rig.overlay.removeTrap(a)
        self.rig.check(self)
        self.assertNotIn(a, self.rig.sync._keys)

    def test_clear(self):
        self.rig.overlay.addTrap([tweezer(10, 12), tweezer(30, 20)])
        self.rig.overlay.clearTraps()
        self.assertEqual(self.rig.engine._replicas, {})
        self.rig.check(self)

    def test_undo_redo(self):
        overlay = self.rig.overlay
        overlay.addTrap(QtCore.QPointF(20., 15.))
        overlay.addTrap(QtCore.QPointF(40., 25.))
        self.rig.check(self)
        overlay._undoStack.undo()
        self.rig.check(self)
        overlay._undoStack.redo()
        self.rig.check(self)

    def test_unknown_trap_is_ignored(self):
        self.rig.sync.removeTrap(tweezer(1, 1))
        self.assertEqual(self.rig.sync.keysOf([tweezer(1, 1)]), [])

    def test_changed_after_removal_is_not_sent(self):
        a = tweezer(10, 12)
        self.rig.overlay.addTrap(a)
        self.rig.overlay.removeTrap(a)
        spy = QtTest.QSignalSpy(self.rig.sync.changed)
        a.x = 5
        self.assertEqual(len(spy), 0)


class TestStructure(unittest.TestCase):

    def setUp(self):
        self.rig = Rig()

    def test_vortex(self):
        v = QVortex(r=(20, 20, 0), ell=3, phase=0.3)
        self.rig.overlay.addTrap(v)
        self.rig.check(self)
        v.ell = 7
        self.rig.check(self)

    def test_ring(self):
        ring = QRingTrap(r=(30, 24, 0), radius=6., ell=4, phase=1.)
        self.rig.overlay.addTrap(ring)
        self.rig.check(self)
        ring.radius = 9.
        self.rig.check(self)
        ring.ell = 2
        self.rig.check(self)

    def test_replica_is_of_the_same_class(self):
        v = QVortex(r=(20, 20, 0), ell=3)
        self.rig.overlay.addTrap(v)
        replica = self.rig.engine._replicas[self.rig.sync.keyOf(v)]
        self.assertIsInstance(replica, QVortex)
        self.assertEqual(replica.ell, 3)
        self.assertIsNot(replica, v)

    def test_unknown_class_falls_back_to_a_plain_trap(self):
        node = {'key': 99, 'type': 'NoSuchTrap',
                'settings': {'x': 1., 'y': 2., 'z': 3.,
                             'amplitude': 1., 'phase': 0.}}
        self.rig.engine.addReplica(node, None)
        replica = self.rig.engine._replicas[99]
        self.assertIs(type(replica), QTrap)
        self.assertEqual(list(replica.r), [1., 2., 3.])


def make_group():
    '''A group whose members all lie in one plane.

    Moving a group in one piece reuses the structure that was cached for
    it, which is exact only when the members share their z: the
    correction for the splay of the beam depends on z.
    '''
    group = QTrapGroup(r=(30., 24., 0.), phase=0.)
    group.addTrap([tweezer(20, 20), tweezer(40, 20),
                   QVortex(r=(30, 30, 0), ell=3, phase=0.7),
                   QRingTrap(r=(30, 15, 0), radius=5., ell=2, phase=0.2)])
    return group


class TestGroups(unittest.TestCase):

    ENGINE = CGH

    def setUp(self):
        self.rig = Rig(engine=self.ENGINE)
        self.group = make_group()
        self.rig.overlay.addTrap(self.group)

    def breakAt(self, leaf):
        '''Detach *leaf* from its group, as a click on it would.

        The overlay finds a trap by its spot on the screen, which a test
        without a view cannot do.
        '''
        overlay = self.rig.overlay
        with patch.object(overlay, 'trapAt', return_value=leaf):
            return overlay.breakGroup(QtCore.QPointF(leaf.x, leaf.y))

    def test_group(self):
        self.rig.check(self)

    def test_translate(self):
        self.group.r = (35., 28., 0.)
        self.rig.check(self)
        self.group.r = (10., 10., 0.)
        self.rig.check(self)

    def test_member_moved(self):
        self.rig.check(self)
        self.group.traps[0].x = 25.
        self.rig.check(self)

    def test_member_moved_after_translation(self):
        self.group.r = (35., 28., 0.)
        self.rig.check(self)
        self.group.traps[1].y = 11.
        self.rig.check(self)

    def test_member_structure_changed(self):
        self.rig.check(self)
        self.group.traps[2].ell = 6
        self.rig.check(self)
        self.group.traps[3].radius = 8.
        self.rig.check(self)

    def test_rotate(self):
        self.rig.check(self)
        snapshot = self.group._snapshot()
        for angle in (0.3, 0.6, 1.1):
            self.group.rotate(angle, snapshot)
            self.rig.check(self)

    def test_remove_group(self):
        self.rig.check(self)
        self.rig.overlay.removeTrap(self.group)
        self.rig.check(self)
        self.assertEqual(self.rig.engine._replicas, {})

    def test_group_with_members_at_different_z_matches_the_live_path(self):
        '''The engine reproduces the algorithm, not just its exact cases.'''
        group = QTrapGroup(r=(30., 24., 0.), phase=0.)
        group.addTrap([tweezer(20, 20, 0.), tweezer(40, 20, 3.)])
        self.rig.overlay.addTrap(group)
        live = CGH(shape=SHAPE)
        for r in ((30., 24., 0.), (36., 27., 0.), (22., 30., 0.)):
            group.r = r
            replicated = self.rig.replicated()
            self.assertTrue(close(
                replicated, live.compute(list(self.rig.overlay._traps))))

    def test_replica_tree_has_the_same_shape(self):
        replica = self.rig.engine._replicas[self.rig.sync.keyOf(self.group)]
        self.assertIsInstance(replica, QTrapGroup)
        self.assertEqual([type(c) for c in replica],
                         [type(c) for c in self.group])

    def test_nested(self):
        inner = QTrapGroup(r=(10., 36., 0.), phase=0.)
        inner.addTrap([tweezer(8, 36), tweezer(12, 38)])
        outer = QTrapGroup(r=(50., 30., 0.), phase=0.)
        outer.addTrap([inner, tweezer(55, 20, 0., 1.4)])
        self.rig.overlay.addTrap(outer)
        self.rig.check(self)
        outer.r = (45., 28., 0.)
        self.rig.check(self)
        inner.r = (12., 30., 0.)
        self.rig.check(self)
        inner.traps[0].x = 5.
        self.rig.check(self)

    def test_regroup_after_break(self):
        leaf = self.group.traps[0]
        self.rig.check(self)
        self.assertTrue(self.breakAt(leaf))
        self.assertNotIsInstance(leaf.parent(), QTrapGroup)
        self.rig.check(self)
        leaf.x = 22.
        self.rig.check(self)
        self.group.r = (33., 26., 0.)
        self.rig.check(self)

    def test_break_nested(self):
        overlay = self.rig.overlay
        overlay.removeTrap(self.group)
        inner = QTrapGroup(r=(10., 36., 0.), phase=0.)
        inner.addTrap([tweezer(8, 36), tweezer(12, 38)])
        outer = QTrapGroup(r=(50., 30., 0.), phase=0.)
        outer.addTrap([inner, tweezer(55, 20, 0., 1.4),
                       tweezer(58, 24, 0., 0.9)])
        overlay.addTrap(outer)
        self.rig.check(self)
        leaf = inner.traps[0]
        self.assertTrue(self.breakAt(leaf))
        self.assertIs(inner.parent(), overlay)
        self.rig.check(self)
        outer.r = (40., 20., 0.)
        self.rig.check(self)


    def test_break_three_levels(self):
        '''A group that keeps its place while a subgroup leaves it.'''
        overlay = self.rig.overlay
        overlay.removeTrap(self.group)
        inner = QTrapGroup(r=(10., 36., 0.), phase=0.)
        inner.addTrap([tweezer(8, 36), tweezer(12, 38)])
        middle = QTrapGroup(r=(30., 34., 0.), phase=0.)
        middle.addTrap([inner, tweezer(30, 40, 0., 0.8)])
        top = QTrapGroup(r=(50., 30., 0.), phase=0.)
        top.addTrap([middle, tweezer(55, 20, 0., 1.4)])
        overlay.addTrap(top)
        self.rig.check(self)
        self.assertTrue(self.breakAt(inner.traps[0]))
        self.assertIs(inner.parent(), overlay)
        self.assertIs(middle.parent(), top)
        self.rig.check(self)
        top.r = (44., 26., 0.)
        self.rig.check(self)
        middle.traps[0].x = 14.
        self.rig.check(self)


@unittest.skipIf(TorchCGH is None, 'torch is not installed')
class TestTorchEngine(TestGroups):

    '''The same operations on groups, computed by TorchCGH.'''

    ENGINE = TorchCGH


class TestThreaded(unittest.TestCase):

    def setUp(self):
        self.rig = Rig(threaded=True)
        self.addCleanup(self.rig.close)

    def test_replicas_live_in_the_engine_thread(self):
        a = tweezer(10, 12)
        self.rig.overlay.addTrap(a)
        self.rig.replicated()
        replica = self.rig.engine._replicas[self.rig.sync.keyOf(a)]
        self.assertIs(replica.thread(), self.rig.thread)

    def test_computation_after_changes_sees_the_changes(self):
        a = tweezer(10, 12)
        self.rig.overlay.addTrap(a)
        self.rig.check(self)
        for n in range(20):
            a.r = (10 + n, 12 + n / 2., n / 4.)
        self.rig.check(self)

    def test_group_operations(self):
        group = make_group()
        self.rig.overlay.addTrap(group)
        self.rig.check(self)
        group.r = (35., 28., 0.)
        group.traps[2].ell = 5
        snapshot = group._snapshot()
        group.rotate(0.4, snapshot)
        self.rig.check(self)
        self.rig.overlay.removeTrap(group)
        self.rig.check(self)

    def test_calibration_change_while_computing(self):
        for n in range(10):
            self.rig.overlay.addTrap(tweezer(5 + 5 * n, 10 + n))
        self.rig.replicated()
        keys = self.rig.sync.keysOf(self.rig.overlay._traps)
        spy = QtTest.QSignalSpy(self.rig.engine.hologramReady)
        for n in range(5):
            QtCore.QMetaObject.invokeMethod(
                self.rig.engine, 'computeKeys',
                QtCore.Qt.ConnectionType.QueuedConnection,
                QtCore.Q_ARG(list, keys))
            self.rig.engine.xc = 300. + n
            self.rig.reference.xc = 300. + n
        QtTest.QTest.qWait(300)
        self.assertGreaterEqual(len(spy), 1)
        self.rig.check(self)


class TestFailure(unittest.TestCase):

    def test_compute_failure_is_reported(self):
        rig = Rig()
        rig.overlay.addTrap(tweezer(10, 12))
        spy = QtTest.QSignalSpy(rig.engine.computeFailed)
        ready = QtTest.QSignalSpy(rig.engine.hologramReady)
        with patch.object(rig.engine, 'compute',
                          side_effect=RuntimeError('boom')):
            rig.engine.computeKeys(rig.sync.keysOf(rig.overlay._traps))
        self.assertEqual(len(spy), 1)
        self.assertEqual(spy[0][0], 'boom')
        self.assertEqual(len(ready), 0)

    def test_unknown_keys_are_skipped(self):
        rig = Rig()
        ready = QtTest.QSignalSpy(rig.engine.hologramReady)
        rig.engine.computeKeys([12345])
        self.assertEqual(len(ready), 1)


if __name__ == '__main__':
    unittest.main()
