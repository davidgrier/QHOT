from __future__ import annotations

import functools
import logging

from qtpy import QtCore, QtWidgets

from QHOT.lib.tasks.QTask import QTask
from QHOT.lib.tasks.QTaskManager import QTaskManager


logger = logging.getLogger(__name__)

__all__ = 'QueueMenu'.split()


class QueueMenu(QtWidgets.QMenu):

    '''Submenu for adding tasks to the task manager queue.

    Populates itself from ``QTask._registry`` and calls
    ``manager.register()`` when the user picks an entry.  Set
    ``manager``, ``overlay``, ``cgh``, and ``dvr`` before the menu
    is shown so that each newly queued task receives the correct
    hardware dependencies.

    Parameters
    ----------
    title : str
        Menu title shown in the menu bar.  Defaults to ``'Queue'``.
    *args, **kwargs
        Forwarded to ``QMenu``.

    Attributes
    ----------
    manager : QTaskManager or None
        Task manager that receives ``register()`` calls.
    overlay : QTrapOverlay or None
        Passed to tasks that manipulate the trap overlay.
    cgh : CGH or None
        Passed to tasks that compute holograms.
    dvr : QDVRWidget or None
        Passed to tasks that record video.
    '''

    def __init__(self, *args, title: str = 'Queue', **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setTitle(title)
        self._manager: QTaskManager | None = None
        self._overlay = None
        self._cgh = None
        self._dvr = None
        self._populateMenu()

    # ------------------------------------------------------------------
    # Properties

    @property
    def manager(self) -> QTaskManager | None:
        '''Task manager that receives register() calls.'''
        return self._manager

    @manager.setter
    def manager(self, manager: QTaskManager | None) -> None:
        self._manager = manager

    @property
    def overlay(self):
        '''Trap overlay passed to tasks that need it.'''
        return self._overlay

    @overlay.setter
    def overlay(self, overlay) -> None:
        self._overlay = overlay

    @property
    def cgh(self):
        '''CGH engine passed to tasks that need it.'''
        return self._cgh

    @cgh.setter
    def cgh(self, cgh) -> None:
        self._cgh = cgh

    @property
    def dvr(self):
        '''Video recorder passed to tasks that need it.'''
        return self._dvr

    @dvr.setter
    def dvr(self, dvr) -> None:
        self._dvr = dvr

    # ------------------------------------------------------------------
    # Private

    def _populateMenu(self) -> None:
        '''Add one action per task type in the registry.

        ``QHOT.tasks`` is imported here to ensure all concrete task
        subclasses have been registered via ``__init_subclass__``
        before the menu is built.
        '''
        import QHOT.tasks  # noqa: F401 — triggers __init_subclass__ registrations
        for name in QTask._registry:
            action = self.addAction(name)
            action.triggered.connect(
                functools.partial(self._onTaskSelected, name))

    @QtCore.Slot()
    def _onTaskSelected(self, name: str) -> None:
        '''Instantiate the chosen task and register it with the manager.

        All dependencies (overlay, cgh, dvr) are injected as keyword
        arguments; tasks that do not use a dependency simply ignore it.

        Parameters
        ----------
        name : str
            Class name as stored in ``QTask._registry``.
        '''
        if self._manager is None:
            logger.warning(f'No manager set; cannot queue {name!r}')
            return
        cls = QTask._registry.get(name)
        if cls is None:
            logger.warning(f'Unknown task type: {name!r}')
            return
        was_idle = (self._manager.active_raw is None
                    and not self._manager.background)
        task = cls(overlay=self._overlay, cgh=self._cgh, dvr=self._dvr)
        self._manager.register(task)
        if was_idle:
            self._manager.pause(True)
        logger.debug(f'Queued {name}')
