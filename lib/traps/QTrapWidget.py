from pyqtgraph.Qt.QtCore import (pyqtSignal, pyqtSlot, pyqtProperty,
                                 Qt, QRegularExpression)
from pyqtgraph.Qt.QtWidgets import (QWidget, QFrame, QLineEdit, QLabel,
                                    QScrollArea,
                                    QHBoxLayout, QVBoxLayout)
from pyqtgraph.Qt.QtGui import (QDoubleValidator,
                                QRegularExpressionValidator)
from QFab.lib.traps.QTrap import QTrap
import numpy as np
import logging


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


def getWidth():
    '''Get width of line edit in screen pixels'''
    edit = QLineEdit()
    fm = edit.fontMetrics()
    return fm.boundingRect('12345.6').width()


class QTrapPropertyEdit(QLineEdit):

    '''Control for one property of one trap'''

    valueChanged = pyqtSignal(str, float)

    def __init__(self, name: str, value: float, *args,
                 decimals: int = 2, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.name = name
        self.decimals = decimals
        self._setupUi()
        self._connectSignals()
        self.value = value

    def _setupUi(self) -> None:
        self.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.setFixedWidth(getWidth())
        self.setMaxLength(8)
        v = QDoubleValidator(decimals=self.decimals)
        v.setNotation(QDoubleValidator.Notation.StandardNotation)
        self.setValidator(v)

    def _connectSignals(self) -> None:
        self.returnPressed.connect(self.updateValue)

    def format(self, value: float) -> str:
        return f'{value:.{self.decimals}f}'

    @pyqtSlot()
    def updateValue(self) -> None:
        self.value = float(str(self.text()))
        logger.debug(f'Changing {self.name}: {self.value}')
        self.valueChanged.emit(self.name, self.value)

    @pyqtProperty(float)
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, value: float) -> None:
        self.setText(self.format(value))
        self._value = value


class QTrapPropertyWidget(QWidget):

    '''Control for properties of one trap.'''

    def __init__(self, trap: QTrap, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._setupUi(trap)

    def _setupUi(self, trap: QTrap) -> None:
        layout = QHBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.wid = dict()
        for name in trap.properties.keys():
            self.wid[name] = self.propertyWidget(trap, name)
            tip = trap.__class__.__name__ + ': ' + name
            self.wid[name].setStatusTip(tip)
            if trap.properties[name]['tooltip']:
                self.wid[name].setToolTip(name)
            layout.addWidget(self.wid[name])
        trap.changed.connect(self.updateValues)
        self.setLayout(layout)

    def propertyWidget(self, trap: QTrap, name: str) -> QWidget:
        value = getattr(trap, name)
        decimals = trap.properties[name]['decimals']
        wid = QTrapPropertyEdit(name, value, decimals=decimals)
        wid.valueChanged.connect(trap.setTrapProperty)
        return wid

    @pyqtSlot()
    def updateValues(self) -> None:
        trap = self.sender()
        for name in trap.properties.keys():
            value = getattr(trap, name)
            self.wid[name].value = value


class QTrapWidget(QFrame):

    '''Controls for all traps.'''

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.properties = dict()
        self._setupUi()

    def _setupUi(self) -> None:
        self.setFrameShape(QFrame.Shape.Box)
        inner = QWidget()
        self.layout = QVBoxLayout()
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        inner.setLayout(self.layout)
        scroll = QScrollArea()
        policy = Qt.ScrollBarPolicy
        scroll.setVerticalScrollBarPolicy(policy.ScrollBarAlwaysOn)
        scroll.setHorizontalScrollBarPolicy(policy.ScrollBarAsNeeded)
        scroll.setWidgetResizable(True)
        scroll.setWidget(inner)
        layout = QVBoxLayout(self)
        layout.addWidget(scroll)
        self.setLayout(layout)
        self.layout.addWidget(self.labelLine())

    def labelLine(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        for name in 'x y z A ϕ'.split():
            label = QLabel(name)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setFixedWidth(getWidth())
            layout.addWidget(label)
        widget.setLayout(layout)
        return widget

    @pyqtSlot(QTrap)
    def registerTrap(self, trap: QTrap) -> None:
        trapWidget = QTrapPropertyWidget(trap)
        self.properties[trap] = trapWidget
        self.layout.addWidget(trapWidget)

    @pyqtSlot(QTrap)
    def unregisterTrap(self, trap: QTrap) -> None:
        try:
            self.properties[trap].deleteLater()
        except Exception as ex:
            logger.warning(f'Error unregistering trap: {ex}')

    def count(self) -> int:
        return self.layout.count()


if __name__ == '__main__':
    import pyqtgraph as pg

    app = pg.mkQApp('QTrapWidget Example')
    table = QTrapWidget()
    trapa = QTrap()
    trapb = QTrap()
    trapc = QTrap()
    table.registerTrap(trapa)
    table.registerTrap(trapb)
    table.show()
    # change trap properties
    trapa.r = (100, 100, 10)
    trapc.r = (50, 50, 5)
    # remove trap after display
    trapb.deleteLater()
    table.registerTrap(trapc)
    pg.exec()
