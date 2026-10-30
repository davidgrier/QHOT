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

    r'''The calibration of the optical train, and what follows from it.

    An ``Optics`` is a value: it never changes, so a hologram computed
    from it in one thread cannot be disturbed by a calibration edited in
    another.  A changed calibration is a new ``Optics``.

    A trap at :math:`\mathbf r = (r_x, r_y, r_z)` in the camera plane is
    brought to a focus there by a phase that is linear in the position
    :math:`(x, y)` in the SLM plane, which moves the focus across the
    plane, and quadratic, which moves it along the axis,

    .. math::

        \varphi(x, y) = q_\perp (x\, r_x - y\, r_y)
            + q_\parallel (x^2 + y^2)\, r_z,

    with the gradient :math:`q_\perp` and the curvature :math:`q_\parallel`
    that the calibration sets (:attr:`qprp`, :attr:`qpar`).  Because the
    phase is a sum of a function of :math:`x` and a function of :math:`y`,
    the phasor :math:`e^{i\varphi}` is the product of a factor for each
    column and a factor for each row (:meth:`phasors`), which is what makes
    a hologram of many traps cheap to compute.

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
        '''Number of rows of the hologram.'''
        return self.shape[0]

    @property
    def width(self) -> int:
        '''Number of columns of the hologram.'''
        return self.shape[1]

    @property
    def wavenumber(self) -> float:
        r'''Wavenumber of the light in the medium [radians/um].

        .. math:: k = 2\pi n_m / \lambda
        '''
        return 2. * np.pi * self.n_m / self.wavelength

    @property
    def qprp(self) -> float:
        r'''Phase gradient in the plane per unit displacement of a trap.

        .. math::

            q_\perp = \frac{k}{f}\,\frac{p_c}{M}\,\frac{p_s}{s}

        with the focal length :math:`f`, the camera pitch :math:`p_c`, the
        magnification :math:`M`, the SLM pitch :math:`p_s` and its scale
        :math:`s`.
        '''
        cfactor = self.camerapitch / self.magnification  # [um/pixel]
        sfactor = self.slmpitch / self.scale             # [um/phixel]
        return (self.wavenumber / self.focallength) * cfactor * sfactor

    @property
    def qpar(self) -> float:
        r'''Phase curvature per unit axial displacement of a trap.

        .. math::

            q_\parallel = \frac{q_\perp}{2 f}\,\frac{p_s}{s}
        '''
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
    def qx(self) -> np.ndarray:
        '''Phase gradient along x at each column [radians/pixel].'''
        return self.qprp * self.x

    @cached_property
    def qy(self) -> np.ndarray:
        '''Phase gradient along y at each row [radians/pixel].'''
        return self.qprp * self.y

    @cached_property
    def geometry(self) -> Geometry:
        '''The coordinates that a trap makes its structuring field from.'''
        theta = np.arctan2.outer(self.y, self.x)
        qr = np.hypot.outer(self.qprp * self.y, self.qprp * self.x)
        return Geometry(self.shape, theta, qr)

    def toSLM(self, r) -> np.ndarray:
        '''Map a position in the camera plane to the SLM plane.

        Translates to the optical axis, rotates by ``thetac`` and corrects
        the in-plane position for the splay of the beam with depth.

        Parameters
        ----------
        r : array_like
            Position (x, y, z) in the camera plane [pixels], or an array
            of them with the coordinates along the last axis.

        Returns
        -------
        np.ndarray
            Position (x, y, z) in the SLM plane, in the shape of ``r``.

        Notes
        -----
        The depth of a trap is its distance ``z - zc`` from the focal
        plane, and the splay grows with that depth.
        '''
        c, s = (f(np.radians(self.thetac)) for f in (np.cos, np.sin))
        d = np.asarray(r, dtype=float) - (self.xc, self.yc, self.zc)
        dx, dy, dz = d[..., 0], d[..., 1], d[..., 2]
        x, y = c * dx - s * dy, s * dx + c * dy
        fac = 1. / (1. + self.splay * dz)
        return np.stack([x * fac, y * fac, dz], axis=-1)

    def phasors(self, r) -> tuple[np.ndarray, np.ndarray]:
        r'''Return the phasors that move a focus to ``r``.

        The field of a focus at ``r`` is the outer product of the two
        vectors: one factor :math:`e^{i\varphi_y(y)}` for each row and one
        factor :math:`e^{i\varphi_x(x)}` for each column.

        Parameters
        ----------
        r : array_like
            Position (x, y, z) in the camera plane [pixels].

        Returns
        -------
        tuple[np.ndarray, np.ndarray]
            The phasor of each row (length ``height``) and of each column
            (length ``width``).
        '''
        rx, ry, rz = self.toSLM(r)
        ex = np.exp(1j * (self.qx * rx + self.qpar * self.x**2 * rz))
        ey = np.exp(1j * (-self.qy * ry + self.qpar * self.y**2 * rz))
        return ey, ex
