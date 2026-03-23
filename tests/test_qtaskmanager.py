'''Unit tests for QTaskManager.'''
import unittest
from unittest.mock import MagicMock

from pyqtgraph.Qt import QtCore, QtWidgets, QtTest

from QHOT.lib.tasks.QTask import QTask
from QHOT.lib.tasks.QTaskManager import QTaskManager

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class MockScreen(QtCore.QObject):
    '''Minimal screen substitute with a rendered signal.'''
    rendered = QtCore.pyqtSignal()


class TestQTaskManagerInit(unittest.TestCase):

    def setUp(self):
        self.screen = MockScreen()

    def test_no_active_task_initially(self):
        mgr = QTaskManager(self.screen)
        self.assertIsNone(mgr.active)

    def test_queue_size_zero_initially(self):
        mgr = QTaskManager(self.screen)
        self.assertEqual(mgr.queue_size, 0)

    def test_background_empty_initially(self):
        mgr = QTaskManager(self.screen)
        self.assertEqual(mgr.background, [])

    def test_not_paused_initially(self):
        mgr = QTaskManager(self.screen)
        self.assertFalse(mgr.paused)

    def test_overlay_stored(self):
        overlay = MagicMock()
        mgr = QTaskManager(self.screen, overlay=overlay)
        self.assertIs(mgr.overlay, overlay)

    def test_cgh_stored(self):
        cgh = MagicMock()
        mgr = QTaskManager(self.screen, cgh=cgh)
        self.assertIs(mgr.cgh, cgh)


class TestQTaskManagerRegistration(unittest.TestCase):

    def setUp(self):
        self.screen  = MockScreen()
        self.manager = QTaskManager(self.screen)

    def test_first_blocking_task_becomes_active(self):
        task = QTask()
        self.manager.register(task)
        self.assertIs(self.manager.active_raw, task)

    def test_first_blocking_task_starts_running(self):
        task = QTask()
        self.manager.register(task)
        self.assertEqual(task.state, QTask.State.RUNNING)

    def test_second_blocking_task_queued(self):
        t1, t2 = QTask(), QTask()
        self.manager.register(t1)
        self.manager.register(t2)
        self.assertEqual(self.manager.queue_size, 1)

    def test_third_blocking_task_increments_queue(self):
        t1, t2, t3 = QTask(), QTask(), QTask()
        self.manager.register(t1)
        self.manager.register(t2)
        self.manager.register(t3)
        self.assertEqual(self.manager.queue_size, 2)

    def test_nonblocking_task_not_queued(self):
        task = QTask()
        self.manager.register(task, blocking=False)
        self.assertEqual(self.manager.queue_size, 0)
        self.assertIsNone(self.manager.active)

    def test_nonblocking_task_starts_immediately(self):
        task = QTask()
        self.manager.register(task, blocking=False)
        self.assertEqual(task.state, QTask.State.RUNNING)

    def test_nonblocking_task_in_background_list(self):
        task = QTask()
        self.manager.register(task, blocking=False)
        self.assertIn(task, self.manager.background)

    def test_register_returns_task(self):
        task = QTask()
        result = self.manager.register(task)
        self.assertIs(result, task)

    def test_background_property_is_copy(self):
        task = QTask()
        self.manager.register(task, blocking=False)
        bg = self.manager.background
        bg.clear()
        self.assertEqual(len(self.manager.background), 1)

    def test_queued_empty_initially(self):
        self.assertEqual(self.manager.queued, [])

    def test_queued_contains_pending_tasks(self):
        t1, t2 = QTask(), QTask()
        self.manager.register(t1)
        self.manager.register(t2)
        # t1 activated but not yet stepped — still in queued
        self.assertIn(t1, self.manager.queued)
        self.assertIn(t2, self.manager.queued)

    def test_queued_property_is_copy(self):
        t1, t2 = QTask(), QTask()
        self.manager.register(t1)
        self.manager.register(t2)
        q = self.manager.queued
        q.clear()
        self.assertEqual(len(self.manager.queued), 2)


class TestQTaskManagerFrameDispatch(unittest.TestCase):

    def setUp(self):
        self.screen  = MockScreen()
        self.manager = QTaskManager(self.screen)

    def _emit(self, n: int = 1) -> None:
        for _ in range(n):
            self.screen.rendered.emit()

    def test_frame_steps_active_blocking_task(self):
        task = QTask()
        task._step = MagicMock()
        self.manager.register(task)
        self._emit()
        task._step.assert_called_once()

    def test_frame_steps_background_task(self):
        task = QTask()
        task._step = MagicMock()
        self.manager.register(task, blocking=False)
        self._emit()
        task._step.assert_called_once()

    def test_pause_prevents_blocking_step(self):
        task = QTask()
        task._step = MagicMock()
        self.manager.register(task)
        self.manager.pause(True)
        self._emit()
        task._step.assert_not_called()

    def test_pause_prevents_background_step(self):
        task = QTask()
        task._step = MagicMock()
        self.manager.register(task, blocking=False)
        self.manager.pause(True)
        self._emit()
        task._step.assert_not_called()

    def test_resume_restores_dispatch(self):
        task = QTask()
        task._step = MagicMock()
        self.manager.register(task)
        self.manager.pause(True)
        self.manager.pause(False)
        self._emit()
        task._step.assert_called_once()

    def test_paused_property_reflects_state(self):
        self.manager.pause(True)
        self.assertTrue(self.manager.paused)
        self.manager.pause(False)
        self.assertFalse(self.manager.paused)

    def test_no_step_when_no_active_task(self):
        # Should not raise even with nothing registered
        self._emit()


class TestQTaskManagerSequencing(unittest.TestCase):

    def setUp(self):
        self.screen  = MockScreen()
        self.manager = QTaskManager(self.screen)

    def _emit(self, n: int = 1) -> None:
        for _ in range(n):
            self.screen.rendered.emit()

    def test_second_task_activates_after_first_completes(self):
        t1 = QTask(duration=1)
        t2 = QTask()
        self.manager.register(t1)
        self.manager.register(t2)
        self._emit(1)
        self.assertEqual(t1.state, QTask.State.COMPLETED)
        self.assertIs(self.manager.active_raw, t2)

    def test_previous_passed_from_first_to_second(self):
        t1 = QTask(duration=1)
        t2 = QTask()
        self.manager.register(t1)
        self.manager.register(t2)
        self._emit(1)
        self.assertIs(t2.previous, t1)

    def test_previous_is_none_for_first_task(self):
        task = QTask()
        self.manager.register(task)
        self.assertIsNone(task.previous)

    def test_three_tasks_run_in_order(self):
        order = []
        tasks = [QTask(duration=1) for _ in range(3)]
        for i, t in enumerate(tasks):
            t.started.connect(lambda _i=i: order.append(_i))
            self.manager.register(t)
        self._emit(3)
        self.assertEqual(order, [0, 1, 2])

    def test_queue_depletes_as_tasks_complete(self):
        tasks = [QTask(duration=1) for _ in range(3)]
        for t in tasks:
            self.manager.register(t)
        self.assertEqual(self.manager.queue_size, 2)
        self._emit(1)
        self.assertEqual(self.manager.queue_size, 1)
        self._emit(1)
        self.assertEqual(self.manager.queue_size, 0)

    def test_active_is_none_after_all_complete(self):
        task = QTask(duration=1)
        self.manager.register(task)
        self._emit(1)
        self.assertIsNone(self.manager.active)

    def test_blocking_failure_clears_queue(self):
        t1, t2, t3 = QTask(), QTask(), QTask()
        self.manager.register(t1)
        self.manager.register(t2)
        self.manager.register(t3)
        t1.abort('test failure')
        self.assertEqual(self.manager.queue_size, 0)
        self.assertIsNone(self.manager.active)

    def test_blocking_failure_does_not_affect_background(self):
        blocking = QTask()
        bg = QTask()
        self.manager.register(blocking)
        self.manager.register(bg, blocking=False)
        blocking.abort()
        self.assertIn(bg, self.manager.background)


class TestQTaskManagerStop(unittest.TestCase):

    def setUp(self):
        self.screen  = MockScreen()
        self.manager = QTaskManager(self.screen)

    def test_stop_clears_queue(self):
        for _ in range(3):
            self.manager.register(QTask())
        self.manager.stop()
        self.assertEqual(self.manager.queue_size, 0)

    def test_stop_aborts_active_task(self):
        task = QTask()
        self.manager.register(task)
        self.manager.stop()
        self.assertEqual(task.state, QTask.State.FAILED)

    def test_stop_removes_background_tasks(self):
        for _ in range(2):
            self.manager.register(QTask(), blocking=False)
        self.manager.stop()
        self.assertEqual(len(self.manager.background), 0)

    def test_stop_aborts_background_tasks(self):
        task = QTask()
        self.manager.register(task, blocking=False)
        self.manager.stop()
        self.assertEqual(task.state, QTask.State.FAILED)

    def test_stop_clears_active_reference(self):
        self.manager.register(QTask())
        self.manager.stop()
        self.assertIsNone(self.manager.active)

    def test_stop_preserves_schedule(self):
        tasks = [QTask() for _ in range(3)]
        for t in tasks:
            self.manager.register(t)
        self.manager.stop()
        self.assertEqual(len(self.manager.scheduled), 3)

    def test_stop_on_empty_manager_does_not_raise(self):
        self.manager.stop()


class TestQTaskManagerSchedule(unittest.TestCase):

    def setUp(self):
        self.screen  = MockScreen()
        self.manager = QTaskManager(self.screen)

    def _emit(self, n: int = 1) -> None:
        for _ in range(n):
            self.screen.rendered.emit()

    def test_scheduled_empty_initially(self):
        self.assertEqual(self.manager.scheduled, [])

    def test_registered_task_in_scheduled(self):
        task = QTask()
        self.manager.register(task)
        self.assertIn(task, self.manager.scheduled)

    def test_scheduled_preserves_order(self):
        tasks = [QTask() for _ in range(3)]
        for t in tasks:
            self.manager.register(t)
        self.assertEqual(self.manager.scheduled, tasks)

    def test_scheduled_persists_after_task_completes(self):
        task = QTask(duration=1)
        self.manager.register(task)
        self._emit(1)
        self.assertIn(task, self.manager.scheduled)

    def test_scheduled_persists_after_stop(self):
        task = QTask()
        self.manager.register(task)
        self.manager.stop()
        self.assertIn(task, self.manager.scheduled)

    def test_scheduled_property_is_copy(self):
        task = QTask()
        self.manager.register(task)
        s = self.manager.scheduled
        s.clear()
        self.assertEqual(len(self.manager.scheduled), 1)

    def test_background_tasks_not_in_scheduled(self):
        bg = QTask()
        self.manager.register(bg, blocking=False)
        self.assertNotIn(bg, self.manager.scheduled)

    def test_clear_empties_schedule(self):
        for _ in range(3):
            self.manager.register(QTask())
        self.manager.clear()
        self.assertEqual(self.manager.scheduled, [])

    def test_clear_also_stops_execution(self):
        task = QTask()
        self.manager.register(task)
        self.manager.clear()
        self.assertIsNone(self.manager.active)
        self.assertEqual(self.manager.queue_size, 0)

    def test_clear_on_empty_manager_does_not_raise(self):
        self.manager.clear()

    def test_restart_reruns_schedule(self):
        from QHOT.tasks.Delay import Delay
        self.manager.register(Delay(frames=5))
        self.manager.restart()
        self.assertEqual(len(self.manager.scheduled), 1)
        self.assertEqual(self.manager.active_raw.frames, 5)

    def test_restart_creates_fresh_instances(self):
        from QHOT.tasks.Delay import Delay
        task = Delay(frames=1)
        self.manager.register(task)
        self._emit(1)         # task completes
        self.manager.restart()
        new_task = self.manager.active_raw
        self.assertIsNot(new_task, task)
        self.assertEqual(new_task.state, QTask.State.RUNNING)

    def test_restart_on_empty_schedule_is_noop(self):
        self.manager.restart()  # should not raise
        self.assertEqual(self.manager.scheduled, [])


class TestQTaskManagerAutoReset(unittest.TestCase):

    def setUp(self):
        self.screen  = MockScreen()
        self.manager = QTaskManager(self.screen)

    def _emit(self, n: int = 1) -> None:
        for _ in range(n):
            self.screen.rendered.emit()

    def test_manager_paused_after_auto_reset(self):
        from QHOT.tasks.Delay import Delay
        self.manager.register(Delay(frames=1))
        self._emit(1)             # task completes → auto-reset
        self.assertTrue(self.manager.paused)

    def test_first_task_activated_after_auto_reset(self):
        from QHOT.tasks.Delay import Delay
        task = Delay(frames=1)
        self.manager.register(task)
        self._emit(1)             # task completes → auto-reset, re-activated
        self.assertIs(self.manager.active_raw, task)

    def test_task_running_after_auto_reset(self):
        from QHOT.tasks.Delay import Delay
        task = Delay(frames=1)
        self.manager.register(task)
        self._emit(1)
        self.assertEqual(task.state, QTask.State.RUNNING)

    def test_schedule_preserved_after_auto_reset(self):
        from QHOT.tasks.Delay import Delay
        task = Delay(frames=1)
        self.manager.register(task)
        self._emit(1)
        self.assertIn(task, self.manager.scheduled)

    def test_resuming_after_auto_reset_reruns_tasks(self):
        from QHOT.tasks.Delay import Delay
        from pyqtgraph.Qt import QtTest
        task = Delay(frames=1)
        self.manager.register(task)
        self._emit(1)             # first run completes → auto-reset, re-activated
        spy = QtTest.QSignalSpy(task.started)
        self.manager.pause(False)
        self._emit(1)             # second run
        self.assertGreater(len(spy), 0)

    def test_auto_reset_does_not_occur_after_stop(self):
        from QHOT.tasks.Delay import Delay
        self.manager.register(Delay(frames=1))
        self.manager.stop()
        self.assertFalse(self.manager.paused)
        self.assertEqual(self.manager.queue_size, 0)


class TestQTaskManagerBackground(unittest.TestCase):

    def setUp(self):
        self.screen  = MockScreen()
        self.manager = QTaskManager(self.screen)

    def _emit(self, n: int = 1) -> None:
        for _ in range(n):
            self.screen.rendered.emit()

    def test_background_task_removed_on_completion(self):
        task = QTask(duration=1)
        self.manager.register(task, blocking=False)
        self._emit(1)
        self.assertEqual(len(self.manager.background), 0)

    def test_background_task_removed_on_failure(self):
        task = QTask()
        self.manager.register(task, blocking=False)
        task.abort('test')
        self.assertEqual(len(self.manager.background), 0)

    def test_multiple_background_tasks_run_simultaneously(self):
        steps = []
        for i in range(3):
            t = QTask()
            t.process = MagicMock(
                side_effect=lambda f, _i=i: steps.append(_i))
            self.manager.register(t, blocking=False)
        self._emit(1)
        self.assertEqual(sorted(steps), [0, 1, 2])

    def test_background_runs_alongside_blocking(self):
        blocking = QTask()
        bg       = QTask()
        blocking._step = MagicMock()
        bg._step       = MagicMock()
        self.manager.register(blocking)
        self.manager.register(bg, blocking=False)
        self._emit(1)
        blocking._step.assert_called_once()
        bg._step.assert_called_once()


class TestQTaskManagerLoad(unittest.TestCase):

    def setUp(self):
        self.screen  = MockScreen()
        self.overlay = MagicMock()
        self.cgh     = MagicMock()
        self.dvr     = MagicMock()
        self.manager = QTaskManager(
            self.screen,
            overlay=self.overlay,
            cgh=self.cgh,
            dvr=self.dvr)

    def test_load_registers_tasks(self):
        from QHOT.tasks.ClearTraps import ClearTraps
        t1, t2 = ClearTraps(), ClearTraps()
        self.manager.register(t1)   # becomes active
        self.manager.register(t2)   # queued
        dicts = [t.to_dict() for t in self.manager.queued]
        self.manager.stop()
        self.manager.load(dicts)
        self.assertIsNotNone(self.manager.active_raw)

    def test_load_injects_overlay(self):
        from QHOT.tasks.ClearTraps import ClearTraps
        d = ClearTraps().to_dict()
        self.manager.load([d])
        self.assertIs(self.manager.active_raw.overlay, self.overlay)

    def test_load_injects_cgh(self):
        from QHOT.tasks.ClearTraps import ClearTraps
        d = ClearTraps().to_dict()
        self.manager.load([d])
        self.assertIs(self.manager.active_raw.cgh, self.cgh)

    def test_load_injects_dvr(self):
        from QHOT.tasks.ClearTraps import ClearTraps
        d = ClearTraps().to_dict()
        self.manager.load([d])
        self.assertIs(self.manager.active_raw.dvr, self.dvr)

    def test_load_preserves_task_params(self):
        from QHOT.tasks.Delay import Delay
        d = Delay(frames=99).to_dict()
        self.manager.load([d])
        self.assertEqual(self.manager.active_raw.frames, 99)

    def test_load_appends_to_existing_queue(self):
        from QHOT.tasks.ClearTraps import ClearTraps
        self.manager.register(QTask())       # becomes active
        self.manager.register(QTask())       # queued
        self.manager.load([ClearTraps().to_dict()])
        self.assertEqual(self.manager.queue_size, 2)

    def test_load_multiple_tasks_in_order(self):
        from QHOT.tasks.Delay import Delay
        dicts = [Delay(frames=i).to_dict() for i in (10, 20, 30)]
        self.manager.load(dicts)
        # first task activated (not yet stepped) — still in queued
        queued = self.manager.queued
        frames = [t.frames for t in queued]
        self.assertEqual(frames, [10, 20, 30])

    def test_load_empty_list_is_noop(self):
        self.manager.load([])
        self.assertIsNone(self.manager.active)
        self.assertEqual(self.manager.queue_size, 0)


class TestQTaskManagerChanged(unittest.TestCase):

    def setUp(self):
        self.screen  = MockScreen()
        self.manager = QTaskManager(self.screen)

    def _emit(self, n: int = 1) -> None:
        for _ in range(n):
            self.screen.rendered.emit()

    def test_changed_emitted_on_first_blocking_register(self):
        spy = QtTest.QSignalSpy(self.manager.changed)
        self.manager.register(QTask())
        self.assertGreater(len(spy), 0)

    def test_changed_emitted_on_queued_blocking_register(self):
        self.manager.register(QTask())           # activates
        spy = QtTest.QSignalSpy(self.manager.changed)
        self.manager.register(QTask())           # queues
        self.assertGreater(len(spy), 0)

    def test_changed_emitted_on_background_register(self):
        spy = QtTest.QSignalSpy(self.manager.changed)
        self.manager.register(QTask(), blocking=False)
        self.assertGreater(len(spy), 0)

    def test_changed_emitted_on_pause(self):
        spy = QtTest.QSignalSpy(self.manager.changed)
        self.manager.pause(True)
        self.assertEqual(len(spy), 1)

    def test_changed_not_emitted_on_repeated_pause(self):
        self.manager.pause(True)
        spy = QtTest.QSignalSpy(self.manager.changed)
        self.manager.pause(True)          # same state — no change
        self.assertEqual(len(spy), 0)

    def test_changed_emitted_on_resume(self):
        self.manager.pause(True)
        spy = QtTest.QSignalSpy(self.manager.changed)
        self.manager.pause(False)
        self.assertEqual(len(spy), 1)

    def test_changed_emitted_on_stop(self):
        self.manager.register(QTask())
        spy = QtTest.QSignalSpy(self.manager.changed)
        self.manager.stop()
        self.assertGreater(len(spy), 0)

    def test_changed_emitted_when_task_completes(self):
        self.manager.register(QTask(duration=1))
        spy = QtTest.QSignalSpy(self.manager.changed)
        self._emit(1)
        self.assertGreater(len(spy), 0)

    def test_changed_emitted_when_background_completes(self):
        self.manager.register(QTask(duration=1), blocking=False)
        spy = QtTest.QSignalSpy(self.manager.changed)
        self._emit(1)
        self.assertGreater(len(spy), 0)

    def test_changed_emitted_when_task_fails(self):
        task = QTask()
        self.manager.register(task)
        spy = QtTest.QSignalSpy(self.manager.changed)
        task.abort('test')
        self.assertGreater(len(spy), 0)


if __name__ == '__main__':
    unittest.main()
