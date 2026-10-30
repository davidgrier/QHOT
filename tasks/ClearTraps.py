from QHOT.lib.tasks.QTask import QTask


class ClearTraps(QTask):

    '''Remove all traps from the overlay.

    Completes in a single frame: ``initialize()`` clears the overlay
    and the task finishes immediately without calling ``process()``.

    Parameters
    ----------
    **kwargs
        Forwarded to ``QTask``.

    Examples
    --------
    Clear all traps, then wait 30 frames, then add a tweezer::

        manager.register(ClearTraps(overlay))
        manager.register(Delay(30))
        manager.register(AddTrap(overlay, pos=QtCore.QPointF(320, 240)))
    '''

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, duration=0, **kwargs)

    def initialize(self) -> None:
        self.overlay.clearTraps()
