'''Unit tests for QImageFile.'''
import unittest

import numpy as np
from pyqtgraph import ImageItem
from pyqtgraph.Qt import QtGui, QtTest

from QHOT.lib.QImageFile import QImageFile

try:
    from filefixtures import FileCase
except ImportError:  # run from the root of the repository
    from tests.filefixtures import FileCase


class ImageCase(FileCase):

    def setUp(self):
        super().setUp()
        self.image = (np.arange(24 * 32) % 251).astype(np.uint8)
        self.image = self.image.reshape(24, 32)
        self.file = QImageFile(
            'hologram',
            prefix='holo',
            source=lambda: self.image,
            files=self.files,
            parent=self.window,
        )
        self.status = QtTest.QSignalSpy(self.file.status)

    def message(self) -> str:
        return self.status[len(self.status) - 1][0]

    def pixels(self, path) -> np.ndarray:
        image = QtGui.QImage(str(path))
        rows, columns = range(image.height()), range(image.width())
        return np.array([[QtGui.qGray(image.pixel(x, y)) for x in columns]
                         for y in rows])


class TestSave(ImageCase):

    def test_it_writes_a_png_with_a_timestamped_name(self):
        self.file.save()
        (path,) = self.written()
        self.assertTrue(path.name.startswith('holo_'))
        self.assertEqual(path.suffix, '.png')

    def test_the_file_holds_the_image(self):
        self.file.save()
        (path,) = self.written()
        np.testing.assert_array_equal(self.pixels(path), self.image)

    def test_the_image_is_the_one_there_is_at_the_time(self):
        self.file.save()
        self.image = self.image[::-1].copy()
        self.file.save()
        first, second = self.written()
        self.assertFalse(np.array_equal(self.pixels(first),
                                        self.pixels(second)))

    def test_it_says_where_it_saved(self):
        self.file.save()
        (path,) = self.written()
        self.assertEqual(self.message(), f'Saved hologram as {path}')

    def test_an_image_that_cannot_be_saved_is_reported_not_raised(self):
        self.image = np.zeros((4, 4), dtype=np.float64)    # not 8-bit
        with self.assertLogs('QHOT.lib.QFileAction', level='ERROR'):
            self.file.save()
        self.assertTrue(self.message().startswith('Could not save hologram'))
        self.assertEqual(self.written(), [])

    def test_an_image_item_with_no_image_is_reported_not_raised(self):
        # the exporter of pyqtgraph raises a plain Exception for this
        self.image = ImageItem()
        with self.assertLogs('QHOT.lib.QFileAction', level='ERROR'):
            self.file.save()
        self.assertTrue(self.message().startswith('Could not save hologram'))


class TestSaveAs(ImageCase):

    def test_it_writes_the_file_that_was_chosen(self):
        path = self.data / 'chosen.png'
        with self.answering('getSaveFileName', path):
            self.file.saveAs()
        np.testing.assert_array_equal(self.pixels(path), self.image)
        self.assertEqual(self.message(), f'Saved hologram as {path}')

    def test_a_canceled_dialog_writes_nothing(self):
        with self.answering('getSaveFileName'):
            self.file.saveAs()
        self.assertEqual(self.written(), [])
        self.assertEqual(self.message(), 'Save hologram canceled')

    def test_the_dialog_suggests_a_name_and_offers_the_image_types(self):
        with self.answering('getSaveFileName') as dialog:
            self.file.saveAs()
        args = dialog.call_args.args
        self.assertIs(args[0], self.window)
        self.assertIn('holo_', args[2])
        self.assertTrue(args[2].endswith('.png'))
        for kind in ('png', 'jpg', 'tif'):
            self.assertIn(kind, args[3])

    def test_a_file_that_cannot_be_written_is_reported(self):
        path = self.home / 'no' / 'such' / 'x.png'
        with self.answering('getSaveFileName', path):
            with self.assertLogs('QHOT.lib.QFileAction', level='ERROR'):
                self.file.saveAs()
        self.assertTrue(self.message().startswith('Could not save hologram'))


if __name__ == '__main__':
    unittest.main()
