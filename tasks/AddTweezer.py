from __future__ import annotations

from qtpy import QtCore

from QHOT.lib.tasks.QTask import QTask


class AddTweezer(QTask):

    '''Add a single QTweezer to the trap overlay.

    Completes in a single frame.  The tweezer is placed at
    ``(x, y)`` in camera pixel coordinates.  If ``x`` or ``y``
    is not supplied, the CGH optical-axis coordinates
    (``cgh.xc``, ``cgh.yc``) of the CGH that the task works with are
    used, as they are when the position is read.

    The addition is pushed onto the overlay undo stack, so it can
    be undone with Ctrl+Z.

    Parameters
    ----------
    x : float or None
        Horizontal position [pixels].  Defaults to ``cgh.xc``.
    y : float or None
        Vertical position [pixels].  Defaults to ``cgh.yc``.
    **kwargs
        Forwarded to ``QTask``.

    Examples
    --------
    Clear all traps, wait 60 frames, then add a tweezer at center::

        manager.register(ClearTraps())
        manager.register(Delay(60))
        manager.register(AddTweezer())
    '''

    parameters = (
        dict(name='x', type='float', value=0., default=0.),
        dict(name='y', type='float', value=0., default=0.),
    )

    def __init__(self,
                 *args,
                 x: float | None = None,
                 y: float | None = None,
                 **kwargs) -> None:
        super().__init__(*args, duration=0, **kwargs)
        self._x = None if x is None else float(x)
        self._y = None if y is None else float(y)

    @property
    def x(self) -> float:
        '''Horizontal position [pixels]; ``cgh.xc`` until it is set.'''
        return self.cgh.xc if self._x is None else self._x

    @x.setter
    def x(self, x: float) -> None:
        self._x = float(x)

    @property
    def y(self) -> float:
        '''Vertical position [pixels]; ``cgh.yc`` until it is set.'''
        return self.cgh.yc if self._y is None else self._y

    @y.setter
    def y(self, y: float) -> None:
        self._y = float(y)

    def initialize(self) -> None:
        self.overlay.addTrap(QtCore.QPointF(self.x, self.y))
