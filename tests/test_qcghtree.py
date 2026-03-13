'''Unit tests for QCGHTree.'''
import unittest
from unittest.mock import MagicMock, patch
from pyqtgraph.Qt import QtWidgets
from QFab.lib.holograms.CGH import CGH
from QFab.lib.holograms.QCGHTree import QCGHTree

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

# Parameters exposed by the tree (excludes 'shape', which comes from the SLM)
_TREE_PARAMS = {'wavelength', 'n_m', 'magnification', 'focallength',
                'camerapitch', 'slmpitch', 'splay',
                'xs', 'ys', 'phis', 'scale',
                'xc', 'yc', 'zc', 'thetac'}


class TestInit(unittest.TestCase):

    def test_no_cgh(self):
        widget = QCGHTree()
        self.assertIsNone(widget.cgh)

    def test_with_cgh(self):
        cgh = CGH()
        widget = QCGHTree(cgh=cgh)
        self.assertIs(widget.cgh, cgh)

    def test_cgh_initialised_before_setter(self):
        # Setting cgh=None should not raise even before _cgh exists
        try:
            widget = QCGHTree(cgh=None)
        except AttributeError as e:
            self.fail(f'__init__ raised AttributeError: {e}')


class TestProperties(unittest.TestCase):

    def setUp(self):
        self.widget = QCGHTree()

    def test_returns_keys_view(self):
        from collections.abc import KeysView
        self.assertIsInstance(self.widget.properties, KeysView)

    def test_contains_all_tree_params(self):
        self.assertTrue(_TREE_PARAMS <= set(self.widget.properties))

    def test_does_not_contain_shape(self):
        self.assertNotIn('shape', self.widget.properties)


class TestGet(unittest.TestCase):

    def setUp(self):
        self.widget = QCGHTree()

    def test_known_key_returns_value(self):
        value = self.widget.get('wavelength')
        self.assertIsNotNone(value)
        self.assertAlmostEqual(value, 1.064, places=4)

    def test_unknown_key_returns_none(self):
        self.assertIsNone(self.widget.get('nonexistent'))

    def test_unknown_key_returns_custom_default(self):
        self.assertEqual(self.widget.get('nonexistent', 42), 42)


class TestSet(unittest.TestCase):

    def setUp(self):
        self.widget = QCGHTree()

    def test_known_key_updates_value(self):
        self.widget.set('wavelength', 0.532)
        self.assertAlmostEqual(self.widget.get('wavelength'), 0.532, places=4)

    def test_unknown_key_logs_warning(self):
        with self.assertLogs('QFab.lib.holograms.QCGHTree', level='WARNING') as cm:
            self.widget.set('nonexistent', 1.0)
        self.assertTrue(any('nonexistent' in line for line in cm.output))


class TestSettings(unittest.TestCase):

    def setUp(self):
        self.widget = QCGHTree()

    def test_getter_returns_dict(self):
        self.assertIsInstance(self.widget.settings, dict)

    def test_getter_contains_all_params(self):
        self.assertTrue(_TREE_PARAMS <= set(self.widget.settings.keys()))

    def test_getter_values_match_get(self):
        for key in _TREE_PARAMS:
            self.assertEqual(self.widget.settings[key],
                             self.widget.get(key))

    def test_setter_updates_multiple(self):
        self.widget.settings = {'wavelength': 0.532, 'n_m': 1.0}
        self.assertAlmostEqual(self.widget.get('wavelength'), 0.532, places=4)
        self.assertAlmostEqual(self.widget.get('n_m'), 1.0, places=4)

    def test_setter_ignores_unknown_keys(self):
        try:
            self.widget.settings = {'nonexistent': 99.}
        except Exception as e:
            self.fail(f'settings setter raised unexpectedly: {e}')


class TestCghProperty(unittest.TestCase):

    def test_getter_returns_none_initially(self):
        widget = QCGHTree()
        self.assertIsNone(widget.cgh)

    def test_getter_returns_set_cgh(self):
        cgh = CGH()
        widget = QCGHTree(cgh=cgh)
        self.assertIs(widget.cgh, cgh)

    def test_setter_calls_update_tree(self):
        widget = QCGHTree()
        with patch.object(widget, 'updateTree') as mock_update:
            widget.cgh = CGH()
            mock_update.assert_called_once()

    def test_setter_same_object_does_not_update(self):
        cgh = CGH()
        widget = QCGHTree(cgh=cgh)
        with patch.object(widget, 'updateTree') as mock_update:
            widget.cgh = cgh
            mock_update.assert_not_called()

    def test_setter_none_clears_cgh(self):
        widget = QCGHTree(cgh=CGH())
        widget.cgh = None
        self.assertIsNone(widget.cgh)


class TestUpdateCGH(unittest.TestCase):

    def setUp(self):
        self.cgh = CGH()
        self.widget = QCGHTree(cgh=self.cgh)

    def _make_change(self, name, value, change='value'):
        param = MagicMock()
        param.name.return_value = name
        return (param, change, value)

    def test_known_field_updates_cgh(self):
        self.widget.updateCGH(None, [self._make_change('wavelength', 0.532)])
        self.assertAlmostEqual(self.cgh.wavelength, 0.532, places=4)

    def test_non_value_change_ignored(self):
        original = self.cgh.wavelength
        self.widget.updateCGH(None, [self._make_change('wavelength', 0.532,
                                                        change='childAdded')])
        self.assertEqual(self.cgh.wavelength, original)

    def test_unknown_field_logs_warning(self):
        with self.assertLogs('QFab.lib.holograms.QCGHTree', level='WARNING') as cm:
            self.widget.updateCGH(None, [self._make_change('nonexistent', 1.)])
        self.assertTrue(any('nonexistent' in line for line in cm.output))

    def test_no_cgh_does_not_raise(self):
        widget = QCGHTree()
        try:
            widget.updateCGH(None, [self._make_change('wavelength', 0.532)])
        except Exception as e:
            self.fail(f'updateCGH raised unexpectedly: {e}')


class TestUpdateTree(unittest.TestCase):

    def test_populates_from_cgh(self):
        cgh = CGH(wavelength=0.532)
        widget = QCGHTree(cgh=cgh)
        self.assertAlmostEqual(widget.get('wavelength'), 0.532, places=4)

    def test_no_cgh_does_not_raise(self):
        widget = QCGHTree()
        try:
            widget.updateTree()
        except Exception as e:
            self.fail(f'updateTree raised unexpectedly: {e}')

    def test_reflects_cgh_change_on_reconnect(self):
        cgh = CGH(wavelength=0.532)
        widget = QCGHTree()
        widget.cgh = cgh
        self.assertAlmostEqual(widget.get('wavelength'), 0.532, places=4)


if __name__ == '__main__':
    unittest.main()
