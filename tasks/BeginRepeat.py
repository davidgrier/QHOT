from QHOT.lib.tasks.QTask import QTask


class BeginRepeat(QTask):

    '''Marks the start of a repeatable block.

    Place ``BeginRepeat()`` immediately before the tasks you want to
    loop, then close the block with ``Repeat(n)``.  ``BeginRepeat``
    itself completes in zero frames and performs no action — it exists
    solely as a bracket marker for ``Repeat`` to locate.

    Examples
    --------
    Repeat tasks A and B three times, then run C once::

        manager.register(BeginRepeat())
        manager.register(TaskA(...))
        manager.register(TaskB(...))
        manager.register(Repeat(n=3))
        manager.register(TaskC(...))
    '''

    parameters = ()

    def __init__(self, **kwargs) -> None:
        if 'duration' in kwargs:
            raise TypeError("BeginRepeat does not accept 'duration'")
        super().__init__(duration=0, **kwargs)
