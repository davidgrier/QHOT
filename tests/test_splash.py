'''Unit tests for the splash screen.'''
import unittest
from unittest.mock import patch

import numpy as np
from pyqtgraph.Qt import QtGui, QtWidgets

import importlib
from QHOT.lib.splash import SIZE, hologram, say, splash
_splash = importlib.import_module('QHOT.lib.splash')

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def pixels(image: QtGui.QImage) -> np.ndarray:
    '''Return an RGB image as an array.'''
    ptr = image.constBits()
    ptr.setsize(image.sizeInBytes())
    rows = np.frombuffer(ptr, dtype=np.uint8).reshape(
        image.height(), image.bytesPerLine())
    return rows[:, :3 * image.width()].reshape(
        image.height(), image.width(), 3).copy()  # the image may not last


class TestTheHologram(unittest.TestCase):

    def test_size(self):
        image = hologram(120, 60)
        self.assertEqual((image.width(), image.height()), (120, 60))

    def test_is_rgb(self):
        self.assertEqual(hologram(40, 20).format(),
                         QtGui.QImage.Format.Format_RGB888)

    def test_has_fringes(self):
        rgb = pixels(hologram(200, 100))
        self.assertGreater(rgb[..., 0].std(), 2.)

    def test_is_purple(self):
        red, green, blue = pixels(hologram(200, 100)).reshape(-1, 3).mean(0)
        self.assertGreater(blue, red)
        self.assertGreater(red, green)

    def test_the_corners_are_darker_than_the_middle(self):
        rgb = pixels(hologram(400, 200)).astype(float).sum(axis=2)
        self.assertLess(rgb[-1, -1], rgb[100:140, 150:250].mean())

    def test_is_the_same_each_time(self):
        a, b = pixels(hologram(80, 40)), pixels(hologram(80, 40))
        self.assertTrue(np.array_equal(a, b))


class TestTheSplashScreen(unittest.TestCase):

    def test_is_a_splash_screen(self):
        self.assertIsInstance(splash(), QtWidgets.QSplashScreen)

    def test_is_sharp_on_a_high_resolution_display(self):
        pixmap = splash().pixmap()
        self.assertEqual(pixmap.devicePixelRatio(), 2.)
        self.assertEqual((pixmap.width(), pixmap.height()),
                         (2 * SIZE[0], 2 * SIZE[1]))

    def test_the_text_is_drawn_over_the_fringes(self):
        plain = pixels(hologram(2 * SIZE[0], 2 * SIZE[1]))
        drawn = pixels(splash().pixmap().toImage().convertToFormat(
            QtGui.QImage.Format.Format_RGB888))
        self.assertGreater(np.abs(plain.astype(int) - drawn).max(), 100)

    def test_the_text_is_at_the_bottom_right(self):
        plain = pixels(hologram(2 * SIZE[0], 2 * SIZE[1])).astype(int)
        drawn = pixels(splash().pixmap().toImage().convertToFormat(
            QtGui.QImage.Format.Format_RGB888)).astype(int)
        changed = np.argwhere(np.abs(plain - drawn).max(axis=2) > 60)
        self.assertGreater(changed[:, 0].min(), SIZE[1])        # lower half
        self.assertGreater(changed[:, 1].min(), SIZE[0] * 0.8)  # right

    def test_uses_the_version_of_qhot(self):
        with patch.object(_splash, '__version__', '9.8.7'):
            with patch.object(QtGui.QPainter, 'drawText') as draw:
                splash()
        texts = [call.args[-1] for call in draw.call_args_list]
        self.assertTrue(any('9.8.7' in str(t) for t in texts), texts)

    def test_leaves_out_a_version_that_is_not_known(self):
        with patch.object(_splash, '__version__', 'unknown'):
            with patch.object(QtGui.QPainter, 'drawText') as draw:
                splash()
        texts = [str(call.args[-1]) for call in draw.call_args_list]
        self.assertFalse(any('unknown' in t for t in texts), texts)

    def test_takes_a_name(self):
        with patch.object(QtGui.QPainter, 'drawText') as draw:
            splash(title='Something', version='1')
        texts = [str(call.args[-1]) for call in draw.call_args_list]
        self.assertIn('Something', texts)


class TestSay(unittest.TestCase):

    def test_shows_the_message(self):
        screen = splash()
        say(screen, 'Opening the camera...')
        self.assertEqual(screen.message(), 'Opening the camera...')

    def test_replaces_the_message(self):
        screen = splash()
        say(screen, 'one')
        say(screen, 'two')
        self.assertEqual(screen.message(), 'two')

    def test_lets_the_application_repaint(self):
        with patch.object(QtWidgets.QApplication,
                          'processEvents') as events:
            say(splash(), 'x')
        events.assert_called_once()


if __name__ == '__main__':
    unittest.main()
