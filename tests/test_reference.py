'''Specification tests for the hologram of a pattern of traps.

The reference (``lib/holograms/reference.py``) is the algorithm as plainly
as it can be written.  These tests state what it must do, and that the
engines of QHOT do the same.
'''
import dataclasses
import unittest

import numpy as np
from pyqtgraph.Qt import QtWidgets

from QHOT.lib.holograms import CGH, Geometry, Optics
from QHOT.lib.holograms import reference as ref
from QHOT.lib.traps import QTrap, QTrapGroup, TrapSpec
from QHOT.traps import QRingTrap, QTweezer, QVortex

try:
    from patterns import (CALIBRATIONS, SHAPE, Composite, group, levels,
                          optics, patterns, tweezer)
except ImportError:  # run from the root of the repository
    from tests.patterns import (CALIBRATIONS, SHAPE, Composite, group,
                                levels, optics, patterns, tweezer)

try:
    from QHOT.lib.holograms.TorchCGH import TorchCGH
    import torch  # noqa: F401
except ImportError:
    TorchCGH = None

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

class TestOptics(unittest.TestCase):

    def test_is_immutable(self):
        o = optics()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            o.xc = 1.

    def test_from_settings_ignores_unknown_names(self):
        o = Optics.from_settings({'xc': 5., 'nonsense': 1})
        self.assertEqual(o.xc, 5.)

    def test_settings_round_trip(self):
        o = optics(thetac=5.)
        self.assertEqual(Optics.from_settings(o.settings).settings,
                         o.settings)

    def test_agrees_with_cgh_settings(self):
        cgh = CGH(shape=SHAPE, thetac=7.)
        self.assertEqual(Optics.from_settings(cgh.settings).settings,
                         cgh.settings)

    def test_geometry_is_all_a_trap_gets(self):
        g = optics().geometry
        self.assertIsInstance(g, Geometry)
        self.assertEqual(g.shape, SHAPE)
        self.assertEqual(g.theta.shape, SHAPE)
        self.assertEqual(g.qr.shape, SHAPE)

    def test_splay_follows_the_depth_from_the_focal_plane(self):
        '''The same height above the focal plane splays the same.'''
        for zc in (0., 7., -4.):
            with self.subTest(zc=zc):
                o = optics(zc=zc, splay=0.05)
                x, y, z = o.transform((o.xc + 10., o.yc, zc + 5.))
                self.assertAlmostEqual(x, 10. / (1. + 0.05 * 5.))
                self.assertAlmostEqual(z, 5.)

    def test_displacement_has_unit_modulus(self):
        ey, ex = optics().displacement((10., 20., 3.))
        self.assertTrue(np.allclose(np.abs(ey), 1.))
        self.assertTrue(np.allclose(np.abs(ex), 1.))

    def test_displacement_shape(self):
        ey, ex = optics().displacement((10., 20., 3.))
        self.assertEqual(ey.shape, (SHAPE[0],))
        self.assertEqual(ex.shape, (SHAPE[1],))


class TestOpticsAgreesWithTheEngine(unittest.TestCase):

    def pairs(self, name):
        settings = dict(shape=SHAPE, xc=32., yc=24.)
        settings.update(CALIBRATIONS[name])
        cgh = CGH(**settings)
        return cgh, Optics.from_settings(cgh.settings)

    def test_geometry(self):
        for name in CALIBRATIONS:
            with self.subTest(name):
                cgh, o = self.pairs(name)
                self.assertTrue(np.allclose(o.geometry.theta, cgh.theta,
                                            atol=1e-5))
                self.assertTrue(np.allclose(o.geometry.qr, cgh.qr,
                                            rtol=1e-5, atol=1e-6))

    def test_transform(self):
        from qtpy import QtGui
        rng = np.random.default_rng(0)
        for name in CALIBRATIONS:
            cgh, o = self.pairs(name)
            for r in rng.uniform(-20, 60, size=(5, 3)):
                with self.subTest(name, r=r):
                    q = cgh.transform(QtGui.QVector3D(*r))
                    self.assertTrue(np.allclose(
                        o.transform(r), (q.x(), q.y(), q.z()), atol=1e-4))

    def test_engine_splay_follows_the_depth_from_the_focal_plane(self):
        from qtpy import QtGui
        for zc in (0., 7., -4.):
            with self.subTest(zc=zc):
                cgh = CGH(shape=SHAPE, xc=32., yc=24., zc=zc, splay=0.05)
                q = cgh.transform(QtGui.QVector3D(42., 24., zc + 5.))
                self.assertAlmostEqual(q.x(), 10. / (1. + 0.05 * 5.),
                                       places=4)

    def test_displacement(self):
        for name in CALIBRATIONS:
            cgh, o = self.pairs(name)
            trap = tweezer(21., 17., 2., phase=0.)
            engine = cgh.fieldOf(trap)
            ey, ex = o.displacement(trap.r)
            with self.subTest(name):
                self.assertTrue(np.allclose(np.outer(ey, ex), engine,
                                            atol=1e-3))


class TestTrapSpec(unittest.TestCase):

    def test_tweezer(self):
        spec = tweezer(1., 2., 3., phase=0.25, amplitude=0.5).spec()
        self.assertEqual(spec.kind, 'QTweezer')
        self.assertEqual(spec.r, (1., 2., 3.))
        self.assertEqual(spec.amplitude, 0.5)
        self.assertEqual(spec.phase, 0.25)
        self.assertEqual(spec.params, ())
        self.assertFalse(spec.isGroup)

    def test_vortex_records_its_charge(self):
        spec = QVortex(r=(1, 2, 3), ell=4, phase=0.).spec()
        self.assertEqual(spec.parameters(), {'ell': 4})

    def test_ring_records_its_radius_and_charge(self):
        spec = QRingTrap(r=(1, 2, 3), radius=7., ell=2, phase=0.).spec()
        self.assertEqual(spec.parameters(), {'ell': 2, 'radius': 7.})

    def test_group_holds_its_members(self):
        inner = group(tweezer(1, 1), QVortex(r=(2, 2, 0), ell=1, phase=0.))
        outer = group(inner, tweezer(3, 3))
        spec = outer.spec()
        self.assertTrue(spec.isGroup)
        self.assertEqual([c.kind for c in spec.children],
                         ['QTrapGroup', 'QTweezer'])
        self.assertEqual([c.kind for c in spec.children[0].children],
                         ['QTweezer', 'QVortex'])

    def test_leaves_at_any_depth(self):
        outer = group(group(tweezer(1, 1), tweezer(2, 2)), tweezer(3, 3))
        self.assertEqual(len(list(outer.spec().leaves())), 3)

    def test_empty_group(self):
        spec = QTrapGroup(r=(0, 0, 0)).spec()
        self.assertTrue(spec.isGroup)
        self.assertEqual(spec.children, ())
        self.assertEqual(list(spec.leaves()), [])

    def test_is_a_snapshot(self):
        trap = tweezer(1., 2., 3.)
        spec = trap.spec()
        trap.r = (9., 9., 9.)
        trap.phase = 2.
        self.assertEqual(spec.r, (1., 2., 3.))
        self.assertEqual(spec.phase, 0.5)

    def test_is_immutable(self):
        spec = tweezer(1., 2.).spec()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            spec.phase = 1.

    def test_equal_by_value_and_hashable(self):
        a = QVortex(r=(1, 2, 3), ell=4, phase=0.5).spec()
        b = QVortex(r=(1, 2, 3), ell=4, phase=0.5).spec()
        self.assertEqual(a, b)
        self.assertEqual(hash(a), hash(b))
        self.assertNotEqual(a, QVortex(r=(1, 2, 3), ell=5,
                                       phase=0.5).spec())

    def test_group_equality_includes_members(self):
        a = group(tweezer(1, 1)).spec()
        b = group(tweezer(1, 1)).spec()
        self.assertEqual(a, b)
        b = group(tweezer(1, 2)).spec()
        self.assertNotEqual(a, b)

    def test_every_trap_class_has_a_structuring_field(self):
        o = optics()
        self.assertIsNone(QTweezer.structuringField(o.geometry))
        ell3 = QVortex.structuringField(o.geometry, ell=3)
        self.assertEqual(ell3.shape, SHAPE)
        self.assertTrue(np.allclose(np.abs(ell3), 1.))

    def test_engine_structure_is_the_structuring_field(self):
        '''One source of physics: the old method defers to the new.'''
        cgh = CGH(shape=SHAPE)
        for trap in (QVortex(ell=3), QRingTrap(radius=6., ell=2)):
            expected = trap.structuringField(
                Optics.from_settings(cgh.settings).geometry,
                **trap.spec().parameters())
            self.assertTrue(np.allclose(trap.structure(cgh), expected,
                                        atol=1e-4))


class TestTheReference(unittest.TestCase):

    def setUp(self):
        self.o = optics()

    def test_empty_pattern(self):
        h = ref.hologram([], self.o)
        self.assertEqual(h.dtype, np.uint8)
        self.assertEqual(h.shape, SHAPE)
        self.assertTrue((h == 127).all())

    def test_a_tweezer_is_its_displacement(self):
        spec = tweezer(20., 25., 2., phase=0.7).spec()
        expected = np.exp(0.7j) * ref.displacement(spec.r, self.o)
        self.assertTrue(np.allclose(ref.field(spec, self.o), expected))

    def test_a_tweezer_has_no_structure(self):
        self.assertEqual(ref.structure(tweezer(1, 1).spec(), self.o), 1.)

    def test_a_vortex_has_a_helical_structure(self):
        spec = QVortex(r=(20, 20, 0), ell=3, phase=0.).spec()
        expected = np.exp(3j * self.o.geometry.theta)
        self.assertTrue(np.allclose(ref.structure(spec, self.o), expected))

    def test_amplitude_does_not_change_the_phase_of_one_trap(self):
        a = ref.hologram([tweezer(20, 25, amplitude=1.).spec()], self.o)
        b = ref.hologram([tweezer(20, 25, amplitude=7.).spec()], self.o)
        self.assertTrue(np.array_equal(a, b))

    def test_unknown_kind_is_an_error(self):
        with self.assertRaises(KeyError):
            ref.field(TrapSpec(kind='NoSuchTrap', r=(0., 0., 0.)), self.o)

    def test_the_group_own_amplitude_and_phase_are_not_used(self):
        a = group(tweezer(20, 20), tweezer(40, 28, phase=1.))
        b = group(tweezer(20, 20), tweezer(40, 28, phase=1.))
        b.phase, b.amplitude = 2.5, 9.
        self.assertEqual(a.spec(), b.spec())
        self.assertTrue(np.array_equal(
            ref.hologram([a.spec()], self.o),
            ref.hologram([b.spec()], self.o)))


class TestSuperposition(unittest.TestCase):

    '''A group is exactly the superposition of its members.'''

    def setUp(self):
        self.o = optics(splay=0.03, zc=1.)
        self.members = [tweezer(20, 20, 0.), tweezer(40, 28, 2., phase=1.),
                        QVortex(r=(30, 15, -1.), ell=3, phase=0.2),
                        QRingTrap(r=(15, 30, 1.), radius=5., ell=2,
                                  phase=0.9)]

    def total(self, pattern):
        return sum(ref.field(s, self.o) for s in pattern)

    def test_group_is_the_sum_of_its_members(self):
        grouped = [group(*self.members).spec()]
        loose = [m.spec() for m in self.members]
        self.assertTrue(np.allclose(self.total(grouped), self.total(loose)))

    def test_nesting_does_not_matter(self):
        a, b, c, d = self.members
        flat = [m.spec() for m in self.members]
        nested = [group(group(a, b), group(c, group(d))).spec()]
        self.assertTrue(np.allclose(self.total(nested), self.total(flat)))

    def test_holograms_agree_to_rounding(self):
        a = ref.hologram([group(*self.members).spec()], self.o)
        b = ref.hologram([m.spec() for m in self.members], self.o)
        self.assertLessEqual(levels(a, b).max(), 1)

    def test_a_group_may_be_empty(self):
        spec = QTrapGroup(r=(10., 10., 0.)).spec()
        self.assertTrue((ref.field(spec, self.o) == 0).all())


class TestPlainGroupsAndComposites(unittest.TestCase):

    '''Plain groups have no amplitude of their own; composites do.'''

    def setUp(self):
        self.o = optics()

    def members(self):
        return [tweezer(20, 20, amplitude=2.), tweezer(40, 28, phase=1.),
                QVortex(r=(30, 15, 0), ell=2, phase=0.3, amplitude=0.5)]

    def test_a_plain_group_has_unit_amplitude_and_no_phase(self):
        spec = group(*self.members()).spec()
        self.assertEqual((spec.amplitude, spec.phase), (1., 0.))

    def test_a_plain_group_has_nothing_to_edit_but_its_position(self):
        self.assertEqual(sorted(QTrapGroup().properties), ['x', 'y', 'z'])

    def test_a_plain_group_does_not_save_an_amplitude(self):
        d = group(*self.members()).to_dict()
        self.assertNotIn('amplitude', d)
        self.assertNotIn('phase', d)

    def test_older_files_with_a_group_amplitude_still_load(self):
        d = {'type': 'QTrapGroup', 'x': 1., 'y': 2., 'z': 0.,
             'amplitude': 3., 'phase': 1.5, 'children': []}
        spec = QTrapGroup.from_dict(d).spec()
        self.assertEqual((spec.amplitude, spec.phase), (1., 0.))

    def test_setting_it_anyway_changes_nothing(self):
        a, b = group(*self.members()), group(*self.members())
        b.amplitude, b.phase = 9., 2.5
        self.assertEqual(a.spec(), b.spec())

    def test_a_member_means_the_same_in_a_group_as_alone(self):
        alone = [m.spec() for m in self.members()]
        grouped = group(*self.members()).spec()
        total = sum(ref.field(s, self.o) for s in alone)
        self.assertTrue(np.allclose(ref.field(grouped, self.o), total))

    def test_a_composite_has_an_amplitude_and_a_phase_to_edit(self):
        self.assertEqual(sorted(Composite().properties),
                         ['amplitude', 'phase', 'x', 'y', 'z'])

    def test_a_composite_records_its_own(self):
        c = Composite(r=(32., 24., 0.), amplitude=3., phase=0.7)
        c.addTrap(self.members())
        spec = c.spec()
        self.assertEqual((spec.amplitude, spec.phase), (3., 0.7))
        self.assertTrue(spec.isGroup)

    def test_a_composite_scales_the_superposition_of_its_members(self):
        c = Composite(r=(32., 24., 0.), amplitude=3., phase=0.7)
        c.addTrap(self.members())
        total = sum(ref.field(m.spec(), self.o) for m in self.members())
        self.assertTrue(np.allclose(ref.field(c.spec(), self.o),
                                    3. * np.exp(0.7j) * total))

    def test_a_composite_mixes_with_other_traps_by_amplitude(self):
        other = tweezer(10, 40, phase=0.2).spec()
        weak, strong = (Composite(r=(32., 24., 0.), amplitude=a, phase=0.)
                        for a in (0.2, 5.))
        for c in (weak, strong):
            c.addTrap(self.members()[:2])
        near = lambda c: ref.hologram([c.spec(), other], self.o)  # noqa
        self.assertFalse(np.array_equal(near(weak), near(strong)))

    def test_the_phase_of_a_composite_shifts_its_hologram(self):
        shifts = []
        for phase in (0., 1.2):
            c = Composite(r=(32., 24., 0.), amplitude=1., phase=phase)
            c.addTrap(self.members())
            shifts.append(ref.hologram([c.spec()], self.o))
        d = (shifts[1].astype(int) - shifts[0].astype(int)) % 256
        expected = round(1.2 * 128. / np.pi)
        wrapped = np.minimum(np.abs(d - expected), 256 - np.abs(d - expected))
        self.assertLessEqual(wrapped.max(), 2)


class TestRelocation(unittest.TestCase):

    '''The structure of a group does not change when the group moves.'''

    def members(self, dx, dy, dz, spread):
        return [tweezer(20 + dx, 20 + dy, 0. + dz),
                tweezer(40 + dx, 28 + dy, spread + dz, phase=1.),
                QVortex(r=(30 + dx, 15 + dy, dz), ell=3, phase=0.2)]

    def structure(self, o, dx, dy, dz, spread):
        g = group(*self.members(dx, dy, dz, spread),
                  r=(30. + dx, 21. + dy, dz))
        return ref.structure(g.spec(), o)

    def test_rigid_motion_leaves_the_structure_alone(self):
        o = optics(splay=0.)
        s0 = self.structure(o, 0, 0, 0, spread=2.)
        for move in ((5., -3., 0.), (0., 0., 4.), (-7., 6., -2.)):
            with self.subTest(move=move):
                self.assertTrue(np.allclose(
                    self.structure(o, *move, spread=2.), s0))

    def test_splay_with_uniform_depth_leaves_it_alone_too(self):
        '''Members at one depth are scaled alike, so they stay put.'''
        o = optics(splay=0.03)
        s0 = self.structure(o, 0, 0, 0, spread=0.)
        self.assertTrue(np.allclose(
            self.structure(o, 5., -3., 0., spread=0.), s0))

    def test_splay_with_spread_in_depth_does_not(self):
        '''Then a cached structure would be stale: it must be rebuilt.'''
        o = optics(splay=0.03)
        s0 = self.structure(o, 0, 0, 0, spread=6.)
        moved = self.structure(o, 8., -5., 0., spread=6.)
        self.assertFalse(np.allclose(moved, s0, atol=1e-3))


class TestAgainstTheEngine(unittest.TestCase):

    '''The engines compute what the reference states.'''

    ENGINE = CGH

    def check(self, name, settings, pattern):
        # A new engine has cached nothing, so it computes exactly what is
        # asked, however the traps of a group are spread in depth.
        engine = self.ENGINE(**{**dict(shape=SHAPE, xc=32., yc=24.),
                                **settings})
        o = Optics.from_settings(engine.settings)
        expected = ref.hologram([t.spec() for t in pattern], o)
        actual = engine.compute(pattern)
        d = levels(actual, expected)
        with self.subTest(name, calibration=settings):
            self.assertLessEqual(d.max(), 1)
            self.assertLess(np.count_nonzero(d), 0.01 * d.size)

    def test_every_pattern_and_calibration(self):
        for label, settings in CALIBRATIONS.items():
            for name, pattern in patterns():
                if name.startswith('composite'):
                    continue  # this engine does not apply their weight
                self.check(f'{name} / {label}', settings, pattern)


@unittest.skipIf(TorchCGH is None, 'torch is not installed')
class TestTorchAgainstTheReference(TestAgainstTheEngine):

    ENGINE = TorchCGH


if __name__ == '__main__':
    unittest.main()
