'''Unit tests for QLetterArray.'''
import unittest
import numpy as np
from pyqtgraph.Qt import QtWidgets, QtTest
from QHOT.lib.traps.QTrapGroup import QTrapGroup  # must precede traps imports
from QHOT.traps.QTrapArray import QTrapArray
from QHOT.traps.QLetterArray import QLetterArray, _FONT, _char_positions, _char_mask
from QHOT.traps.QTweezer import QTweezer

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class TestInit(unittest.TestCase):

    def test_default_char(self):
        la = QLetterArray()
        self.assertEqual(la.char, 'A')

    def test_default_separation(self):
        la = QLetterArray()
        self.assertEqual(la.separation, 40.)

    def test_custom_char(self):
        la = QLetterArray(char='N')
        self.assertEqual(la.char, 'N')

    def test_custom_separation(self):
        la = QLetterArray(separation=20.)
        self.assertEqual(la.separation, 20.)

    def test_is_qtraparray(self):
        la = QLetterArray()
        self.assertIsInstance(la, QTrapArray)

    def test_is_qtrapgroup(self):
        la = QLetterArray()
        self.assertIsInstance(la, QTrapGroup)

    def test_kwargs_forwarded(self):
        la = QLetterArray(r=(10., 20., 5.))
        np.testing.assert_array_almost_equal(la.r, [10., 20., 5.])


class TestShape(unittest.TestCase):

    def test_nx_is_five(self):
        la = QLetterArray(char='A')
        self.assertEqual(la.nx, 5)

    def test_ny_is_seven(self):
        la = QLetterArray(char='A')
        self.assertEqual(la.ny, 7)

    def test_shape_is_5x7(self):
        la = QLetterArray(char='Z')
        self.assertEqual(la.shape, (5, 7))


class TestDotCount(unittest.TestCase):

    def test_n_dot_count(self):
        la = QLetterArray(char='N')
        self.assertEqual(len(list(la.leaves())), len(_char_positions('N')))

    def test_y_dot_count(self):
        la = QLetterArray(char='Y')
        self.assertEqual(len(list(la.leaves())), len(_char_positions('Y')))

    def test_u_dot_count(self):
        la = QLetterArray(char='U')
        self.assertEqual(len(list(la.leaves())), len(_char_positions('U')))

    def test_space_has_no_traps(self):
        la = QLetterArray(char=' ')
        self.assertEqual(len(list(la.leaves())), 0)

    def test_all_leaves_are_tweezers(self):
        la = QLetterArray(char='A')
        for trap in la.leaves():
            self.assertIsInstance(trap, QTweezer)


class TestMask(unittest.TestCase):

    def test_mask_shape_is_5x7(self):
        la = QLetterArray(char='A')
        self.assertEqual(la.mask.shape, (5, 7))

    def test_mask_matches_char_positions(self):
        la = QLetterArray(char='N')
        expected = _char_mask('N')
        np.testing.assert_array_equal(la.mask, expected)

    def test_space_mask_all_false(self):
        la = QLetterArray(char=' ')
        self.assertFalse(la.mask.any())

    def test_mask_dot_count_matches_leaves(self):
        for char in 'NYU nyu 0':
            la = QLetterArray(char=char)
            self.assertEqual(la.mask.sum(), len(list(la.leaves())),
                             msg=f'char={char!r}')


class TestRegisteredProperties(unittest.TestCase):

    def setUp(self):
        self.la = QLetterArray()

    def test_separation_is_registered(self):
        self.assertIn('separation', self.la.properties)

    def test_nx_is_not_registered(self):
        self.assertNotIn('nx', self.la.properties)

    def test_ny_is_not_registered(self):
        self.assertNotIn('ny', self.la.properties)

    def test_char_is_not_registered(self):
        self.assertNotIn('char', self.la.properties)

    def test_fuzz_is_not_registered(self):
        self.assertNotIn('fuzz', self.la.properties)

    def test_separation_decimals(self):
        self.assertEqual(self.la.properties['separation']['decimals'], 1)


class TestCharSetter(unittest.TestCase):

    def test_char_setter_updates_char(self):
        la = QLetterArray(char='A')
        la.char = 'B'
        self.assertEqual(la.char, 'B')

    def test_char_setter_updates_dot_count(self):
        la = QLetterArray(char='A')
        la.char = 'N'
        self.assertEqual(len(list(la.leaves())), len(_char_positions('N')))

    def test_char_setter_updates_mask(self):
        la = QLetterArray(char='A')
        la.char = 'N'
        np.testing.assert_array_equal(la.mask, _char_mask('N'))

    def test_lowercase_char_accepted(self):
        la = QLetterArray(char='n')
        self.assertEqual(la.char, 'n')
        self.assertEqual(len(list(la.leaves())), len(_char_positions('n')))

    def test_upper_and_lower_differ(self):
        la_upper = QLetterArray(char='N')
        la_lower = QLetterArray(char='n')
        self.assertNotEqual(len(list(la_upper.leaves())),
                            len(list(la_lower.leaves())))


class TestCentering(unittest.TestCase):

    def test_grid_centered_on_group_r(self):
        # For a full grid (no masking), centroid of dots equals group center.
        # Pick a char with roughly uniform dot distribution for a clean test:
        # we use the mask directly rather than a specific char.
        la = QLetterArray(char='H', separation=10., r=(50., 60., 0.))
        positions = np.array([t.r for t in la.leaves()])
        # The geometric grid center equals la.r:
        cx, cy, cz = la.r
        xs = cx + 10. * (np.arange(5) - 2.)
        ys = cy + 10. * (np.arange(7) - 3.)
        # All dot x-positions should be in xs, y-positions in ys
        for t in la.leaves():
            self.assertTrue(np.any(np.isclose(t.r[0], xs)),
                            msg=f'x={t.r[0]} not on grid')
            self.assertTrue(np.any(np.isclose(t.r[1], ys)),
                            msg=f'y={t.r[1]} not on grid')

    def test_z_matches_group_z(self):
        la = QLetterArray(char='A', r=(0., 0., 15.))
        for trap in la.leaves():
            self.assertAlmostEqual(trap.r[2], 15., places=6)


class TestSignals(unittest.TestCase):

    def setUp(self):
        self.la = QLetterArray(char='A')

    def test_reshaping_emitted_on_char_change(self):
        spy = QtTest.QSignalSpy(self.la.reshaping)
        self.la.char = 'B'
        self.assertEqual(len(spy), 1)

    def test_reshaped_emitted_on_char_change(self):
        spy = QtTest.QSignalSpy(self.la.reshaped)
        self.la.char = 'B'
        self.assertEqual(len(spy), 1)

    def test_reshaping_emitted_on_separation_change(self):
        spy = QtTest.QSignalSpy(self.la.reshaping)
        self.la.separation = 20.
        self.assertEqual(len(spy), 1)

    def test_reshaping_before_reshaped(self):
        order = []
        self.la.reshaping.connect(lambda: order.append('reshaping'))
        self.la.reshaped.connect(lambda: order.append('reshaped'))
        self.la.char = 'Z'
        self.assertEqual(order, ['reshaping', 'reshaped'])

    def test_reshaping_fired_with_old_leaves(self):
        old_count = [0]
        self.la.reshaping.connect(
            lambda: old_count.__setitem__(0, len(list(self.la.leaves()))))
        original = len(list(self.la.leaves()))
        self.la.char = 'N'
        self.assertEqual(old_count[0], original)

    def test_reshaped_fired_with_new_leaves(self):
        new_count = [0]
        self.la.reshaped.connect(
            lambda: new_count.__setitem__(0, len(list(self.la.leaves()))))
        self.la.char = 'N'
        self.assertEqual(new_count[0], len(_char_positions('N')))


class TestInMenu(unittest.TestCase):

    def test_in_all(self):
        import QHOT.traps as traps_pkg
        self.assertIn('QLetterArray', traps_pkg.__all__)

    def test_importable(self):
        from QHOT.traps import QLetterArray as LA
        self.assertIsNotNone(LA)


if __name__ == '__main__':
    unittest.main()
