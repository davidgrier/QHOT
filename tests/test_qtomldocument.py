'''Unit tests for QTomlDocument: a file that a person can write.'''
import tomllib
import unittest

from pyqtgraph.Qt import QtTest

from QHOT.lib.QTomlDocument import QTomlDocument

try:
    from filefixtures import FileCase
except ImportError:  # run from the root of the repository
    from tests.filefixtures import FileCase

HEADER = 'A queue of tasks.\nEdit it by hand.'


class TomlCase(FileCase):

    def setUp(self):
        super().setUp()
        self.content = [{'type': 'Delay', 'frames': 30},
                        {'type': 'Move', 'x': 1.5, 'y': 2.0}]
        self.loaded = []
        self.document = QTomlDocument(
            'queue',
            'Task Queue',
            root='tasks',
            header=HEADER,
            dump=lambda: self.content,
            load=self.loaded.append,
            files=self.files,
            parent=self.window,
        )
        self.status = QtTest.QSignalSpy(self.document.status)

    def message(self) -> str:
        return self.status[len(self.status) - 1][0]

    def hand(self, text: str):
        '''A file that a person wrote.'''
        path = self.data / 'by_hand.toml'
        path.write_text(text)
        return path

    def open(self, path):
        with self.answering('getOpenFileName', path):
            self.document.open()


class TestSave(TomlCase):

    def test_it_writes_a_toml_file_with_a_timestamped_name(self):
        self.document.save()
        (path,) = self.written()
        self.assertTrue(path.name.startswith('queue_'))
        self.assertEqual(path.suffix, '.toml')

    def test_the_tasks_are_tables_that_a_person_can_read(self):
        self.document.save()
        (path,) = self.written()
        text = path.read_text()
        self.assertEqual(text.count('[[tasks]]'), 2)
        self.assertIn('type = "Delay"', text)
        self.assertIn('frames = 30', text)
        self.assertEqual(tomllib.loads(text), {'tasks': self.content})

    def test_the_file_says_at_the_top_what_it_is(self):
        self.document.save()
        (path,) = self.written()
        lines = path.read_text().splitlines()
        self.assertEqual(lines[:2], ['# A queue of tasks.', '# Edit it by hand.'])
        self.assertEqual(lines[2], '')

    def test_it_says_where_it_saved(self):
        self.document.save()
        self.assertEqual(self.message(),
                         f'Saved queue to {self.document.filename}')

    def test_save_as_offers_the_toml_type(self):
        with self.answering('getSaveFileName') as dialog:
            self.document.saveAs()
        args = dialog.call_args.args
        self.assertTrue(args[2].endswith('.toml'))
        self.assertEqual(args[3], 'Task Queue (*.toml)')

    def test_an_empty_queue_is_a_file_with_no_tasks(self):
        self.content = []
        self.document.save()
        self.assertEqual(self.written()[0].suffix, '.toml')


class TestOpen(TomlCase):

    def test_a_file_that_was_saved_is_read_back(self):
        self.document.save()
        (path,) = self.written()
        self.open(path)
        self.assertEqual(self.loaded, [self.content])
        self.assertEqual(self.message(), f'Opened queue from {path}')

    def test_a_file_that_a_person_wrote(self):
        path = self.hand('''
            # my experiment
            [[tasks]]
            type = "Delay"      # let the sample settle
            frames = 60

            [[tasks]]
            type = "Move"
            x = 320
            y = 240.5
        '''.replace('            ', ''))
        self.open(path)
        self.assertEqual(self.loaded, [[{'type': 'Delay', 'frames': 60},
                                        {'type': 'Move', 'x': 320,
                                         'y': 240.5}]])

    def test_the_dialog_offers_the_toml_type(self):
        with self.answering('getOpenFileName') as dialog:
            self.document.open()
        self.assertEqual(dialog.call_args.args[3], 'Task Queue (*.toml)')

    def test_a_file_with_no_tasks_says_what_is_missing(self):
        path = self.hand('title = "nothing here"\n')
        with self.assertLogs('QHOT.lib.QFileAction', level='ERROR'):
            self.open(path)
        self.assertIn('no [[tasks]] tables', self.message())
        self.assertEqual(self.loaded, [])
        self.assertIsNone(self.document.filename)

    def test_a_fault_in_the_toml_says_where_it_is(self):
        path = self.hand('[[tasks]]\ntype = "Delay"\nframes = = 30\n')
        with self.assertLogs('QHOT.lib.QFileAction', level='ERROR'):
            self.open(path)
        self.assertTrue(self.message().startswith('Could not open queue'))
        self.assertIn('line 3', self.message())
        self.assertEqual(self.loaded, [])


if __name__ == '__main__':
    unittest.main()
