from pyqtgraph.Qt import QtGui


def letterSymbol(letter: str) -> QtGui.QPainterPath:
    '''Returns the symbol for a trap in the shape of a letter'''
    symbol = QtGui.QPainterPath()
    font = QtGui.QFont('Arial', 14, QtGui.QFont.Weight.Bold)
    symbol.addText(0, 0, font, letter)
    box = symbol.boundingRect()
    scale = 1. / max(box.width(), box.height())
    tr = QtGui.QTransform().scale(scale, scale)
    tr.translate(-box.x() - box.width()/2.,
                 -box.y() - box.height()/2.)
    return tr.map(symbol)
