from pyqtgraph.Qt import QtCore, QtGui
from QFab.lib.traps.QTrap import QTrap
from QFab.lib.traps.QTrapGroup import QTrapGroup
from functools import partial
import weakref
import numpy as np
import logging


logger = logging.getLogger(__name__)


class CGH(QtCore.QObject):

    '''Base class for computing computer-generated holograms.

    For each trap, the coordinate r obtained from the fabscreen is
    measured relative to the calibrated location rc of the zeroth-order
    focal point, which itself is measured relative to the center of the
    focal plane. The resulting displacement is projected onto the
    coordinate system in the SLM plane via a calibrated rotation matrix.

    The hologram is computed using calibrated wavenumbers for the
    Cartesian coordinates in the SLM plane.  These differ from each other
    because the SLM is likely to be tilted relative to the optical axis.

    Assigning any calibration attribute automatically triggers
    ``updateGeometry`` or ``updateTransformationMatrix`` as appropriate,
    and emits the ``recalculate`` signal.

    Attributes
    ----------
    dtype : type
        NumPy dtype used for complex field arrays. Defaults to
        ``np.complex128``. Subclasses (e.g. GPU-accelerated variants)
        may override this to use an alternative complex type.
    phase : np.ndarray
        Quantized phase hologram from the most recent ``compute()`` call.
        Undefined before the first call to ``compute()``.
    shape : tuple[int, int]
        Hologram dimensions (height, width) in pixels.
    wavelength : float
        Vacuum wavelength of trapping light [μm].
    n_m : float
        Refractive index of the trapping medium.
    magnification : float
        Magnification of the objective lens.
    focallength : float
        Focal length of the tube lens [μm].
    camerapitch : float
        Camera pixel pitch [μm/pixel].
    slmpitch : float
        SLM pixel pitch [μm/phixel].
    scale : float
        SLM scale factor.
    splay : float
        Axial splay correction factor (dimensionless).
    xs, ys : float
        Coordinates of the optical axis in the SLM plane [phixels].
    phis : float
        Tilt of the SLM relative to the optical axis [degrees].
    xc, yc, zc : float
        Coordinates of the optical axis in the camera plane [pixels].
    thetac : float
        Rotation of the camera relative to the SLM [degrees].

    Signals
    -------
    hologramReady : QtCore.pyqtSignal(np.ndarray)
        Emitted with the quantized phase array when a hologram is computed.
    recalculate : QtCore.pyqtSignal()
        Emitted when the geometry or transformation matrix is updated.
    '''

    hologramReady = QtCore.pyqtSignal(np.ndarray)
    recalculate = QtCore.pyqtSignal()

    dtype = np.complex64

    _fields = ('shape', 'wavelength', 'n_m', 'magnification', 'focallength',
               'camerapitch', 'slmpitch', 'scale', 'splay',
               'xs', 'ys', 'phis', 'xc', 'yc', 'zc', 'thetac')

    _matrix_attrs = frozenset({'xc', 'yc', 'zc', 'thetac'})
    _geometry_attrs = frozenset(_fields) - _matrix_attrs
    assert _matrix_attrs <= frozenset(_fields), \
        '_matrix_attrs contains entries not in _fields'

    def __init__(self, *,
                 shape: tuple[int, int] = (512, 512),
                 wavelength: float = 1.064,
                 n_m: float = 1.340,
                 magnification: float = 100.,
                 focallength: float = 200.,
                 camerapitch: float = 4.8,
                 slmpitch: float = 8.,
                 scale: float = 3.,
                 splay: float = 0.01,
                 xs: float = 0.,
                 ys: float = 0.,
                 phis: float = 8.,
                 xc: float = 320.,
                 yc: float = 240.,
                 zc: float = 0.,
                 thetac: float = 0.,
                 parent: QtCore.QObject | None = None) -> None:
        '''Initialize the CGH pipeline.

        Parameters
        ----------
        shape : tuple[int, int]
            Hologram dimensions (height, width) in pixels.
        wavelength : float
            Vacuum wavelength of trapping light [μm].
        n_m : float
            Refractive index of the trapping medium.
        magnification : float
            Magnification of the objective lens.
        focallength : float
            Focal length of the tube lens [μm].
        camerapitch : float
            Camera pixel pitch [μm/pixel].
        slmpitch : float
            SLM pixel pitch [μm/phixel].
        scale : float
            SLM scale factor.
        splay : float
            Axial splay correction factor (dimensionless).
        xs, ys : float
            Coordinates of the optical axis in the SLM plane [phixels].
        phis : float
            Tilt of the SLM relative to the optical axis [degrees].
        xc, yc, zc : float
            Coordinates of the optical axis in the camera plane [pixels].
        thetac : float
            Rotation of the camera relative to the SLM [degrees].
        parent : QtCore.QObject or None
            Qt parent object.
        '''
        super().__init__(parent)
        # Use object.__setattr__ to set all attributes without triggering
        # __setattr__ dispatch before initialization is complete.
        object.__setattr__(self, 'matrix', QtGui.QMatrix4x4())
        object.__setattr__(self, '_field_cache',
                           weakref.WeakKeyDictionary())
        object.__setattr__(self, '_structure_cache',
                           weakref.WeakKeyDictionary())
        object.__setattr__(self, '_connected_traps',
                           weakref.WeakSet())
        object.__setattr__(self, '_connected_groups',
                           weakref.WeakSet())
        for attr, val in (('shape', shape),
                          ('wavelength', wavelength),
                          ('n_m', n_m),
                          ('magnification', magnification),
                          ('focallength', focallength),
                          ('camerapitch', camerapitch),
                          ('slmpitch', slmpitch),
                          ('scale', scale),
                          ('splay', splay),
                          ('xs', xs),
                          ('ys', ys),
                          ('phis', phis),
                          ('xc', xc),
                          ('yc', yc),
                          ('zc', zc),
                          ('thetac', thetac)):
            object.__setattr__(self, attr, val)
        self.blockSignals(True)
        self.updateTransformationMatrix()
        self.updateGeometry()
        self.blockSignals(False)

    def __setattr__(self, key: str, value: object) -> None:
        if key in self._matrix_attrs or key in self._geometry_attrs:
            if getattr(self, key, None) == value:
                return
        super().__setattr__(key, value)
        if key in self._matrix_attrs:
            self.updateTransformationMatrix()
        elif key in self._geometry_attrs:
            self.updateGeometry()

    def updateTransformationMatrix(self) -> None:
        '''Rebuild the camera-to-SLM transformation matrix.

        Accounts for the position (xc, yc, zc) and orientation (thetac)
        of the camera relative to the SLM. Clears only the field cache
        (structure arrays are independent of the transformation) and
        emits ``recalculate``.
        '''
        logger.debug('updating transformation matrix')
        self.matrix.setToIdentity()
        self.matrix.rotate(self.thetac, 0., 0., 1.)
        self.matrix.translate(-self.rc)
        self._field_cache.clear()
        self.recalculate.emit()

    def updateGeometry(self) -> None:
        '''Recompute position-dependent phase factors in the SLM plane.

        Rebuilds ``iqx``, ``iqy``, ``iqxz``, ``iqyz``, ``theta``, and
        ``qr`` from the current calibration parameters. Also resets the
        accumulation ``field`` buffer, clears the field cache, and emits
        ``recalculate``.
        '''
        logger.debug('updating geometry')
        self.field = np.zeros(self.shape, dtype=self.dtype)
        alpha = np.cos(np.radians(self.phis))
        x = alpha*(np.arange(self.width) - self.xs)
        y = np.arange(self.height) - self.ys
        self.iqx = (1j * self.qprp * x).astype(self.dtype)
        self.iqy = (-1j * self.qprp * y).astype(self.dtype)
        self.iqxz = (1j * self.qpar * x * x).astype(self.dtype)
        self.iqyz = (1j * self.qpar * y * y).astype(self.dtype)
        self.theta = np.arctan2.outer(y, x).astype(np.float32)
        self.qr = np.hypot.outer(self.qprp * y, self.qprp * x).astype(np.float32)
        self._clearCache()
        self.recalculate.emit()

    def _clearCache(self) -> None:
        '''Discard all cached per-trap fields and structures.

        Called automatically when CGH geometry is updated. All entries
        will be recomputed on the next call to ``fieldOf``.
        '''
        self._field_cache.clear()
        self._structure_cache.clear()

    def _invalidateField(self, trap_ref: weakref.ref) -> None:
        '''Discard the cached displacement field for one trap.

        Connected to ``trap.changed`` so that position, amplitude, or
        phase changes are reflected in the next computation.

        Parameters
        ----------
        trap_ref : weakref.ref
            Weak reference to the trap whose field cache entry should be
            removed.
        '''
        trap = trap_ref()
        if trap is not None:
            self._field_cache.pop(trap, None)

    def _invalidateStructure(self, trap_ref: weakref.ref) -> None:
        '''Discard the cached structure field for one trap.

        Connected to ``trap.structureChanged`` so that changes to
        structural parameters (e.g. topological charge) are reflected
        in the next computation without discarding the displacement field.

        Parameters
        ----------
        trap_ref : weakref.ref
            Weak reference to the trap whose structure cache entry should
            be removed.
        '''
        trap = trap_ref()
        if trap is not None:
            self._structure_cache.pop(trap, None)

    @QtCore.pyqtSlot(object, object)
    def _onGroupMoved(self, leaves: list, delta: np.ndarray) -> None:
        '''Bulk-invalidate field caches for all leaves of a translated group.

        Connected to ``QTrapGroup.groupMoved``. In Step 3 this will be
        replaced by a phase-factor update; for now it ensures that N
        individual ``changed`` signals do not each trigger a separate
        cache look-up.

        Parameters
        ----------
        leaves : list[QTrap]
            All leaf traps belonging to the translated group.
        delta : np.ndarray
            Translation vector in camera coordinates (unused here).
        '''
        for trap in leaves:
            self._field_cache.pop(trap, None)

    @property
    def properties(self) -> list[str]:
        '''Names of all calibration attributes.

        Returns
        -------
        list[str]
            Ordered list of calibration attribute names.
        '''
        return list(self._fields)

    @property
    def settings(self) -> dict[str, object]:
        '''Current calibration settings as a dictionary.

        Returns
        -------
        dict[str, object]
            Mapping of calibration attribute name to current value.
        '''
        return {name: getattr(self, name) for name in self._fields}

    @settings.setter
    def settings(self, settings: dict[str, object]) -> None:
        '''Apply calibration settings from a dictionary.

        Updates all recognized attributes first, then calls
        ``updateTransformationMatrix`` and/or ``updateGeometry`` once
        each as needed, rather than once per attribute.

        Parameters
        ----------
        settings : dict[str, object]
            Mapping of attribute name to value. Unknown keys are ignored
            with a warning.
        '''
        needs_geometry = False
        needs_matrix = False
        for key, value in settings.items():
            if key in self._fields:
                if getattr(self, key, None) != value:
                    object.__setattr__(self, key, value)
                    if key in self._geometry_attrs:
                        needs_geometry = True
                    elif key in self._matrix_attrs:
                        needs_matrix = True
            else:
                logger.warning(f'Unsupported property: {key}')
        if needs_matrix:
            self.updateTransformationMatrix()
        if needs_geometry:
            self.updateGeometry()

    @property
    def height(self) -> int:
        '''Height of the hologram in pixels.'''
        return self.shape[0]

    @property
    def width(self) -> int:
        '''Width of the hologram in pixels.'''
        return self.shape[1]

    @property
    def rc(self) -> QtGui.QVector3D:
        '''Coordinates of optical axis in camera plane.

        Returns
        -------
        QtGui.QVector3D
            Position (xc, yc, zc) as a 3D vector.
        '''
        return QtGui.QVector3D(self.xc, self.yc, self.zc)

    @property
    def wavenumber(self) -> float:
        '''Wavenumber of trapping light in the medium [radians/μm].

        Returns
        -------
        float
            2π n_m / wavelength.
        '''
        return 2.*np.pi*self.n_m/self.wavelength

    @property
    def qprp(self) -> float:
        '''In-plane displacement factor [radians/(pixel·phixel)].

        Returns
        -------
        float
            Lateral phase gradient per unit displacement.
        '''
        cfactor = self.camerapitch/self.magnification  # [um/pixel]
        sfactor = self.slmpitch/self.scale             # [um/phixel]
        return (self.wavenumber/self.focallength)*cfactor*sfactor

    @property
    def qpar(self) -> float:
        '''Axial displacement factor [radians/(pixel·phixel²)].

        Returns
        -------
        float
            Axial phase gradient per unit displacement.
        '''
        sfactor = self.slmpitch/self.scale             # [um/phixel]
        return self.qprp * sfactor / (2.*self.focallength)

    # Slots for threaded operation

    @QtCore.pyqtSlot()
    def start(self) -> 'CGH':
        '''Initialize the CGH pipeline and return self.

        Returns
        -------
        CGH
            This instance, for chaining.
        '''
        logger.info('starting CGH pipeline')
        self.blockSignals(True)
        self.updateGeometry()
        self.updateTransformationMatrix()
        self.blockSignals(False)
        self.recalculate.emit()
        return self

    @QtCore.pyqtSlot()
    def stop(self) -> None:
        '''Shut down the CGH pipeline.'''
        logger.info('stopping CGH pipeline')

    # Methods for computing holograms

    @staticmethod
    def quantize(field: np.ndarray) -> np.ndarray:
        '''Scale the phase of a complex field to an 8-bit integer array.

        Parameters
        ----------
        field : np.ndarray
            Complex-valued field array.

        Returns
        -------
        np.ndarray
            Phase encoded as uint8 in the range [0, 255].
        '''
        return ((128./np.pi)*np.angle(field) + 127.).astype(np.uint8)

    def window(self, r: QtGui.QVector3D) -> float:
        '''Compute the sinc-aperture amplitude correction for a trap position.

        Parameters
        ----------
        r : QtGui.QVector3D
            Trap position in SLM coordinates.

        Returns
        -------
        float
            Amplitude correction factor, clamped to a maximum of 100.
        '''
        x = 0.5 * np.pi * np.array([r.x() / self.width,
                                    r.y() / self.height])
        fac = 1. / np.prod(np.sinc(x))
        return np.min((np.abs(fac), 100.))

    def transform(self, r: QtGui.QVector3D) -> QtGui.QVector3D:
        '''Map camera-plane coordinates to SLM-plane coordinates.

        Applies the calibrated rotation/translation matrix and the
        axial splay correction.

        Parameters
        ----------
        r : QtGui.QVector3D
            Position in camera coordinates.

        Returns
        -------
        QtGui.QVector3D
            Position in SLM coordinates.
        '''
        r = self.matrix * r
        fac = 1. / (1. + self.splay*(r.z() - self.zc))
        r *= QtGui.QVector3D(fac, fac, 1.)
        return r

    def fieldOf(self, trap: QTrap) -> np.ndarray:
        '''Compute the complex field contribution of a single trap.

        The displacement field and structure field are cached separately.
        ``trap.changed`` invalidates the displacement field cache;
        ``trap.structureChanged`` (if present) invalidates only the
        structure cache, leaving the displacement field intact.

        Parameters
        ----------
        trap : QTrap
            The trap to compute the field for.

        Returns
        -------
        np.ndarray
            Complex field array with shape equal to ``self.shape``.
        '''
        if trap not in self._connected_traps:
            trap_ref = weakref.ref(trap)
            trap.changed.connect(partial(self._invalidateField, trap_ref))
            if hasattr(trap, 'structureChanged'):
                trap.structureChanged.connect(
                    partial(self._invalidateStructure, trap_ref))
            parent = trap.parent()
            if isinstance(parent, QTrapGroup) and parent not in self._connected_groups:
                parent.groupMoved.connect(self._onGroupMoved)
                self._connected_groups.add(parent)
            self._connected_traps.add(trap)
        if trap not in self._field_cache:
            amplitude = np.dtype(self.dtype).type(trap.amplitude * np.exp(1j * trap.phase))
            r = self.transform(QtGui.QVector3D(*trap.r))
            rx, ry, rz = np.float32(r.x()), np.float32(r.y()), np.float32(r.z())
            ex = np.exp(self.iqx * rx + self.iqxz * rz)
            ey = np.exp(self.iqy * ry + self.iqyz * rz)
            self._field_cache[trap] = np.outer(amplitude * ey, ex)
        if trap not in self._structure_cache:
            if hasattr(trap, 'structure'):
                self._structure_cache[trap] = trap.structure(self)
            else:
                self._structure_cache[trap] = 1.
        return self._field_cache[trap] * self._structure_cache[trap]

    @QtCore.pyqtSlot(list)
    def compute(self, traps: list[QTrap]) -> np.ndarray:
        '''Compute the phase hologram for a list of traps.

        Accumulates the complex fields of all traps, quantizes the result
        to uint8, and emits ``hologramReady``.

        Parameters
        ----------
        traps : list[QTrap]
            Traps to include in the hologram.

        Returns
        -------
        np.ndarray
            Quantized phase hologram as a uint8 array.
        '''
        logger.debug(f'computing hologram for {len(traps)} traps')
        self.field.fill(0j)
        for trap in traps:
            self.field += self.fieldOf(trap)
        self.phase = self.quantize(self.field)
        self.hologramReady.emit(self.phase)
        return self.phase

    def bless(self, field: np.ndarray | None) -> np.ndarray | None:
        '''Cast a field array to ``self.dtype``, or return None.

        Parameters
        ----------
        field : np.ndarray or None
            Array to cast, or None.

        Returns
        -------
        np.ndarray or None
            Field cast to ``self.dtype``, or None if input is None.
        '''
        if field is None:
            return None
        return field.astype(self.dtype)

    @classmethod
    def example(cls) -> None:
        '''Demonstrate the CGH pipeline.

        Creates a CGH instance, computes a hologram for a single on-axis
        tweezer trap, and prints the result shape and dtype. Can be
        called on any subclass.
        '''
        from QFab.traps.QTweezer import QTweezer

        cgh = cls()
        trap = QTweezer(r=(cgh.xc, cgh.yc, 0.))
        hologram = cgh.compute([trap])
        print(f'{cls.__name__}: hologram shape={hologram.shape}, '
              f'dtype={hologram.dtype}')


if __name__ == '__main__':
    CGH.example()
