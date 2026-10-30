'''Unit tests for QDocument.'''
import json
import unittest
from unittest.mock import MagicMock

from pyqtgraph.Qt import QtGui, QtTest

from QHOT.lib.QDocument import QDocument

try:
    from filefixtures import FileCase
except ImportError:  # run from the root of the repository
    from tests.filefixtures import FileCase


class DocumentCase(FileCase):

    def setUp(self):
        super().setUp()
        self.content = [{'type': 'QTweezer', 'x': 1.5}]
        self.loaded = []
        self.document = QDocument(
            'traps',
            'Trap Configuration',
            dump=lambda: self.content,
            load=self.loaded.append,
            files=self.files,
            parent=self.window,
        )
        self.status = QtTest.QSignalSpy(self.document.status)

    def message(self) -> str:
        return self.status[len(self.status) - 1][0]


class TestSave(DocumentCase):

    def test_with_no_file_it_writes_one_with_a_timestamped_name(self):
        self.document.save()
        (path,) = self.written()
        self.assertTrue(path.name.startswith('traps_'))
        self.assertEqual(path.suffix, '.json')
        self.assertEqual(json.loads(path.read_text()), self.content)

    def test_the_file_is_remembered(self):
        self.document.save()
        (path,) = self.written()
        self.assertEqual(self.document.filename, str(path))

    def test_it_saves_to_the_same_file_again(self):
        self.document.save()
        self.content = [{'type': 'QTweezer', 'x': 9.}]
        self.document.save()
        (path,) = self.written()
        self.assertEqual(json.loads(path.read_text()), self.content)

    def test_what_is_saved_is_the_document_as_it_is_then(self):
        self.content = []
        self.document.save()
        self.content = ['later']
        self.document.save()
        (path,) = self.written()
        self.assertEqual(json.loads(path.read_text()), ['later'])

    def test_it_says_where_it_saved(self):
        self.document.save()
        self.assertEqual(self.message(),
                         f'Saved traps to {self.document.filename}')

    def test_a_file_that_cannot_be_written_is_reported_not_raised(self):
        self.document.filename = str(self.home / 'no' / 'such' / 'x.json')
        with self.assertLogs('QHOT.lib.QFileAction', level='ERROR'):
            self.document.save()
        self.assertTrue(self.message().startswith('Could not save traps'))
        self.assertEqual(self.document.filename,
                         str(self.home / 'no' / 'such' / 'x.json'))


class TestSaveAs(DocumentCase):

    def test_it_writes_the_file_that_was_chosen(self):
        path = self.data / 'mine.json'
        with self.answering('getSaveFileName', path):
            self.document.saveAs()
        self.assertEqual(json.loads(path.read_text()), self.content)
        self.assertEqual(self.document.filename, str(path))
        self.assertEqual(self.message(), f'Saved traps to {path}')

    def test_save_then_goes_to_that_file(self):
        path = self.data / 'mine.json'
        with self.answering('getSaveFileName', path):
            self.document.saveAs()
        self.content = ['changed']
        self.document.save()
        self.assertEqual(self.written(), [path])
        self.assertEqual(json.loads(path.read_text()), ['changed'])

    def test_a_canceled_dialog_writes_nothing(self):
        with self.answering('getSaveFileName'):
            self.document.saveAs()
        self.assertEqual(self.written(), [])
        self.assertIsNone(self.document.filename)
        self.assertEqual(self.message(), 'Save traps canceled')

    def test_the_dialog_suggests_a_timestamped_name_and_the_type(self):
        with self.answering('getSaveFileName') as dialog:
            self.document.saveAs()
        args = dialog.call_args.args
        self.assertIs(args[0], self.window)
        self.assertIn('traps_', args[2])
        self.assertEqual(args[3], 'Trap Configuration (*.json)')


class TestOpen(DocumentCase):

    def test_it_loads_what_the_file_holds(self):
        path = self.files.toJson(self.content, str(self.data / 'in.json'))
        with self.answering('getOpenFileName', path):
            self.document.open()
        self.assertEqual(self.loaded, [self.content])
        self.assertEqual(self.document.filename, path)
        self.assertEqual(self.message(), f'Opened traps from {path}')

    def test_save_then_goes_to_the_file_that_was_opened(self):
        path = self.files.toJson(self.content, str(self.data / 'in.json'))
        with self.answering('getOpenFileName', path):
            self.document.open()
        self.content = ['edited']
        self.document.save()
        self.assertEqual(json.loads(open(path).read()), ['edited'])

    def test_a_canceled_dialog_loads_nothing(self):
        with self.answering('getOpenFileName'):
            self.document.open()
        self.assertEqual(self.loaded, [])
        self.assertEqual(self.message(), 'Open traps canceled')

    def test_the_dialog_starts_in_the_data_directory(self):
        with self.answering('getOpenFileName') as dialog:
            self.document.open()
        self.assertEqual(dialog.call_args.args[2], str(self.data))
        self.assertEqual(dialog.call_args.args[3],
                         'Trap Configuration (*.json)')

    def test_what_a_user_chose_may_be_anything(self):
        bad = self.data / 'bad.json'
        bad.write_text('this is not json')
        for name, path in (('missing', self.data / 'missing.json'),
                           ('not json', bad)):
            with self.subTest(name):
                with self.answering('getOpenFileName', path):
                    with self.assertLogs('QHOT.lib.QFileAction',
                                         level='ERROR'):
                        self.document.open()
                self.assertTrue(
                    self.message().startswith('Could not open traps'))
                self.assertIsNone(self.document.filename)

    def test_content_that_the_program_cannot_use_is_reported(self):
        failing = QDocument(
            'traps',
            'Trap Configuration',
            dump=list,
            load=MagicMock(side_effect=KeyError('Unknown trap type')),
            files=self.files,
            parent=self.window,
        )
        status = QtTest.QSignalSpy(failing.status)
        path = self.files.toJson([{'type': 'Strange'}],
                                 str(self.data / 'in.json'))
        with self.answering('getOpenFileName', path):
            with self.assertLogs('QHOT.lib.QFileAction', level='ERROR'):
                failing.open()
        self.assertIn('Unknown trap type', status[0][0])
        self.assertIsNone(failing.filename)


class TestAsASlot(DocumentCase):

    def test_an_action_can_save_the_document(self):
        action = QtGui.QAction('Save', self.window)
        action.triggered.connect(self.document.save)
        action.trigger()
        self.assertEqual(len(self.written()), 1)

    def test_an_action_can_open_a_document(self):
        path = self.files.toJson(self.content, str(self.data / 'in.json'))
        action = QtGui.QAction('Open', self.window)
        action.triggered.connect(self.document.open)
        with self.answering('getOpenFileName', path):
            action.trigger()
        self.assertEqual(self.loaded, [self.content])


if __name__ == '__main__':
    unittest.main()
