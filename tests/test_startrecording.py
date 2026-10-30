'''Unit tests for StartRecording.'''
import unittest
from unittest.mock import MagicMock

from pyqtgraph.Qt import QtTest

from QHOT.lib.tasks.QTask import QTask
from QHOT.tasks.StartRecording import StartRecording
from recordingfixtures import RealDVRCase, make_dvr

try:
    from taskmanagers import attached
except ImportError:  # run from the root of the repository
    from tests.taskmanagers import attached


def run(task):
    '''Run a task that finishes at once.'''
    task._start()
    task._step()


class TestStartRecordingInit(unittest.TestCase):

    def test_initial_state_is_pending(self):
        task = attached(StartRecording(), dvr=make_dvr())
        self.assertEqual(task.state, QTask.State.PENDING)

    def test_duration_is_zero(self):
        task = attached(StartRecording(), dvr=make_dvr())
        self.assertEqual(task.duration, 0)

    def test_defaults(self):
        task = attached(StartRecording(), dvr=make_dvr())
        self.assertEqual(task.filename, '')
        self.assertEqual(task.nframes, 10_000)
        self.assertEqual(task.nskip, 1)
        self.assertFalse(task.overwrite)

    def test_values_stored(self):
        task = attached(
            StartRecording(filename='clip.mkv', nframes=500, nskip=3, overwrite=True),
            dvr=make_dvr(),
        )
        self.assertEqual(task.filename, 'clip.mkv')
        self.assertEqual(task.nframes, 500)
        self.assertEqual(task.nskip, 3)
        self.assertTrue(task.overwrite)

    def test_values_are_coerced(self):
        task = attached(
            StartRecording(nframes=42.9, nskip=2.7),
            dvr=make_dvr(),
        )
        self.assertEqual(task.nframes, 42)
        self.assertEqual(task.nskip, 2)

    def test_construction_does_not_touch_the_dvr(self):
        dvr = make_dvr(filename='keep.mkv', nframes=123)
        attached(
            StartRecording(filename='clip.mkv', nframes=500, nskip=3),
            dvr=dvr,
        )
        self.assertEqual(dvr.filename, 'keep.mkv')
        dvr.nframes.setValue.assert_not_called()
        dvr.nskip.setValue.assert_not_called()



class TestStartRecordingExecution(unittest.TestCase):

    def setUp(self):
        self.dvr = make_dvr(filename='widget.mkv')

    def test_starts_the_recorder(self):
        task = attached(
            StartRecording(filename='clip.mkv', nframes=500, nskip=3),
            dvr=self.dvr,
        )
        run(task)
        self.dvr.recorder.start.assert_called_once_with(
            'clip.mkv', 500, 3, overwrite=False)

    def test_overwrite_is_passed_on(self):
        run(attached(
            StartRecording(filename='clip.mkv', overwrite=True),
            dvr=self.dvr,
        ))
        self.assertTrue(
            self.dvr.recorder.start.call_args.kwargs['overwrite'])

    def test_empty_filename_uses_the_one_of_the_widget(self):
        run(attached(StartRecording(), dvr=self.dvr))
        self.assertEqual(self.dvr.recorder.start.call_args.args[0],
                         'widget.mkv')

    def test_widget_shows_the_file_being_recorded(self):
        run(attached(StartRecording(filename='clip.mkv'), dvr=self.dvr))
        self.assertEqual(self.dvr.filename, 'clip.mkv')

    def test_no_button_is_clicked(self):
        run(attached(StartRecording(), dvr=self.dvr))
        self.dvr.recordButton.animateClick.assert_not_called()
        self.dvr.record.assert_not_called()

    def test_not_started_before_the_first_step(self):
        task = attached(StartRecording(), dvr=self.dvr)
        task._step()
        self.dvr.recorder.start.assert_not_called()

    def test_completes_after_one_step(self):
        task = attached(StartRecording(), dvr=self.dvr)
        run(task)
        self.assertEqual(task.state, QTask.State.COMPLETED)

    def test_finished_emitted_after_one_step(self):
        task = attached(StartRecording(), dvr=self.dvr)
        spy = QtTest.QSignalSpy(task.finished)
        run(task)
        self.assertEqual(len(spy), 1)

    def test_refuses_during_playback(self):
        self.dvr.isPlaying.return_value = True
        task = attached(StartRecording(), dvr=self.dvr)
        spy = QtTest.QSignalSpy(task.failed)
        run(task)
        self.assertEqual(task.state, QTask.State.FAILED)
        self.assertIn('playing', spy[0][0])
        self.dvr.recorder.start.assert_not_called()

    def test_recorder_error_fails_the_task_with_its_reason(self):
        self.dvr.recorder.start.side_effect = FileExistsError('it exists')
        task = attached(StartRecording(), dvr=self.dvr)
        spy = QtTest.QSignalSpy(task.failed)
        run(task)
        self.assertEqual(task.state, QTask.State.FAILED)
        self.assertEqual(spy[0][0], 'it exists')

    def test_failed_start_leaves_the_widget_alone(self):
        self.dvr.recorder.start.side_effect = RuntimeError('no source')
        run(attached(StartRecording(filename='clip.mkv'), dvr=self.dvr))
        self.assertEqual(self.dvr.filename, 'widget.mkv')

    def test_no_dvr_fails_the_task(self):
        task = StartRecording()
        spy = QtTest.QSignalSpy(task.failed)
        run(task)
        self.assertEqual(task.state, QTask.State.FAILED)
        self.assertEqual(len(spy), 1)


class TestStartRecordingSerialization(unittest.TestCase):

    def test_to_dict(self):
        task = StartRecording(
            filename='out.mkv',
            nframes=300,
            nskip=2,
            overwrite=True,
        )
        d = task.toDict()
        self.assertEqual(d['type'], 'StartRecording')
        self.assertEqual(d['filename'], 'out.mkv')
        self.assertEqual(d['nframes'], 300)
        self.assertEqual(d['nskip'], 2)
        self.assertTrue(d['overwrite'])

    def test_blank_filename_stays_blank(self):
        '''The file of the widget is not frozen into a saved queue.'''
        task = attached(StartRecording(), dvr=make_dvr(filename='widget.mkv'))
        self.assertEqual(task.toDict()['filename'], '')

    def test_round_trip(self):
        task = StartRecording(
            filename='clip.mkv',
            nframes=100,
            nskip=2,
            overwrite=True,
        )
        task2 = QTask.fromDict(task.toDict())
        self.assertIsInstance(task2, StartRecording)
        self.assertEqual(task2.filename, 'clip.mkv')
        self.assertEqual(task2.nframes, 100)
        self.assertEqual(task2.nskip, 2)
        self.assertTrue(task2.overwrite)

    def test_saved_queue_loads_without_a_dvr(self):
        '''QTaskManager.load builds a task before it gives it a DVR.'''
        d = {'type': 'StartRecording', 'delay': 0, 'filename': 'a.mkv',
             'nframes': 100, 'nskip': 1}
        self.assertIsInstance(QTask.fromDict(d), StartRecording)


class TestStartRecordingWithARealRecorder(RealDVRCase):

    def start(self, path, **kwargs):
        task = attached(
            StartRecording(filename=path, nframes=5, **kwargs),
            dvr=self.dvr,
        )
        spy = QtTest.QSignalSpy(task.failed)
        run(task)
        return task, spy

    def test_records_frames_to_the_file(self):
        task, _ = self.start(self.path())
        self.assertEqual(task.state, QTask.State.COMPLETED)
        self.assertTrue(self.dvr.recorder.isRecording())
        self.source.emit(8)
        self.dvr.recorder.stop()
        self.assertEqual(self.frames(self.path()), 5)

    def test_existing_file_fails_and_is_left_alone(self):
        self.start(self.path())
        self.source.emit(8)
        self.dvr.recorder.stop()
        task, spy = self.start(self.path())
        self.assertEqual(task.state, QTask.State.FAILED)
        self.assertIn('exists', spy[0][0])
        self.assertFalse(self.dvr.recorder.isRecording())
        self.assertEqual(self.frames(self.path()), 5)

    def test_overwrite_replaces_the_file(self):
        self.start(self.path())
        self.source.emit(8)
        self.dvr.recorder.stop()
        task, _ = self.start(self.path(), overwrite=True)
        self.assertEqual(task.state, QTask.State.COMPLETED)
        self.source.emit(3)
        self.dvr.recorder.stop()
        self.assertEqual(self.frames(self.path()), 3)

    def test_unsupported_extension_fails(self):
        task, spy = self.start(self.path('run.xyz'))
        self.assertEqual(task.state, QTask.State.FAILED)
        self.assertEqual(len(spy), 1)
        self.assertFalse(self.dvr.recorder.isRecording())

    def test_second_recording_fails(self):
        self.start(self.path('a.h5'))
        task, spy = self.start(self.path('b.h5'))
        self.assertEqual(task.state, QTask.State.FAILED)
        self.assertIn('already', spy[0][0])

    def test_no_source_fails(self):
        self.dvr.source = None
        task, spy = self.start(self.path())
        self.assertEqual(task.state, QTask.State.FAILED)
        self.assertIn('source', spy[0][0])


if __name__ == '__main__':
    unittest.main()
