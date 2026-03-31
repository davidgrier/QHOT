from __future__ import annotations

from qtpy import QtCore

from QHOT.lib.tasks.QTask import QTask


class AddTweezer(QTask):

    '''Add a single QTweezer to the trap overlay.

    Completes in a single frame.  The tweezer is placed at
    ``(x, y)`` in camera pixel coordinates.  If ``x`` or ``y``
    is not supplied, the CGH optical-axis coordinates
    (``cgh.xc``, ``cgh.yc``) are used; if no CGH is available
    either, the position defaults to ``(0., 0.)``.

    The addition is pushed onto the overlay undo stack, so it can
    be undone with Ctrl+Z.

    Parameters
    ----------
    x : float or None
        Horizontal position [pixels].  Defaults to ``cgh.xc``.
    y : float or None
        Vertical position [pixels].  Defaults to ``cgh.yc``.
    overlay : QTrapOverlay
        The trap overlay.  Required.
    **kwargs
        Forwarded to ``QTask``.

    Examples
    --------
    Clear all traps, wait 60 frames, then add a tweezer at center::

        manager.register(ClearTraps(overlay=overlay))
        manager.register(Delay(60))
        manager.register(AddTweezer(overlay=overlay, cgh=cgh))
    '''

    parameters = [
        dict(name='x', type='float', value=0., default=0.),
        dict(name='y', type='float', value=0., default=0.),
    ]

    def __init__(self, *args,
                 x: float | None = None,
                 y: float | None = None,
                 **kwargs) -> None:
        super().__init__(*args, duration=0, **kwargs)
        if x is None:
            x = self.cgh.xc if self.cgh is not None else 0.
        if y is None:
            y = self.cgh.yc if self.cgh is not None else 0.
        self.x = float(x)
        self.y = float(y)

    def initialize(self) -> None:
        self.overlay.addTrap(QtCore.QPointF(self.x, self.y))
