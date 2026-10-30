'''What every task must satisfy to be a part of the program.

QHOT is a finished program, not a library: a developer who adds a task
finds out here, when the tests run, that it does not fit, and not when a
user picks it in the middle of an experiment.  Every task that is
registered is taken through the path that a user takes: it is queued from
the menu, it is given what it works with, it is shown in the interface,
and it is saved in a queue file and read back.
'''
import unittest
from unittest.mock import MagicMock

from pyqtgraph.Qt import QtCore, QtWidgets

import QHOT.tasks
from QHOT.lib.tasks.QTask import QTask
from QHOT.lib.tasks.QTaskTree import QTaskTree
from QHOT.lib.tasks.QueueMenu import QueueMenu

try:
    from taskmanagers import RESOURCES, Screen, manager_for
except ImportError:  # run from the root of the repository
    from tests.taskmanagers import RESOURCES, Screen, manager_for

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class ContractCase(unittest.TestCase):

    def setUp(self):
        self.manager = manager_for(Screen())
        self.manager.cgh.xc, self.manager.cgh.yc = 320., 240.
        self.menu = QueueMenu()
        self.menu.manager = self.manager

    def queue(self, name: str) -> QTask:
        '''Queue a task as a user does, from the menu.'''
        self.manager.clear()
        self.menu._onTaskSelected(name)
        self.assertTrue(self.manager.scheduled, f'{name} was not queued')
        return self.manager.scheduled[-1]


class TestEveryTask(ContractCase):

    def test_the_registry_holds_the_tasks_of_the_program(self):
        self.assertGreaterEqual(len(QTask._registry), 10)

    def test_it_can_be_queued_from_the_menu(self):
        for name, cls in QTask._registry.items():
            with self.subTest(name):
                self.assertIsInstance(self.queue(name), cls)

    def test_it_is_given_everything_that_the_manager_has(self):
        for name in QTask._registry:
            with self.subTest(name):
                task = self.queue(name)
                for resource in RESOURCES:
                    self.assertIs(
                        getattr(task, resource),
                        getattr(self.manager, resource),
                        resource,
                    )
                self.assertIs(task.manager, self.manager)

    def test_the_interface_can_show_it(self):
        for name in QTask._registry:
            with self.subTest(name):
                tree = QTaskTree(self.queue(name))
                self.assertIsNotNone(tree.task)

    def test_it_survives_a_queue_file(self):
        for name in QTask._registry:
            with self.subTest(name):
                task = self.queue(name)
                again = QTask.fromDict(task.toDict())
                self.assertIs(type(again), type(task))
                self.assertEqual(again.toDict(), task.toDict())

    def test_a_task_that_is_loaded_works_as_one_that_is_queued(self):
        for name in QTask._registry:
            with self.subTest(name):
                task = self.queue(name)
                saved = [task.toDict()]
                self.manager.clear()
                self.manager.load(saved)
                loaded = self.manager.scheduled[-1]
                for resource in RESOURCES:
                    self.assertIs(
                        getattr(loaded, resource),
                        getattr(self.manager, resource),
                        resource,
                    )


class TestWhatTheTasksDoWithTheirResources(ContractCase):

    def test_a_tweezer_is_added_on_the_axis_of_the_cgh(self):
        task = self.queue('AddTweezer')
        task.initialize()
        pos = self.manager.overlay.addTrap.call_args.args[0]
        self.assertEqual((pos.x(), pos.y()), (320., 240.))

    def test_a_snapshot_is_of_the_live_image(self):
        task = self.queue('Snapshot')
        task.initialize()
        self.manager.save.image.assert_called_once()
        self.assertIs(
            self.manager.save.image.call_args.args[0],
            self.manager.image,
        )

    def test_traps_are_saved_from_the_overlay_with_the_file_helper(self):
        task = self.queue('SaveTraps')
        task.initialize()
        self.manager.save.traps.assert_called_once()
        self.assertIs(
            self.manager.save.traps.call_args.args[0],
            self.manager.overlay,
        )

    def test_traps_are_cleared_on_the_overlay(self):
        task = self.queue('ClearTraps')
        task.initialize()
        self.manager.overlay.clearTraps.assert_called_once()


if __name__ == '__main__':
    unittest.main()
