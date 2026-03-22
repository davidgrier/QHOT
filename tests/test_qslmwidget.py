'''Unit tests for QSLMWidget.'''
import unittest
import numpy as np
from pyqtgraph import GraphicsLayoutWidget, ImageItem
from pyqtgraph.Qt import QtWidgets
from QHOT.lib.QSLMWidget import QSLMWidget

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

SHAPE = (480, 640)


def _hologram(shape=SHAPE):
    '''Return a representative uint8 phase pattern.'''
    return (np.indices(shape).sum(axis=0) % 256).astype(np.uint8)


class TestInit(unittest.TestCase):

    def setUp(self):
        self.w = QSLMWidget()

    def tearDown(self):
        self.w.close()

    def test_is_graphics_layout_widget(self):
        self.assertIsInstance(self.w, GraphicsLayoutWidget)

    def test_has_view(self):
        self.assertIsNotNone(self.w.view)

    def test_has_image_item(self):
        self.assertIsInstance(self.w.image, ImageItem)

    def test_data_is_none_before_setdata(self):
        self.assertIsNone(self.w.data)

    def test_hologram_cache_is_none_before_setdata(self):
        self.assertIsNone(self.w._hologram)

    def test_aspect_locked(self):
        self.assertTrue(self.w.view.state['aspectLocked'])


class TestSetData(unittest.TestCase):

    def setUp(self):
        self.w = QSLMWidget()
        self.phase = _hologram()

    def tearDown(self):
        self.w.close()

    def test_hologram_cached_when_hidden(self):
        self.assertFalse(self.w.isVisible())
        self.w.setData(self.phase)
        self.assertIs(self.w._hologram, self.phase)

    def test_data_not_rendered_when_hidden(self):
        self.assertFalse(self.w.isVisible())
        self.w.setData(self.phase)
        self.assertIsNone(self.w.data)

    def test_data_rendered_when_visible(self):
        self.w.show()
        self.w.setData(self.phase)
        self.assertIsNotNone(self.w.data)
        np.testing.assert_array_equal(self.w.data, self.phase)

    def test_data_shape_preserved(self):
        self.w.show()
        self.w.setData(self.phase)
        self.assertEqual(self.w.data.shape, SHAPE)

    def test_data_dtype_preserved(self):
        self.w.show()
        self.w.setData(self.phase)
        self.assertEqual(self.w.data.dtype, np.uint8)

    def test_subsequent_update_replaces_data(self):
        self.w.show()
        self.w.setData(self.phase)
        second = np.zeros(SHAPE, dtype=np.uint8)
        self.w.setData(second)
        np.testing.assert_array_equal(self.w.data, second)

    def test_cache_updated_on_each_call(self):
        self.w.setData(self.phase)
        second = np.zeros(SHAPE, dtype=np.uint8)
        self.w.setData(second)
        self.assertIs(self.w._hologram, second)


class TestShowEvent(unittest.TestCase):

    def setUp(self):
        self.w = QSLMWidget()
        self.phase = _hologram()

    def tearDown(self):
        self.w.close()

    def test_cached_hologram_rendered_on_show(self):
        self.w.setData(self.phase)
        self.assertIsNone(self.w.data)   # not yet rendered
        self.w.show()
        np.testing.assert_array_equal(self.w.data, self.phase)

    def test_no_error_on_show_without_prior_setdata(self):
        try:
            self.w.show()
        except Exception as e:
            self.fail(f'show() raised {e} with no prior setData')

    def test_data_is_none_on_show_without_prior_setdata(self):
        self.w.show()
        self.assertIsNone(self.w.data)


class TestDataProperty(unittest.TestCase):

    def setUp(self):
        self.w = QSLMWidget()

    def tearDown(self):
        self.w.close()

    def test_returns_none_initially(self):
        self.assertIsNone(self.w.data)

    def test_returns_array_after_visible_setdata(self):
        self.w.show()
        phase = _hologram()
        self.w.setData(phase)
        self.assertIsInstance(self.w.data, np.ndarray)


if __name__ == '__main__':
    unittest.main()
