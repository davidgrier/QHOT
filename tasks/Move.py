import numpy as np

from QHOT.tasks.MoveTraps import MoveTraps


class Move(MoveTraps):

    '''Translate marked traps to an absolute target over multiple frames.

    Moves the marked traps and groups, each as a whole, so that the
    centroid of their traps reaches ``(x, y, z)``, preserving the relative
    configuration.  If nothing is marked the task completes immediately
    without moving anything.

    The displacement is divided into steps of at most ``step`` pixels
    (L2 norm of the centroid displacement) so that trapped particles
    are not lost.  ``duration`` is computed automatically.

    Parameters
    ----------
    x : float
        Target x coordinate [pixels].
    y : float
        Target y coordinate [pixels].
    z : float
        Target z coordinate [pixels].  Default: ``0.``.
    step : float
        Maximum displacement per frame [pixels].  Default: ``1.``.
    **kwargs
        Forwarded to :class:`~QHOT.lib.tasks.QTask.QTask`
        (e.g. ``delay``).  ``duration`` may not be supplied.

    Examples
    --------
    Mark a trap with Ctrl+click, then move it to pixel (320, 240)::

        manager.register(Move(x=320., y=240.))
    '''

    parameters = (
        dict(name='x',    type='float', value=0., default=0.),
        dict(name='y',    type='float', value=0., default=0.),
        dict(name='z',    type='float', value=0., default=0.),
        dict(name='step', type='float', value=1., default=1., min=0.01),
    )

    def __init__(self,
                 x: float = 0.,
                 y: float = 0.,
                 z: float = 0.,
                 step: float = 1.,
                 **kwargs) -> None:
        super().__init__(step=step, selected_only=True, **kwargs)
        self._x = float(x)
        self._y = float(y)
        self._z = float(z)

    # ------------------------------------------------------------------
    # Parameter properties

    @property
    def x(self) -> float:
        '''Target x coordinate [pixels].'''
        return self._x

    @x.setter
    def x(self, value: float) -> None:
        self._x = float(value)

    @property
    def y(self) -> float:
        '''Target y coordinate [pixels].'''
        return self._y

    @y.setter
    def y(self, value: float) -> None:
        self._y = float(value)

    @property
    def z(self) -> float:
        '''Target z coordinate [pixels].'''
        return self._z

    @z.setter
    def z(self, value: float) -> None:
        self._z = float(value)

    # ------------------------------------------------------------------
    # QTask lifecycle hooks

    def initialize(self) -> None:
        '''Find the displacement that takes the centroid of the marked
        traps to the target, then move the marked groups by it.'''
        groups = self.overlay.markedGroups
        if not groups:
            self.duration = 0
            return
        centroid = np.mean([leaf.r for group in groups
                            for leaf in group.leaves()], axis=0)
        self._dx, self._dy, self._dz = (np.array([self._x, self._y, self._z])
                                        - centroid)
        self._updateDuration()
        super().initialize()
