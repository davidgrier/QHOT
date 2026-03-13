'''Unit tests for CGH.'''
import unittest
import weakref
from unittest.mock import MagicMock, patch
import numpy as np
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets, QtTest
from QFab.lib.holograms.CGH import CGH
from QFab.lib.traps.QTrap import QTrap

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def make_trap():
    '''Return a minimal mock QTrap suitable for use with CGH.'''
    trap = MagicMock(spec=QTrap)
    trap.amplitude = 1.0
    trap.phase = 0.0
    trap.r = np.array([0., 0., 0.])
    return trap


class TestInit(unittest.TestCase):

    def test_default_shape(self):
        self.assertEqual(CGH().shape, (512, 512))

    def test_default_wavelength(self):
        self.assertAlmostEqual(CGH().wavelength, 1.064)

    def test_default_n_m(self):
        self.assertAlmostEqual(CGH().n_m, 1.340)

    def test_default_magnification(self):
        self.assertAlmostEqual(CGH().magnification, 100.)

    def test_default_focallength(self):
        self.assertAlmostEqual(CGH().focallength, 200.)

    def test_default_camerapitch(self):
        self.assertAlmostEqual(CGH().camerapitch, 4.8)

    def test_default_slmpitch(self):
        self.assertAlmostEqual(CGH().slmpitch, 8.)

    def test_default_scale(self):
        self.assertAlmostEqual(CGH().scale, 3.)

    def test_default_splay(self):
        self.assertAlmostEqual(CGH().splay, 0.01)

    def test_default_xs(self):
        self.assertAlmostEqual(CGH().xs, 0.)

    def test_default_ys(self):
        self.assertAlmostEqual(CGH().ys, 0.)

    def test_default_phis(self):
        self.assertAlmostEqual(CGH().phis, 8.)

    def test_default_xc(self):
        self.assertAlmostEqual(CGH().xc, 320.)

    def test_default_yc(self):
        self.assertAlmostEqual(CGH().yc, 240.)

    def test_default_zc(self):
        self.assertAlmostEqual(CGH().zc, 0.)

    def test_default_thetac(self):
        self.assertAlmostEqual(CGH().thetac, 0.)

    def test_custom_shape(self):
        self.assertEqual(CGH(shape=(256, 128)).shape, (256, 128))

    def test_custom_wavelength(self):
        self.assertAlmostEqual(CGH(wavelength=0.532).wavelength, 0.532)

    def test_custom_xc(self):
        self.assertAlmostEqual(CGH(xc=100.).xc, 100.)

    def test_matrix_initialized(self):
        self.assertIsInstance(CGH().matrix, QtGui.QMatrix4x4)

    def test_field_initialized(self):
        cgh = CGH()
        self.assertEqual(cgh.field.shape, cgh.shape)

    def test_no_parent_by_default(self):
        self.assertIsNone(CGH().parent())


class TestSetattr(unittest.TestCase):

    def setUp(self):
        self.cgh = CGH()
        self.spy = QtTest.QSignalSpy(self.cgh.recalculate)

    def test_xc_emits_recalculate(self):
        self.cgh.xc = 100.
        self.assertEqual(len(self.spy), 1)

    def test_yc_emits_recalculate(self):
        self.cgh.yc = 100.
        self.assertEqual(len(self.spy), 1)

    def test_zc_emits_recalculate(self):
        self.cgh.zc = 10.
        self.assertEqual(len(self.spy), 1)

    def test_thetac_emits_recalculate(self):
        self.cgh.thetac = 45.
        self.assertEqual(len(self.spy), 1)

    def test_wavelength_emits_recalculate(self):
        self.cgh.wavelength = 0.532
        self.assertEqual(len(self.spy), 1)

    def test_shape_emits_recalculate(self):
        self.cgh.shape = (256, 256)
        self.assertEqual(len(self.spy), 1)

    def test_unrelated_attr_does_not_emit(self):
        self.cgh._custom = 42
        self.assertEqual(len(self.spy), 0)

    def test_same_value_does_not_emit(self):
        self.cgh.wavelength = self.cgh.wavelength
        self.assertEqual(len(self.spy), 0)

    def test_same_shape_does_not_emit(self):
        self.cgh.shape = self.cgh.shape
        self.assertEqual(len(self.spy), 0)


class TestUpdateTransformationMatrix(unittest.TestCase):

    def setUp(self):
        self.cgh = CGH()

    def test_emits_recalculate(self):
        spy = QtTest.QSignalSpy(self.cgh.recalculate)
        self.cgh.updateTransformationMatrix()
        self.assertEqual(len(spy), 1)

    def test_matrix_is_qmatrix4x4(self):
        self.cgh.updateTransformationMatrix()
        self.assertIsInstance(self.cgh.matrix, QtGui.QMatrix4x4)


class TestUpdateGeometry(unittest.TestCase):

    def setUp(self):
        self.cgh = CGH()

    def test_emits_recalculate(self):
        spy = QtTest.QSignalSpy(self.cgh.recalculate)
        self.cgh.updateGeometry()
        self.assertEqual(len(spy), 1)

    def test_field_shape(self):
        self.assertEqual(self.cgh.field.shape, self.cgh.shape)

    def test_field_dtype(self):
        self.assertEqual(self.cgh.field.dtype, np.complex64)

    def test_field_zeros(self):
        self.cgh.updateGeometry()
        np.testing.assert_array_equal(self.cgh.field, 0j)

    def test_iqx_shape(self):
        self.assertEqual(self.cgh.iqx.shape, (self.cgh.width,))

    def test_iqy_shape(self):
        self.assertEqual(self.cgh.iqy.shape, (self.cgh.height,))

    def test_shape_change_rebuilds_field(self):
        self.cgh.shape = (256, 256)
        self.assertEqual(self.cgh.field.shape, (256, 256))


class TestProperties(unittest.TestCase):

    def setUp(self):
        self.cgh = CGH()
        self.props = self.cgh.properties

    def test_returns_list(self):
        self.assertIsInstance(self.props, list)

    def test_contains_shape(self):
        self.assertIn('shape', self.props)

    def test_contains_all_calibration_attrs(self):
        for name in CGH._fields:
            self.assertIn(name, self.props)

    def test_length(self):
        self.assertEqual(len(self.props), len(CGH._fields))


class TestSettings(unittest.TestCase):

    def setUp(self):
        self.cgh = CGH()

    def test_returns_dict(self):
        self.assertIsInstance(self.cgh.settings, dict)

    def test_keys_match_fields(self):
        self.assertEqual(set(self.cgh.settings.keys()), set(CGH._fields))

    def test_values_match_attrs(self):
        for key, value in self.cgh.settings.items():
            self.assertEqual(value, getattr(self.cgh, key))

    def test_setter_updates_attr(self):
        self.cgh.settings = {'wavelength': 0.532}
        self.assertAlmostEqual(self.cgh.wavelength, 0.532)

    def test_setter_multiple_attrs(self):
        self.cgh.settings = {'xc': 100., 'yc': 200.}
        self.assertAlmostEqual(self.cgh.xc, 100.)
        self.assertAlmostEqual(self.cgh.yc, 200.)

    def test_setter_unknown_key_does_not_raise(self):
        try:
            with self.assertLogs('QFab.lib.holograms.CGH', level='WARNING'):
                self.cgh.settings = {'nonexistent': 42}
        except Exception as e:
            self.fail(f'settings setter raised unexpectedly: {e}')

    def test_setter_unknown_key_logs_warning(self):
        with patch('QFab.lib.holograms.CGH.logger') as mock_logger:
            self.cgh.settings = {'nonexistent': 42}
            mock_logger.warning.assert_called_once()


class TestDerivedProperties(unittest.TestCase):

    def setUp(self):
        self.cgh = CGH(shape=(480, 640))

    def test_height(self):
        self.assertEqual(self.cgh.height, 480)

    def test_width(self):
        self.assertEqual(self.cgh.width, 640)

    def test_rc_type(self):
        self.assertIsInstance(self.cgh.rc, QtGui.QVector3D)

    def test_rc_values(self):
        cgh = CGH(xc=10., yc=20., zc=5.)
        self.assertAlmostEqual(cgh.rc.x(), 10.)
        self.assertAlmostEqual(cgh.rc.y(), 20.)
        self.assertAlmostEqual(cgh.rc.z(), 5.)

    def test_wavenumber(self):
        cgh = CGH(wavelength=1.0, n_m=1.0)
        self.assertAlmostEqual(cgh.wavenumber, 2.*np.pi)

    def test_wavenumber_scales_with_n_m(self):
        cgh1 = CGH(n_m=1.0)
        cgh2 = CGH(n_m=2.0)
        self.assertAlmostEqual(cgh2.wavenumber, 2.*cgh1.wavenumber)

    def test_qprp_positive(self):
        self.assertGreater(CGH().qprp, 0.)

    def test_qpar_positive(self):
        self.assertGreater(CGH().qpar, 0.)

    def test_qpar_less_than_qprp(self):
        cgh = CGH()
        self.assertLess(cgh.qpar, cgh.qprp)


class TestStart(unittest.TestCase):

    def setUp(self):
        self.cgh = CGH()

    def test_returns_self(self):
        self.assertIs(self.cgh.start(), self.cgh)

    def test_emits_recalculate(self):
        spy = QtTest.QSignalSpy(self.cgh.recalculate)
        self.cgh.start()
        self.assertEqual(len(spy), 1)  # one consolidated signal


class TestStop(unittest.TestCase):

    def test_does_not_raise(self):
        try:
            CGH().stop()
        except Exception as e:
            self.fail(f'stop() raised unexpectedly: {e}')


class TestQuantize(unittest.TestCase):

    def test_zero_field_gives_midpoint(self):
        field = np.zeros((4, 4), dtype=complex)
        np.testing.assert_array_equal(CGH.quantize(field), 127)

    def test_positive_imaginary(self):
        # angle(1j) = π/2 → (128/π)*(π/2) + 127 = 64 + 127 = 191
        field = np.full((1, 1), 1j)
        self.assertEqual(CGH.quantize(field)[0, 0], 191)

    def test_negative_real(self):
        # angle(-1) = π → (128/π)*π + 127 = 128 + 127 = 255
        field = np.full((1, 1), -1.+0j)
        self.assertEqual(CGH.quantize(field)[0, 0], 255)

    def test_negative_imaginary(self):
        # angle(-1j) = -π/2 → (128/π)*(-π/2) + 127 = -64 + 127 = 63
        field = np.full((1, 1), -1j)
        self.assertEqual(CGH.quantize(field)[0, 0], 63)

    def test_output_dtype(self):
        self.assertEqual(CGH.quantize(np.ones((4, 4), dtype=complex)).dtype,
                         np.uint8)

    def test_output_shape(self):
        field = np.ones((3, 5), dtype=complex)
        self.assertEqual(CGH.quantize(field).shape, (3, 5))


class TestWindow(unittest.TestCase):

    def setUp(self):
        self.cgh = CGH()

    def test_on_axis_returns_one(self):
        r = QtGui.QVector3D(0., 0., 0.)
        self.assertAlmostEqual(self.cgh.window(r), 1.0)

    def test_returns_float(self):
        r = QtGui.QVector3D(10., 10., 0.)
        self.assertIsInstance(float(self.cgh.window(r)), float)

    def test_clamped_to_max(self):
        # Near the edge where sinc → 0 the correction blows up
        r = QtGui.QVector3D(self.cgh.width / 2., 0., 0.)
        self.assertLessEqual(self.cgh.window(r), 100.)


class TestTransform(unittest.TestCase):

    def setUp(self):
        # Identity-like calibration: no offset, no rotation, no splay
        self.cgh = CGH(xc=0., yc=0., zc=0., thetac=0., splay=0.)

    def test_returns_qvector3d(self):
        r = QtGui.QVector3D(5., 3., 0.)
        self.assertIsInstance(self.cgh.transform(r), QtGui.QVector3D)

    def test_identity_calibration_preserves_position(self):
        result = self.cgh.transform(QtGui.QVector3D(5., 3., 0.))
        self.assertAlmostEqual(result.x(), 5., places=5)
        self.assertAlmostEqual(result.y(), 3., places=5)

    def test_translation_by_optical_axis(self):
        cgh = CGH(xc=10., yc=20., zc=0., thetac=0., splay=0.)
        result = cgh.transform(QtGui.QVector3D(10., 20., 0.))
        self.assertAlmostEqual(result.x(), 0., places=5)
        self.assertAlmostEqual(result.y(), 0., places=5)


class TestFieldOf(unittest.TestCase):

    def setUp(self):
        self.cgh = CGH(xc=0., yc=0., zc=0., thetac=0., splay=0.)
        self.trap = make_trap()

    def test_returns_ndarray(self):
        result = self.cgh.fieldOf(self.trap)
        self.assertIsInstance(result, np.ndarray)

    def test_output_shape(self):
        result = self.cgh.fieldOf(self.trap)
        self.assertEqual(result.shape, self.cgh.shape)

    def test_result_is_cached(self):
        self.cgh.fieldOf(self.trap)
        cached = self.cgh._field_cache[self.trap]
        self.cgh.fieldOf(self.trap)
        self.assertIs(self.cgh._field_cache[self.trap], cached)

    def test_geometry_change_invalidates_cache(self):
        first = self.cgh.fieldOf(self.trap)
        self.cgh.wavelength = 0.532
        second = self.cgh.fieldOf(self.trap)
        self.assertIsNot(first, second)

    def test_matrix_change_preserves_structure_cache(self):
        trap = make_trap()
        trap.structure = lambda cgh: cgh.theta
        self.cgh.fieldOf(trap)
        structure_before = self.cgh._structure_cache[trap]
        self.cgh.xc = 50.  # matrix attr: clears field cache, not structure cache
        self.assertNotIn(trap, self.cgh._field_cache)
        self.assertIn(trap, self.cgh._structure_cache)
        self.assertIs(self.cgh._structure_cache[trap], structure_before)

    def test_trap_change_invalidates_cache(self):
        from QFab.traps.QTweezer import QTweezer
        trap = QTweezer(r=(0., 0., 0.), phase=0.)
        first = self.cgh.fieldOf(trap)
        trap.x = 10.
        second = self.cgh.fieldOf(trap)
        self.assertIsNot(first, second)

    def test_changed_does_not_invalidate_structure_cache(self):
        from QFab.traps.QVortex import QVortex
        trap = QVortex(r=(0., 0., 0.), phase=0., ell=1)
        self.cgh.fieldOf(trap)
        structure_before = self.cgh._structure_cache[trap]
        trap.x = 5.  # emits changed, not structureChanged
        self.assertNotIn(trap, self.cgh._field_cache)
        self.assertIn(trap, self.cgh._structure_cache)
        self.assertIs(self.cgh._structure_cache[trap], structure_before)

    def test_structure_changed_invalidates_only_structure_cache(self):
        from QFab.traps.QVortex import QVortex
        trap = QVortex(r=(0., 0., 0.), phase=0., ell=1)
        self.cgh.fieldOf(trap)
        self.assertIn(trap, self.cgh._field_cache)
        self.assertIn(trap, self.cgh._structure_cache)
        trap.ell = 2  # emits structureChanged
        self.assertIn(trap, self.cgh._field_cache)
        self.assertNotIn(trap, self.cgh._structure_cache)

    def test_field_of_connects_structure_changed(self):
        from QFab.traps.QVortex import QVortex
        trap = QVortex(r=(0., 0., 0.), phase=0., ell=0)
        self.cgh.fieldOf(trap)
        trap.ell = 3
        self.assertNotIn(trap, self.cgh._structure_cache)


class TestCompute(unittest.TestCase):

    def setUp(self):
        self.cgh = CGH()
        self.trap = make_trap()

    def test_returns_ndarray(self):
        self.assertIsInstance(self.cgh.compute([self.trap]), np.ndarray)

    def test_output_dtype(self):
        self.assertEqual(self.cgh.compute([self.trap]).dtype, np.uint8)

    def test_output_shape(self):
        self.assertEqual(self.cgh.compute([self.trap]).shape, self.cgh.shape)

    def test_emits_hologram_ready(self):
        spy = QtTest.QSignalSpy(self.cgh.hologramReady)
        self.cgh.compute([self.trap])
        self.assertEqual(len(spy), 1)

    def test_empty_traps_gives_midpoint(self):
        result = self.cgh.compute([])
        np.testing.assert_array_equal(result, 127)

    def test_multiple_traps(self):
        traps = [make_trap() for _ in range(3)]
        result = self.cgh.compute(traps)
        self.assertEqual(result.shape, self.cgh.shape)


class TestBless(unittest.TestCase):

    def setUp(self):
        self.cgh = CGH()

    def test_none_returns_none(self):
        self.assertIsNone(self.cgh.bless(None))

    def test_casts_to_dtype(self):
        field = np.ones((4, 4), dtype=np.float32)
        result = self.cgh.bless(field)
        self.assertEqual(result.dtype, np.complex64)

    def test_preserves_values(self):
        field = np.ones((4, 4), dtype=np.float64)
        result = self.cgh.bless(field)
        np.testing.assert_array_almost_equal(result.real, field)


class TestDtype(unittest.TestCase):

    def test_default_dtype(self):
        self.assertEqual(CGH.dtype, np.complex64)

    def test_field_uses_dtype(self):
        self.assertEqual(CGH().field.dtype, np.complex64)

    def test_subclass_dtype_override(self):
        class SubCGH(CGH):
            dtype = np.complex128
        cgh = SubCGH()
        self.assertEqual(cgh.field.dtype, np.complex128)

    def test_subclass_bless_uses_dtype(self):
        class SubCGH(CGH):
            dtype = np.complex128
        cgh = SubCGH()
        result = cgh.bless(np.ones((4, 4), dtype=np.float64))
        self.assertEqual(result.dtype, np.complex128)


class TestGroupMoved(unittest.TestCase):

    def setUp(self):
        from QFab.lib.traps.QTrapGroup import QTrapGroup
        from QFab.traps.QTweezer import QTweezer
        self.cgh = CGH(xc=0., yc=0., zc=0., thetac=0., splay=0.)
        self.group = QTrapGroup(r=(0., 0., 0.))
        self.t1 = QTweezer(r=(0., 0., 0.), phase=0.)
        self.t2 = QTweezer(r=(10., 0., 0.), phase=0.)
        self.group.addTrap([self.t1, self.t2])

    def test_fieldof_connects_to_parent_group(self):
        from QFab.lib.traps.QTrapGroup import QTrapGroup
        self.cgh.fieldOf(self.t1)
        self.assertIn(self.group, self.cgh._connected_groups)

    def test_group_moved_invalidates_all_leaf_fields(self):
        self.cgh.fieldOf(self.t1)
        self.cgh.fieldOf(self.t2)
        self.assertIn(self.t1, self.cgh._field_cache)
        self.assertIn(self.t2, self.cgh._field_cache)
        self.cgh._onGroupMoved([self.t1, self.t2], np.array([5., 0., 0.]))
        self.assertNotIn(self.t1, self.cgh._field_cache)
        self.assertNotIn(self.t2, self.cgh._field_cache)

    def test_group_field_built_on_first_compute(self):
        from QFab.lib.traps.QTrapGroup import QTrapGroup
        traps = [self.t1, self.t2]
        self.cgh.compute(traps)
        self.assertIn(self.group, self.cgh._group_field_cache)

    def test_group_field_used_in_compute(self):
        traps = [self.t1, self.t2]
        self.cgh.compute(traps)
        # Move the group: phase update should be applied, not full recompute
        self.cgh._onGroupMoved([self.t1, self.t2], np.array([1., 0., 0.]))
        self.assertIn(self.group, self.cgh._group_field_cache)

    def test_group_moved_applies_phase_not_invalidates(self):
        traps = [self.t1, self.t2]
        self.cgh.compute(traps)
        cached_before = self.cgh._group_field_cache[self.group].copy()
        self.cgh._onGroupMoved([self.t1, self.t2], np.array([1., 0., 0.]))
        # Cache entry should still be present (updated, not cleared)
        self.assertIn(self.group, self.cgh._group_field_cache)
        # And its values should have changed (phase was applied in-place)
        self.assertFalse(
            np.allclose(self.cgh._group_field_cache[self.group], cached_before)
        )

    def test_individual_trap_change_clears_group_field(self):
        traps = [self.t1, self.t2]
        self.cgh.compute(traps)
        self.assertIn(self.group, self.cgh._group_field_cache)
        # Simulate an individual trap change (not via groupMoved)
        trap_ref = weakref.ref(self.t1)
        self.cgh._invalidateField(trap_ref)
        self.assertNotIn(self.group, self.cgh._group_field_cache)

    def test_structure_change_clears_group_field(self):
        traps = [self.t1, self.t2]
        self.cgh.compute(traps)
        self.assertIn(self.group, self.cgh._group_field_cache)
        trap_ref = weakref.ref(self.t1)
        self.cgh._invalidateStructure(trap_ref)
        self.assertNotIn(self.group, self.cgh._group_field_cache)

    def test_group_moved_pending_guards_against_double_invalidation(self):
        traps = [self.t1, self.t2]
        self.cgh.compute(traps)
        self.cgh._onGroupMoved([self.t1, self.t2], np.array([1., 0., 0.]))
        # Leaves should be in pending set
        self.assertIn(self.t1, self.cgh._group_moved_pending)
        # Calling _invalidateField for a pending trap should NOT clear group cache
        trap_ref = weakref.ref(self.t1)
        self.cgh._invalidateField(trap_ref)
        self.assertIn(self.group, self.cgh._group_field_cache)
        # And the leaf should be removed from pending
        self.assertNotIn(self.t1, self.cgh._group_moved_pending)

    def test_geometry_change_clears_group_field(self):
        traps = [self.t1, self.t2]
        self.cgh.compute(traps)
        self.assertIn(self.group, self.cgh._group_field_cache)
        self.cgh.wavelength = 0.532
        self.assertNotIn(self.group, self.cgh._group_field_cache)

    def test_ungrouped_traps_unaffected(self):
        from QFab.traps.QTweezer import QTweezer
        solo = QTweezer(r=(50., 50., 0.), phase=0.)
        result = self.cgh.compute([self.t1, self.t2, solo])
        self.assertIsInstance(result, np.ndarray)
        self.assertEqual(result.dtype, np.uint8)


if __name__ == '__main__':
    unittest.main()
