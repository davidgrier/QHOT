'''A task manager, driven as the window drives it.'''
from unittest.mock import MagicMock

from pyqtgraph.Qt import QtCore

from QHOT.lib.tasks import QTaskManager
from QHOT.lib.tasks.QTask import QTask

RESOURCES = 'overlay cgh dvr save image'.split()


def program_tasks() -> dict:
    '''The tasks of the program, by name.

    Every subclass of ``QTask`` registers itself, the ones that the tests
    define too, so the registry holds more than the program has.
    '''
    return {name: cls for name, cls in QTask._registry.items()
            if cls.__module__.startswith('QHOT.tasks.')}


class Screen(QtCore.QObject):

    '''The part of the screen that drives the tasks: a signal per frame.'''

    rendered = QtCore.Signal()


def attached(task, **resources):
    '''Give a task resources, as the manager that takes it would.'''
    for name, resource in resources.items():
        setattr(task, name, resource)
    return task


def manager_for(screen, **resources) -> QTaskManager:
    '''Return a task manager that steps whenever ``screen`` has rendered.

    The manager has all of its resources, as in the program: those that
    are not given are mocks.
    '''
    given = {name: MagicMock() for name in RESOURCES}
    given.update(resources)
    manager = QTaskManager(**given)
    screen.rendered.connect(manager.step)
    return manager
