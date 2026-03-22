'''Unit tests for QVortex.'''
import unittest
import numpy as np
from pyqtgraph.Qt import QtWidgets, QtTest
from QHOT.traps.QVortex import QVortex
from QHOT.lib.holograms.CGH import CGH

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class TestInit(unittest.TestCase):

    def test_default_ell(self):
        self.assertEqual(QVortex().ell, 10)

    def test_custom_ell(self):
        self.assertEqual(QVortex(ell=3).ell, 3)

    def test_ell_stored_as_int(self):
        self.assertIsInstance(QVortex(ell=2).ell, int)

    def test_no_changed_on_init(self):
        trap = QVortex(phase=0.)
        spy = QtTest.QSignalSpy(trap.changed)
        trap.x = 1.
        self.assertEqual(len(spy), 1)

    def test_no_structure_changed_on_init(self):
        trap = QVortex(phase=0.)
        spy = QtTest.QSignalSpy(trap.structureChanged)
        trap.ell = 1
        self.assertEqual(len(spy), 1)


class TestStructureChangedSignal(unittest.TestCase):

    def setUp(self):
        self.trap = QVortex(phase=0., ell=0)

    def test_has_structure_changed_signal(self):
        self.assertTrue(hasattr(self.trap, 'structureChanged'))

    def test_ell_setter_emits_structure_changed(self):
        spy = QtTest.QSignalSpy(self.trap.structureChanged)
        self.trap.ell = 2
        self.assertEqual(len(spy), 1)

    def test_ell_setter_does_not_emit_changed(self):
        spy = QtTest.QSignalSpy(self.trap.changed)
        self.trap.ell = 2
        self.assertEqual(len(spy), 0)

    def test_position_setter_does_not_emit_structure_changed(self):
        spy = QtTest.QSignalSpy(self.trap.structureChanged)
        self.trap.x = 10.
        self.assertEqual(len(spy), 0)


class TestEllProperty(unittest.TestCase):

    def setUp(self):
        self.trap = QVortex(ell=1, phase=0.)

    def test_getter(self):
        self.assertEqual(self.trap.ell, 1)

    def test_setter_updates_value(self):
        self.trap.ell = 5
        self.assertEqual(self.trap.ell, 5)

    def test_setter_casts_to_int(self):
        self.trap.ell = 2.9
        self.assertIsInstance(self.trap.ell, int)
        self.assertEqual(self.trap.ell, 2)

    def test_negative_ell(self):
        self.trap.ell = -3
        self.assertEqual(self.trap.ell, -3)


class TestStructureMethod(unittest.TestCase):

    def setUp(self):
        self.cgh = CGH(shape=(32, 32), xc=0., yc=0., zc=0.,
                       thetac=0., splay=0.)

    def test_returns_ndarray(self):
        trap = QVortex(ell=1, phase=0.)
        result = trap.structure(self.cgh)
        self.assertIsInstance(result, np.ndarray)

    def test_output_shape(self):
        trap = QVortex(ell=1, phase=0.)
        result = trap.structure(self.cgh)
        self.assertEqual(result.shape, self.cgh.shape)

    def test_zero_ell_gives_ones(self):
        trap = QVortex(ell=0, phase=0.)
        result = trap.structure(self.cgh)
        np.testing.assert_array_almost_equal(np.abs(result), 1.)

    def test_unit_magnitude(self):
        trap = QVortex(ell=2, phase=0.)
        result = trap.structure(self.cgh)
        np.testing.assert_array_almost_equal(np.abs(result), 1.)

    def test_helical_phase(self):
        trap = QVortex(ell=1, phase=0.)
        result = trap.structure(self.cgh)
        expected = np.exp(1j * self.cgh.theta)
        np.testing.assert_array_almost_equal(result, expected)


class TestAppearance(unittest.TestCase):

    def test_returns_dict(self):
        trap = QVortex()
        result = trap.appearance()
        self.assertIsInstance(result, dict)

    def test_has_symbol_key(self):
        trap = QVortex()
        result = trap.appearance()
        self.assertIn('symbol', result)


class TestRegisterProperties(unittest.TestCase):

    def test_ell_in_properties(self):
        trap = QVortex()
        self.assertIn('ell', trap.properties)

    def test_inherits_position_properties(self):
        trap = QVortex()
        for name in ('x', 'y', 'z'):
            self.assertIn(name, trap.properties)


if __name__ == '__main__':
    unittest.main()
