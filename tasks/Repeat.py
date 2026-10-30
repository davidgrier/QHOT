import logging

from QHOT.lib.tasks.QTask import QTask


logger = logging.getLogger(__name__)


class Repeat(QTask):

    '''Repeat a bracketed block of tasks n times.

    Place ``BeginRepeat()`` before the block and ``Repeat(n)`` at the
    end.  On the first pass the block runs normally as part of the
    schedule.  When ``Repeat`` executes it injects n-1 fresh copies of
    the bracketed tasks back onto the front of the queue, each followed
    by a ``Repeat`` with a decremented counter.

    Nested ``BeginRepeat``/``Repeat`` pairs are supported.

    Parameters
    ----------
    n : int
        Total number of times the block executes.  ``n=1`` is a
        no-op (the block runs once, same as without any Repeat).
        Default: 1.
    **kwargs
        Forwarded to ``QTask``.  ``duration`` may not be supplied.

    Examples
    --------
    Move to position A, then move to position B, and cycle three
    times before snapping a final snapshot::

        manager.register(BeginRepeat())
        manager.register(Move(x=100, y=100))
        manager.register(Move(x=200, y=200))
        manager.register(Repeat(n=3))
        manager.register(Snapshot())
    '''

    parameters = [
        dict(name='n', type='int', value=1, default=1, min=1),
    ]

    def __init__(self, n: int = 1, *, _specs=None, **kwargs) -> None:
        if 'duration' in kwargs:
            raise TypeError("Repeat does not accept 'duration'")
        super().__init__(duration=0, **kwargs)
        self._n = int(n)
        # None for schedule tasks; set for injected copies
        self._specs = _specs

    @property
    def n(self) -> int:
        '''Total number of times the block executes.'''
        return self._n

    @n.setter
    def n(self, value: int) -> None:
        self._n = int(value)

    def initialize(self) -> None:
        if self._specs is None:
            self._specs = self._find_specs()
        if self._n <= 1 or not self._specs:
            return
        new_tasks = [QTask.from_dict(s) for s in self._specs]
        new_tasks.append(Repeat(n=self._n - 1, _specs=self._specs))
        self.manager.inject(new_tasks)

    def _find_specs(self) -> list:
        '''Scan the schedule backwards to find the matching BeginRepeat.

        Handles nesting by tracking depth: each ``Repeat`` encountered
        while scanning backwards increments the skip counter; each
        ``BeginRepeat`` decrements it.  The first ``BeginRepeat`` at
        depth zero is our bracket.

        Returns
        -------
        list[dict]
            Serialised specs of every task between ``BeginRepeat`` and
            this ``Repeat``, in execution order.  Empty list if no
            matching bracket is found.
        '''
        from QHOT.tasks.BeginRepeat import BeginRepeat
        schedule = self.manager._schedule
        try:
            my_idx = next(i for i, t in enumerate(schedule) if t is self)
        except StopIteration:
            logger.warning('Repeat: task not found in schedule')
            return []
        to_skip = 0
        begin_idx = None
        for i in range(my_idx - 1, -1, -1):
            task = schedule[i]
            if isinstance(task, Repeat):
                to_skip += 1
            elif isinstance(task, BeginRepeat):
                if to_skip > 0:
                    to_skip -= 1
                else:
                    begin_idx = i
                    break
        if begin_idx is None:
            logger.warning('Repeat: no matching BeginRepeat found in schedule')
            return []
        return [t.to_dict() for t in schedule[begin_idx + 1:my_idx]]

    def to_dict(self) -> dict:
        d = super().to_dict()
        if self._specs is not None:
            d['_specs'] = self._specs
        return d
