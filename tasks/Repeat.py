from QHOT.lib.tasks.QTask import QTask


def _opening(kinds: list[str], closing: int) -> int | None:
    '''Return the place of the BeginRepeat that the Repeat at *closing* closes.

    Handles nesting by counting backwards: each ``Repeat`` skips one
    ``BeginRepeat``, and the first one that is not skipped is the bracket.

    Parameters
    ----------
    kinds : list[str]
        The names of the classes of the tasks, in order.
    closing : int
        Place of the ``Repeat`` in *kinds*.

    Returns
    -------
    int or None
        Place of its ``BeginRepeat``, or ``None`` if there is none.
    '''
    skip = 0
    for i in range(closing - 1, -1, -1):
        if kinds[i] == 'Repeat':
            skip += 1
        elif kinds[i] == 'BeginRepeat':
            if skip:
                skip -= 1
            else:
                return i
    return None


def _resolve(specs: list[dict]) -> list[dict]:
    '''Give each Repeat in a block of specs the block that it repeats.

    The copy of a block is made from its specs and is not in the schedule,
    where a ``Repeat`` would look for its ``BeginRepeat``.  The block of
    each ``Repeat`` is found here, in the specs, at any depth of nesting.

    Parameters
    ----------
    specs : list[dict]
        Serialized tasks in execution order.

    Returns
    -------
    list[dict]
        The same specs, with ``_specs`` in those of the ``Repeat`` tasks.
    '''
    resolved = [dict(spec) for spec in specs]
    kinds = [spec['type'] for spec in resolved]
    for i, spec in enumerate(resolved):
        if kinds[i] == 'Repeat' and '_specs' not in spec:
            begin = _opening(kinds, i)
            if begin is not None:
                spec['_specs'] = resolved[begin + 1:i]
    return resolved


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

    parameters = (
        dict(name='n', type='int', value=1, default=1, min=1),
    )

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
        '''Queue n - 1 more copies of the block, each with its own Repeat.

        The block is looked for in the schedule every time, so that a task
        that the user changed since the last run is the one that repeats.
        A copy is not in the schedule, so each ``Repeat`` in it is told
        its block (:func:`_resolve`).

        Raises
        ------
        ValueError
            If the block is to be repeated and there is no ``BeginRepeat``
            for it: the queue would run it once, not ``n`` times.
        '''
        if self._n <= 1:
            return
        specs = self._specs if self._specs is not None else self._findSpecs()
        if not specs:
            return
        new_tasks = [QTask.fromDict(s) for s in _resolve(specs)]
        new_tasks.append(Repeat(n=self._n - 1, _specs=specs))
        self.manager.inject(new_tasks)

    def _findSpecs(self) -> list:
        '''Find the matching BeginRepeat in the schedule; return the block.

        Returns
        -------
        list[dict]
            Serialized specs of every task between ``BeginRepeat`` and
            this ``Repeat``, in execution order.

        Raises
        ------
        ValueError
            If this ``Repeat`` is not in the schedule or has no
            ``BeginRepeat``.
        '''
        schedule = self.manager.scheduled
        mine = next((i for i, t in enumerate(schedule) if t is self), None)
        begin = (None if mine is None else
                 _opening([type(t).__name__ for t in schedule], mine))
        if begin is None:
            raise ValueError(f'Repeat(n={self._n}) has no BeginRepeat '
                             'to repeat from')
        return [t.toDict() for t in schedule[begin + 1:mine]]

    def toDict(self) -> dict:
        d = super().toDict()
        if self._specs is not None:
            d['_specs'] = self._specs
        return d
