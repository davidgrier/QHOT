from __future__ import annotations

from argparse import ArgumentParser

from qtpy import QtCore
from QVideo.cameras import chooser


__all__ = ['QCameraOpener']


class QCameraOpener(QtCore.QThread):

    '''Opens the camera that the command line chooses, off the GUI thread.

    Opening a camera can take seconds (a GenICam camera starts acquiring
    and reads its whole node map), and the window must not wait for it.
    While the camera opens, the rest of the program can start.  Adapted
    from the opener of QVideo, which is private to that project.

    The camera is made in this thread and handed to the thread of the
    application when it is open, because a Qt object can be moved only by
    the thread that it lives in.

    Parameters
    ----------
    parser : ArgumentParser or None
        The parser that holds the camera flags, as ``choose_camera``
        takes it.  Default: a new one.
    parent : QtCore.QObject or None
        Qt parent object.

    Attributes
    ----------
    camera : QCamera or None
        The open camera, once ``opened`` has been emitted.
    key : str or None
        The key of the backend that opened it.
    reason : str or None
        Why no camera could be opened, if that happened.

    Signals
    -------
    opened : Signal(str, object)
        The key of the backend and the open camera.
    failed : Signal(str)
        Why no camera could be opened.
    '''

    #: Emitted with the key of the backend and the open camera.
    opened = QtCore.Signal(str, object)
    #: Emitted with the reason that no camera could be opened.
    failed = QtCore.Signal(str)

    def __init__(self,
                 parser: ArgumentParser | None = None,
                 parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._parser = parser
        self.camera = None
        self.key: str | None = None
        self.reason: str | None = None

    def run(self) -> None:
        '''Open the camera and report; this runs in the thread.'''
        try:
            key, camera = chooser.open_camera(self._parser)
        except Exception as error:
            self.reason = str(error)
            self.failed.emit(self.reason)
            return
        if self.isInterruptionRequested():  # the application is quitting
            camera.close()
            return
        camera.moveToThread(QtCore.QCoreApplication.instance().thread())
        self.key, self.camera = key, camera
        self.opened.emit(key, camera)

    def wait_for_camera(self) -> bool:
        '''Wait, with the event loop running, until the thread is done.

        The splash screen and the rest of the interface stay alive.

        Returns
        -------
        bool
            Whether a camera was opened.
        '''
        loop = QtCore.QEventLoop()
        self.finished.connect(loop.quit)
        if self.isRunning():
            loop.exec()
        self.wait()
        return self.camera is not None

    def stop(self) -> None:
        '''Ask the thread to stop, wait for it, and close its camera.

        For use when the application quits before the interface has taken
        the camera.
        '''
        self.requestInterruption()
        self.wait()
        if self.camera is not None:
            self.camera.close()
            self.camera = None
