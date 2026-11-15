'''The file beside a video that says how the video was made.'''
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
from qtpy import QtCore
from QVideo import __version__ as QVIDEO_VERSION

from QHOT import __version__ as QHOT_VERSION

if TYPE_CHECKING:
    from QVideo.dvr import QDVRWidget
    from QVideo.lib import QCameraTree
    from QHOT.lib.QSaveFile import QSaveFile
    from QHOT.lib.holograms import CGH
    from QHOT.lib.traps.QTrapOverlay import QTrapOverlay


__all__ = 'QSidecar plain'.split()

logger = logging.getLogger(__name__)

#: The version of the layout of the file, for whoever reads it.
FORMAT = 1

#: What the file says about itself, at the top.
HEADER = (
    'Written by QHOT beside the video that it describes: how the camera was\n'
    'set, the calibration of the hologram and the traps at the start of the\n'
    'recording.  [recording] says what happened to the video.'
)


def plain(value: Any) -> Any:
    '''Return *value* as TOML has it: no ``None``, no NumPy.

    TOML has no ``None``, so a key that has none is left out.  Arrays and
    the scalars of NumPy are the lists and numbers of Python.
    '''
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items() if v is not None}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value if v is not None]
    if isinstance(value, np.ndarray):
        return plain(value.tolist())
    if isinstance(value, np.generic):
        return value.item()
    return value


class QSidecar(QtCore.QObject):

    '''Writes, beside each video, how it was made.

    A file with the name of the video and the ending ``.toml`` is written
    when a recording starts, so that a recording that is cut short has one,
    and again when it ends.  The camera cannot be changed while the
    recorder records, so the settings of the camera at the start are the
    settings of the video.  It says:

    ``[recording]``
        The video, the time that it started and ended [ISO 8601, with the
        offset from UTC], how long that was [s], the number of frames that
        were written, and why the recorder stopped, if it did so itself.
        The times are those of the recorder, which starts a little before
        the first frame and ends a little after the last; the times of the
        frames are those of the video.
    ``[software]``
        The versions of QHOT and QVideo.
    ``[camera]``
        The class, the name and the model of the camera, and its settings.
    ``[cgh]``
        The calibration of the hologram, and the backend that computed it.
    ``[[traps]]``
        The traps at the start, as a trap file has them.

    Parameters
    ----------
    dvr : QDVRWidget
        The recorder, whose recordings are described.
    tree : QCameraTree
        The tree of the camera, which knows the settings.
    cgh : CGH
        The calibration.
    overlay : QTrapOverlay
        The traps.
    files : QSaveFile
        The file helper, which writes the file.
    parent : QObject, optional
        Its owner.

    Signals
    -------
    status : Signal(str)
        A message for the user: the file could not be written.
    '''

    #: Emitted with a message about what could not be done.
    status = QtCore.Signal(str)

    def __init__(self,
                 dvr: QDVRWidget,
                 tree: QCameraTree,
                 cgh: CGH,
                 overlay: QTrapOverlay,
                 files: QSaveFile,
                 parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self.dvr = dvr
        self.tree = tree
        self.cgh = cgh
        self.overlay = overlay
        self.files = files
        self._data: dict[str, Any] = {}     # what the file says
        self._running = False
        self._path = ''
        self._start = datetime.now().astimezone()
        self._frames = 0
        self._reason = ''
        dvr.recording.connect(self._onRecording)
        dvr.recorder.frameNumber.connect(self._onFrame)
        dvr.recorder.stopped.connect(self._onStopped)

    @staticmethod
    def pathOf(video: str) -> str:
        '''Return the name of the file that describes *video*.'''
        return str(Path(video).with_suffix('.toml'))

    # ------------------------------------------------------------------
    # What happens to the recorder

    @QtCore.Slot(bool)
    def _onRecording(self, recording: bool) -> None:
        '''Write the file when a recording starts, and again when it ends.'''
        if recording:
            self._begin()
        elif self._running:
            self._end()

    @QtCore.Slot(int)
    def _onFrame(self, frames: int) -> None:
        '''Count the frames that are written.'''
        self._frames = frames

    @QtCore.Slot(str)
    def _onStopped(self, reason: str) -> None:
        '''Note why the recorder stopped itself.'''
        self._reason = reason

    def _begin(self) -> None:
        self._start = datetime.now().astimezone()
        self._frames = 0
        self._reason = ''
        video = self.dvr.filename
        self._path = self.pathOf(video)
        self.tree.flush()               # the camera has what the tree shows
        self._running = True
        self._data = plain({
            'format': FORMAT,
            'recording': {'video': Path(video).name,
                          'start': self._start},
            'software': {'QHOT': QHOT_VERSION, 'QVideo': QVIDEO_VERSION},
            'camera': self._camera(),
            'cgh': {**self.cgh.settings,
                    'shape': list(self.cgh.shape),
                    'backend': type(self.cgh.backend).__name__},
            'traps': self.overlay.toList(),
        })
        self._write()

    def _end(self) -> None:
        stop = datetime.now().astimezone()
        seconds = (stop - self._start).total_seconds()
        self._data['recording'].update(plain({
            'stop': stop,
            'frames': self._frames,
            'seconds': seconds,
            'stopped': self._reason or None,
        }))
        self._write()
        self._running = False

    def _camera(self) -> dict[str, Any]:
        '''Describe the camera: who it is, and what it is set to.'''
        camera = self.tree.camera
        return {'class': type(camera).__name__,
                'name': getattr(camera, 'name', None),
                'model': getattr(camera, 'modelName', None),
                'settings': {key: self.tree.get(key)
                             for key in camera.properties}}

    def _write(self) -> None:
        '''Write the file.  A file that cannot be written is reported, and
        the recording goes on.'''
        try:
            self.files.writeToml(self._data, self._path, header=HEADER)
        except OSError as error:
            logger.exception(f'could not write {self._path}')
            self.status.emit(f'Could not write {Path(self._path).name}: '
                             f'{error}')

