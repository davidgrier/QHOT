'''Unit tests for QHOTScreen.'''
import unittest
import numpy as np
from unittest.mock import MagicMock, patch
from pyqtgraph.Qt import QtWidgets, QtCore, QtGui, QtTest
from QHOT.lib.QHOTScreen import QHOTScreen
from QHOT.lib.traps.QTrap import QTrap
from QHOT.lib.traps.QTrapGroup import QTrapGroup
from QHOT.lib.traps.QTrapOverlay import QTrapOverlay
from QVideo.lib.QVideoScreen import QVideoScreen


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def make_screen():
    return QHOTScreen()


def make_press_event(pos, button=QtCore.Qt.MouseButton.LeftButton,
                     modifiers=QtCore.Qt.KeyboardModifier.NoModifier):
    return QtGui.QMouseEvent(
        QtCore.QEvent.Type.MouseButtonPress,
        QtCore.QPointF(pos),
        button, button, modifiers)


def make_move_event(pos, button=QtCore.Qt.MouseButton.LeftButton,
                    modifiers=QtCore.Qt.KeyboardModifier.NoModifier):
    return QtGui.QMouseEvent(
        QtCore.QEvent.Type.MouseMove,
        QtCore.QPointF(pos),
        QtCore.Qt.MouseButton.NoButton, button, modifiers)


def make_release_event(pos, button=QtCore.Qt.MouseButton.LeftButton,
                       modifiers=QtCore.Qt.KeyboardModifier.NoModifier):
    return QtGui.QMouseEvent(
        QtCore.QEvent.Type.MouseButtonRelease,
        QtCore.QPointF(pos),
        button, QtCore.Qt.MouseButton.NoButton, modifiers)


def make_wheel_event(pos, delta=120):
    return QtGui.QWheelEvent(
        QtCore.QPointF(pos),
        QtCore.QPointF(pos),
        QtCore.QPoint(0, delta),
        QtCore.QPoint(0, delta),
        QtCore.Qt.MouseButton.NoButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
        QtCore.Qt.ScrollPhase.NoScrollPhase,
        False)


class TestSetup(unittest.TestCase):

    def test_has_overlay(self):
        screen = make_screen()
        self.assertIsInstance(screen.overlay, QTrapOverlay)

    def test_overlay_in_view(self):
        screen = make_screen()
        self.assertIn(screen.overlay, screen.view.addedItems)


class TestClearTraps(unittest.TestCase):

    def setUp(self):
        self.screen = make_screen()
        self.screen.overlay.addTrap(QTrap(r=(1., 2., 0.), phase=0.))
        self.screen.overlay.addTrap(QTrap(r=(3., 4., 0.), phase=0.))

    def test_clears_overlay(self):
        self.screen.clearTraps()
        self.assertEqual(self.screen.overlay._traps, [])

    def test_emits_status(self):
        spy = QtTest.QSignalSpy(self.screen.status)
        self.screen.clearTraps()
        self.assertEqual(len(spy), 1)


class TestMousePressEvent(unittest.TestCase):

    def setUp(self):
        self.screen = make_screen()
        self.pos = QtCore.QPoint(100, 100)

    def test_delegates_to_overlay(self):
        event = make_press_event(self.pos)
        with patch.object(self.screen.overlay, 'mousePress',
                          return_value=True) as mock:
            self.screen.mousePressEvent(event)
            self.assertTrue(mock.called)

    def test_accepts_event_when_overlay_handles(self):
        event = make_press_event(self.pos)
        with patch.object(self.screen.overlay, 'mousePress',
                          return_value=True):
            self.screen.mousePressEvent(event)
            self.assertTrue(event.isAccepted())

    def test_propagates_when_overlay_ignores(self):
        event = make_press_event(self.pos)
        with patch.object(self.screen.overlay, 'mousePress',
                          return_value=False):
            with patch.object(QVideoScreen, 'mousePressEvent') as mock_super:
                self.screen.mousePressEvent(event)
                self.assertTrue(mock_super.called)


class TestMouseMoveEvent(unittest.TestCase):

    def setUp(self):
        self.screen = make_screen()
        self.pos = QtCore.QPoint(100, 100)

    def test_delegates_to_overlay(self):
        event = make_move_event(self.pos)
        with patch.object(self.screen.overlay, 'mouseMove',
                          return_value=True) as mock:
            self.screen.mouseMoveEvent(event)
            self.assertTrue(mock.called)

    def test_accepts_event_when_overlay_handles(self):
        event = make_move_event(self.pos)
        with patch.object(self.screen.overlay, 'mouseMove',
                          return_value=True):
            self.screen.mouseMoveEvent(event)
            self.assertTrue(event.isAccepted())

    def test_propagates_when_overlay_ignores(self):
        event = make_move_event(self.pos)
        with patch.object(self.screen.overlay, 'mouseMove',
                          return_value=False):
            with patch.object(QVideoScreen, 'mouseMoveEvent') as mock_super:
                self.screen.mouseMoveEvent(event)
                self.assertTrue(mock_super.called)


class TestMouseReleaseEvent(unittest.TestCase):

    def setUp(self):
        self.screen = make_screen()
        self.pos = QtCore.QPoint(100, 100)

    def test_delegates_to_overlay(self):
        event = make_release_event(self.pos)
        with patch.object(self.screen.overlay, 'mouseRelease',
                          return_value=True) as mock:
            self.screen.mouseReleaseEvent(event)
            self.assertTrue(mock.called)

    def test_accepts_event_when_overlay_handles(self):
        event = make_release_event(self.pos)
        with patch.object(self.screen.overlay, 'mouseRelease',
                          return_value=True):
            self.screen.mouseReleaseEvent(event)
            self.assertTrue(event.isAccepted())

    def test_propagates_when_overlay_ignores(self):
        event = make_release_event(self.pos)
        with patch.object(self.screen.overlay, 'mouseRelease',
                          return_value=False):
            with patch.object(QVideoScreen, 'mouseReleaseEvent') as mock_super:
                self.screen.mouseReleaseEvent(event)
                self.assertTrue(mock_super.called)


class TestWheelEvent(unittest.TestCase):

    def setUp(self):
        self.screen = make_screen()
        self.pos = QtCore.QPoint(100, 100)

    def test_delegates_to_overlay(self):
        event = make_wheel_event(self.pos)
        with patch.object(self.screen.overlay, 'wheel',
                          return_value=True) as mock:
            self.screen.wheelEvent(event)
            self.assertTrue(mock.called)

    def test_accepts_event_when_overlay_handles(self):
        event = make_wheel_event(self.pos)
        with patch.object(self.screen.overlay, 'wheel',
                          return_value=True):
            self.screen.wheelEvent(event)
            self.assertTrue(event.isAccepted())

    def test_propagates_when_overlay_ignores(self):
        event = make_wheel_event(self.pos)
        with patch.object(self.screen.overlay, 'wheel',
                          return_value=False):
            with patch.object(QVideoScreen, 'wheelEvent') as mock_super:
                self.screen.wheelEvent(event)
                self.assertTrue(mock_super.called)


class TestOverlayPos(unittest.TestCase):

    def test_returns_qpointf(self):
        screen = make_screen()
        event = make_press_event(QtCore.QPoint(50, 50))
        pos = screen._overlayPos(event)
        self.assertIsInstance(pos, QtCore.QPointF)


class TestSetImageRendered(unittest.TestCase):
    '''Cover the rendered signal branch in setImage.'''

    def setUp(self):
        self.screen = make_screen()
        self.image = np.zeros((480, 640, 3), dtype=np.uint8)

    def test_rendered_not_emitted_when_not_ready(self):
        spy = QtTest.QSignalSpy(self.screen.rendered)
        self.screen._ready = False
        self.screen.setImage(self.image)
        self.assertEqual(len(spy), 0)

    def test_rendered_emitted_when_ready(self):
        spy = QtTest.QSignalSpy(self.screen.rendered)
        self.screen._ready = True
        self.screen.setImage(self.image)
        self.assertEqual(len(spy), 1)


if __name__ == '__main__':
    unittest.main()
