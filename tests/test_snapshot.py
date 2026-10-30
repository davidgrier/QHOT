'''Unit tests for Snapshot.'''
import unittest
from unittest.mock import MagicMock, call

from pyqtgraph.Qt import QtWidgets

from QHOT.lib.tasks.QTask import QTask
from QHOT.tasks.Snapshot import Snapshot

try:
    from taskmanagers import attached
except ImportError:  # run from the root of the repository
    from tests.taskmanagers import attached

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _run(task):
    task._start()
    task._step()


class TestSnapshotInit(unittest.TestCase):

    def test_registered_in_registry(self):
        self.assertIn('Snapshot', QTask._registry)

    def test_duration_is_zero(self):
        self.assertEqual(attached(Snapshot(), image=MagicMock()).duration, 0)

    def test_default_filename_empty(self):
        self.assertEqual(attached(Snapshot(), image=MagicMock()).filename, '')

    def test_default_prefix(self):
        self.assertEqual(attached(
            Snapshot(),
            image=MagicMock(),
        ).prefix, 'snapshot')

    def test_explicit_filename_stored(self):
        task = attached(Snapshot(filename='/tmp/snap.png'), image=MagicMock())
        self.assertEqual(task.filename, '/tmp/snap.png')

    def test_explicit_prefix_stored(self):
        task = attached(Snapshot(prefix='frame'), image=MagicMock())
        self.assertEqual(task.prefix, 'frame')

    def test_parameters_declared(self):
        names = [p['name'] for p in Snapshot.parameters]
        self.assertIn('filename', names)
        self.assertIn('prefix',   names)


class TestSnapshotExecution(unittest.TestCase):

    def setUp(self):
        self.image = MagicMock()
        self.save  = MagicMock()

    def test_save_image_called_with_image_item(self):
        task = attached(Snapshot(), image=self.image, save=self.save)
        _run(task)
        self.save.image.assert_called_once()
        args, kwargs = self.save.image.call_args
        self.assertIs(args[0], self.image)

    def test_explicit_filename_passed_to_save(self):
        task = attached(
            Snapshot(filename='/tmp/snap.png'),
            image=self.image,
            save=self.save,
        )
        _run(task)
        _, kwargs = self.save.image.call_args
        self.assertEqual(kwargs['filename'], '/tmp/snap.png')

    def test_empty_filename_passes_none(self):
        task = attached(
            Snapshot(filename=''),
            image=self.image,
            save=self.save,
        )
        _run(task)
        _, kwargs = self.save.image.call_args
        self.assertIsNone(kwargs['filename'])

    def test_prefix_passed_to_save(self):
        task = attached(
            Snapshot(prefix='frame'),
            image=self.image,
            save=self.save,
        )
        _run(task)
        _, kwargs = self.save.image.call_args
        self.assertEqual(kwargs['prefix'], 'frame')

    def test_completes_after_one_step(self):
        task = attached(Snapshot(), image=self.image, save=self.save)
        _run(task)
        self.assertEqual(task.state, QTask.State.COMPLETED)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
