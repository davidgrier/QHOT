'''Unit tests for QTask.'''
import unittest
from unittest.mock import MagicMock, call

from pyqtgraph.Qt import QtCore, QtWidgets, QtTest

from QHOT.lib.tasks.QTask import QTask

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class TestQTaskInit(unittest.TestCase):

    def setUp(self):
        self.overlay = MagicMock()

    def test_initial_state_is_pending(self):
        task = QTask(self.overlay)
        self.assertEqual(task.state, QTask.State.PENDING)

    def test_overlay_stored(self):
        task = QTask(self.overlay)
        self.assertIs(task.overlay, self.overlay)

    def test_overlay_defaults_to_none(self):
        task = QTask()
        self.assertIsNone(task.overlay)

    def test_cgh_default_none(self):
        task = QTask()
        self.assertIsNone(task.cgh)

    def test_dvr_default_none(self):
        task = QTask()
        self.assertIsNone(task.dvr)

    def test_delay_default_zero(self):
        task = QTask()
        self.assertEqual(task.delay, 0)

    def test_duration_default_none(self):
        task = QTask()
        self.assertIsNone(task.duration)

    def test_previous_default_none(self):
        task = QTask()
        self.assertIsNone(task.previous)

    def test_cgh_stored(self):
        cgh = MagicMock()
        task = QTask(cgh=cgh)
        self.assertIs(task.cgh, cgh)

    def test_delay_stored(self):
        task = QTask(delay=3)
        self.assertEqual(task.delay, 3)

    def test_duration_stored(self):
        task = QTask(duration=5)
        self.assertEqual(task.duration, 5)


class TestQTaskStart(unittest.TestCase):

    def test_start_transitions_to_running(self):
        task = QTask()
        task._start()
        self.assertEqual(task.state, QTask.State.RUNNING)

    def test_start_stores_previous(self):
        prev = QTask()
        task = QTask()
        task._start(previous=prev)
        self.assertIs(task.previous, prev)

    def test_start_previous_none_by_default(self):
        task = QTask()
        task._start()
        self.assertIsNone(task.previous)

    def test_step_no_op_when_pending(self):
        task = QTask()
        task.process = MagicMock()
        task._step()
        task.process.assert_not_called()

    def test_step_no_op_when_completed(self):
        task = QTask(duration=1)
        task._start()
        task._step()
        self.assertEqual(task.state, QTask.State.COMPLETED)
        task.process = MagicMock()
        task._step()
        task.process.assert_not_called()


class TestQTaskHooks(unittest.TestCase):

    def test_initialize_called_on_first_step(self):
        task = QTask()
        task.initialize = MagicMock()
        task._start()
        task._step()
        task.initialize.assert_called_once_with()

    def test_initialize_called_once_over_multiple_steps(self):
        task = QTask()
        task.initialize = MagicMock()
        task._start()
        task._step()
        task._step()
        task.initialize.assert_called_once()

    def test_process_called_with_frame_index(self):
        task = QTask()
        task.process = MagicMock()
        task._start()
        task._step()
        task._step()
        task._step()
        task.process.assert_has_calls([call(0), call(1), call(2)])

    def test_complete_called_on_finish(self):
        task = QTask()
        task.complete = MagicMock()
        task._start()
        task._step()
        task.finish()
        task.complete.assert_called_once_with()

    def test_complete_called_on_duration_expiry(self):
        task = QTask(duration=2)
        task.complete = MagicMock()
        task._start()
        task._step()
        task._step()
        task.complete.assert_called_once_with()


class TestQTaskDuration(unittest.TestCase):

    def test_duration_none_runs_indefinitely(self):
        task = QTask(duration=None)
        task._start()
        for _ in range(20):
            task._step()
        self.assertEqual(task.state, QTask.State.RUNNING)

    def test_duration_zero_completes_after_initialize(self):
        task = QTask(duration=0)
        task._start()
        task._step()
        self.assertEqual(task.state, QTask.State.COMPLETED)

    def test_duration_zero_never_calls_process(self):
        task = QTask(duration=0)
        task.process = MagicMock()
        task._start()
        task._step()
        task.process.assert_not_called()

    def test_duration_one_auto_completes_after_one_process(self):
        task = QTask(duration=1)
        task._start()
        task._step()
        self.assertEqual(task.state, QTask.State.COMPLETED)

    def test_duration_three_auto_completes_after_three_steps(self):
        task = QTask(duration=3)
        task._start()
        task._step()
        task._step()
        self.assertEqual(task.state, QTask.State.RUNNING)
        task._step()
        self.assertEqual(task.state, QTask.State.COMPLETED)

    def test_process_not_called_after_auto_complete(self):
        task = QTask(duration=1)
        task._start()
        task._step()
        task.process = MagicMock()
        task._step()
        task.process.assert_not_called()


class TestQTaskDelay(unittest.TestCase):

    def test_delay_skips_initialize(self):
        task = QTask(delay=2)
        task.initialize = MagicMock()
        task._start()
        task._step()
        task._step()
        task.initialize.assert_not_called()

    def test_delay_initialize_called_on_correct_frame(self):
        task = QTask(delay=2)
        task.initialize = MagicMock()
        task._start()
        task._step()
        task._step()
        task._step()
        task.initialize.assert_called_once()

    def test_delay_process_not_called_during_delay(self):
        task = QTask(delay=3)
        task.process = MagicMock()
        task._start()
        task._step()
        task._step()
        task._step()
        task.process.assert_not_called()


class TestQTaskFinishAbort(unittest.TestCase):

    def test_finish_completes_task(self):
        task = QTask()
        task._start()
        task._step()
        task.finish()
        self.assertEqual(task.state, QTask.State.COMPLETED)

    def test_finish_no_op_if_pending(self):
        task = QTask()
        task.finish()
        self.assertEqual(task.state, QTask.State.PENDING)

    def test_finish_no_op_if_already_completed(self):
        task = QTask(duration=1)
        task._start()
        task._step()
        task.complete = MagicMock()
        task.finish()
        task.complete.assert_not_called()

    def test_abort_transitions_to_failed(self):
        task = QTask()
        task._start()
        task.abort('test reason')
        self.assertEqual(task.state, QTask.State.FAILED)

    def test_abort_no_op_if_completed(self):
        task = QTask(duration=1)
        task._start()
        task._step()
        task.abort()
        self.assertEqual(task.state, QTask.State.COMPLETED)

    def test_abort_no_op_if_already_failed(self):
        task = QTask()
        task.abort()
        spy = QtTest.QSignalSpy(task.failed)
        task.abort()
        self.assertEqual(len(spy), 0)


class TestQTaskSignals(unittest.TestCase):

    def test_started_emitted_after_initialize(self):
        task = QTask()
        spy = QtTest.QSignalSpy(task.started)
        task._start()
        task._step()
        self.assertEqual(len(spy), 1)

    def test_started_not_emitted_during_delay(self):
        task = QTask(delay=2)
        spy = QtTest.QSignalSpy(task.started)
        task._start()
        task._step()
        task._step()
        self.assertEqual(len(spy), 0)

    def test_finished_emitted_on_duration_expiry(self):
        task = QTask(duration=1)
        spy = QtTest.QSignalSpy(task.finished)
        task._start()
        task._step()
        self.assertEqual(len(spy), 1)

    def test_finished_emitted_on_finish_call(self):
        task = QTask()
        spy = QtTest.QSignalSpy(task.finished)
        task._start()
        task._step()
        task.finish()
        self.assertEqual(len(spy), 1)

    def test_finished_not_emitted_twice(self):
        task = QTask(duration=1)
        spy = QtTest.QSignalSpy(task.finished)
        task._start()
        task._step()
        task.finish()
        self.assertEqual(len(spy), 1)

    def test_failed_emitted_on_abort(self):
        task = QTask()
        spy = QtTest.QSignalSpy(task.failed)
        task._start()
        task.abort('test')
        self.assertEqual(len(spy), 1)
        self.assertEqual(spy[0][0], 'test')

    def test_failed_emitted_on_initialize_exception(self):
        task = QTask()
        task.initialize = MagicMock(
            side_effect=RuntimeError('init error'))
        spy = QtTest.QSignalSpy(task.failed)
        task._start()
        task._step()
        self.assertEqual(len(spy), 1)
        self.assertIn('init error', spy[0][0])

    def test_failed_emitted_on_process_exception(self):
        task = QTask()
        task.process = MagicMock(
            side_effect=ValueError('proc error'))
        spy = QtTest.QSignalSpy(task.failed)
        task._start()
        task._step()   # initialize (ok), then process -> exception
        task._step()
        self.assertEqual(len(spy), 1)
        self.assertIn('proc error', spy[0][0])

    def test_failed_emitted_on_complete_exception(self):
        task = QTask(duration=1)
        task.complete = MagicMock(
            side_effect=RuntimeError('complete error'))
        spy = QtTest.QSignalSpy(task.failed)
        task._start()
        task._step()
        self.assertEqual(len(spy), 1)
        self.assertEqual(task.state, QTask.State.FAILED)

    def test_complete_called_before_finished(self):
        order = []
        task = QTask(duration=1)
        task.complete = lambda: order.append('complete')
        task.finished.connect(lambda: order.append('finished'))
        task._start()
        task._step()
        self.assertEqual(order, ['complete', 'finished'])

    def test_initialize_called_before_started(self):
        order = []
        task = QTask()
        task.initialize = lambda: order.append('initialize')
        task.started.connect(lambda: order.append('started'))
        task._start()
        task._step()
        self.assertEqual(order, ['initialize', 'started'])


class TestQTaskReset(unittest.TestCase):

    def test_reset_pending_stays_pending(self):
        task = QTask()
        task.reset()
        self.assertEqual(task.state, QTask.State.PENDING)

    def test_reset_completed_returns_to_pending(self):
        task = QTask(duration=1)
        task._start()
        task._step()
        self.assertEqual(task.state, QTask.State.COMPLETED)
        task.reset()
        self.assertEqual(task.state, QTask.State.PENDING)

    def test_reset_failed_returns_to_pending(self):
        task = QTask()
        task._start()
        task.abort('test')
        task.reset()
        self.assertEqual(task.state, QTask.State.PENDING)

    def test_reset_clears_frame_counter(self):
        task = QTask(duration=2)
        task._start()
        task._step()
        task._step()                  # completes after 2 steps
        self.assertEqual(task.state, QTask.State.COMPLETED)
        task.reset()
        self.assertEqual(task._frame, 0)

    def test_reset_clears_previous(self):
        t1 = QTask(duration=1)
        t2 = QTask(duration=1)
        t1._start()
        t1._step()
        t2._start(previous=t1)
        t2._step()                    # complete t2 so reset applies
        t2.reset()
        self.assertIsNone(t2.previous)

    def test_reset_does_not_affect_running_task(self):
        task = QTask()
        task._start()
        task.reset()
        self.assertEqual(task.state, QTask.State.RUNNING)

    def test_reset_allows_task_to_run_again(self):
        task = QTask(duration=1)
        task._start()
        task._step()
        self.assertEqual(task.state, QTask.State.COMPLETED)
        task.reset()
        task._start()
        task._step()
        self.assertEqual(task.state, QTask.State.COMPLETED)


if __name__ == '__main__':
    unittest.main()
