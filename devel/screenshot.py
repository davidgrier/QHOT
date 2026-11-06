'''Make the screenshot of the README: the real window, on a made-up frame.

The window is the program itself, built as ``tests/test_qhot.py`` builds it
(it reads and writes none of the files of the user, and puts the SLM window
on the primary screen, never on a display that has an SLM).  Only the camera
is made up: a frame of colloidal spheres, as pylorenzmie computes their
holograms, with traps on some of them.  The window is the size that it has
on a full-HD (1080p) display, so that the markers, which keep their size in
pixels however the video is scaled, are as large next to the video as they
are there.

pylorenzmie needs more than QHOT does, so the frame is made on its own,
in an environment that has it, and the window is grabbed in one that has
QHOT::

    python devel/screenshot.py --make-frame frame.npy      # pylorenzmie
    python devel/screenshot.py --frame frame.npy shot.png  # QHOT

``--camera viva`` makes the camera tree of a GenICam camera that is made up
too: the fake GigE Vision camera that viva-genicam ships, which runs in this
process.  It needs a QVideo that has the viva backend.

Run the second with ``QT_QPA_PLATFORM=cocoa`` on a Mac, so that the window
has the look of the platform, which the offscreen platform cannot draw.  The
window is not shown, so the display need not be as large as the window.
'''
import argparse
import importlib
import sys
import tempfile
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import patch

import numpy as np

SHAPE = (960, 1280)

#: The display that the window is made for, as the window sees it.
DISPLAY = (1920, 1080)

#: Spheres of the frame: x and y [pixels], height above the focal plane z
#: [pixels], radius [um] and how the sphere is trapped.  The hologram of a
#: sphere grows, and blurs, with its height, so the heights are spread to
#: show that the traps work in three dimensions.
SPHERES = (
    (236, 192, 45., 0.75, 'tweezer'), (524, 300, 130., 1.0, 'tweezer'),
    (910, 184, 60., 0.65, None), (1180, 170, 240., 0.75, None),
    (1120, 420, 85., 0.9, 'tweezer'), (800, 470, 180., 0.95, 'vortex'),
    (304, 540, 35., 0.8, 'group'), (660, 660, 110., 1.1, None),
    (990, 770, 215., 0.7, None), (184, 820, 70., 0.85, 'group'),
    (500, 860, 150., 0.6, 'group'),
)


def make_frame(seed: int = 3) -> np.ndarray:
    '''Return a frame of holograms of the spheres, as a camera records it.'''
    from pylorenzmie.theory import LorenzMie, Sphere

    height, width = SHAPE
    model = LorenzMie()
    model.coordinates = model.meshgrid(SHAPE)
    model.particle = [Sphere(a_p=a, n_p=1.45, x_p=x, y_p=y, z_p=z)
                      for x, y, z, a, _ in SPHERES]
    hologram = model.hologram().reshape(height, width)
    hologram *= 100. / np.median(hologram)
    hologram += np.random.default_rng(seed).normal(0., 1.5, SHAPE)
    return np.clip(hologram, 0, 255).astype(np.uint8)


@contextmanager
def fake_gige_camera():
    '''Run the fake camera of viva-genicam, and let QVideo find it.

    Discovery looks on the network and not on the loopback interface, where
    the fake camera is, unless it is asked to.
    '''
    import viva_genicam as vg
    from viva_genicam.testing import FakeGigeCamera

    discover = vg.discover
    with FakeGigeCamera(width=SHAPE[1], height=SHAPE[0], fps=10), \
            patch.object(vg, 'discover',
                         lambda *args, **kwargs: discover(*args, all=True,
                                                          **kwargs)):
        yield


class Display:

    '''A display of a given size, as far as the window asks about it.'''

    def __init__(self, width: int, height: int) -> None:
        self.width, self.height = width, height

    def availableGeometry(self):
        '''The whole display: the window may be as large as it.'''
        from qtpy import QtCore
        return QtCore.QRect(0, 0, self.width, self.height)


def grab(frame: np.ndarray,
         path: str,
         width: int,
         tab: str,
         camera: str) -> None:
    '''Build the window, show the frame and the traps, and save the window.'''
    from qtpy import QtCore, QtWidgets
    from QVideo.cameras import chooser
    from QHOT.lib import QSLM
    from QHOT.lib.holograms import CGH
    from QHOT.lib.traps.QTrapGroup import QTrapGroup
    from QHOT.traps import QTweezer, QVortex

    qhot = importlib.import_module('QHOT.qhot')
    home = tempfile.TemporaryDirectory()
    display = Display(*DISPLAY)
    with ExitStack() as patches:
        for patched in (
                patch.object(qhot.QHOT, 'saveSettings'),
                patch.object(qhot.QHOT, 'restoreSettings'),
                patch.object(Path, 'home', return_value=Path(home.name)),
                patch.object(sys, 'argv',
                             ['qhot'] + (['-g'] if camera == 'viva' else [])),
                patch.object(QtWidgets.QApplication, 'primaryScreen',
                             return_value=display)):
            patches.enter_context(patched)
        if camera == 'viva':
            patches.enter_context(fake_gige_camera())
        key, device = chooser.open_camera()
        tree = chooser.make_tree(key, device).start()
        slm = QSLM(fake=True)
        slm.hide()
        window = qhot.QHOT(tree, slm=slm, cgh=CGH(shape=slm.shape))
        app = QtWidgets.QApplication.instance()

        def spin(ms: int) -> None:
            timer = QtCore.QElapsedTimer()
            timer.start()
            while timer.elapsed() < ms:
                app.processEvents()

        spin(500)
        tree.stop()             # the camera of noise sends no more frames
        # What a camera of this frame size would tell the screen.
        window.videoScreen.updateShape(QtCore.QSize(SHAPE[1], SHAPE[0]))
        window.menuBar().setNativeMenuBar(False)
        # The window is laid out at the size of the display, but is not
        # put on the screen, which may be smaller.
        window.setAttribute(QtCore.Qt.WidgetAttribute.WA_DontShowOnScreen)
        window.resize(*DISPLAY)
        window.show()
        QtWidgets.QApplication.setActiveWindow(window)   # tabs look selected
        spin(500)
        chrome = window.height() - window.centralWidget().height()
        video = (DISPLAY[1] - chrome) * SHAPE[1] // SHAPE[0]
        window.splitter.setSizes(
            [video, DISPLAY[0] - video - window.splitter.handleWidth()])
        spin(500)
        window.resize(*DISPLAY)             # the window snaps to the video
        spin(500)
        window.dvr.filename = '/home/user/default.mkv'   # not a temporary one
        window.videoScreen.setImage(frame)
        overlay = window.videoScreen.overlay
        members = []
        for x, y, z, _, trap in SPHERES:
            if trap == 'tweezer':
                overlay.addTrap(QTweezer(r=(x, y, z)))
            elif trap == 'vortex':
                overlay.addTrap(QVortex(r=(x, y, z), ell=3))
            elif trap == 'group':
                members.append(QTweezer(r=(x, y, z)))
        group = QTrapGroup(r=np.mean([m.r for m in members], axis=0))
        group.addTrap(members)
        overlay.addTrap(group)
        for video_filter in window.filter.filters:
            if video_filter.title() == 'Sample and Hold':
                video_filter.setChecked(True)     # the frame is normalized
        tabs = window.tabWidget
        names = [tabs.tabText(i).lower() for i in range(tabs.count())]
        tabs.setCurrentIndex(names.index(tab))
        spin(800)
        image = window.grab()
        print(f'window {window.width()}x{window.height()}, '
              f'video {window.videoScreen.width()}x{window.videoScreen.height()}, '
              f'image {image.width()}x{image.height()}')
        if width:
            image = image.scaledToWidth(
                width, QtCore.Qt.TransformationMode.SmoothTransformation)
        image.save(path)
        window.close()
        tree.stop()
        device.close()
    home.cleanup()


def main() -> None:
    '''Make the frame or grab the window, as the command line says.'''
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--make-frame', metavar='FILE',
                        help='save a frame of holograms (needs pylorenzmie)')
    parser.add_argument('--frame', metavar='FILE',
                        help='the frame to show (made by --make-frame)')
    parser.add_argument('--width', type=int, default=DISPLAY[0],
                        help='width of the image [pixels]; 0 keeps the '
                        'size at which the window was drawn (default: the '
                        'width of the display, one pixel to a pixel)')
    parser.add_argument('--tab', default='video',
                        choices=('video', 'traps', 'tasks', 'cgh', 'slm'),
                        help='the tab of the panel to show (default: video)')
    parser.add_argument('--camera', default='noise',
                        choices=('noise', 'viva'),
                        help='the camera whose controls the Video tab shows '
                        '(default: noise)')
    parser.add_argument('image', nargs='?', help='where to save the image')
    args = parser.parse_args()
    if args.make_frame:
        np.save(args.make_frame, make_frame())
    elif args.frame and args.image:
        grab(np.load(args.frame), args.image, args.width, args.tab,
             args.camera)
    else:
        parser.error('give --make-frame FILE, or --frame FILE and an image')


if __name__ == '__main__':
    main()
