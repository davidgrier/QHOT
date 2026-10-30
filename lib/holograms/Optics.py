from __future__ import annotations

from dataclasses import dataclass, fields
from functools import cached_property
from typing import NamedTuple

import numpy as np

from QHOT.lib.types import Shape


__all__ = 'Geometry Optics'.split()


class Geometry(NamedTuple):

    '''The coordinates of the SLM plane, as a trap needs them.

    This is all that a trap is given to make its structuring field.

    Attributes
    ----------
    shape : tuple[int, int]
        Height and width of the hologram [pixels].
    theta : np.ndarray
        Angle about the optical axis at each pixel [radians].
    qr : np.ndarray
        Radial wavenumber at each pixel [radians/pixel].
    '''

    shape: Shape
    theta: np.ndarray
    qr: np.ndarray


@dataclass(frozen=True, eq=False)
class Optics:

    '''The calibration of the optical train, and what follows from it.

    An ``Optics`` is a value: it never changes, so a hologram computed
    from it in one thread cannot be disturbed by a calibration edited in
    another.  A changed calibration is a new ``Optics``.

    A trap at ``r`` in the camera plane has the phase ramp that moves the
    focus there (:meth:`displacement`).  The ramp is the product of a
    factor along x and a factor along y, which is what makes a hologram of
    many traps cheap to compute.

    Parameters
    ----------
    shape : tuple[int, int]
        Height and width of the hologram [pixels].
    wavelength : float
        Vacuum wavelength of the trapping light [um].
    n_m : float
        Refractive index of the medium.
    magnification : float
        Magnification of the objective lens.
    focallength : float
        Focal length of the tube lens [um].
    camerapitch : float
        Camera pixel pitch [um/pixel].
    slmpitch : float
        SLM pixel pitch [um/phixel].
    scale : float
        SLM scale factor.
    splay : float
        Axial splay correction (dimensionless).
    xs, ys : float
        Coordinates of the optical axis in the SLM plane [phixels].
    phis : float
        Tilt of the SLM relative to the optical axis [degrees].
    xc, yc, zc : float
        Coordinates of the optical axis in the camera plane [pixels].
    thetac : float
        Rotation of the camera relative to the SLM [degrees].
    '''

    shape: Shape = (512, 512)
    wavelength: float = 1.064
    n_m: float = 1.340
    magnification: float = 100.
    focallength: float = 200.
    camerapitch: float = 4.8
    slmpitch: float = 8.
    scale: float = 3.
    splay: float = 0.01
    xs: float = 0.
    ys: float = 0.
    phis: float = 8.
    xc: float = 320.
    yc: float = 240.
    zc: float = 0.
    thetac: float = 0.

    @classmethod
    def from_settings(cls, settings: dict) -> 'Optics':
        '''Make the optics of a calibration, such as ``CGH.settings``.'''
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in settings.items() if k in names})

    @property
    def settings(self) -> dict[str, object]:
        '''The calibration as a dict.'''
        return {f.name: getattr(self, f.name) for f in fields(self)}

    @property
    def height(self) -> int:
        return self.shape[0]

    @property
    def width(self) -> int:
        return self.shape[1]

    @property
    def wavenumber(self) -> float:
        '''Wavenumber of the light in the medium [radians/um].'''
        return 2. * np.pi * self.n_m / self.wavelength

    @property
    def qprp(self) -> float:
        '''Phase gradient in the plane per unit displacement of a trap.'''
        cfactor = self.camerapitch / self.magnification  # [um/pixel]
        sfactor = self.slmpitch / self.scale             # [um/phixel]
        return (self.wavenumber / self.focallength) * cfactor * sfactor

    @property
    def qpar(self) -> float:
        '''Phase curvature per unit axial displacement of a trap.'''
        sfactor = self.slmpitch / self.scale             # [um/phixel]
        return self.qprp * sfactor / (2. * self.focallength)

    @cached_property
    def x(self) -> np.ndarray:
        '''Coordinate along x of each column, from the optical axis.'''
        alpha = np.cos(np.radians(self.phis))
        return alpha * (np.arange(self.width) - self.xs)

    @cached_property
    def y(self) -> np.ndarray:
        '''Coordinate along y of each row, from the optical axis.'''
        return np.arange(self.height) - self.ys

    @cached_property
    def geometry(self) -> Geometry:
        '''The coordinates that a trap makes its structuring field from.'''
        theta = np.arctan2.outer(self.y, self.x)
        qr = np.hypot.outer(self.qprp * self.y, self.qprp * self.x)
        return Geometry(self.shape, theta, qr)

    def transform(self, r) -> np.ndarray:
        '''Map a position in the camera plane to the SLM plane.

        Translates to the optical axis, rotates by ``thetac`` and corrects
        the in-plane position for the splay of the beam with depth.

        Parameters
        ----------
        r : array_like
            Position (x, y, z) in the camera plane [pixels].

        Returns
        -------
        np.ndarray
            Position (x, y, z) in the SLM plane.

        Notes
        -----
        The depth of a trap is its distance ``z - zc`` from the focal
        plane, and the splay grows with that depth.
        '''
        c, s = (f(np.radians(self.thetac)) for f in (np.cos, np.sin))
        dx, dy, dz = np.asarray(r, dtype=float) - (self.xc, self.yc, self.zc)
        x, y = c * dx - s * dy, s * dx + c * dy
        fac = 1. / (1. + self.splay * dz)
        return np.array([x * fac, y * fac, dz])

    def displacement(self, r) -> tuple[np.ndarray, np.ndarray]:
        '''Return the phase ramps that move a focus to ``r``.

        The field of a focus at ``r`` is the outer product of the two
        vectors: one factor for each row and one for each column.

        Parameters
        ----------
        r : array_like
            Position (x, y, z) in the camera plane [pixels].

        Returns
        -------
        tuple[np.ndarray, np.ndarray]
            The factor of each row (length ``height``) and of each column
            (length ``width``).
        '''
        rx, ry, rz = self.transform(r)
        qx, qy = self.qprp * self.x, self.qprp * self.y
        ex = np.exp(1j * (qx * rx + self.qpar * self.x**2 * rz))
        ey = np.exp(-1j * (qy * ry) + 1j * self.qpar * self.y**2 * rz)
        return ey, ex
