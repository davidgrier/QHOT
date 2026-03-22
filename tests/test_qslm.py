'''Unit tests for QSLM.'''
import unittest
from unittest.mock import MagicMock, patch
import numpy as np
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets
import importlib as _importlib
from QHOT.lib.QSLM import QSLM
_qslm_mod = _importlib.import_module('QHOT.lib.QSLM')

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class TestInit(unittest.TestCase):

    def setUp(self):
        self.slm = QSLM(fake=True)

    def tearDown(self):
        self.slm.close()

    def test_has_view(self):
        self.assertIsNotNone(self.slm.view)

    def test_has_image_item(self):
        self.assertIsNotNone(self.slm.image)

    def test_is_visible(self):
        self.assertTrue(self.slm.isVisible())

    def test_fake_mode_not_maximized(self):
        self.assertFalse(self.slm.isMaximized())


class TestShape(unittest.TestCase):

    def setUp(self):
        self.slm = QSLM(fake=True)

    def tearDown(self):
        self.slm.close()

    def test_returns_tuple(self):
        self.assertIsInstance(self.slm.shape, tuple)

    def test_two_elements(self):
        self.assertEqual(len(self.slm.shape), 2)

    def test_height_is_first(self):
        h, _ = self.slm.shape
        self.assertEqual(h, self.slm.height())

    def test_width_is_second(self):
        _, w = self.slm.shape
        self.assertEqual(w, self.slm.width())

    def test_positive_dimensions(self):
        h, w = self.slm.shape
        self.assertGreater(h, 0)
        self.assertGreater(w, 0)


class TestSetData(unittest.TestCase):

    def setUp(self):
        self.slm = QSLM(fake=True)

    def tearDown(self):
        self.slm.close()

    def test_accepts_correct_shape(self):
        hologram = np.zeros(self.slm.shape, dtype=np.uint8)
        try:
            self.slm.setData(hologram)
        except Exception as e:
            self.fail(f'setData raised unexpectedly: {e}')

    def test_raises_on_wrong_shape(self):
        hologram = np.zeros((10, 10), dtype=np.uint8)
        with self.assertRaises(ValueError):
            self.slm.setData(hologram)

    def test_error_contains_actual_shape(self):
        hologram = np.zeros((10, 10), dtype=np.uint8)
        with self.assertRaises(ValueError) as ctx:
            self.slm.setData(hologram)
        self.assertIn('(10, 10)', str(ctx.exception))

    def test_error_contains_slm_shape(self):
        hologram = np.zeros((10, 10), dtype=np.uint8)
        with self.assertRaises(ValueError) as ctx:
            self.slm.setData(hologram)
        self.assertIn(str(self.slm.shape), str(ctx.exception))

    def test_accepts_full_range_values(self):
        hologram = np.full(self.slm.shape, 255, dtype=np.uint8)
        self.slm.setData(hologram)  # should not raise


class TestData(unittest.TestCase):

    def setUp(self):
        self.slm = QSLM(fake=True)

    def tearDown(self):
        self.slm.close()

    def test_returns_ndarray(self):
        self.assertIsInstance(self.slm.data, np.ndarray)

    def test_shape_matches_slm(self):
        self.assertEqual(self.slm.data.shape, self.slm.shape)

    def test_dtype_is_uint8(self):
        self.assertEqual(self.slm.data.dtype, np.uint8)

    def test_initial_data_is_zeros(self):
        np.testing.assert_array_equal(self.slm.data, 0)

    def test_reflects_setdata(self):
        hologram = np.full(self.slm.shape, 128, dtype=np.uint8)
        self.slm.setData(hologram)
        np.testing.assert_array_equal(self.slm.data, hologram)


class TestScreenSelection(unittest.TestCase):

    def test_fake_mode_does_not_maximize(self):
        with patch.object(QSLM, 'showMaximized') as mock_max:
            slm = QSLM(fake=True)
            mock_max.assert_not_called()
            slm.close()

    def test_single_screen_does_not_maximize(self):
        mock_qtgui = MagicMock()
        mock_qtgui.QGuiApplication.screens.return_value = [MagicMock()]
        with patch.object(_qslm_mod, 'QtGui', mock_qtgui):
            with patch.object(QSLM, 'showMaximized') as mock_max:
                slm = QSLM(fake=False)
                mock_max.assert_not_called()
                slm.close()

    def test_secondary_screen_maximizes(self):
        mock_screen = MagicMock()
        mock_screen.geometry.return_value.topLeft.return_value = (
            QtCore.QPoint(1920, 0))
        mock_qtgui = MagicMock()
        mock_qtgui.QGuiApplication.screens.return_value = [
            MagicMock(), mock_screen]
        with patch.object(_qslm_mod, 'QtGui', mock_qtgui):
            with patch.object(QSLM, 'showMaximized') as mock_max:
                slm = QSLM(fake=False)
                mock_max.assert_called_once()
                slm.close()

    def test_secondary_screen_moves_to_correct_position(self):
        mock_point = QtCore.QPoint(1920, 0)
        mock_screen = MagicMock()
        mock_screen.geometry.return_value.topLeft.return_value = mock_point
        mock_qtgui = MagicMock()
        mock_qtgui.QGuiApplication.screens.return_value = [
            MagicMock(), mock_screen]
        with patch.object(_qslm_mod, 'QtGui', mock_qtgui):
            with patch.object(QSLM, 'move') as mock_move:
                slm = QSLM(fake=False)
                mock_move.assert_called_once_with(mock_point)
                slm.close()

    def test_fake_overrides_secondary_screen(self):
        mock_qtgui = MagicMock()
        mock_qtgui.QGuiApplication.screens.return_value = [
            MagicMock(), MagicMock()]
        with patch.object(_qslm_mod, 'QtGui', mock_qtgui):
            with patch.object(QSLM, 'showMaximized') as mock_max:
                slm = QSLM(fake=True)
                mock_max.assert_not_called()
                slm.close()


if __name__ == '__main__':
    unittest.main()
