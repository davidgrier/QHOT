from __future__ import annotations

import logging
from collections import deque

from qtpy import QtCore

from QVideo.dvr import QDVRWidget
from QHOT.lib.QHOTScreen import QHOTScreen
from QHOT.lib.traps.QTrapOverlay import QTrapOverlay
from QHOT.lib.holograms.CGH import CGH
from QHOT.lib.tasks.QTask import QTask


logger = logging.getLogger(__name__)


class QTaskManager(QtCore.QObject):

    '''Schedules and dispatches QHOT tasks.

    Connects to ``QHOTScreen.rendered`` and advances each registered
    task by one step per video frame.  Blocking tasks are queued
    sequentially: the next task starts only after the current one
    finishes.  Non-blocking tasks start immediately and run in
    parallel with the blocking queue.

    The full ordered list of registered blocking tasks is retained in
    ``scheduled`` even after tasks complete, so the same sequence can
    be inspected and re-run.  Call ``clear()`` to discard it, or
    ``restart()`` to run it again from fresh instances.

    When a blocking task finishes, the completed task object is
    passed to the next task's ``initialize()`` via ``task.previous``,
    allowing results to flow down the queue without a shared
    dictionary.

    If a blocking task fails, the remaining pending tasks are cleared
    and logged.  Background tasks fail independently without
    affecting the queue.

    Parameters
    ----------
    screen : QHOTScreen
        The live video screen.  Its ``rendered`` signal drives all
        registered tasks.
    overlay : QTrapOverlay or None
        Trap overlay, stored as ``self.overlay`` for tasks that need
        it.  ``None`` if not available.
    cgh : CGH or None
        Hologram computation engine, stored as ``self.cgh``.
    dvr : QDVRWidget or None
        Video recorder, stored as ``self.dvr``.
    save : QSaveFile or None
        File-save helper, stored as ``self.save``.

    Attributes
    ----------
    overlay : QTrapOverlay or None
        Trap overlay (readable by tasks via ``self.manager``).
    cgh : CGH or None
        Hologram computation engine.
    dvr : object or None
        Video recorder.
    save : object or None
        File-save helper.
    '''

    #: Emitted whenever the active task, queue, background list, or
    #: pause state changes.  Connect widgets to this signal and call
    #: their refresh method to stay up to date.
    changed = QtCore.Signal()

    def __init__(self,
                 screen: QHOTScreen,
                 *,
                 overlay: QTrapOverlay | None = None,
                 cgh: CGH | None = None,
                 dvr: QDVRWidget | None = None,
                 save=None,
                 parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self.overlay = overlay
        self.cgh = cgh
        self.dvr = dvr
        self.save = save
        self._schedule:        list[QTask] = []
        self._queue:           deque[QTask] = deque()
        self._background:      list[QTask] = []
        self._current:         QTask | None = None
        self._current_stepped: bool = False
        self._paused:          bool = False
        screen.rendered.connect(self._onFrame)

    # ------------------------------------------------------------------
    # Public read-only properties

    @property
    def paused(self) -> bool:
        '''True when frame dispatch is suspended for all tasks.'''
        return self._paused

    @property
    def active(self) -> QTask | None:
        '''The blocking task that has received at least one frame, or ``None``.

        A task that has been activated but not yet stepped (e.g. because
        the manager is paused) is not considered active; it appears in
        ``queued`` instead.
        '''
        return self._current if self._current_stepped else None

    @property
    def active_raw(self) -> QTask | None:
        '''The activated blocking task whether or not it has been stepped.

        Used internally.  Prefer ``active`` for display and ``queued``
        for the full list of not-yet-completed tasks.
        '''
        return self._current

    @property
    def queue_size(self) -> int:
        '''Number of blocking tasks waiting (excludes active task).'''
        return len(self._queue)

    @property
    def queued(self) -> list[QTask]:
        '''All blocking tasks not yet receiving frames.

        Includes the activated-but-not-yet-stepped task (if any) at
        position 0, followed by the remaining pending tasks.  This is
        the canonical list for saving.
        '''
        head = ([] if self._current_stepped or self._current is None
                else [self._current])
        return head + list(self._queue)

    @property
    def scheduled(self) -> list[QTask]:
        '''All registered blocking tasks in registration order.

        Includes tasks in every state (pending, running, completed,
        failed).  This list persists until ``clear()`` is called,
        allowing completed runs to be inspected and restarted.
        '''
        return list(self._schedule)

    @property
    def background(self) -> list[QTask]:
        '''Snapshot of the currently running background tasks.'''
        return list(self._background)

    # ------------------------------------------------------------------
    # Public control

    def register(self,
                 task: QTask,
                 *,
                 blocking: bool = True) -> QTask:
        '''Register a task with the manager.

        Blocking tasks are run one at a time in the order they are
        registered.  The first blocking task starts immediately; each
        subsequent task waits for the previous one to finish.

        Non-blocking tasks start immediately and run in parallel with
        the blocking queue until they complete or are stopped.

        Parameters
        ----------
        task : QTask
            The task to register.
        blocking : bool
            ``True`` (default) to add to the sequential blocking
            queue.  ``False`` to start immediately as a background
            task.

        Returns
        -------
        QTask
            The registered task, for inspection or chaining.
        '''
        if blocking:
            task.manager = self
            task.finished.connect(self._onBlockingFinished)
            task.failed.connect(self._onBlockingFailed)
            self._schedule.append(task)
            self._queue.append(task)
            if self._current is None:
                self._activateNext()
            else:
                self.changed.emit()
        else:
            task.finished.connect(self._onBackgroundFinished)
            task.failed.connect(self._onBackgroundFailed)
            self._background.append(task)
            task._start()
            self.changed.emit()
        return task

    def pause(self, state: bool = True) -> None:
        '''Suspend or resume frame dispatch for all tasks.

        Parameters
        ----------
        state : bool
            ``True`` to pause (default), ``False`` to resume.
        '''
        if state != self._paused:
            self._paused = state
            self.changed.emit()

    def load(self, task_dicts: list[dict]) -> None:
        '''Deserialise a list of task dicts and append them to the queue.

        Dependencies (overlay, cgh, dvr) held by the manager are
        injected into each reconstructed task before registration.

        ``QHOT.tasks`` is imported lazily here to ensure all concrete
        subclasses have registered themselves via ``__init_subclass__``
        before ``QTask.from_dict`` is called.

        Parameters
        ----------
        task_dicts : list[dict]
            Dicts previously produced by ``QTask.to_dict()``.
        '''
        import QHOT.tasks  # noqa: F401 — populate QTask._registry
        for d in task_dicts:
            task = QTask.from_dict(d)
            task.overlay = self.overlay
            task.cgh = self.cgh
            task.dvr = self.dvr
            task.save = self.save
            self.register(task)

    def stop(self) -> None:
        '''Rewind the schedule to the beginning and pause.

        Aborts any running tasks, resets every scheduled task to
        ``PENDING``, and leaves the manager paused at the first task —
        ready to run again when ``pause(False)`` is called.
        The ``scheduled`` list is preserved.  Call ``clear()`` to
        discard it entirely.
        '''
        self._abort_active_and_background()
        self._reset_to_start()
        self.changed.emit()

    def clear(self) -> None:
        '''Stop all tasks and discard the entire schedule.

        After this call the manager is completely idle with no
        registered blocking tasks.
        '''
        self._abort_active_and_background()
        self._schedule.clear()
        self._queue.clear()
        self._current = None
        self._current_stepped = False
        self._paused = False
        self.changed.emit()

    def restart(self) -> None:
        '''Re-run the current schedule from fresh task instances.

        Serialises the current ``scheduled`` list, clears the manager,
        then reloads the specs so that every task starts from
        ``PENDING`` with its saved parameters.  Has no effect if the
        schedule is empty.
        '''
        specs = [t.to_dict() for t in self._schedule]
        if not specs:
            return
        self.clear()
        self.load(specs)

    def remove(self, task: QTask) -> None:
        '''Remove a task from the schedule and pending queue.

        Has no effect if *task* is not in the schedule, or if it is
        the currently active (running) task.

        Parameters
        ----------
        task : QTask
            The task to remove.
        '''
        if task is self._current:
            logger.warning('remove: cannot remove the active task')
            return
        if task not in self._schedule:
            return
        self._schedule.remove(task)
        try:
            self._queue.remove(task)
        except ValueError:
            pass  # completed or failed — not in the pending queue
        self.changed.emit()

    def reorder(self, tasks: 'list[QTask]') -> None:
        '''Reorder the persistent schedule and pending queue.

        Accepts a permutation of the current ``scheduled`` list and
        updates the manager so that pending tasks run in the new order.
        Already-running and completed tasks are left in place; only the
        relative order of ``PENDING`` tasks changes.

        Has no effect if *tasks* does not contain exactly the same task
        objects as ``scheduled`` (checked by identity, not equality).

        Parameters
        ----------
        tasks : list[QTask]
            All scheduled tasks in the desired new order.
        '''
        if {id(t) for t in tasks} != {id(t) for t in self._schedule}:
            logger.warning('reorder: task set mismatch; ignoring')
            return
        self._schedule[:] = tasks
        pending = [t for t in tasks
                   if t.state is QTask.State.PENDING
                   and t is not self._current]
        self._queue.clear()
        self._queue.extend(pending)
        self.changed.emit()

    def inject(self, tasks: 'list[QTask]') -> None:
        '''Prepend tasks to the blocking queue without adding to the schedule.

        Used by ``Repeat`` to insert fresh copies of a sub-sequence at
        the front of the queue.  The manager's resources are injected
        into each task and signal connections are wired up, but the
        tasks are **not** added to ``_schedule``, so they do not persist
        across ``stop()`` / ``restart()`` calls.

        Parameters
        ----------
        tasks : list[QTask]
            Tasks to insert, in execution order.
        '''
        for task in tasks:
            task.overlay = self.overlay
            task.cgh = self.cgh
            task.dvr = self.dvr
            task.save = self.save
            task.manager = self
            task.finished.connect(self._onBlockingFinished)
            task.failed.connect(self._onBlockingFailed)
        self._queue.extendleft(reversed(tasks))

    # ------------------------------------------------------------------
    # Private slots

    @QtCore.Slot()
    def _onFrame(self) -> None:
        if self._paused:
            return
        if self._current is not None:
            if not self._current_stepped:
                self._current_stepped = True
                self.changed.emit()   # task moves from queue to active display
            self._current._step()
        for task in list(self._background):
            task._step()

    @QtCore.Slot()
    def _onBlockingFinished(self) -> None:
        task = self.sender()
        if self._current is task:
            logger.debug(f'Blocking task {type(task).__name__} finished')
            self._activateNext(previous=task)

    @QtCore.Slot(str)
    def _onBlockingFailed(self, reason: str) -> None:
        task = self.sender()
        logger.error(f'Blocking task {type(task).__name__} '
                     f'failed ({reason}); clearing pending tasks')
        self._queue.clear()
        if self._current is task:
            self._current = None
            self._current_stepped = False
        self.changed.emit()

    @QtCore.Slot()
    def _onBackgroundFinished(self) -> None:
        task = self.sender()
        logger.debug(f'Background task {type(task).__name__} finished')
        if task in self._background:
            self._background.remove(task)
        self.changed.emit()

    @QtCore.Slot(str)
    def _onBackgroundFailed(self, reason: str) -> None:
        task = self.sender()
        logger.error(f'Background task {type(task).__name__} '
                     f'failed: {reason}')
        if task in self._background:
            self._background.remove(task)
        self.changed.emit()

    # ------------------------------------------------------------------
    # Private helpers

    def _abort_active_and_background(self) -> None:
        '''Abort the active and all background tasks.

        Clears ``_queue`` first so that ``_onBlockingFailed`` (which
        fires synchronously inside ``abort()``) finds an already-empty
        queue and treats the abort as a no-op to the schedule.
        '''
        self._queue.clear()
        if self._current is not None:
            self._current.abort('manager stopped')
        for task in list(self._background):
            task.abort('manager stopped')
        self._background.clear()
        self._current = None
        self._current_stepped = False

    def _reset_to_start(self) -> None:
        '''Reset every scheduled task to PENDING and activate the first.

        Repopulates ``_queue`` from ``_schedule``, pops and starts the
        first task, and sets ``_paused = True`` so execution waits for
        an explicit resume.
        '''
        for task in self._schedule:
            task.reset()
            self._queue.append(task)
        if self._queue:
            self._current = self._queue.popleft()
            self._current_stepped = False
            self._current._start()
        self._paused = True

    def _activateNext(self,
                      previous: QTask | None = None) -> None:
        if self._queue:
            self._current = self._queue.popleft()
            self._current_stepped = False
            self._current._start(previous)
            logger.debug(f'Activating {type(self._current).__name__}')
        else:
            self._current = None
            self._current_stepped = False
            if self._schedule:
                # All tasks completed — reset to start for next run
                self._reset_to_start()
                logger.debug('Schedule complete; reset and paused')
        self.changed.emit()
