'''Unit tests for Record.'''
import unittest

from pyqtgraph.Qt import QtTest

from QHOT.lib.tasks.QTask import QTask
from QHOT.tasks.Record import Record
from recordingfixtures import RealDVRCase, make_dvr

try:
    from taskmanagers import attached
except ImportError:  # run from the root of the repository
    from tests.taskmanagers import attached


class TestRecordInit(unittest.TestCase):

    def setUp(self):
        self.dvr = make_dvr()

    def test_initial_state_is_pending(self):
        task = attached(Record(), dvr=self.dvr)
        self.assertEqual(task.state, QTask.State.PENDING)

    def test_filename_default_empty(self):
        task = attached(Record(), dvr=self.dvr)
        self.assertEqual(task.filename, '')

    def test_filename_stored(self):
        task = attached(Record(filename='out.mkv'), dvr=self.dvr)
        self.assertEqual(task.filename, 'out.mkv')

    def test_nframes_forwarded(self):
        task = attached(Record(nframes=120), dvr=self.dvr)
        self.assertEqual(task.duration, 120)

    def test_nframes_default_unlimited(self):
        task = attached(Record(), dvr=self.dvr)
        self.assertIsNone(task.duration)

    def test_overwrite_default_false(self):
        self.assertFalse(attached(Record(), dvr=self.dvr).overwrite)

    def test_nframes_setter_updates_duration(self):
        task = attached(Record(), dvr=self.dvr)
        task.nframes = 30
        self.assertEqual(task.duration, 30)
        task.nframes = 0
        self.assertIsNone(task.duration)



class TestRecordExecution(unittest.TestCase):

    def setUp(self):
        self.dvr = make_dvr(filename='widget.mkv', nframes=777)

    def test_starts_the_recorder_on_initialize(self):
        task = attached(Record(nframes=1), dvr=self.dvr)
        task._start()
        task._step()
        self.dvr.recorder.start.assert_called_once()

    def test_no_button_is_clicked(self):
        task = attached(Record(nframes=1), dvr=self.dvr)
        task._start()
        task._step()
        self.dvr.record.assert_not_called()
        self.dvr.stop.assert_not_called()

    def test_recorder_arguments(self):
        task = attached(
            Record(filename='test.mkv', nframes=5, overwrite=True),
            dvr=self.dvr,
        )
        task._start()
        task._step()
        self.dvr.recorder.start.assert_called_once_with(
            'test.mkv', 777, 1, overwrite=True)

    def test_empty_filename_uses_the_one_of_the_widget(self):
        task = attached(Record(nframes=1), dvr=self.dvr)
        task._start()
        task._step()
        self.assertEqual(self.dvr.recorder.start.call_args.args[0],
                         'widget.mkv')

    def test_filename_shown_by_the_widget(self):
        task = attached(Record(filename='test.mkv', nframes=1), dvr=self.dvr)
        task._start()
        task._step()
        self.assertEqual(self.dvr.filename, 'test.mkv')

    def test_not_started_before_the_first_step(self):
        task = attached(Record(), dvr=self.dvr)
        task._step()
        self.dvr.recorder.start.assert_not_called()

    def test_not_stopped_mid_recording(self):
        task = attached(Record(nframes=5), dvr=self.dvr)
        task._start()
        task._step()   # initialize -> start
        task._step()   # process(1)
        self.dvr.recorder.stop.assert_not_called()

    def test_stopped_after_duration_expires(self):
        task = attached(Record(nframes=3), dvr=self.dvr)
        task._start()
        for _ in range(3):
            task._step()
        self.dvr.recorder.stop.assert_called_once()

    def test_stopped_on_finish(self):
        task = attached(Record(), dvr=self.dvr)
        task._start()
        task._step()
        task.finish()
        self.dvr.recorder.stop.assert_called_once()

    def test_stopped_once_only(self):
        task = attached(Record(nframes=1), dvr=self.dvr)
        task._start()
        task._step()
        task.abort()
        self.dvr.recorder.stop.assert_called_once()

    def test_abort_stops_the_recording(self):
        task = attached(Record(), dvr=self.dvr)
        task._start()
        task._step()
        task.abort('queue stopped')
        self.dvr.recorder.stop.assert_called_once()
        self.assertEqual(task.state, QTask.State.FAILED)

    def test_abort_before_start_stops_nothing(self):
        task = attached(Record(), dvr=self.dvr)
        task.abort()
        self.dvr.recorder.stop.assert_not_called()
        self.assertEqual(task.state, QTask.State.FAILED)

    def test_refused_start_leaves_nothing_to_stop(self):
        self.dvr.recorder.start.side_effect = FileExistsError('exists')
        task = attached(Record(), dvr=self.dvr)
        task._start()
        task._step()
        task.abort()
        self.dvr.recorder.stop.assert_not_called()

    def test_start_error_fails_task_with_its_reason(self):
        self.dvr.recorder.start.side_effect = RuntimeError('device busy')
        task = attached(Record(), dvr=self.dvr)
        spy = QtTest.QSignalSpy(task.failed)
        task._start()
        task._step()
        self.assertEqual(spy[0][0], 'device busy')
        self.assertEqual(task.state, QTask.State.FAILED)

    def test_refuses_during_playback(self):
        self.dvr.isPlaying.return_value = True
        task = attached(Record(), dvr=self.dvr)
        task._start()
        task._step()
        self.assertEqual(task.state, QTask.State.FAILED)
        self.dvr.recorder.start.assert_not_called()

    def test_stop_error_fails_task(self):
        self.dvr.recorder.stop.side_effect = RuntimeError('stop failed')
        task = attached(Record(nframes=1), dvr=self.dvr)
        spy = QtTest.QSignalSpy(task.failed)
        task._start()
        task._step()
        self.assertEqual(len(spy), 1)
        self.assertEqual(task.state, QTask.State.FAILED)

    def test_completes_after_duration(self):
        task = attached(Record(nframes=2), dvr=self.dvr)
        task._start()
        task._step()
        task._step()
        self.assertEqual(task.state, QTask.State.COMPLETED)

    def test_can_run_again_after_reset(self):
        task = attached(Record(nframes=1), dvr=self.dvr)
        task._start()
        task._step()
        task.reset()
        task._start()
        task._step()
        self.assertEqual(self.dvr.recorder.start.call_count, 2)
        self.assertEqual(self.dvr.recorder.stop.call_count, 2)


class TestRecordSerialization(unittest.TestCase):

    def test_to_dict_type(self):
        self.assertEqual(Record().toDict()['type'], 'Record')

    def test_to_dict_values(self):
        d = Record(
            filename='out.mkv',
            nframes=60,
            overwrite=True,
            delay=5,
        ).toDict()
        self.assertEqual(d['filename'], 'out.mkv')
        self.assertEqual(d['nframes'], 60)
        self.assertTrue(d['overwrite'])
        self.assertEqual(d['delay'], 5)

    def test_round_trip(self):
        task = Record(filename='clip.mkv', nframes=100, overwrite=True)
        task2 = QTask.fromDict(task.toDict())
        self.assertEqual(task2.filename, 'clip.mkv')
        self.assertEqual(task2.nframes, 100)
        self.assertEqual(task2.duration, 100)
        self.assertTrue(task2.overwrite)


class TestRecordWithARealRecorder(RealDVRCase):

    def test_records_for_as_long_as_the_task_runs(self):
        task = attached(Record(filename=self.path(), nframes=3), dvr=self.dvr)
        task._start()
        task._step()
        self.assertTrue(self.dvr.recorder.isRecording())
        self.source.emit(9)
        task._step()
        task._step()
        self.assertEqual(task.state, QTask.State.COMPLETED)
        self.assertFalse(self.dvr.recorder.isRecording())
        self.assertEqual(self.frames(self.path()), 9)

    def test_aborting_stops_a_running_recording(self):
        task = attached(Record(filename=self.path()), dvr=self.dvr)
        task._start()
        task._step()
        self.source.emit(4)
        task.abort('queue stopped')
        self.assertFalse(self.dvr.recorder.isRecording())
        self.assertEqual(self.frames(self.path()), 4)

    def test_existing_file_fails_without_a_dialog(self):
        open(self.path(), 'wb').close()
        task = attached(Record(filename=self.path(), nframes=2), dvr=self.dvr)
        spy = QtTest.QSignalSpy(task.failed)
        task._start()
        task._step()
        self.assertEqual(task.state, QTask.State.FAILED)
        self.assertIn('exists', spy[0][0])
        self.assertFalse(self.dvr.recorder.isRecording())


if __name__ == '__main__':
    unittest.main()
