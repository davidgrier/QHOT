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

        manager.register(ClearTraps())
        manager.register(Delay(30))
        manager.register(AddTweezer(x=320., y=240.))
    '''

    def __init__(self, **kwargs) -> None:
        super().__init__(duration=0, **kwargs)

    def initialize(self) -> None:
        self.overlay.clearTraps()
