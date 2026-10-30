'''A task manager, driven as the window drives it.'''
from unittest.mock import MagicMock

from QHOT.lib.tasks import QTaskManager

RESOURCES = 'overlay cgh dvr save image'.split()


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
