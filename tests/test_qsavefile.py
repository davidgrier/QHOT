'''Unit tests for QSaveFile.'''
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
from pyqtgraph import ImageItem
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

import importlib as _importlib
from QHOT.lib.QSaveFile import QSaveFile

try:
    from taskmanagers import Screen, manager_for
except ImportError:  # run from the root of the repository
    from tests.taskmanagers import Screen, manager_for
_qsavefile_mod = _importlib.import_module('QHOT.lib.QSaveFile')


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class _FakeQObj(QtCore.QObject):
    '''Minimal QObject with a settable settings property.'''

    def __init__(self):
        super().__init__()
        self._settings = {}

    @property
    def settings(self):
        return self._settings

    @settings.setter
    def settings(self, value):
        self._settings = dict(value)


class _Base(unittest.TestCase):
    '''Base that provides a QMainWindow parent and an isolated temp home.'''

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.home = Path(self._tmpdir.name)
        self.parent = QtWidgets.QMainWindow()
        with patch('pathlib.Path.home', return_value=self.home):
            self.save = QSaveFile(self.parent)

    def tearDown(self):
        self.parent.close()
        self._tmpdir.cleanup()


# ---------------------------------------------------------------------------
# Directory creation
# ---------------------------------------------------------------------------

class TestMakeDirs(_Base):

    def test_datadir_exists(self):
        self.assertTrue(self.save.datadir.exists())

    def test_configdir_exists(self):
        self.assertTrue(self.save.configdir.exists())

    def test_datadir_under_home(self):
        self.assertEqual(self.save.datadir, self.home / 'data')

    def test_configdir_under_home(self):
        self.assertEqual(self.save.configdir,
                         self.home / '.qmainwindow')

    def test_classname_is_lowercase_parent_class(self):
        self.assertEqual(self.save.classname, 'qmainwindow')


# ---------------------------------------------------------------------------
# timestamp()
# ---------------------------------------------------------------------------

class TestTimestamp(unittest.TestCase):

    def test_returns_string(self):
        self.assertIsInstance(QSaveFile.timestamp(), str)

    def test_matches_format(self):
        self.assertRegex(QSaveFile.timestamp(), r'^\d{8}_\d{6}$')


# ---------------------------------------------------------------------------
# filename()
# ---------------------------------------------------------------------------

class TestFilename(_Base):

    def test_in_datadir(self):
        self.assertTrue(
            self.save.filename().startswith(str(self.save.datadir)))

    def test_default_prefix_is_classname(self):
        fname = Path(self.save.filename()).name
        self.assertTrue(fname.startswith(self.save.classname + '_'))

    def test_custom_prefix(self):
        fname = Path(self.save.filename(prefix='hologram')).name
        self.assertTrue(fname.startswith('hologram_'))

    def test_suffix_appended(self):
        fname = self.save.filename(suffix='.png')
        self.assertTrue(fname.endswith('.png'))

    def test_no_suffix_by_default(self):
        fname = Path(self.save.filename()).name
        self.assertNotIn('.', fname)

    def test_contains_timestamp(self):
        fname = self.save.filename()
        self.assertRegex(fname, r'\d{8}_\d{6}')


# ---------------------------------------------------------------------------
# configname()
# ---------------------------------------------------------------------------

class TestFilenameIsFree(_Base):

    '''A file that is saved must not replace one saved a moment before.'''

    def setUp(self):
        super().setUp()
        patcher = patch.object(
            QSaveFile,
            'timestamp',
            return_value='20260101_120000',
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_a_name_that_is_free_has_no_counter(self):
        name = Path(self.save.filename(prefix='p', suffix='.png')).name
        self.assertEqual(name, 'p_20260101_120000.png')

    def test_a_name_that_is_taken_gets_a_counter(self):
        first = Path(self.save.filename(prefix='p', suffix='.png'))
        first.write_text('x')
        second = Path(self.save.filename(prefix='p', suffix='.png'))
        self.assertEqual(second.name, 'p_20260101_120000_1.png')
        second.write_text('x')
        third = Path(self.save.filename(prefix='p', suffix='.png'))
        self.assertEqual(third.name, 'p_20260101_120000_2.png')

    def test_a_different_prefix_or_suffix_is_not_taken(self):
        Path(self.save.filename(prefix='p', suffix='.png')).write_text('x')
        self.assertEqual(
            Path(self.save.filename(prefix='q', suffix='.png')).name,
            'q_20260101_120000.png')
        self.assertEqual(
            Path(self.save.filename(prefix='p', suffix='.json')).name,
            'p_20260101_120000.json')

    def test_many_saves_in_one_second_make_many_files(self):
        for _ in range(5):
            Path(self.save.filename(prefix='snap', suffix='.png')
                 ).write_text('x')
        self.assertEqual(len(list(self.save.datadir.glob('snap_*.png'))), 5)


class TestConfigname(_Base):

    def test_in_configdir(self):
        qobj = _FakeQObj()
        self.assertTrue(
            self.save.configname(qobj).startswith(str(self.save.configdir)))

    def test_uses_qobj_class_name(self):
        qobj = _FakeQObj()
        name = Path(self.save.configname(qobj)).name
        self.assertEqual(name, '_FakeQObj.toml')

    def test_ends_with_toml(self):
        qobj = _FakeQObj()
        self.assertTrue(self.save.configname(qobj).endswith('.toml'))


# ---------------------------------------------------------------------------
# image() — ImageItem path
# ---------------------------------------------------------------------------

class TestImageWithImageItem(_Base):

    def setUp(self):
        super().setUp()
        self.item = ImageItem(np.zeros((10, 10), dtype=np.uint8))

    def test_calls_image_exporter(self):
        with patch.object(_qsavefile_mod, 'ImageExporter') as MockExp:
            self.save.image(self.item, filename='out.png')
        MockExp.assert_called_once_with(self.item)

    def test_calls_export_with_filename(self):
        with patch.object(_qsavefile_mod, 'ImageExporter') as MockExp:
            self.save.image(self.item, filename='out.png')
        MockExp.return_value.export.assert_called_once_with('out.png')

    def test_returns_provided_filename(self):
        with patch.object(_qsavefile_mod, 'ImageExporter'):
            result = self.save.image(self.item, filename='out.png')
        self.assertEqual(result, 'out.png')

    def test_auto_generates_filename_when_none(self):
        with patch.object(_qsavefile_mod, 'ImageExporter'):
            result = self.save.image(self.item)
        self.assertTrue(result.endswith('.png'))
        self.assertIn(str(self.save.datadir), result)


# ---------------------------------------------------------------------------
# image() — numpy array path
# ---------------------------------------------------------------------------

class TestImageWithArray(_Base):

    '''An array is saved as it is: the file is read back, not mocked.'''

    def setUp(self):
        super().setUp()
        self.path = str(self.home / 'out.png')

    def read(self, channels: int) -> np.ndarray:
        '''Read the file back, a pixel at a time.'''
        image = QtGui.QImage(self.path)
        out = np.zeros((image.height(), image.width(), 4), dtype=np.uint8)
        for y in range(image.height()):
            for x in range(image.width()):
                c = image.pixelColor(x, y)
                out[y, x] = (c.red(), c.green(), c.blue(), c.alpha())
        return out[..., 0] if channels == 1 else out[..., :channels]

    def test_a_hologram_is_saved_pixel_for_pixel(self):
        # the shape and the values of a hologram, not symmetric
        hologram = (np.arange(48 * 64) % 251).astype(np.uint8).reshape(48, 64)
        self.save.image(hologram, filename=self.path)
        back = self.read(1)
        np.testing.assert_array_equal(back, hologram)

    def test_the_rows_are_rows_and_the_columns_are_columns(self):
        hologram = np.zeros((6, 10), dtype=np.uint8)
        hologram[2, 7] = 200
        self.save.image(hologram, filename=self.path)
        back = self.read(1)
        self.assertEqual(back.shape, (6, 10))
        self.assertEqual(back[2, 7], 200)

    def test_an_rgb_image(self):
        rgb = np.random.default_rng(1).integers(
            0, 256, (12, 9, 3), dtype=np.uint8)
        self.save.image(rgb, filename=self.path)
        np.testing.assert_array_equal(
            self.read(3), rgb)

    def test_an_rgba_image(self):
        rgba = np.random.default_rng(2).integers(
            0, 256, (12, 9, 4), dtype=np.uint8)
        self.save.image(rgba, filename=self.path)
        np.testing.assert_array_equal(
            self.read(4), rgba)

    def test_an_array_that_is_not_contiguous(self):
        hologram = np.arange(40 * 40, dtype=np.uint8).reshape(40, 40)[::2, ::3]
        self.save.image(hologram, filename=self.path)
        back = self.read(1)
        np.testing.assert_array_equal(back, hologram)

    def test_pixels_that_are_not_8_bit_are_refused(self):
        with self.assertRaises(ValueError):
            self.save.image(np.zeros((4, 4), dtype=np.float64),
                            filename=self.path)

    def test_a_shape_that_is_not_an_image_is_refused(self):
        for shape in ((4,), (4, 4, 2), (2, 2, 2, 3)):
            with self.subTest(shape), self.assertRaises(ValueError):
                self.save.image(np.zeros(shape, dtype=np.uint8),
                                filename=self.path)

    def test_a_file_that_cannot_be_written_is_an_error(self):
        missing = str(self.home / 'no' / 'such' / 'directory' / 'out.png')
        with self.assertRaises(OSError):
            self.save.image(np.zeros((4, 4), dtype=np.uint8),
                            filename=missing)

    def test_returns_the_filename(self):
        result = self.save.image(np.zeros((4, 4), dtype=np.uint8),
                                 filename=self.path)
        self.assertEqual(result, self.path)

    def test_auto_generates_filename_when_none(self):
        result = self.save.image(np.zeros((4, 4), dtype=np.uint8))
        self.assertTrue(result.endswith('.png'))
        self.assertIn(str(self.save.datadir), result)
        self.assertTrue(Path(result).exists())

    def test_custom_prefix_in_auto_filename(self):
        result = self.save.image(np.zeros((4, 4), dtype=np.uint8),
                                 prefix='hologram')
        self.assertIn('hologram', Path(result).name)





class TestFromToml(_Base):

    def test_returns_empty_when_file_missing(self):
        qobj = _FakeQObj()
        result = self.save.fromToml(qobj)
        self.assertEqual(result, '')

    def test_returns_configname_when_file_exists(self):
        qobj = _FakeQObj()
        qobj._settings = {'x': 1.0}
        self.save.toToml(qobj)
        result = self.save.fromToml(qobj)
        self.assertEqual(result, self.save.configname(qobj))

    def test_restores_settings(self):
        writer = _FakeQObj()
        writer._settings = {'x': 2.0, 'y': 3.0}
        self.save.toToml(writer)
        reader = _FakeQObj()
        self.save.fromToml(reader)
        self.assertAlmostEqual(float(reader.settings['x']), 2.0)
        self.assertAlmostEqual(float(reader.settings['y']), 3.0)

    def test_does_not_modify_qobj_when_file_missing(self):
        qobj = _FakeQObj()
        qobj._settings = {'original': True}
        self.save.fromToml(qobj)
        self.assertIn('original', qobj.settings)


# ---------------------------------------------------------------------------
# queue() / queueAs() / openQueue()
# ---------------------------------------------------------------------------


class TestToJson(_Base):

    def test_writes_the_data(self):
        path = str(self.home / 'out.json')
        self.save.toJson({'a': [1, 2.5, 'x']}, path)
        self.assertEqual(json.loads(Path(path).read_text()),
                         {'a': [1, 2.5, 'x']})

    def test_returns_the_filename(self):
        path = str(self.home / 'out.json')
        self.assertEqual(self.save.toJson([], path), path)

    def test_auto_generates_filename_when_none(self):
        result = self.save.toJson([1])
        self.assertTrue(result.endswith('.json'))
        self.assertEqual(Path(result).parent, self.save.datadir)

    def test_custom_prefix_in_auto_filename(self):
        result = self.save.toJson([1], prefix='traps')
        self.assertTrue(Path(result).name.startswith('traps_'))

    def test_a_file_that_cannot_be_written_is_an_error(self):
        with self.assertRaises(OSError):
            self.save.toJson([], str(self.home / 'no' / 'such' / 'x.json'))


class TestFromJson(_Base):

    def test_reads_what_was_written(self):
        data = {'traps': [{'x': 1.5, 'phase': 0.25}]}
        path = self.save.toJson(data, str(self.home / 'rt.json'))
        self.assertEqual(self.save.fromJson(path), data)

    def test_a_file_that_is_missing_is_an_error(self):
        with self.assertRaises(OSError):
            self.save.fromJson(str(self.home / 'missing.json'))

    def test_a_file_that_is_not_json_is_an_error(self):
        path = self.home / 'bad.json'
        path.write_text('not json at all')
        with self.assertRaises(ValueError):
            self.save.fromJson(str(path))


if __name__ == '__main__':
    unittest.main()
