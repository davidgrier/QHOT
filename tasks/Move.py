import math

import numpy as np

from QHOT.lib.tasks.QTask import QTask


class Move(QTask):

    '''Translate marked traps to an absolute target over multiple frames.

    Moves every leaf trap in the marked set so that their centroid
    reaches ``(x, y, z)``, preserving the relative configuration.
    If no traps are marked the task completes immediately without
    moving anything.

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
        (e.g. ``overlay``, ``delay``).
        ``duration`` may not be supplied.

    Examples
    --------
    Mark a trap with Ctrl+click, then move it to pixel (320, 240)::

        manager.register(Move(overlay=overlay, x=320., y=240.))
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
        if 'duration' in kwargs:
            raise TypeError(
                "'duration' may not be set on Move; "
                'duration is computed from the displacement and step',
            )
        self._x = float(x)
        self._y = float(y)
        self._z = float(z)
        self._stepSize = max(1e-6, float(step))
        super().__init__(duration=1, **kwargs)
        self._starts: dict = {}
        self._dr: np.ndarray = np.zeros(3)

    # ------------------------------------------------------------------
    # Internal helpers

    def _centroid(self, starts: dict) -> np.ndarray:
        '''Return the mean position of the given trap start positions.'''
        positions = np.array(list(starts.values()))
        return positions.mean(axis=0)

    def _computeDuration(self, displacement: float) -> int:
        return max(1, math.ceil(displacement / self._stepSize))

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

    @property
    def step(self) -> float:
        '''Maximum displacement per frame [pixels].'''
        return self._stepSize

    @step.setter
    def step(self, value: float) -> None:
        self._stepSize = max(1e-6, float(value))

    # ------------------------------------------------------------------
    # QTask lifecycle hooks

    def initialize(self) -> None:
        '''Record starting positions and compute the duration from the
        displacement of the centroid.'''
        traps = list(self.overlay.marked)
        if not traps:
            self.duration = 0
            return
        self._starts = {trap: trap.r.copy() for trap in traps}
        centroid = self._centroid(self._starts)
        target = np.array([self._x, self._y, self._z])
        self._dr = target - centroid
        dist = float(np.linalg.norm(self._dr))
        self.duration = self._computeDuration(dist)

    def process(self, frame: int) -> None:
        '''Interpolate each trap toward its target position.'''
        t = (frame + 1) / self.duration
        for trap, r0 in self._starts.items():
            trap.r = r0 + t * self._dr
