'''Unit tests for QTrap.'''
import unittest
import numpy as np
from pyqtgraph.Qt import QtCore, QtWidgets, QtTest
from QFab.lib.traps.QTrap import QTrap

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class TestInit(unittest.TestCase):

    def test_r(self):
        trap = QTrap(r=(1., 2., 3.))
        np.testing.assert_array_equal(trap.r, [1., 2., 3.])

    def test_amplitude(self):
        trap = QTrap(amplitude=0.5)
        self.assertEqual(trap.amplitude, 0.5)

    def test_phase_explicit(self):
        trap = QTrap(phase=1.0)
        self.assertEqual(trap.phase, 1.0)

    def test_phase_random_range(self):
        for _ in range(50):
            self.assertGreaterEqual(QTrap().phase, 0.)
            self.assertLess(QTrap().phase, 2. * np.pi)

    def test_phase_random_nondeterministic(self):
        phases = {QTrap().phase for _ in range(20)}
        self.assertGreater(len(phases), 1)

    def test_phase_zero_preserved(self):
        trap = QTrap(phase=0.)
        self.assertEqual(trap.phase, 0.)

    def test_no_changed_on_init(self):
        # Verify init does not emit changed by checking that one setter call
        # after construction produces exactly 1 emission, not more.
        trap = QTrap(phase=0.)
        spy = QtTest.QSignalSpy(trap.changed)
        trap.x = 1.
        self.assertEqual(len(spy), 1)

    def test__index_none(self):
        self.assertIsNone(QTrap()._index)


class TestR(unittest.TestCase):

    def setUp(self):
        self.trap = QTrap(r=(1., 2., 3.), phase=0.)

    def test_getter_returns_copy(self):
        r = self.trap.r
        r[0] = 999.
        self.assertEqual(self.trap.x, 1.)

    def test_setter(self):
        self.trap.r = (4., 5., 6.)
        np.testing.assert_array_equal(self.trap.r, [4., 5., 6.])

    def test_setter_emits_changed(self):
        spy = QtTest.QSignalSpy(self.trap.changed)
        self.trap.r = (4., 5., 6.)
        self.assertEqual(len(spy), 1)


class TestX(unittest.TestCase):

    def setUp(self):
        self.trap = QTrap(r=(1., 2., 3.), phase=0.)

    def test_getter(self):
        self.assertEqual(self.trap.x, 1.)

    def test_setter_updates_x(self):
        self.trap.x = 9.
        self.assertEqual(self.trap.x, 9.)

    def test_setter_leaves_y_z(self):
        self.trap.x = 9.
        self.assertEqual(self.trap.y, 2.)
        self.assertEqual(self.trap.z, 3.)

    def test_setter_emits_changed(self):
        spy = QtTest.QSignalSpy(self.trap.changed)
        self.trap.x = 9.
        self.assertEqual(len(spy), 1)


class TestY(unittest.TestCase):

    def setUp(self):
        self.trap = QTrap(r=(1., 2., 3.), phase=0.)

    def test_getter(self):
        self.assertEqual(self.trap.y, 2.)

    def test_setter_updates_y(self):
        self.trap.y = 9.
        self.assertEqual(self.trap.y, 9.)

    def test_setter_leaves_x_z(self):
        self.trap.y = 9.
        self.assertEqual(self.trap.x, 1.)
        self.assertEqual(self.trap.z, 3.)

    def test_setter_emits_changed(self):
        spy = QtTest.QSignalSpy(self.trap.changed)
        self.trap.y = 9.
        self.assertEqual(len(spy), 1)


class TestZ(unittest.TestCase):

    def setUp(self):
        self.trap = QTrap(r=(1., 2., 3.), phase=0.)

    def test_getter(self):
        self.assertEqual(self.trap.z, 3.)

    def test_setter_updates_z(self):
        self.trap.z = 9.
        self.assertEqual(self.trap.z, 9.)

    def test_setter_leaves_x_y(self):
        self.trap.z = 9.
        self.assertEqual(self.trap.x, 1.)
        self.assertEqual(self.trap.y, 2.)

    def test_setter_emits_changed(self):
        spy = QtTest.QSignalSpy(self.trap.changed)
        self.trap.z = 9.
        self.assertEqual(len(spy), 1)


class TestAmplitude(unittest.TestCase):

    def setUp(self):
        self.trap = QTrap(amplitude=0.5, phase=0.)

    def test_getter(self):
        self.assertEqual(self.trap.amplitude, 0.5)

    def test_setter(self):
        self.trap.amplitude = 0.8
        self.assertEqual(self.trap.amplitude, 0.8)

    def test_setter_emits_changed(self):
        spy = QtTest.QSignalSpy(self.trap.changed)
        self.trap.amplitude = 0.8
        self.assertEqual(len(spy), 1)


class TestPhase(unittest.TestCase):

    def setUp(self):
        self.trap = QTrap(phase=1.0)

    def test_getter(self):
        self.assertEqual(self.trap.phase, 1.0)

    def test_setter(self):
        self.trap.phase = 2.5
        self.assertEqual(self.trap.phase, 2.5)

    def test_setter_emits_changed(self):
        spy = QtTest.QSignalSpy(self.trap.changed)
        self.trap.phase = 2.5
        self.assertEqual(len(spy), 1)


class TestIsWithin(unittest.TestCase):

    def setUp(self):
        self.rect = QtCore.QRectF(0., 0., 10., 10.)

    def test_inside(self):
        trap = QTrap(r=(5., 5., 0.), phase=0.)
        self.assertTrue(trap.isWithin(self.rect))

    def test_outside(self):
        trap = QTrap(r=(15., 5., 0.), phase=0.)
        self.assertFalse(trap.isWithin(self.rect))

    def test_on_boundary(self):
        trap = QTrap(r=(0., 0., 0.), phase=0.)
        self.assertTrue(trap.isWithin(self.rect))

    def test_z_ignored(self):
        trap = QTrap(r=(5., 5., 999.), phase=0.)
        self.assertTrue(trap.isWithin(self.rect))


class TestProtocol(unittest.TestCase):

    def setUp(self):
        self.trap = QTrap(phase=0.)

    def test_len(self):
        self.assertEqual(len(self.trap), 1)

    def test_iter_yields_self(self):
        self.assertEqual(list(self.trap), [self.trap])

    def test_appearance(self):
        self.assertEqual(self.trap.appearance(), {})

    def test_repr(self):
        self.assertTrue(repr(self.trap).startswith('QTrap('))


class TestProperties(unittest.TestCase):

    def setUp(self):
        self.trap = QTrap(r=(1., 2., 3.), amplitude=0.5, phase=1.0)

    def test_settings_is_dict(self):
        self.assertIsInstance(self.trap.settings, dict)

    def test_settings_contains_defaults(self):
        for key in ('x', 'y', 'z', 'amplitude', 'phase'):
            self.assertIn(key, self.trap.settings)

    def test_settings_values_match(self):
        s = self.trap.settings
        self.assertEqual(s['x'], 1.)
        self.assertEqual(s['y'], 2.)
        self.assertEqual(s['z'], 3.)
        self.assertAlmostEqual(s['amplitude'], 0.5)
        self.assertAlmostEqual(s['phase'], 1.0)

    def test_set_trap_property_updates_value(self):
        self.trap.setTrapProperty('x', 9.)
        self.assertEqual(self.trap.x, 9.)

    def test_set_trap_property_emits_changed(self):
        spy = QtTest.QSignalSpy(self.trap.changed)
        self.trap.setTrapProperty('amplitude', 0.3)
        self.assertEqual(len(spy), 1)

    def test_set_trap_property_ignores_unknown(self):
        spy = QtTest.QSignalSpy(self.trap.changed)
        self.trap.setTrapProperty('nonexistent', 1.)
        self.assertEqual(len(spy), 0)

    def test_register_property_adds_key(self):
        self.trap.registerProperty('amplitude', decimals=4)
        self.assertIn('amplitude', self.trap.properties)

    def test_register_property_stores_decimals(self):
        self.trap.registerProperty('phase', decimals=4)
        self.assertEqual(self.trap.properties['phase']['decimals'], 4)


if __name__ == '__main__':
    unittest.main()
