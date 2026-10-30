'''Unit tests for QCameraOpener.'''
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from pyqtgraph.Qt import QtCore, QtTest, QtWidgets

import importlib
from QHOT.lib.QCameraOpener import QCameraOpener
_opener = importlib.import_module('QHOT.lib.QCameraOpener')

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class FakeCamera(QtCore.QObject):

    '''A camera that remembers where it was made and whether it is open.'''

    def __init__(self):
        super().__init__()
        self.made_in = threading.current_thread()
        self.closed = False

    def close(self):
        self.closed = True


def opens(camera_class=FakeCamera, key='noise', delay=0.):
    def open_camera(parser=None):
        time.sleep(delay)
        return key, camera_class()
    return patch.object(_opener.chooser, 'open_camera', open_camera)


class TestOpening(unittest.TestCase):

    def test_opens_the_camera(self):
        with opens():
            opener = QCameraOpener()
            opener.start()
            self.assertTrue(opener.wait_for_camera())
        self.assertIsInstance(opener.camera, FakeCamera)
        self.assertEqual(opener.key, 'noise')

    def test_opens_it_in_a_thread_of_its_own(self):
        with opens():
            opener = QCameraOpener()
            opener.start()
            opener.wait_for_camera()
        self.assertIsNot(opener.camera.made_in, threading.main_thread())

    def test_hands_the_camera_to_the_thread_of_the_application(self):
        with opens():
            opener = QCameraOpener()
            opener.start()
            opener.wait_for_camera()
        self.assertIs(opener.camera.thread(), app.thread())

    def test_announces_the_camera(self):
        with opens():
            opener = QCameraOpener()
            spy = QtTest.QSignalSpy(opener.opened)
            opener.start()
            opener.wait_for_camera()
            QtTest.QTest.qWait(20)
        self.assertEqual(len(spy), 1)
        self.assertEqual(spy[0][0], 'noise')

    def test_gives_the_parser_to_the_chooser(self):
        seen = []

        def open_camera(parser=None):
            seen.append(parser)
            return 'noise', FakeCamera()

        parser = object()
        with patch.object(_opener.chooser, 'open_camera', open_camera):
            opener = QCameraOpener(parser)
            opener.start()
            opener.wait_for_camera()
        self.assertEqual(seen, [parser])

    def test_does_not_make_the_caller_wait_for_a_slow_camera(self):
        with opens(delay=0.4):
            opener = QCameraOpener()
            t0 = time.perf_counter()
            opener.start()
            self.assertLess(time.perf_counter() - t0, 0.2)
            self.assertTrue(opener.isRunning())
            opener.wait_for_camera()
        self.assertFalse(opener.isRunning())

    def test_the_event_loop_runs_while_it_waits(self):
        ticks = []
        timer = QtCore.QTimer()
        timer.timeout.connect(lambda: ticks.append(1))
        timer.start(10)
        with opens(delay=0.3):
            opener = QCameraOpener()
            opener.start()
            opener.wait_for_camera()
        timer.stop()
        self.assertGreater(len(ticks), 5)


class TestFailing(unittest.TestCase):

    def failing(self, message='no camera could be opened'):
        def open_camera(parser=None):
            raise RuntimeError(message)
        return patch.object(_opener.chooser, 'open_camera', open_camera)

    def test_reports_that_there_is_no_camera(self):
        with self.failing():
            opener = QCameraOpener()
            opener.start()
            self.assertFalse(opener.wait_for_camera())
        self.assertIsNone(opener.camera)

    def test_says_why(self):
        with self.failing():
            opener = QCameraOpener()
            spy = QtTest.QSignalSpy(opener.failed)
            opener.start()
            opener.wait_for_camera()
            QtTest.QTest.qWait(20)
        self.assertEqual(opener.reason, 'no camera could be opened')
        self.assertEqual(spy[0][0], 'no camera could be opened')

    def test_does_not_announce_a_camera(self):
        with self.failing():
            opener = QCameraOpener()
            spy = QtTest.QSignalSpy(opener.opened)
            opener.start()
            opener.wait_for_camera()
            QtTest.QTest.qWait(20)
        self.assertEqual(len(spy), 0)


class TestStopping(unittest.TestCase):

    def test_closes_a_camera_that_nobody_took(self):
        camera = MagicMock()
        opener = QCameraOpener()
        opener.camera = camera
        opener.stop()
        camera.close.assert_called_once()
        self.assertIsNone(opener.camera)

    def test_stopping_twice_is_harmless(self):
        opener = QCameraOpener()
        opener.stop()
        opener.stop()

    def test_a_camera_that_opens_after_the_request_is_closed(self):
        made = []

        def open_camera(parser=None):
            time.sleep(0.2)
            camera = MagicMock()
            made.append(camera)
            return 'noise', camera

        with patch.object(_opener.chooser, 'open_camera', open_camera):
            opener = QCameraOpener()
            opener.start()
            opener.stop()
        self.assertIsNone(opener.camera)
        made[0].close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
