from qtpy import QtCore
from pyqtgraph.parametertree import Parameter, ParameterTree


from QHOT.lib.tasks.QTask import QTask


__all__ = ['QTaskTree']


class QTaskTree(ParameterTree):

    '''ParameterTree widget for editing a QTask's parameters.

    Builds a ``Parameter`` group from the task's ``parameters`` spec,
    initialises values from the current task instance attributes, and
    writes every user edit back to the task via ``setattr``.

    Intended to be created on demand when the user selects a task in
    ``QTaskManagerWidget`` and destroyed when the task is deselected or
    removed from the queue.

    Parameters
    ----------
    task : QTask
        The task whose parameters are displayed and edited.
    *args, **kwargs
        Forwarded to ``ParameterTree``.

    Attributes
    ----------
    task : QTask
        The task being displayed (read-only).
    '''

    def __init__(self, task: QTask, *args, **kwargs) -> None:
        kwargs.setdefault('showHeader', False)
        super().__init__(*args, **kwargs)
        self._task = task
        self._ignoreSync = False
        self._params = self._buildParams()
        self.setParameters(self._params, showTop=True)
        self._params.sigTreeStateChanged.connect(self._sync)

    @property
    def task(self) -> QTask:
        '''The task being displayed.'''
        return self._task

    def _buildParams(self) -> Parameter:
        '''Build a Parameter group initialised from task instance attrs.'''
        specs = []
        for spec in type(self._task).parameters:
            s = dict(spec)
            s['value'] = getattr(self._task, s['name'], s.get('value'))
            s.setdefault('default', s['value'])
            specs.append(s)
        return Parameter.create(
            name=type(self._task).__name__, type='group', children=specs)

    @QtCore.Slot(object, object)
    def _sync(self, _param, changes) -> None:
        '''Write parameter changes back to the task instance.'''
        if self._ignoreSync:
            return
        for param, change, value in changes:
            if change == 'value':
                setattr(self._task, param.name(), value)
