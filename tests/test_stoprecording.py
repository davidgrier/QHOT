'''Unit tests for StopRecording.'''
import unittest

from pyqtgraph.Qt import QtTest

from QHOT.lib.tasks.QTask import QTask
from QHOT.tasks.StartRecording import StartRecording
from QHOT.tasks.StopRecording import StopRecording
from recordingfixtures import RealDVRCase, make_dvr

try:
    from taskmanagers import attached
except ImportError:  # run from the root of the repository
    from tests.taskmanagers import attached


def run(task):
    task._start()
    task._step()


class TestStopRecordingInit(unittest.TestCase):

    def test_initial_state_is_pending(self):
        task = attached(StopRecording(), dvr=make_dvr())
        self.assertEqual(task.state, QTask.State.PENDING)

    def test_duration_is_zero(self):
        task = attached(StopRecording(), dvr=make_dvr())
        self.assertEqual(task.duration, 0)

    def test_delay_forwarded(self):
        task = attached(StopRecording(delay=3), dvr=make_dvr())
        self.assertEqual(task.delay, 3)


class TestStopRecordingExecution(unittest.TestCase):

    def setUp(self):
        self.dvr = make_dvr()

    def test_stops_the_recorder(self):
        run(attached(StopRecording(), dvr=self.dvr))
        self.dvr.recorder.stop.assert_called_once()

    def test_no_button_is_clicked(self):
        run(attached(StopRecording(), dvr=self.dvr))
        self.dvr.stopButton.animateClick.assert_not_called()
        self.dvr.stop.assert_not_called()

    def test_playback_is_left_alone(self):
        run(attached(StopRecording(), dvr=self.dvr))
        self.dvr.playback.stop.assert_not_called()

    def test_not_stopped_before_the_first_step(self):
        task = attached(StopRecording(), dvr=self.dvr)
        task._step()
        self.dvr.recorder.stop.assert_not_called()

    def test_completes_after_one_step(self):
        task = attached(StopRecording(), dvr=self.dvr)
        run(task)
        self.assertEqual(task.state, QTask.State.COMPLETED)

    def test_finished_emitted(self):
        task = attached(StopRecording(), dvr=self.dvr)
        spy = QtTest.QSignalSpy(task.finished)
        run(task)
        self.assertEqual(len(spy), 1)

    def test_error_fails_the_task(self):
        self.dvr.recorder.stop.side_effect = RuntimeError('stop failed')
        task = attached(StopRecording(), dvr=self.dvr)
        spy = QtTest.QSignalSpy(task.failed)
        run(task)
        self.assertEqual(len(spy), 1)
        self.assertEqual(task.state, QTask.State.FAILED)


class TestStopRecordingSerialization(unittest.TestCase):

    def test_to_dict_type(self):
        task = attached(StopRecording(), dvr=make_dvr())
        self.assertEqual(task.toDict()['type'], 'StopRecording')

    def test_round_trip(self):
        task = attached(StopRecording(delay=2), dvr=make_dvr())
        task2 = QTask.fromDict(task.toDict())
        self.assertIsInstance(task2, StopRecording)
        self.assertEqual(task2.delay, 2)


class TestStopRecordingWithARealRecorder(RealDVRCase):

    def test_stops_a_recording_and_keeps_the_frames(self):
        start = attached(
            StartRecording(filename=self.path(), nframes=100),
            dvr=self.dvr,
        )
        run(start)
        self.source.emit(7)
        self.assertTrue(self.dvr.recorder.isRecording())
        stop = attached(StopRecording(), dvr=self.dvr)
        run(stop)
        self.assertEqual(stop.state, QTask.State.COMPLETED)
        self.assertFalse(self.dvr.recorder.isRecording())
        self.assertEqual(self.frames(self.path()), 7)

    def test_nothing_to_stop_is_not_an_error(self):
        stop = attached(StopRecording(), dvr=self.dvr)
        run(stop)
        self.assertEqual(stop.state, QTask.State.COMPLETED)


if __name__ == '__main__':
    unittest.main()
