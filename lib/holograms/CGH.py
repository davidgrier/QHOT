from __future__ import annotations

import logging
import weakref
from collections.abc import Iterable

import numpy as np
from qtpy import QtCore, QtGui

from QHOT.lib.traps import TrapSpec
from QHOT.lib.types import PatternSource, Shape
from .backends import Backend, NumpyBackend
from .optics import Optics
from .QHologramWorker import QHologramWorker


logger = logging.getLogger(__name__)


def _stopThread(thread: QtCore.QThread) -> None:
    '''Stop the thread of a pipeline that has not been stopped.'''
    thread.quit()
    thread.wait()


class CGH(QtCore.QObject):

    '''The pipeline that computes holograms of optical traps.

    A ``CGH`` holds the calibration of the optical train, and computes
    holograms with a :class:`~QHOT.lib.holograms.backends.Backend` in a
    thread of its own, so that the interface never waits for one.

    The calibration is a set of attributes (``xc``, ``wavelength``, ...)
    that the interface edits.  Assigning one emits ``recalculate``.  The
    calibration as it is at any moment is available as an immutable
    :class:`~QHOT.lib.holograms.optics.Optics`.

    A hologram is asked for with :meth:`compute`, which takes a pattern
    of traps (see :meth:`~QHOT.lib.traps.QTrapOverlay.QTrapOverlay.pattern`)
    and returns at once.  The pattern and the optics at the time of the
    request are plain values that nothing changes, so the thread that
    computes never reads anything that the interface is editing.  At most
    one hologram is computed at a time; if more requests arrive while it
    is, only the newest is kept, so the hologram that follows is always
    of the latest pattern.  The result arrives as ``hologramReady``.

    :meth:`follow` asks for the holograms: it keeps the hologram of a
    source of patterns, such as the overlay of traps, up to date.

    Parameters
    ----------
    shape : tuple[int, int]
        Hologram dimensions (height, width) in pixels.
    wavelength : float
        Vacuum wavelength of trapping light [um].
    n_m : float
        Refractive index of the trapping medium.
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
        Axial splay correction factor (dimensionless).
    xs, ys : float
        Coordinates of the optical axis in the SLM plane [phixels].
    phis : float
        Tilt of the SLM relative to the optical axis [degrees].
    xc, yc, zc : float
        Coordinates of the optical axis in the camera plane [pixels].
    thetac : float
        Rotation of the camera relative to the SLM [degrees].
    backend : Backend or None
        What computes the holograms.  Default: a ``NumpyBackend``.
    parent : QtCore.QObject or None
        Qt parent object.

    Signals
    -------
    hologramReady : QtCore.Signal(np.ndarray)
        Emitted with the quantized phase array when a hologram is computed.
    computeFailed : QtCore.Signal(str)
        Emitted with the reason when a hologram cannot be computed.
    recalculate : QtCore.Signal()
        Emitted when the calibration changes.
    '''

    #: Emitted with the quantized phase array when a hologram is computed.
    hologramReady = QtCore.Signal(np.ndarray)
    #: Emitted with the reason when a hologram cannot be computed.
    computeFailed = QtCore.Signal(str)
    #: Emitted when the calibration changes.
    recalculate = QtCore.Signal()

    #: Shortest time between the requests of :meth:`follow` [ms].
    INTERVAL = 15
    _request = QtCore.Signal(object, object)

    _fields = ('shape', 'wavelength', 'n_m', 'magnification', 'focallength',
               'camerapitch', 'slmpitch', 'scale', 'splay',
               'xs', 'ys', 'phis', 'xc', 'yc', 'zc', 'thetac')

    def __init__(self, *,
                 shape: Shape = (512, 512),
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
                 backend: Backend | None = None,
                 parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        # Plain assignment, so that building the object emits nothing.
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
        object.__setattr__(self, '_optics', None)
        self.backend = backend or NumpyBackend()
        self._busy = False
        self._next: tuple | None = None
        # The thread and its worker exist only while the pipeline runs: a
        # CGH that is used only for its calibration owns no thread.
        self._thread: QtCore.QThread | None = None
        self._worker: QHologramWorker | None = None
        self._quitConnected = False
        self._finalizer: weakref.finalize | None = None
        # What follows a source of patterns (see ``follow``).
        self._source: PatternSource | None = None
        self._stale = True
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._requestIfStale)
        self.recalculate.connect(self._markStale)

    def __setattr__(self, key: str, value: object) -> None:
        if key in self._fields:
            if getattr(self, key, None) == value:
                return
            super().__setattr__(key, value)
            self._changed()
        else:
            super().__setattr__(key, value)

    def _changed(self) -> None:
        '''Forget the optics, which no longer describe the calibration,
        and tell the interface.'''
        object.__setattr__(self, '_optics', None)
        self.recalculate.emit()

    @property
    def optics(self) -> Optics:
        '''The calibration as an immutable value.

        It does not change when the calibration does; ask again for the
        new calibration.
        '''
        if self._optics is None:
            object.__setattr__(
                self, '_optics', Optics.from_settings(self.settings))
        return self._optics

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

        Updates all recognized attributes first and emits ``recalculate``
        once, if anything changed.

        Parameters
        ----------
        settings : dict[str, object]
            Mapping of attribute name to value. Unknown keys are ignored
            with a warning.
        '''
        changed = False
        for key, value in settings.items():
            if key in self._fields:
                if getattr(self, key, None) != value:
                    object.__setattr__(self, key, value)
                    changed = True
            else:
                logger.warning(f'Unsupported property: {key}')
        if changed:
            self._changed()

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
        '''Wavenumber of trapping light in the medium [radians/um].'''
        return self.optics.wavenumber

    @property
    def qprp(self) -> float:
        '''In-plane displacement factor [radians/(pixel*phixel)].'''
        return self.optics.qprp

    @property
    def qpar(self) -> float:
        '''Axial displacement factor [radians/(pixel*phixel^2)].'''
        return self.optics.qpar

    # Computing holograms

    @QtCore.Slot()
    def start(self) -> CGH:
        '''Start the thread that computes holograms and return self.

        Requests made before it starts are computed when it does.

        Returns
        -------
        CGH
            This instance, for chaining.
        '''
        if self._thread is not None:
            return self
        logger.info('starting CGH pipeline')
        self._busy = False
        self._worker = QHologramWorker(self.backend)
        self._thread = QtCore.QThread()
        self._worker.moveToThread(self._thread)
        # Qt deletes the worker in its own thread as that thread ends.
        self._thread.finished.connect(self._worker.deleteLater)
        self._request.connect(self._worker.compute)
        self._worker.done.connect(self._onDone)
        self._worker.failed.connect(self._onFailed)
        self._thread.start()
        self._timer.start()
        # A pipeline that is dropped, or left running when the program
        # ends without an event loop, must not leave its thread running
        # while Python shuts down.
        self._finalizer = weakref.finalize(self, _stopThread, self._thread)
        app = QtCore.QCoreApplication.instance()
        if app is not None and not self._quitConnected:
            app.aboutToQuit.connect(self.stop)
            self._quitConnected = True
        self.recalculate.emit()
        self._dispatch()
        return self

    def follow(self,
               source: PatternSource,
               interval: int = INTERVAL) -> CGH:
        '''Keep the hologram of a source of patterns up to date.

        While the pipeline runs, a hologram of ``source.pattern()`` is
        requested whenever the source says that its pattern changed, or
        the calibration did, and no more often than every ``interval``
        milliseconds.  This is independent of the video, so the hologram
        keeps up with the traps however slowly the camera delivers frames.
        The first hologram is requested as soon as the pipeline starts.

        Parameters
        ----------
        source : PatternSource
            Has ``pattern()`` and the signal ``patternChanged``.
        interval : int
            Shortest time between requests [ms].  Default: ``INTERVAL``.

        Returns
        -------
        CGH
            This instance, for chaining.
        '''
        if self._source is not None:
            self._source.patternChanged.disconnect(self._markStale)
        self._source = source
        source.patternChanged.connect(self._markStale)
        self._timer.setInterval(interval)
        self._markStale()
        return self

    @QtCore.Slot()
    def _markStale(self) -> None:
        '''Note that the hologram is out of date.'''
        self._stale = True

    @QtCore.Slot()
    def _requestIfStale(self) -> None:
        '''Ask for a new hologram if the old one is out of date.'''
        if self._stale and self._source is not None:
            self._stale = False
            self.compute(self._source.pattern())

    @QtCore.Slot()
    def stop(self) -> None:
        '''Stop the thread that computes holograms.

        A hologram that is being computed is finished and lost.
        '''
        if self._thread is None:
            return
        logger.info('stopping CGH pipeline')
        self._timer.stop()
        self._thread.quit()
        self._thread.wait()
        self._finalizer.detach()
        # The worker is gone, and Qt has dropped its connections.
        self._thread = None
        self._worker = None

    @QtCore.Slot(object)
    def compute(self, pattern: Iterable[TrapSpec]) -> None:
        '''Ask for the hologram of a pattern of traps.

        Returns at once.  The hologram arrives as ``hologramReady``, or
        the reason that there is none as ``computeFailed``.  The pattern
        and the calibration are captured now: what happens to the traps
        or the calibration afterwards does not affect this hologram.

        If a hologram is being computed, this request waits for it, and
        replaces any request that was already waiting.

        Parameters
        ----------
        pattern : iterable of TrapSpec
            The top-level traps and groups, as
            :meth:`~QHOT.lib.traps.QTrapOverlay.QTrapOverlay.pattern`
            returns them.
        '''
        self._next = (tuple(pattern), self.optics)
        self._dispatch()

    def _dispatch(self) -> None:
        '''Send the waiting request to the thread, if it is idle.'''
        if self._thread is None or self._busy or self._next is None:
            return
        pattern, optics = self._next
        self._next = None
        self._busy = True
        self._request.emit(pattern, optics)

    @QtCore.Slot(object)
    def _onDone(self, hologram: np.ndarray) -> None:
        self._busy = False
        self.hologramReady.emit(hologram)
        self._dispatch()

    @QtCore.Slot(str)
    def _onFailed(self, reason: str) -> None:
        self._busy = False
        self.computeFailed.emit(reason)
        self._dispatch()
