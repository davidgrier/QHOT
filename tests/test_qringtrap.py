'''Unit tests for QRingTrap.'''
import unittest
import numpy as np
from pyqtgraph.Qt import QtWidgets, QtTest
from QFab.traps.QRingTrap import QRingTrap
from QFab.lib.holograms.CGH import CGH

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class TestInit(unittest.TestCase):

    def test_default_radius(self):
        self.assertAlmostEqual(QRingTrap().radius, 10.)

    def test_default_ell(self):
        self.assertAlmostEqual(QRingTrap().ell, 10.)

    def test_custom_radius(self):
        self.assertAlmostEqual(QRingTrap(radius=5.).radius, 5.)

    def test_custom_ell(self):
        self.assertAlmostEqual(QRingTrap(ell=2.).ell, 2.)

    def test_radius_stored_as_float(self):
        self.assertIsInstance(QRingTrap(radius=7).radius, float)

    def test_ell_stored_as_float(self):
        self.assertIsInstance(QRingTrap(ell=1).ell, float)

    def test_no_changed_on_init(self):
        trap = QRingTrap(phase=0.)
        spy = QtTest.QSignalSpy(trap.changed)
        trap.x = 1.
        self.assertEqual(len(spy), 1)

    def test_no_structure_changed_on_init(self):
        trap = QRingTrap(phase=0.)
        spy = QtTest.QSignalSpy(trap.structureChanged)
        trap.ell = 1.
        self.assertEqual(len(spy), 1)


class TestStructureChangedSignal(unittest.TestCase):

    def setUp(self):
        self.trap = QRingTrap(phase=0., radius=10., ell=0.)

    def test_has_structure_changed_signal(self):
        self.assertTrue(hasattr(self.trap, 'structureChanged'))

    def test_ell_setter_emits_structure_changed(self):
        spy = QtTest.QSignalSpy(self.trap.structureChanged)
        self.trap.ell = 2.
        self.assertEqual(len(spy), 1)

    def test_radius_setter_emits_structure_changed(self):
        spy = QtTest.QSignalSpy(self.trap.structureChanged)
        self.trap.radius = 20.
        self.assertEqual(len(spy), 1)

    def test_ell_setter_does_not_emit_changed(self):
        spy = QtTest.QSignalSpy(self.trap.changed)
        self.trap.ell = 2.
        self.assertEqual(len(spy), 0)

    def test_radius_setter_does_not_emit_changed(self):
        spy = QtTest.QSignalSpy(self.trap.changed)
        self.trap.radius = 20.
        self.assertEqual(len(spy), 0)

    def test_position_setter_does_not_emit_structure_changed(self):
        spy = QtTest.QSignalSpy(self.trap.structureChanged)
        self.trap.x = 10.
        self.assertEqual(len(spy), 0)


class TestRadiusProperty(unittest.TestCase):

    def setUp(self):
        self.trap = QRingTrap(radius=10., phase=0.)

    def test_getter(self):
        self.assertAlmostEqual(self.trap.radius, 10.)

    def test_setter_updates_value(self):
        self.trap.radius = 25.
        self.assertAlmostEqual(self.trap.radius, 25.)

    def test_setter_casts_to_float(self):
        self.trap.radius = 5
        self.assertIsInstance(self.trap.radius, float)


class TestEllProperty(unittest.TestCase):

    def setUp(self):
        self.trap = QRingTrap(ell=1., phase=0.)

    def test_getter(self):
        self.assertAlmostEqual(self.trap.ell, 1.)

    def test_setter_updates_value(self):
        self.trap.ell = 3.
        self.assertAlmostEqual(self.trap.ell, 3.)

    def test_setter_casts_to_float(self):
        self.trap.ell = 2
        self.assertIsInstance(self.trap.ell, float)

    def test_negative_ell(self):
        self.trap.ell = -2.
        self.assertAlmostEqual(self.trap.ell, -2.)


class TestStructureMethod(unittest.TestCase):

    def setUp(self):
        self.cgh = CGH(shape=(32, 32), xc=0., yc=0., zc=0.,
                       thetac=0., splay=0.)

    def test_returns_ndarray(self):
        trap = QRingTrap(radius=10., ell=0., phase=0.)
        result = trap.structure(self.cgh)
        self.assertIsInstance(result, np.ndarray)

    def test_output_shape(self):
        trap = QRingTrap(radius=10., ell=0., phase=0.)
        result = trap.structure(self.cgh)
        self.assertEqual(result.shape, self.cgh.shape)

    def test_zero_ell_is_real(self):
        from scipy.special import jv
        trap = QRingTrap(radius=10., ell=0., phase=0.)
        result = trap.structure(self.cgh)
        expected = jv(0., 10. * self.cgh.qr)
        np.testing.assert_array_almost_equal(result.real, expected)
        np.testing.assert_array_almost_equal(result.imag, 0.)

    def test_nonzero_ell_has_helical_phase(self):
        from scipy.special import jv
        trap = QRingTrap(radius=10., ell=1., phase=0.)
        result = trap.structure(self.cgh)
        expected = jv(1., 10. * self.cgh.qr) * np.exp(1j * self.cgh.theta)
        np.testing.assert_array_almost_equal(result, expected)

    def test_structure_depends_on_radius(self):
        trap1 = QRingTrap(radius=5., ell=0., phase=0.)
        trap2 = QRingTrap(radius=20., ell=0., phase=0.)
        r1 = trap1.structure(self.cgh)
        r2 = trap2.structure(self.cgh)
        self.assertFalse(np.allclose(r1, r2))


class TestAppearance(unittest.TestCase):

    def test_returns_dict(self):
        trap = QRingTrap()
        result = trap.appearance()
        self.assertIsInstance(result, dict)

    def test_has_symbol_key(self):
        trap = QRingTrap()
        result = trap.appearance()
        self.assertIn('symbol', result)


class TestRegisterProperties(unittest.TestCase):

    def test_radius_in_properties(self):
        trap = QRingTrap()
        self.assertIn('radius', trap.properties)

    def test_ell_in_properties(self):
        trap = QRingTrap()
        self.assertIn('ell', trap.properties)

    def test_inherits_position_properties(self):
        trap = QRingTrap()
        for name in ('x', 'y', 'z'):
            self.assertIn(name, trap.properties)


if __name__ == '__main__':
    unittest.main()
