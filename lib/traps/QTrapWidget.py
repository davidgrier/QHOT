from pyqtgraph.Qt import QtCore, QtWidgets, QtGui
from QFab.lib.traps.QTrap import QTrap
import logging


logger = logging.getLogger(__name__)


class QTrapPropertyEdit(QtWidgets.QLineEdit):

    '''Single-property editor for one numeric trap attribute.

    Displays a right-aligned, fixed-width line edit with a double
    validator.  Emits ``valueChanged(name, value)`` when the user
    commits a new value with Return.

    Parameters
    ----------
    name : str
        Name of the trap property this editor controls.
    value : float
        Initial value to display.
    decimals : int
        Number of decimal places for display and validation. Default: 2.
    '''

    valueChanged = QtCore.pyqtSignal(str, float)

    _field_width: int | None = None

    @classmethod
    def fieldWidth(cls) -> int:
        '''Return the pixel width needed to display a typical value.

        Computed once from font metrics and cached on the class.
        '''
        if cls._field_width is None:
            cls._field_width = (QtWidgets.QLineEdit()
                                .fontMetrics()
                                .boundingRect('12345.6')
                                .width())
        return cls._field_width

    def __init__(self, name: str, value: float, *args,
                 decimals: int = 2, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.name = name
        self.decimals = decimals
        self._value: float = 0.
        self._setupUi()
        self._connectSignals()
        self.value = value

    def _setupUi(self) -> None:
        '''Configure alignment, width, length, and numeric validator.'''
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        self.setFixedWidth(self.fieldWidth())
        self.setMaxLength(8)
        v = QtGui.QDoubleValidator(decimals=self.decimals)
        v.setNotation(QtGui.QDoubleValidator.Notation.StandardNotation)
        self.setValidator(v)

    def _connectSignals(self) -> None:
        '''Connect Return key to value update.'''
        self.returnPressed.connect(self.updateValue)

    def format(self, value: float) -> str:
        '''Format a float for display with the configured decimal places.'''
        return f'{value:.{self.decimals}f}'

    @QtCore.pyqtSlot()
    def updateValue(self) -> None:
        '''Read the current text, update the stored value, and emit signal.'''
        self.value = float(self.text())
        logger.debug(f'Changing {self.name}: {self.value}')
        self.valueChanged.emit(self.name, self.value)

    @property
    def value(self) -> float:
        '''Current numeric value displayed in the editor.'''
        return self._value

    @value.setter
    def value(self, value: float) -> None:
        self.setText(self.format(value))
        self._value = value


class QTrapPropertyWidget(QtWidgets.QWidget):

    '''Row of property editors for a single trap.

    Creates one ``QTrapPropertyEdit`` per registered property and
    connects each to ``trap.setTrapProperty``.  Updates automatically
    when the trap emits ``changed``.

    Parameters
    ----------
    trap : QTrap
        The trap whose properties will be displayed and edited.
    '''

    def __init__(self, trap: QTrap, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._setupUi(trap)

    def _setupUi(self, trap: QTrap) -> None:
        '''Build the row of editors from the trap's registered properties.'''
        layout = QtWidgets.QHBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        self.wid: dict[str, QTrapPropertyEdit] = {}
        for name in trap.properties.keys():
            self.wid[name] = self.propertyWidget(trap, name)
            tip = trap.__class__.__name__ + ': ' + name
            self.wid[name].setStatusTip(tip)
            if trap.properties[name]['tooltip']:
                self.wid[name].setToolTip(name)
            layout.addWidget(self.wid[name])
        trap.changed.connect(self.updateValues)
        self.setLayout(layout)

    def propertyWidget(self, trap: QTrap, name: str) -> QTrapPropertyEdit:
        '''Create an editor widget for a single trap property.'''
        value = getattr(trap, name)
        decimals = trap.properties[name]['decimals']
        wid = QTrapPropertyEdit(name, value, decimals=decimals)
        wid.valueChanged.connect(trap.setTrapProperty)
        return wid

    @QtCore.pyqtSlot()
    def updateValues(self) -> None:
        '''Refresh all editors from the trap's current property values.'''
        trap = self.sender()
        for name in trap.properties.keys():
            self.wid[name].value = getattr(trap, name)


class QTrapWidget(QtWidgets.QFrame):

    '''Scrollable panel showing property editors for all active traps.

    Maintains a ``QTrapPropertyWidget`` row for each registered trap.
    Traps are added via ``registerTrap`` and removed via
    ``unregisterTrap``.
    '''

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._trap_widgets: dict[QTrap, QTrapPropertyWidget] = {}
        self._setupUi()

    def _setupUi(self) -> None:
        '''Build the scrollable frame with a column header row.'''
        self.setFrameShape(QtWidgets.QFrame.Shape.Box)
        inner = QtWidgets.QWidget()
        self.layout = QtWidgets.QVBoxLayout()
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        inner.setLayout(self.layout)
        scroll = QtWidgets.QScrollArea()
        policy = QtCore.Qt.ScrollBarPolicy
        scroll.setVerticalScrollBarPolicy(policy.ScrollBarAlwaysOn)
        scroll.setHorizontalScrollBarPolicy(policy.ScrollBarAsNeeded)
        scroll.setWidgetResizable(True)
        scroll.setWidget(inner)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(scroll)
        self.setLayout(layout)
        self.layout.addWidget(self._labelLine())

    def _labelLine(self) -> QtWidgets.QWidget:
        '''Build the column header row.'''
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout()
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        for name in 'x y z A ϕ'.split():
            label = QtWidgets.QLabel(name)
            label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            label.setFixedWidth(QTrapPropertyEdit.fieldWidth())
            layout.addWidget(label)
        widget.setLayout(layout)
        return widget

    @QtCore.pyqtSlot(QTrap)
    def registerTrap(self, trap: QTrap) -> None:
        '''Add a property editor row for ``trap``.'''
        trapWidget = QTrapPropertyWidget(trap)
        self._trap_widgets[trap] = trapWidget
        self.layout.addWidget(trapWidget)

    @QtCore.pyqtSlot(QTrap)
    def unregisterTrap(self, trap: QTrap) -> None:
        '''Remove and destroy the property editor row for ``trap``.'''
        try:
            self._trap_widgets.pop(trap).deleteLater()
        except KeyError:
            logger.warning(f'Trap not registered: {trap}')

    def count(self) -> int:
        '''Return the number of rows currently in the layout.'''
        return self.layout.count()

    @classmethod
    def example(cls) -> None:
        '''Display a QTrapWidget demo with several traps.'''
        import pyqtgraph as pg

        pg.mkQApp('QTrapWidget Example')
        table = cls()
        trapa = QTrap(phase=0.)
        trapb = QTrap(phase=0.)
        trapc = QTrap(phase=0.)
        table.registerTrap(trapa)
        table.registerTrap(trapb)
        table.show()
        trapa.r = (100, 100, 10)
        trapc.r = (50, 50, 5)
        trapb.deleteLater()
        table.registerTrap(trapc)
        pg.exec()


if __name__ == '__main__':
    QTrapWidget.example()
