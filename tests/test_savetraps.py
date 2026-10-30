'''Unit tests for SaveTraps.'''
import unittest
from unittest.mock import MagicMock

from pyqtgraph.Qt import QtWidgets

from QHOT.lib.tasks.QTask import QTask
from QHOT.tasks.SaveTraps import SaveTraps

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _run(task):
    task._start()
    task._step()


class TestSaveTrapsInit(unittest.TestCase):

    def test_registered_in_registry(self):
        self.assertIn('SaveTraps', QTask._registry)

    def test_duration_is_zero(self):
        self.assertEqual(SaveTraps().duration, 0)

    def test_default_filename_empty(self):
        self.assertEqual(SaveTraps().filename, '')

    def test_explicit_filename_stored(self):
        task = SaveTraps(filename='/tmp/traps.json')
        self.assertEqual(task.filename, '/tmp/traps.json')

    def test_parameters_declared(self):
        names = [p['name'] for p in SaveTraps.parameters]
        self.assertIn('filename', names)


class TestSaveTrapsExecution(unittest.TestCase):

    def setUp(self):
        self.overlay = MagicMock()
        self.save    = MagicMock()

    def test_save_traps_called_with_overlay(self):
        task = SaveTraps(overlay=self.overlay, save=self.save)
        _run(task)
        self.save.traps.assert_called_once()
        args, _ = self.save.traps.call_args
        self.assertIs(args[0], self.overlay)

    def test_explicit_filename_passed(self):
        task = SaveTraps(
            overlay=self.overlay,
            save=self.save,
            filename='/tmp/traps.json',
        )
        _run(task)
        _, kwargs = self.save.traps.call_args
        self.assertEqual(kwargs['filename'], '/tmp/traps.json')

    def test_empty_filename_passes_none(self):
        task = SaveTraps(overlay=self.overlay, save=self.save, filename='')
        _run(task)
        _, kwargs = self.save.traps.call_args
        self.assertIsNone(kwargs['filename'])

    def test_completes_after_one_step(self):
        task = SaveTraps(overlay=self.overlay, save=self.save)
        _run(task)
        self.assertEqual(task.state, QTask.State.COMPLETED)


class TestSaveTrapsSerialization(unittest.TestCase):

    def test_to_dict_includes_type(self):
        self.assertEqual(SaveTraps().toDict()['type'], 'SaveTraps')

    def test_round_trip(self):
        task = SaveTraps(filename='/tmp/traps.json')
        restored = QTask.fromDict(task.toDict())
        self.assertIsInstance(restored, SaveTraps)
        self.assertEqual(restored.filename, '/tmp/traps.json')


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
