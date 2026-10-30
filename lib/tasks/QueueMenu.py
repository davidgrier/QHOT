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
    ``manager`` before the menu is shown; the manager gives each task
    that it takes the resources that the task works with.

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
    '''

    def __init__(self, *args, title: str = 'Queue', **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setTitle(title)
        self._manager: QTaskManager | None = None
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

    # ------------------------------------------------------------------
    # Private

    def _populateMenu(self) -> None:
        '''Add one action per task type in the registry.

        ``QHOT.tasks`` is imported here to ensure all concrete task
        subclasses have been registered via ``__init_subclass__``
        before the menu is built.
        '''
        import QHOT.tasks  # noqa: F401 -- fills QTask._registry
        for name in QTask._registry:
            action = self.addAction(name)
            action.triggered.connect(
                functools.partial(self._onTaskSelected, name))

    @QtCore.Slot()
    def _onTaskSelected(self, name: str) -> None:
        '''Instantiate the chosen task and register it with the manager.

        The manager gives the task the resources that it works with.

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
        self._manager.enqueue([cls()])
        logger.debug(f'Queued {name}')
