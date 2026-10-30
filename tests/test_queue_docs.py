'''The documentation of the task queue is true.

A person writes a queue from what the documentation says, so the example
must open, and every task and every parameter must be in the page.
'''
import re
import unittest
from pathlib import Path

from pyqtgraph.Qt import QtWidgets

import QHOT.tasks
from QHOT.lib.QSaveFile import QSaveFile
from QHOT.lib.tasks.QTask import QTask

try:
    from taskmanagers import manager_for, program_tasks
except ImportError:  # run from the root of the repository
    from tests.taskmanagers import manager_for, program_tasks

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

DOCS = Path(__file__).resolve().parent.parent / 'docs'


class Screen:
    class rendered:
        @staticmethod
        def connect(slot):
            pass


class TestTheExample(unittest.TestCase):

    def setUp(self):
        self.table = QSaveFile.readToml(str(DOCS / 'examples' / 'queue.toml'))

    def test_it_is_a_list_of_tasks(self):
        self.assertEqual(list(self.table), ['tasks'])
        self.assertGreater(len(self.table['tasks']), 5)

    def test_every_task_in_it_exists(self):
        for entry in self.table['tasks']:
            self.assertIn(entry['type'], program_tasks())

    def test_the_manager_takes_it(self):
        manager = manager_for(Screen())
        manager.load(self.table['tasks'])
        names = [type(t).__name__ for t in manager.scheduled]
        self.assertEqual(names, [e['type'] for e in self.table['tasks']])

    def test_what_it_says_is_what_the_tasks_have(self):
        manager = manager_for(Screen())
        manager.load(self.table['tasks'])
        by_type = {type(t).__name__: t for t in manager.scheduled}
        self.assertEqual(by_type['Delay'].frames, 60)
        self.assertEqual(by_type['MoveTraps'].dx, 10.0)
        self.assertEqual(by_type['Repeat'].n, 20)
        self.assertEqual(by_type['StartRecording'].filename, 'approach.mkv')


class TestThePage(unittest.TestCase):

    def setUp(self):
        self.page = (DOCS / 'queues.rst').read_text()

    def test_it_includes_the_example(self):
        self.assertIn('examples/queue.toml', self.page)

    def test_every_task_is_described(self):
        for name in program_tasks():
            with self.subTest(name):
                self.assertIn(f'``{name}``', self.page)

    def test_every_parameter_of_every_task_is_described(self):
        for name, cls in program_tasks().items():
            for parameter in cls.parameters:
                key = parameter['name']
                with self.subTest(f'{name}.{key}'):
                    self.assertRegex(self.page, rf'``{re.escape(key)}``')

    def test_the_page_names_no_task_that_does_not_exist(self):
        table = self.page[self.page.index('The tasks'):
                          self.page.index('When something is wrong')]
        named = set(re.findall(r'^   \* - ``(\w+)``', table, re.M))
        named.discard('type')                   # the head of the column
        self.assertEqual(named, set(program_tasks()))


if __name__ == '__main__':
    unittest.main()
