'''Unit tests for QSaveFile.'''
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
from pyqtgraph import ImageItem
from pyqtgraph.Qt import QtCore, QtWidgets

import importlib as _importlib
from QHOT.lib.QSaveFile import QSaveFile

try:
    from taskmanagers import manager_for
except ImportError:  # run from the root of the repository
    from tests.taskmanagers import manager_for
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

    def setUp(self):
        super().setUp()
        self.array = np.zeros((10, 10), dtype=np.uint8)

    def test_calls_make_qimage(self):
        with patch.object(_qsavefile_mod, 'pg') as mock_pg:
            self.save.image(self.array, filename='out.png')
        mock_pg.makeQImage.assert_called_once()

    def test_passes_array_to_make_qimage(self):
        with patch.object(_qsavefile_mod, 'pg') as mock_pg:
            self.save.image(self.array, filename='out.png')
        arg = mock_pg.makeQImage.call_args[0][0]
        np.testing.assert_array_equal(arg, self.array)

    def test_calls_save_with_filename(self):
        with patch.object(_qsavefile_mod, 'pg') as mock_pg:
            self.save.image(self.array, filename='out.png')
        mock_pg.makeQImage.return_value.save.assert_called_once_with('out.png')

    def test_returns_provided_filename(self):
        with patch.object(_qsavefile_mod, 'pg'):
            result = self.save.image(self.array, filename='out.png')
        self.assertEqual(result, 'out.png')

    def test_auto_generates_filename_when_none(self):
        with patch.object(_qsavefile_mod, 'pg'):
            result = self.save.image(self.array)
        self.assertTrue(result.endswith('.png'))
        self.assertIn(str(self.save.datadir), result)

    def test_custom_prefix_in_auto_filename(self):
        with patch.object(_qsavefile_mod, 'pg'):
            result = self.save.image(self.array, prefix='hologram')
        self.assertIn('hologram', Path(result).name)


# ---------------------------------------------------------------------------
# imageAs()
# ---------------------------------------------------------------------------

class TestImageAs(_Base):

    def setUp(self):
        super().setUp()
        self.array = np.zeros((10, 10), dtype=np.uint8)

    def _patch_dialog(self, chosen):
        return patch.object(_qsavefile_mod.QtWidgets.QFileDialog,
                            'getSaveFileName',
                            return_value=(chosen, 'PNG Image (*.png)'))

    def test_canceled_returns_empty_string(self):
        with self._patch_dialog(''):
            result = self.save.imageAs(self.array)
        self.assertEqual(result, '')

    def test_confirmed_delegates_to_image(self):
        with self._patch_dialog('chosen.png'):
            with patch.object(
                self.save,
                'image',
                return_value='chosen.png',
            ) as mock_image:
                self.save.imageAs(self.array)
        mock_image.assert_called_once_with(self.array, filename='chosen.png')

    def test_confirmed_returns_filename(self):
        with self._patch_dialog('chosen.png'):
            with patch.object(self.save, 'image', return_value='chosen.png'):
                result = self.save.imageAs(self.array)
        self.assertEqual(result, 'chosen.png')

    def test_default_suggestion_contains_prefix(self):
        captured = {}

        def fake_dialog(parent, title, default, filters):
            captured['default'] = default
            return ('', '')

        with patch.object(
            _qsavefile_mod.QtWidgets.QFileDialog,
            'getSaveFileName',
            side_effect=fake_dialog,
        ):
            self.save.imageAs(self.array, prefix='hologram')
        self.assertIn('hologram', Path(captured['default']).name)


# ---------------------------------------------------------------------------
# toToml() / fromToml()
# ---------------------------------------------------------------------------

class TestToToml(_Base):

    def test_creates_file(self):
        qobj = _FakeQObj()
        qobj._settings = {'x': 1.0}
        self.save.toToml(qobj)
        self.assertTrue(Path(self.save.configname(qobj)).exists())

    def test_returns_configname(self):
        qobj = _FakeQObj()
        result = self.save.toToml(qobj)
        self.assertEqual(result, self.save.configname(qobj))

    def test_file_contains_settings(self):
        import tomlkit
        qobj = _FakeQObj()
        qobj._settings = {'alpha': 1.5, 'label': 'test'}
        self.save.toToml(qobj)
        with open(self.save.configname(qobj), encoding='utf-8') as f:
            doc = tomlkit.load(f)
        self.assertAlmostEqual(float(doc['settings']['alpha']), 1.5)
        self.assertEqual(doc['settings']['label'], 'test')

    def test_file_is_utf8(self):
        qobj = _FakeQObj()
        qobj._settings = {'note': 'café'}
        self.save.toToml(qobj)
        with open(self.save.configname(qobj), encoding='utf-8') as f:
            content = f.read()
        self.assertIn('café', content)


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

class TestQueueSave(_Base):

    def _make_manager(self):
        from pyqtgraph.Qt import QtCore as _QtCore
        from QHOT.lib.tasks.QTaskManager import QTaskManager

        class _Screen(_QtCore.QObject):
            rendered = _QtCore.pyqtSignal()

        screen = _Screen()
        mgr = manager_for(screen)
        return mgr

    def test_queue_creates_file(self):
        import QHOT.tasks
        from QHOT.tasks.Delay import Delay
        mgr = self._make_manager()
        mgr.register(Delay(frames=5))   # active
        mgr.register(Delay(frames=10))  # queued
        filename = self.save.queue(mgr)
        self.assertTrue(Path(filename).exists())

    def test_queue_saves_pending_tasks_including_active(self):
        import QHOT.tasks
        from QHOT.tasks.Delay import Delay
        mgr = self._make_manager()
        mgr.register(Delay(frames=5))   # activated (not yet stepped — in queued)
        mgr.register(Delay(frames=10))  # queued
        filename = self.save.queue(mgr)
        with open(filename) as f:
            data = json.load(f)
        # Both tasks saved: activated-not-stepped task is included in queued
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]['frames'], 5)
        self.assertEqual(data[1]['frames'], 10)

    def test_queue_saves_to_specified_filename(self):
        import QHOT.tasks
        from QHOT.tasks.ClearTraps import ClearTraps
        mgr = self._make_manager()
        dest = str(self.save.datadir / 'myqueue.json')
        mgr.register(ClearTraps())
        self.save.queue(mgr, dest)
        self.assertTrue(Path(dest).exists())

    def test_queue_returns_filename(self):
        mgr = self._make_manager()
        result = self.save.queue(mgr)
        self.assertTrue(result.endswith('.json'))

    def test_queue_empty_manager_saves_empty_list(self):
        mgr = self._make_manager()
        filename = self.save.queue(mgr)
        with open(filename) as f:
            data = json.load(f)
        self.assertEqual(data, [])


class TestQueueAs(_Base):

    def _make_manager(self):
        from pyqtgraph.Qt import QtCore as _QtCore
        from QHOT.lib.tasks.QTaskManager import QTaskManager

        class _Screen(_QtCore.QObject):
            rendered = _QtCore.pyqtSignal()

        return manager_for(_Screen())

    def _patch_dialog(self, chosen):
        return patch.object(_qsavefile_mod.QtWidgets.QFileDialog,
                            'getSaveFileName',
                            return_value=(chosen, 'Task Queue (*.json)'))

    def test_canceled_returns_empty_string(self):
        mgr = self._make_manager()
        with self._patch_dialog(''):
            result = self.save.queueAs(mgr)
        self.assertEqual(result, '')

    def test_confirmed_delegates_to_queue(self):
        mgr = self._make_manager()
        with self._patch_dialog('chosen.json'):
            with patch.object(
                self.save,
                'queue',
                return_value='chosen.json',
            ) as mock_q:
                self.save.queueAs(mgr)
        mock_q.assert_called_once_with(mgr, 'chosen.json')

    def test_confirmed_returns_filename(self):
        mgr = self._make_manager()
        with self._patch_dialog('chosen.json'):
            with patch.object(self.save, 'queue', return_value='chosen.json'):
                result = self.save.queueAs(mgr)
        self.assertEqual(result, 'chosen.json')


class TestOpenQueue(_Base):

    def _make_manager(self):
        from pyqtgraph.Qt import QtCore as _QtCore
        from QHOT.lib.tasks.QTaskManager import QTaskManager

        class _Screen(_QtCore.QObject):
            rendered = _QtCore.pyqtSignal()

        return manager_for(_Screen())

    def _write_queue(self, task_dicts):
        path = self.save.datadir / 'test_queue.json'
        with open(path, 'w') as f:
            json.dump(task_dicts, f)
        return str(path)

    def _patch_dialog(self, chosen):
        return patch.object(_qsavefile_mod.QtWidgets.QFileDialog,
                            'getOpenFileName',
                            return_value=(chosen, 'Task Queue (*.json)'))

    def test_canceled_returns_empty_string(self):
        mgr = self._make_manager()
        with self._patch_dialog(''):
            result = self.save.openQueue(mgr)
        self.assertEqual(result, '')

    def test_canceled_does_not_change_manager(self):
        mgr = self._make_manager()
        with self._patch_dialog(''):
            self.save.openQueue(mgr)
        self.assertIsNone(mgr.active)

    def test_confirmed_calls_manager_load(self):
        import QHOT.tasks
        mgr = self._make_manager()
        path = self._write_queue([{'type': 'ClearTraps', 'delay': 0}])
        with self._patch_dialog(path):
            with patch.object(mgr, 'load') as mock_load:
                self.save.openQueue(mgr)
        mock_load.assert_called_once()

    def test_confirmed_returns_filename(self):
        import QHOT.tasks
        mgr = self._make_manager()
        path = self._write_queue([{'type': 'ClearTraps', 'delay': 0}])
        with self._patch_dialog(path):
            with patch.object(mgr, 'load'):
                result = self.save.openQueue(mgr)
        self.assertEqual(result, path)

    def test_round_trip_preserves_task_type_and_params(self):
        import QHOT.tasks
        from QHOT.tasks.Delay import Delay
        mgr_save = self._make_manager()
        mgr_load = self._make_manager()
        mgr_save.register(Delay(frames=5))   # activated (in queued)
        mgr_save.register(Delay(frames=42))  # queued — both saved
        filename = self.save.queue(mgr_save)
        with self._patch_dialog(filename):
            self.save.openQueue(mgr_load)
        # first saved task becomes activeRaw in loaded manager
        self.assertEqual(mgr_load.activeRaw.frames, 5)


if __name__ == '__main__':
    unittest.main()
