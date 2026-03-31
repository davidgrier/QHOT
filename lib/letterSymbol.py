from qtpy import QtGui


def letterSymbol(letter: str) -> QtGui.QPainterPath:
    '''Return a normalised ``QPainterPath`` glyph for use as a trap symbol.

    Renders ``letter`` in bold Arial at 14 pt, then scales and centers the
    resulting path so it fits within the unit square centered on the origin.

    Parameters
    ----------
    letter : str
        Single character to render (e.g. ``'V'``, ``'O'``, ``'T'``).

    Returns
    -------
    QtGui.QPainterPath
        Normalised glyph path suitable for use as a pyqtgraph scatter symbol.
    '''
    symbol = QtGui.QPainterPath()
    font = QtGui.QFont('Arial', 14, QtGui.QFont.Weight.Bold)
    symbol.addText(0, 0, font, letter)
    box = symbol.boundingRect()
    scale = 1. / max(box.width(), box.height())
    tr = QtGui.QTransform().scale(scale, scale)
    tr.translate(-box.x() - box.width()/2.,
                 -box.y() - box.height()/2.)
    return tr.map(symbol)
