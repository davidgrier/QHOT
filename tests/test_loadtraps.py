'''Unit tests for LoadTraps.'''
import json
import tempfile
import unittest
from unittest.mock import MagicMock

from qtpy import QtWidgets

from QHOT.lib.QSaveFile import QSaveFile
from QHOT.lib.tasks.QTask import QTask
from QHOT.tasks.LoadTraps import LoadTraps

try:
    from taskmanagers import attached
except ImportError:  # run from the root of the repository
    from tests.taskmanagers import attached

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _run(task):
    task._start()
    task._step()


class TestLoadTrapsInit(unittest.TestCase):

    def test_registered_in_registry(self):
        self.assertIn('LoadTraps', QTask._registry)

    def test_duration_is_zero(self):
        self.assertEqual(LoadTraps().duration, 0)

    def test_default_filename_empty(self):
        self.assertEqual(LoadTraps().filename, '')

    def test_explicit_filename_stored(self):
        task = LoadTraps(filename='/tmp/traps.json')
        self.assertEqual(task.filename, '/tmp/traps.json')

    def test_parameters_declared(self):
        names = [p['name'] for p in LoadTraps.parameters]
        self.assertIn('filename', names)


class TestLoadTrapsExecution(unittest.TestCase):

    def setUp(self):
        self.overlay = MagicMock()
        self.trap_data = [{'type': 'QTweezer', 'x': 10., 'y': 20., 'z': 0.}]
        self.tmp = tempfile.NamedTemporaryFile(
            suffix='.json', mode='w', delete=False)
        json.dump(self.trap_data, self.tmp)
        self.tmp.close()

    def test_from_list_called_with_file_contents(self):
        task = self.attach(LoadTraps(filename=self.tmp.name))
        _run(task)
        self.overlay.fromList.assert_called_once_with(self.trap_data)

    def attach(self, task):
        return attached(task, overlay=self.overlay, save=QSaveFile)

    def test_empty_filename_fails_and_leaves_the_traps(self):
        task = self.attach(LoadTraps(filename=''))
        _run(task)
        self.assertEqual(task.state, QTask.State.FAILED)
        self.overlay.fromList.assert_not_called()

    def test_a_file_that_is_not_there_fails_and_leaves_the_traps(self):
        task = self.attach(LoadTraps(filename=self.tmp.name + '.missing'))
        _run(task)
        self.assertEqual(task.state, QTask.State.FAILED)
        self.overlay.fromList.assert_not_called()

    def test_completes_after_one_step(self):
        task = self.attach(LoadTraps(filename=self.tmp.name))
        _run(task)
        self.assertEqual(task.state, QTask.State.COMPLETED)


class TestLoadTrapsSerialization(unittest.TestCase):

    def test_to_dict_includes_type(self):
        self.assertEqual(LoadTraps().toDict()['type'], 'LoadTraps')

    def test_round_trip(self):
        task = LoadTraps(filename='/tmp/traps.json')
        restored = QTask.fromDict(task.toDict())
        self.assertIsInstance(restored, LoadTraps)
        self.assertEqual(restored.filename, '/tmp/traps.json')


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
