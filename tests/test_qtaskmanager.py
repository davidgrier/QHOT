'''Unit tests for QTaskManager.'''
import unittest
from unittest.mock import MagicMock

from pyqtgraph.Qt import QtCore, QtWidgets, QtTest

from QHOT.lib.tasks.QTask import QTask
from QHOT.lib.tasks.QTaskManager import QTaskManager

try:
    from taskmanagers import RESOURCES, manager_for
except ImportError:  # run from the root of the repository
    from tests.taskmanagers import RESOURCES, manager_for

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class MockScreen(QtCore.QObject):
    '''Minimal screen substitute with a rendered signal.'''
    rendered = QtCore.pyqtSignal()


class TestQTaskManagerInit(unittest.TestCase):

    def setUp(self):
        self.screen = MockScreen()

    def test_no_active_task_initially(self):
        mgr = manager_for(self.screen)
        self.assertIsNone(mgr.active)

    def test_queue_size_zero_initially(self):
        mgr = manager_for(self.screen)
        self.assertEqual(mgr.queueSize, 0)

    def test_background_empty_initially(self):
        mgr = manager_for(self.screen)
        self.assertEqual(mgr.background, [])

    def test_not_paused_initially(self):
        mgr = manager_for(self.screen)
        self.assertFalse(mgr.paused)

    def test_overlay_stored(self):
        overlay = MagicMock()
        mgr = manager_for(self.screen, overlay=overlay)
        self.assertIs(mgr.overlay, overlay)

    def test_cgh_stored(self):
        cgh = MagicMock()
        mgr = manager_for(self.screen, cgh=cgh)
        self.assertIs(mgr.cgh, cgh)


class TestQTaskManagerRegistration(unittest.TestCase):

    def setUp(self):
        self.screen  = MockScreen()
        self.manager = manager_for(self.screen)

    def test_first_blocking_task_becomes_active(self):
        task = QTask()
        self.manager.register(task)
        self.assertIs(self.manager.activeRaw, task)

    def test_first_blocking_task_starts_running(self):
        task = QTask()
        self.manager.register(task)
        self.assertEqual(task.state, QTask.State.RUNNING)

    def test_second_blocking_task_queued(self):
        t1, t2 = QTask(), QTask()
        self.manager.register(t1)
        self.manager.register(t2)
        self.assertEqual(self.manager.queueSize, 1)

    def test_third_blocking_task_increments_queue(self):
        t1, t2, t3 = QTask(), QTask(), QTask()
        self.manager.register(t1)
        self.manager.register(t2)
        self.manager.register(t3)
        self.assertEqual(self.manager.queueSize, 2)

    def test_nonblocking_task_not_queued(self):
        task = QTask()
        self.manager.register(task, blocking=False)
        self.assertEqual(self.manager.queueSize, 0)
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


class TestQTaskManagerResources(unittest.TestCase):

    '''The manager gives its tasks the resources that they work with.'''

    def setUp(self):
        self.resources = {name: MagicMock() for name in RESOURCES}
        self.manager = QTaskManager(**self.resources)

    def assertHasAll(self, task):
        for name, resource in self.resources.items():
            self.assertIs(getattr(task, name), resource, name)
        self.assertIs(task.manager, self.manager)

    def test_every_resource_is_required(self):
        for missing in RESOURCES:
            given = {k: v for k, v in self.resources.items() if k != missing}
            with self.subTest(missing), self.assertRaises(TypeError):
                QTaskManager(**given)

    def test_the_resources_are_the_ones_that_tasks_work_with(self):
        self.assertEqual(sorted(QTaskManager.RESOURCES), sorted(RESOURCES))
        for name in RESOURCES:
            self.assertIs(getattr(self.manager, name), self.resources[name])

    def test_a_registered_task_gets_them(self):
        task = self.manager.register(QTask())
        self.assertHasAll(task)

    def test_a_background_task_gets_them(self):
        task = self.manager.register(QTask(), blocking=False)
        self.assertHasAll(task)

    def test_a_loaded_task_gets_them(self):
        from QHOT.tasks import Delay
        self.manager.load([Delay(frames=2).toDict()])
        self.assertHasAll(self.manager.scheduled[-1])

    def test_an_injected_task_gets_them(self):
        task = QTask()
        self.manager.inject([task])
        self.assertHasAll(task)

    def test_a_resource_that_a_task_was_given_is_its_own(self):
        mine = MagicMock()
        task = self.manager.register(QTask(overlay=mine))
        self.assertIs(task.overlay, mine)
        self.assertIs(task.cgh, self.resources['cgh'])

    def test_step_advances_the_tasks_when_it_is_called(self):
        task = QTask(duration=3)
        self.manager.register(task)
        self.manager.step()
        self.manager.step()
        self.assertEqual(task._frame, 2)


class TestQTaskManagerUserAdditions(unittest.TestCase):

    '''What the user adds is looked at before it runs.'''

    def setUp(self):
        self.screen = MockScreen()
        self.manager = manager_for(self.screen)

    def test_tasks_that_are_enqueued_are_registered_in_order(self):
        a, b = QTask(), QTask()
        self.manager.enqueue([a, b])
        self.assertEqual(self.manager.scheduled, [a, b])

    def test_an_idle_manager_is_paused_by_what_is_enqueued(self):
        self.manager.enqueue([QTask()])
        self.assertTrue(self.manager.paused)

    def test_a_manager_that_is_running_a_task_is_not_paused(self):
        self.manager.register(QTask(duration=5))
        self.manager.enqueue([QTask()])
        self.assertFalse(self.manager.paused)

    def test_a_manager_with_a_background_task_is_not_paused(self):
        self.manager.register(QTask(duration=5), blocking=False)
        self.manager.enqueue([QTask()])
        self.assertFalse(self.manager.paused)

    def test_enqueueing_nothing_pauses_an_idle_manager_harmlessly(self):
        self.manager.enqueue([])
        self.assertEqual(self.manager.scheduled, [])

    def test_a_loaded_queue_is_paused_when_the_manager_was_idle(self):
        from QHOT.tasks import Delay
        self.manager.load([Delay(frames=2).toDict()])
        self.assertTrue(self.manager.paused)
        self.assertEqual(len(self.manager.scheduled), 1)

    def test_the_queue_is_a_list_that_load_reads(self):
        from QHOT.tasks import Delay
        self.manager.pause(True)
        self.manager.register(Delay(frames=3))
        self.manager.register(Delay(frames=7))
        saved = self.manager.toList()
        self.assertEqual([d['type'] for d in saved], ['Delay', 'Delay'])
        other = manager_for(MockScreen())
        other.load(saved)
        self.assertEqual(other.toList(), saved)

    def test_the_queue_leaves_out_what_is_running(self):
        from QHOT.tasks import Delay
        self.manager.register(Delay(frames=5))
        self.manager.register(Delay(frames=6))
        self.screen.rendered.emit()                  # the first is running
        self.assertEqual(len(self.manager.toList()), 1)


class TestQTaskManagerFrameDispatch(unittest.TestCase):

    def setUp(self):
        self.screen  = MockScreen()
        self.manager = manager_for(self.screen)

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
        self.manager = manager_for(self.screen)

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
        self.assertIs(self.manager.activeRaw, t2)

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
        self.assertEqual(self.manager.queueSize, 2)
        self._emit(1)
        self.assertEqual(self.manager.queueSize, 1)
        self._emit(1)
        self.assertEqual(self.manager.queueSize, 0)

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
        self.assertEqual(self.manager.queueSize, 0)
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
        self.manager = manager_for(self.screen)

    def test_stop_rewinds_queue(self):
        # After stop, tasks are reset and first is activated;
        # remaining tasks are back in the queue.
        for _ in range(3):
            self.manager.register(QTask())
        self.manager.stop()
        self.assertEqual(self.manager.queueSize, 2)

    def test_stop_resets_active_task_to_running(self):
        # stop() aborts the current task then resets and re-activates it.
        task = QTask()
        self.manager.register(task)
        self.manager.stop()
        # Task is reset to PENDING then immediately started → RUNNING,
        # but not yet stepped so active returns None.
        self.assertIsNone(self.manager.active)
        self.assertEqual(self.manager.activeRaw.state, QTask.State.RUNNING)

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
        self.manager = manager_for(self.screen)

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
        self.assertEqual(self.manager.queueSize, 0)

    def test_clear_on_empty_manager_does_not_raise(self):
        self.manager.clear()

    def test_restart_reruns_schedule(self):
        from QHOT.tasks.Delay import Delay
        self.manager.register(Delay(frames=5))
        self.manager.restart()
        self.assertEqual(len(self.manager.scheduled), 1)
        self.assertEqual(self.manager.activeRaw.frames, 5)

    def test_restart_creates_fresh_instances(self):
        from QHOT.tasks.Delay import Delay
        task = Delay(frames=1)
        self.manager.register(task)
        self._emit(1)         # task completes
        self.manager.restart()
        new_task = self.manager.activeRaw
        self.assertIsNot(new_task, task)
        self.assertEqual(new_task.state, QTask.State.RUNNING)

    def test_restart_on_empty_schedule_is_noop(self):
        self.manager.restart()  # should not raise
        self.assertEqual(self.manager.scheduled, [])


class TestQTaskManagerAutoReset(unittest.TestCase):

    def setUp(self):
        self.screen  = MockScreen()
        self.manager = manager_for(self.screen)

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
        self.assertIs(self.manager.activeRaw, task)

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

    def test_stop_leaves_manager_paused(self):
        from QHOT.tasks.Delay import Delay
        self.manager.register(Delay(frames=1))
        self.manager.stop()
        self.assertTrue(self.manager.paused)


class TestQTaskManagerBackground(unittest.TestCase):

    def setUp(self):
        self.screen  = MockScreen()
        self.manager = manager_for(self.screen)

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
        self.manager = manager_for(
            self.screen,
            overlay=self.overlay,
            cgh=self.cgh,
            dvr=self.dvr)

    def test_load_registers_tasks(self):
        from QHOT.tasks.ClearTraps import ClearTraps
        t1, t2 = ClearTraps(), ClearTraps()
        self.manager.register(t1)   # becomes active
        self.manager.register(t2)   # queued
        dicts = [t.toDict() for t in self.manager.queued]
        self.manager.stop()
        self.manager.load(dicts)
        self.assertIsNotNone(self.manager.activeRaw)

    def test_load_injects_overlay(self):
        from QHOT.tasks.ClearTraps import ClearTraps
        d = ClearTraps().toDict()
        self.manager.load([d])
        self.assertIs(self.manager.activeRaw.overlay, self.overlay)

    def test_load_injects_cgh(self):
        from QHOT.tasks.ClearTraps import ClearTraps
        d = ClearTraps().toDict()
        self.manager.load([d])
        self.assertIs(self.manager.activeRaw.cgh, self.cgh)

    def test_load_injects_dvr(self):
        from QHOT.tasks.ClearTraps import ClearTraps
        d = ClearTraps().toDict()
        self.manager.load([d])
        self.assertIs(self.manager.activeRaw.dvr, self.dvr)

    def test_load_preserves_task_params(self):
        from QHOT.tasks.Delay import Delay
        d = Delay(frames=99).toDict()
        self.manager.load([d])
        self.assertEqual(self.manager.activeRaw.frames, 99)

    def test_load_appends_to_existing_queue(self):
        from QHOT.tasks.ClearTraps import ClearTraps
        self.manager.register(QTask())       # becomes active
        self.manager.register(QTask())       # queued
        self.manager.load([ClearTraps().toDict()])
        self.assertEqual(self.manager.queueSize, 2)

    def test_load_multiple_tasks_in_order(self):
        from QHOT.tasks.Delay import Delay
        dicts = [Delay(frames=i).toDict() for i in (10, 20, 30)]
        self.manager.load(dicts)
        # first task activated (not yet stepped) — still in queued
        queued = self.manager.queued
        frames = [t.frames for t in queued]
        self.assertEqual(frames, [10, 20, 30])

    def test_load_empty_list_is_noop(self):
        self.manager.load([])
        self.assertIsNone(self.manager.active)
        self.assertEqual(self.manager.queueSize, 0)


class TestQTaskManagerRemove(unittest.TestCase):

    def setUp(self):
        self.screen  = MockScreen()
        self.manager = manager_for(self.screen)

    def _register(self, n: int) -> list:
        tasks = [QTask() for _ in range(n)]
        for t in tasks:
            self.manager.register(t)
        return tasks

    def test_remove_pending_task_from_schedule(self):
        t1, t2 = self._register(2)
        self.manager.remove(t2)
        self.assertNotIn(t2, self.manager.scheduled)

    def test_remove_pending_task_from_queue(self):
        t1, t2 = self._register(2)
        self.manager.remove(t2)
        self.assertEqual(self.manager.queueSize, 0)

    def test_remove_active_task_is_ignored(self):
        t1, t2 = self._register(2)
        # t1 is active
        self.manager.remove(t1)
        self.assertIn(t1, self.manager.scheduled)
        self.assertIs(self.manager.activeRaw, t1)

    def test_remove_active_logs_warning(self):
        t1 = self._register(1)[0]
        with self.assertLogs('QHOT.lib.tasks.QTaskManager', level='WARNING'):
            self.manager.remove(t1)

    def test_remove_task_not_in_schedule_is_noop(self):
        t1 = self._register(1)[0]
        outsider = QTask()
        self.manager.remove(outsider)   # should not raise
        self.assertEqual(len(self.manager.scheduled), 1)

    def test_remove_completed_task(self):
        from QHOT.tasks.Delay import Delay
        mgr = manager_for(self.screen)
        d1 = Delay(frames=0)
        d2 = Delay(frames=0)
        mgr.register(d1)
        mgr.register(d2)
        self.screen.rendered.emit()   # d1 completes
        self.assertEqual(d1.state, QTask.State.COMPLETED)
        mgr.remove(d1)
        self.assertNotIn(d1, mgr.scheduled)

    def test_remove_emits_changed(self):
        t1, t2 = self._register(2)
        spy = QtTest.QSignalSpy(self.manager.changed)
        self.manager.remove(t2)
        self.assertGreater(len(spy), 0)

    def test_remove_only_removes_one_task(self):
        t1, t2, t3 = self._register(3)
        self.manager.remove(t2)
        self.assertEqual(len(self.manager.scheduled), 2)
        self.assertIn(t1, self.manager.scheduled)
        self.assertIn(t3, self.manager.scheduled)


class TestQTaskManagerChanged(unittest.TestCase):

    def setUp(self):
        self.screen  = MockScreen()
        self.manager = manager_for(self.screen)

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


class TestQTaskManagerReorder(unittest.TestCase):

    def setUp(self):
        self.screen  = MockScreen()
        self.manager = manager_for(self.screen)

    def _register(self, n: int) -> list:
        tasks = [QTask() for _ in range(n)]
        for t in tasks:
            self.manager.register(t)
        return tasks

    def test_reorder_changes_schedule_order(self):
        t1, t2, t3 = self._register(3)
        self.manager.reorder([t3, t1, t2])
        self.assertEqual(self.manager.scheduled, [t3, t1, t2])

    def test_reorder_changes_queue_order(self):
        t1, t2, t3 = self._register(3)
        # t1 is active (running), t2 and t3 are pending in queue
        self.manager.reorder([t1, t3, t2])
        self.assertEqual(list(self.manager._queue), [t3, t2])

    def test_reorder_active_task_excluded_from_queue(self):
        t1, t2, t3 = self._register(3)
        # t1 is currently active (_current); reorder puts t1 last
        self.manager.reorder([t2, t3, t1])
        # t1 is still _current, not re-enqueued
        self.assertIs(self.manager.activeRaw, t1)
        self.assertNotIn(t1, list(self.manager._queue))

    def test_reorder_with_wrong_tasks_ignored(self):
        t1, t2 = self._register(2)
        outsider = QTask()
        original = self.manager.scheduled[:]
        self.manager.reorder([t1, outsider])
        self.assertEqual(self.manager.scheduled, original)

    def test_reorder_emits_changed(self):
        t1, t2 = self._register(2)
        spy = QtTest.QSignalSpy(self.manager.changed)
        self.manager.reorder([t2, t1])
        self.assertGreater(len(spy), 0)

    def test_reorder_completed_tasks_stay_in_place(self):
        screen = self.screen
        t1, t2, t3 = self._register(3)
        # Complete t1 by stepping it (t1 has duration=None, won't complete)
        # Use a zero-duration task instead
        from QHOT.tasks.Delay import Delay
        mgr = manager_for(screen)
        d1 = Delay(frames=0)
        d2 = Delay(frames=0)
        d3 = Delay(frames=0)
        mgr.register(d1)
        mgr.register(d2)
        mgr.register(d3)
        screen.rendered.emit()   # d1 completes, d2 activates
        self.assertEqual(d1.state, QTask.State.COMPLETED)
        # Reorder d2 and d3 (both PENDING/RUNNING)
        mgr.reorder([d1, d3, d2])
        self.assertEqual(mgr.scheduled, [d1, d3, d2])

    def test_reorder_preserves_same_set(self):
        t1, t2, t3 = self._register(3)
        self.manager.reorder([t3, t2, t1])
        self.assertEqual(set(id(t) for t in self.manager.scheduled),
                         {id(t1), id(t2), id(t3)})


if __name__ == '__main__':
    unittest.main()
