'''Make the screenshot of the README: the real window, on a made-up frame.

The window is the program itself, built as ``tests/test_qhot.py`` builds it
(it reads and writes none of the files of the user, and puts the SLM window
on the primary screen, never on a display that has an SLM).  Only the camera
is made up: a frame of colloidal spheres, as pylorenzmie computes their
holograms, with traps on some of them.

pylorenzmie needs more than QHOT does, so the frame is made on its own,
in an environment that has it, and the window is grabbed in one that has
QHOT::

    python devel/screenshot.py --make-frame frame.npy      # pylorenzmie
    python devel/screenshot.py --frame frame.npy shot.png  # QHOT

Run the second with ``QT_QPA_PLATFORM=cocoa`` on a Mac, so that the window
has the look of the platform, which the offscreen platform cannot draw.  It
opens windows on the display for a few seconds.
'''
import argparse
import importlib
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np

SHAPE = (480, 640)

#: Spheres of the frame: x and y [pixels], height above the focal plane
#: [pixels] and radius [um].
SPHERES = (
    (118, 96, 150., 0.75), (262, 150, 190., 1.0), (455, 92, 120., 0.65),
    (560, 210, 210., 0.9), (152, 270, 170., 0.8), (330, 330, 140., 1.1),
    (495, 385, 180., 0.7), (92, 410, 200., 0.85), (250, 430, 130., 0.6),
    (590, 85, 160., 0.75), (400, 235, 230., 0.95),
)

#: Spheres that are trapped: by tweezers, by a vortex, and as a group.
TWEEZERS = ((118, 96), (262, 150), (560, 210))
VORTEX = (400, 235)
GROUP = ((92, 410), (250, 430), (152, 270))


def make_frame(seed: int = 3) -> np.ndarray:
    '''Return a frame of holograms of the spheres, as a camera records it.'''
    from pylorenzmie.theory import LorenzMie, Sphere

    height, width = SHAPE
    model = LorenzMie()
    model.coordinates = model.meshgrid(SHAPE)
    model.particle = [Sphere(a_p=a, n_p=1.45, x_p=x, y_p=y, z_p=z)
                      for x, y, z, a in SPHERES]
    hologram = model.hologram().reshape(height, width)
    hologram *= 100. / np.median(hologram)
    hologram += np.random.default_rng(seed).normal(0., 1.5, SHAPE)
    return np.clip(hologram, 0, 255).astype(np.uint8)


def grab(frame: np.ndarray, path: str, width: int) -> None:
    '''Build the window, show the frame and the traps, and save the window.'''
    from qtpy import QtCore, QtWidgets
    from QVideo.cameras import chooser
    from QHOT.lib import QSLM
    from QHOT.lib.holograms import CGH
    from QHOT.lib.traps.QTrapGroup import QTrapGroup
    from QHOT.traps import QTweezer, QVortex

    qhot = importlib.import_module('QHOT.qhot')
    home = tempfile.TemporaryDirectory()
    with patch.object(qhot.QHOT, 'saveSettings'), \
            patch.object(qhot.QHOT, 'restoreSettings'), \
            patch.object(Path, 'home', return_value=Path(home.name)), \
            patch.object(sys, 'argv', ['qhot']):
        key, camera = chooser.open_camera()
        tree = chooser.make_tree(key, camera).start()
        slm = QSLM(fake=True)
        window = qhot.QHOT(tree, slm=slm, cgh=CGH(shape=slm.shape))
    app = QtWidgets.QApplication.instance()

    def spin(ms: int) -> None:
        timer = QtCore.QElapsedTimer()
        timer.start()
        while timer.elapsed() < ms:
            app.processEvents()

    spin(500)
    tree.stop()                 # the camera of noise sends no more frames
    window.menuBar().setNativeMenuBar(False)
    window.resize(1090, 560)
    window.show()
    window.splitter.setSizes([660, 430])
    spin(500)
    window.screen.setImage(frame)
    overlay = window.screen.overlay
    for x, y in TWEEZERS:
        overlay.addTrap(QTweezer(r=(x, y, 0.)))
    overlay.addTrap(QVortex(r=(*VORTEX, 0.), ell=3))
    center = np.mean(GROUP, axis=0)
    group = QTrapGroup(r=(*center, 0.))
    group.addTrap([QTweezer(r=(x, y, 0.)) for x, y in GROUP])
    overlay.addTrap(group)
    window.tabWidget.setCurrentIndex(1)       # the Traps tab
    spin(800)
    image = window.grab()
    if width:
        image = image.scaledToWidth(
            width, QtCore.Qt.TransformationMode.SmoothTransformation)
    image.save(path)
    with patch.object(qhot.QHOT, 'saveSettings'):
        window.close()
    tree.stop()
    camera.close()
    home.cleanup()


def main() -> None:
    '''Make the frame or grab the window, as the command line says.'''
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--make-frame', metavar='FILE',
                        help='save a frame of holograms (needs pylorenzmie)')
    parser.add_argument('--frame', metavar='FILE',
                        help='the frame to show (made by --make-frame)')
    parser.add_argument('--width', type=int, default=1600,
                        help='width of the image [pixels]; 0 keeps the '
                        'size of the window as drawn (default: 1600)')
    parser.add_argument('image', nargs='?', help='where to save the image')
    args = parser.parse_args()
    if args.make_frame:
        np.save(args.make_frame, make_frame())
    elif args.frame and args.image:
        grab(np.load(args.frame), args.image, args.width)
    else:
        parser.error('give --make-frame FILE, or --frame FILE and an image')


if __name__ == '__main__':
    main()
