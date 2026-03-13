from pyqtgraph.parametertree import Parameter, ParameterTree
from pyqtgraph.Qt import QtCore
from QFab.lib.holograms.CGH import CGH
from collections.abc import KeysView
import logging


logger = logging.getLogger(__name__)


class QCGHTree(ParameterTree):

    '''Parameter tree widget for editing CGH calibration settings.

    Displays all CGH calibration parameters grouped by subsystem
    (instrument, SLM, camera) and synchronises changes bidirectionally
    with a connected ``CGH`` instance.

    Parameters
    ----------
    cgh : CGH or None
        The hologram computation object to synchronise with.
        Can be changed at runtime via the ``cgh`` property.
    *args, **kwargs
        Forwarded to ``ParameterTree``.

    Attributes
    ----------
    cgh : CGH or None
        The currently connected CGH instance.
    settings : dict[str, object]
        Current values of all parameters, keyed by parameter name.
    properties : KeysView[str]
        Names of all registered parameters.
    '''

    def __init__(self, *args,
                 cgh: CGH | None = None,
                 **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._cgh: CGH | None = cgh
        self._setupUi()
        self._connectSignals()
        self.updateTree()

    def _setupUi(self) -> None:
        '''Build the parameter tree and index all leaf parameters.'''
        self.tree = self._description()
        self.setParameters(self.tree, showTop=False)
        self._parameters = self._getParameters(self.tree)

    def _connectSignals(self) -> None:
        '''Connect tree state changes to CGH updates.'''
        self.tree.sigTreeStateChanged.connect(self.updateCGH)

    def _description(self) -> Parameter:
        '''Return the parameter tree description for all CGH settings.'''
        instr = dict(name='instrument', type='group', children=[
            dict(name='wavelength', type='float',
                 value=1.064, decimals=4, suffix='μm'),
            dict(name='n_m', type='float', value=1.340, decimals=4),
            dict(name='magnification', type='float', value=100., suffix='×'),
            dict(name='focallength', type='float', value=200., suffix='μm'),
            dict(name='camerapitch', type='float', value=4.8, suffix='μm'),
            dict(name='slmpitch', type='float', value=8., suffix='μm'),
            dict(name='splay', type='float', value=0.01)])
        slm = dict(name='SLM', type='group', children=[
            dict(name='xs', type='float', value=256., suffix='phixels'),
            dict(name='ys', type='float', value=256., suffix='phixels'),
            dict(name='phis', type='float', value=8., suffix='°'),
            dict(name='scale', type='float', value=3.)])
        camera = dict(name='camera', type='group', children=[
            dict(name='xc', type='float', value=320., suffix='pixels'),
            dict(name='yc', type='float', value=240., suffix='pixels'),
            dict(name='zc', type='float', value=0., suffix='pixels'),
            dict(name='thetac', type='float', value=0., suffix='°')])
        return Parameter.create(name='params', type='group',
                                children=[instr, slm, camera])

    def _getParameters(self, parameter: Parameter) -> dict[str, Parameter]:
        '''Recursively index all leaf parameters by name.

        Parameters
        ----------
        parameter : Parameter
            Root of the subtree to index.

        Returns
        -------
        dict[str, Parameter]
            Flat mapping of parameter name to ``Parameter`` object.
        '''
        parameters: dict[str, Parameter] = {}
        for child in parameter.children():
            if child.hasChildren():
                parameters.update(self._getParameters(child))
            else:
                parameters[child.name()] = child
        return parameters

    @property
    def cgh(self) -> CGH | None:
        '''The currently connected CGH instance.'''
        return self._cgh

    @cgh.setter
    def cgh(self, cgh: CGH | None) -> None:
        if cgh is self._cgh:
            return
        self._cgh = cgh
        self.updateTree()

    def get(self, key: str, default: object = None) -> object:
        '''Return the current value of a parameter by name.

        Parameters
        ----------
        key : str
            Parameter name.
        default : object
            Value to return if the key is not found. Default: ``None``.

        Returns
        -------
        object
            Current parameter value, or ``default`` if not found.
        '''
        if key in self._parameters:
            return self._parameters[key].value()
        return default

    def set(self, key: str, value: object) -> None:
        '''Set the value of a parameter by name.

        Parameters
        ----------
        key : str
            Parameter name.
        value : object
            New value to assign.
        '''
        if key in self._parameters:
            self._parameters[key].setValue(value)
        else:
            logger.warning(f'unknown parameter: {key}')

    @property
    def properties(self) -> KeysView[str]:
        '''Names of all registered parameters.'''
        return self._parameters.keys()

    @property
    def settings(self) -> dict[str, object]:
        '''Current values of all parameters as a dict.'''
        return {p: self.get(p) for p in self.properties}

    @settings.setter
    def settings(self, settings: dict[str, object]) -> None:
        '''Set multiple parameters at once without triggering per-change
        CGH updates.

        Uses ``treeChangeBlocker`` to suppress ``sigTreeStateChanged``
        for the duration of the batch, so ``updateCGH`` (and any other
        connected slots) fire only once after all values are applied.
        '''
        with self.tree.treeChangeBlocker():
            for key, value in settings.items():
                self.set(key, value)

    @QtCore.pyqtSlot(object, object)
    def updateCGH(self, tree: Parameter, changes: list) -> None:
        '''Slot called when any parameter value changes.

        Applies the changed value to the connected CGH instance if the
        parameter name matches a known CGH field.

        Parameters
        ----------
        tree : Parameter
            The parameter tree (unused).
        changes : list[tuple[Parameter, str, object]]
            List of ``(param, change, value)`` tuples emitted by
            ``sigTreeStateChanged``.
        '''
        if self._cgh is None:
            return
        for param, change, value in changes:
            if change == 'value':
                key = param.name()
                if key in self._cgh._fields:
                    setattr(self._cgh, key, value)
                else:
                    logger.warning(f'CGH has no field: {key}')

    def updateTree(self) -> None:
        '''Populate the tree with the current CGH settings.

        Only parameters that have a corresponding tree entry are applied;
        CGH fields with no tree representation (e.g. ``shape``) are
        silently skipped.
        '''
        if self._cgh is not None:
            self.settings = {k: v for k, v in self._cgh.settings.items()
                             if k in self._parameters}

    @classmethod
    def example(cls) -> None:
        '''Display an interactive CGH parameter tree demo.'''
        import pyqtgraph as pg

        pg.mkQApp()
        cgh = CGH()
        widget = cls(cgh=cgh)
        widget.show()
        print('CGH settings:', widget.settings)
        pg.exec()


if __name__ == '__main__':
    QCGHTree.example()
