'''The splash screen that QHOT shows while it starts.

The image is the hologram of a particle: far from a small scatterer the
fringes are the zones of a Fresnel lens, rings that crowd together and
fade with distance.  It is drawn in purple, with a vignette, so that the
text stays legible.  Adapted from the splash screen of QVideo, which is
private to that project.
'''
import numpy as np
from qtpy import QtCore, QtGui, QtWidgets

from QHOT import __version__


__all__ = ['splash', 'say']

#: Size of the image on the screen; it is drawn at twice this size, so
#: that it is sharp on high-resolution displays.
SIZE = (480, 240)
#: Where the particle is, as a fraction of the size: upper left.
CENTER = (0.31, 0.31)
#: Contrast of the fringes: low, so that the text stays legible.
CONTRAST = 0.7
#: NYU purple.
PURPLE = np.array([87, 6, 140]) / 255.
#: What QHOT does.
SUBTITLE = 'holographic optical trapping'


def hologram(width: int, height: int) -> QtGui.QImage:
    '''Return the fringes of a particle that scatters light, in purple.

    Parameters
    ----------
    width, height : int
        Size of the image [pixels].

    Returns
    -------
    QtGui.QImage
        An RGB image.  A vignette darkens the corners.
    '''
    y, x = np.mgrid[:height, :width]
    r = np.hypot(x - CENTER[0] * width, y - CENTER[1] * height) / width
    fringes = 1. + np.cos(2 * np.pi * (60. * r**2 + 5. * r)) / (1. + 12. * r)
    edge = np.hypot(x / width - 0.5, y / height - 0.5)
    brightness = (1. + CONTRAST * (fringes - 1.)) * (1. - 0.8 * edge**2)
    rgb = np.clip(PURPLE * brightness[..., None] * 1.15, 0., 1.)
    pixels = np.ascontiguousarray(255 * rgb, dtype=np.uint8)
    image = QtGui.QImage(
        pixels.data,
        width,
        height,
        3 * width,
        QtGui.QImage.Format.Format_RGB888,
    )
    return image.copy()  # the copy owns its pixels


def splash(title: str = 'QHOT',
           version: str | None = None) -> QtWidgets.QSplashScreen:
    '''Return a splash screen with the fringes, the name and the version.

    Parameters
    ----------
    title : str
        The name, in large type.  Default: ``'QHOT'``.
    version : str or None
        The version, after the subtitle.  Default: the version of QHOT.

    Returns
    -------
    QtWidgets.QSplashScreen
        The splash screen, not yet shown.
    '''
    if version is None:
        version = __version__ if __version__[:1].isdigit() else ''
    width, height = (2 * n for n in SIZE)
    pixmap = QtGui.QPixmap.fromImage(hologram(width, height))
    pixmap.setDevicePixelRatio(2.)
    align = QtCore.Qt.AlignmentFlag
    painter = QtGui.QPainter(pixmap)
    painter.setPen(QtGui.QColor('white'))
    font = QtGui.QFont()
    font.setPointSize(30)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(
        0,
        0,
        SIZE[0] - 16,
        SIZE[1] - 46,
        align.AlignRight | align.AlignBottom,
        title,
    )
    font.setPointSize(11)
    font.setBold(False)
    painter.setFont(font)
    painter.drawText(
        0,
        0,
        SIZE[0] - 16,
        SIZE[1] - 28,
        align.AlignRight | align.AlignBottom,
        f'{SUBTITLE} {version}'.strip(),
    )
    painter.end()
    screen = QtWidgets.QSplashScreen(pixmap)
    screen.setFont(QtGui.QFont(screen.font().family(), 10))
    return screen


def say(screen: QtWidgets.QSplashScreen, message: str) -> None:
    '''Show a message on a splash screen, and repaint it.

    Call this before a slow step, so that the message says what is
    happening while the step runs.

    Parameters
    ----------
    screen : QtWidgets.QSplashScreen
        The splash screen.
    message : str
        What is happening.
    '''
    align = QtCore.Qt.AlignmentFlag
    screen.showMessage(
        message,
        align.AlignBottom | align.AlignRight,
        QtGui.QColor('#d9b8f0'),
    )
    QtWidgets.QApplication.processEvents()
