'''Unit tests for QTrapMenu.'''
import unittest
from unittest.mock import patch
from pyqtgraph.Qt import QtCore, QtWidgets, QtTest
import importlib as _importlib
from QHOT.lib.traps.QTrapMenu import QTrapMenu
_qtrapmenu_mod = _importlib.import_module('QHOT.lib.traps.QTrapMenu')
import QHOT.traps

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class TestInit(unittest.TestCase):

    def test_default_pos_is_origin(self):
        menu = QTrapMenu()
        self.assertAlmostEqual(menu.pos.x(), 0.)
        self.assertAlmostEqual(menu.pos.y(), 0.)

    def test_action_count_matches_all(self):
        menu = QTrapMenu()
        self.assertEqual(len(menu.actions()), len(QFab.traps.__all__))

    def test_action_names_match_all(self):
        menu = QTrapMenu()
        names = [a.text() for a in menu.actions()]
        for trapname in QFab.traps.__all__:
            self.assertIn(trapname, names)


class TestPos(unittest.TestCase):

    def test_pos_setter(self):
        menu = QTrapMenu()
        menu.pos = QtCore.QPointF(42., 99.)
        self.assertAlmostEqual(menu.pos.x(), 42.)
        self.assertAlmostEqual(menu.pos.y(), 99.)


class TestTrapRequested(unittest.TestCase):

    def _trigger_action(self, menu, trapname):
        for action in menu.actions():
            if action.text() == trapname:
                action.trigger()
                return
        raise AssertionError(f'No action named {trapname!r}')

    def test_emits_trap_requested(self):
        menu = QTrapMenu()
        spy = QtTest.QSignalSpy(menu.trapRequested)
        self._trigger_action(menu, 'QTweezer')
        self.assertEqual(len(spy), 1)

    def test_emits_correct_trap_class(self):
        from QHOT.traps.QTweezer import QTweezer
        menu = QTrapMenu()
        spy = QtTest.QSignalSpy(menu.trapRequested)
        self._trigger_action(menu, 'QTweezer')
        _, trap = spy[0]
        self.assertIsInstance(trap, QTweezer)

    def test_emits_configured_pos(self):
        menu = QTrapMenu()
        menu.pos = QtCore.QPointF(7., 13.)
        spy = QtTest.QSignalSpy(menu.trapRequested)
        self._trigger_action(menu, 'QTweezer')
        pos, _ = spy[0]
        self.assertAlmostEqual(pos.x(), 7.)
        self.assertAlmostEqual(pos.y(), 13.)

    def test_each_trap_type_emits(self):
        for trapname in QFab.traps.__all__:
            with self.subTest(trapname=trapname):
                menu = QTrapMenu()
                spy = QtTest.QSignalSpy(menu.trapRequested)
                self._trigger_action(menu, trapname)
                self.assertEqual(len(spy), 1)

    def test_unknown_trap_logs_warning(self):
        menu = QTrapMenu()
        with patch.object(_qtrapmenu_mod, 'logger') as mock_log:
            menu._onTrapSelected('NoSuchTrap')
            mock_log.warning.assert_called_once()

    def test_unknown_trap_does_not_emit(self):
        menu = QTrapMenu()
        spy = QtTest.QSignalSpy(menu.trapRequested)
        with self.assertLogs('QHOT.lib.traps.QTrapMenu', level='WARNING'):
            menu._onTrapSelected('NoSuchTrap')
        self.assertEqual(len(spy), 0)


if __name__ == '__main__':
    unittest.main()
