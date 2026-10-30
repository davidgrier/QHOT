'''Tests of the backends that compute holograms.

Every backend must compute what the reference states.  The tests that
follow are the same for each, and are run for each backend that is
installed.
'''
import importlib
import os
import subprocess
import sys
import types
import unittest
from unittest.mock import patch

import numpy as np
from pyqtgraph.Qt import QtCore, QtWidgets

from QHOT.lib.holograms import NumpyBackend, Optics
from QHOT.lib.holograms import reference as ref
from QHOT.lib.traps import QTrapOverlay
from QHOT.traps import QRingTrap, QTweezer, QVortex

try:
    from patterns import (CALIBRATIONS, SHAPE, Composite, group, levels,
                          optics, patterns, tweezer)
except ImportError:  # run from the root of the repository
    from tests.patterns import (CALIBRATIONS, SHAPE, Composite, group,
                                levels, optics, patterns, tweezer)

try:
    import torch
    from QHOT.lib.holograms.backends import TorchBackend
except ImportError:
    TorchBackend = None

try:
    import numba
    from QHOT.lib.holograms.backends import NumbaBackend
    numba_module = importlib.import_module(
        'QHOT.lib.holograms.backends._numba',
    )
except ImportError:
    NumbaBackend = None

from QHOT.lib.holograms.backends import CupyBackend
cupy_module = importlib.import_module('QHOT.lib.holograms.backends._cupy')

try:
    import cupy
    cupy.cuda.Device()
    HAVE_CUPY = True
except Exception:
    HAVE_CUPY = False


def numpy_as_cupy(device=lambda: None) -> types.SimpleNamespace:
    '''Return NumPy dressed as the part of CuPy that CupyBackend uses.

    It offers nothing else, so that a backend that reaches for something
    that is not on this list fails here and not on the first GPU.
    '''
    return types.SimpleNamespace(
        float32=np.float32,
        complex64=np.complex64,
        uint8=np.uint8,
        asarray=np.asarray,
        zeros=np.zeros,
        exp=np.exp,
        angle=np.angle,
        asnumpy=np.asarray,
        cuda=types.SimpleNamespace(Device=device),
    )

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def specs(traps):
    return [t.spec() for t in traps]


class TestBackend(unittest.TestCase):

    BACKEND = NumpyBackend

    def setUp(self):
        self.backend = self.BACKEND()
        self.o = optics()

    def assertAgrees(self, a, b, label=''):
        d = levels(a, b)
        self.assertLessEqual(d.max(), 1, label)
        self.assertLess(np.count_nonzero(d), 0.01 * d.size, label)

    def test_computes_what_the_reference_states(self):
        for label, calibration in CALIBRATIONS.items():
            o = optics(**calibration)
            for name, traps in patterns():
                with self.subTest(name, calibration=label):
                    pattern = specs(traps)
                    self.assertAgrees(self.backend.hologram(pattern, o),
                                      ref.hologram(pattern, o))

    def test_empty_pattern(self):
        h = self.backend.hologram([], self.o)
        self.assertEqual(h.shape, SHAPE)
        self.assertTrue((h == 127).all())

    def test_result_is_an_array_of_bytes_in_the_shape_of_the_slm(self):
        h = self.backend.hologram(specs([tweezer(20, 20)]), self.o)
        self.assertIsInstance(h, np.ndarray)
        self.assertEqual(h.dtype, np.uint8)
        self.assertEqual(h.shape, SHAPE)

    def test_repeatable(self):
        pattern = specs([tweezer(20, 20), QVortex(r=(30, 20, 0), ell=3, phase=0.2)])
        self.assertTrue(np.array_equal(
            self.backend.hologram(pattern, self.o),
            self.backend.hologram(pattern, self.o)))

    def test_does_not_depend_on_the_order_of_the_traps(self):
        traps = [tweezer(10, 12), tweezer(40, 30, 2.),
                 QVortex(r=(30, 24, 1), ell=3, phase=0.4),
                 QRingTrap(r=(20, 30, 0), radius=6., ell=2, phase=1.)]
        a = self.backend.hologram(specs(traps), self.o)
        b = self.backend.hologram(specs(traps[::-1]), self.o)
        self.assertAgrees(a, b)

    def test_many_traps(self):
        rng = np.random.default_rng(3)
        traps = [
            tweezer(
                rng.uniform(0, 64),
                rng.uniform(0, 48),
                rng.uniform(-3, 3),
                rng.uniform(0, 6.28),
            )
            for _ in range(300)
        ]
        self.assertAgrees(self.backend.hologram(specs(traps), self.o),
                          ref.hologram(specs(traps), self.o))

    def test_traps_that_share_a_structure_and_those_that_do_not(self):
        same = [QVortex(r=(8 + 7 * n, 10 + 4 * n, 0), ell=3, phase=0.2 * n)
                for n in range(7)]
        different = [
            QVortex(r=(8 + 7 * n, 10 + 4 * n, 0), ell=1 + n, phase=0.2 * n)
            for n in range(7)
        ]
        for traps in (same, different):
            self.assertAgrees(self.backend.hologram(specs(traps), self.o),
                              ref.hologram(specs(traps), self.o))

    def test_the_weight_of_a_composite_reaches_its_members(self):
        c = Composite(r=(32., 24., 0.), amplitude=3., phase=0.8)
        c.addTrap([tweezer(20, 20), QVortex(r=(40, 28, 0), ell=2, phase=0.2)])
        other = tweezer(10, 40)
        for pattern in ([c, other], [group(c, other)]):
            with self.subTest(depth=len(pattern)):
                self.assertAgrees(
                    self.backend.hologram(specs(pattern), self.o),
                    ref.hologram(specs(pattern), self.o))

    def test_follows_a_change_of_calibration(self):
        pattern = specs([tweezer(20, 20), QVortex(r=(30, 20, 0), ell=3, phase=0.2)])
        for calibration in (dict(), dict(thetac=20.), dict(phis=15.),
                            dict()):
            o = optics(**calibration)
            self.assertAgrees(self.backend.hologram(pattern, o),
                              ref.hologram(pattern, o))

    def test_the_input_is_not_changed(self):
        pattern = specs([group(tweezer(20, 20), QVortex(r=(30, 20, 0), phase=0.2))])
        before = list(pattern)
        self.backend.hologram(pattern, self.o)
        self.assertEqual(pattern, before)

    def test_an_unknown_kind_is_an_error(self):
        from QHOT.lib.traps import TrapSpec
        with self.assertRaises(KeyError):
            self.backend.hologram(
                [TrapSpec(kind='NoSuchTrap', r=(0., 0., 0.))], self.o)


class TestStructuresAreKeptByValue(unittest.TestCase):

    BACKEND = NumpyBackend

    def setUp(self):
        self.backend = self.BACKEND()
        self.o = optics()

    def calls(self, traps, o=None):
        '''Count how often a vortex is asked for its structuring field.'''
        with patch.object(
            QVortex,
            'structuringField',
            wraps=QVortex.structuringField,
        ) as made:
            self.backend.hologram(specs(traps), o or self.o)
        return made.call_count

    def vortices(self, *ells):
        return [QVortex(r=(10 + 8 * n, 12 + 3 * n, 0), ell=ell, phase=0.1)
                for n, ell in enumerate(ells)]

    def test_made_once_for_traps_that_share_it(self):
        self.assertEqual(self.calls(self.vortices(3, 3, 3, 3)), 1)

    def test_made_once_for_each_that_differs(self):
        self.assertEqual(self.calls(self.vortices(3, 4, 3, 5)), 3)

    def test_reused_by_the_next_hologram(self):
        traps = self.vortices(3, 4)
        self.assertEqual(self.calls(traps), 2)
        self.assertEqual(self.calls(traps), 0)

    def test_reused_when_the_traps_move(self):
        traps = self.vortices(3, 4)
        self.calls(traps)
        for trap in traps:
            trap.x = trap.x + 5.
        self.assertEqual(self.calls(traps), 0)

    def test_made_again_when_the_parameters_change(self):
        traps = self.vortices(3)
        self.calls(traps)
        traps[0].ell = 7
        self.assertEqual(self.calls(traps), 1)

    def test_made_again_when_the_calibration_changes(self):
        traps = self.vortices(3)
        self.calls(traps)
        self.assertEqual(self.calls(traps, optics(thetac=10.)), 1)

    def test_plain_tweezers_ask_for_none(self):
        self.assertEqual(
            self.calls([tweezer(20, 20), tweezer(30, 30)]), 0)

    def test_the_cache_is_bounded(self):
        backend = self.BACKEND(cache=3)
        traps = self.vortices(*range(1, 9))
        backend.hologram(specs(traps), self.o)
        self.assertLessEqual(len(backend._structures), 3)


class TestOpticsInSupport(unittest.TestCase):

    def test_toSLM_of_many_positions(self):
        o = optics(thetac=12., zc=2., splay=0.03)
        rng = np.random.default_rng(1)
        R = rng.uniform(-20, 60, size=(7, 3))
        many = o.toSLM(R)
        self.assertEqual(many.shape, (7, 3))
        for r, m in zip(R, many):
            self.assertTrue(np.allclose(o.toSLM(r), m))

    def test_toSLM_of_one_position_is_still_a_vector(self):
        self.assertEqual(optics().toSLM((1., 2., 3.)).shape, (3,))


class TestPatternOfAnOverlay(unittest.TestCase):

    def test_is_the_tuple_of_the_specs_of_the_traps(self):
        overlay = QTrapOverlay()
        a, g = tweezer(10, 12), group(tweezer(20, 20), tweezer(30, 30))
        overlay.addTrap([a, g])
        pattern = overlay.pattern()
        self.assertIsInstance(pattern, tuple)
        self.assertEqual(set(pattern), {a.spec(), g.spec()})

    def test_is_empty_without_traps(self):
        self.assertEqual(QTrapOverlay().pattern(), ())

    def test_is_a_snapshot(self):
        overlay = QTrapOverlay()
        a = tweezer(10, 12)
        overlay.addTrap(a)
        pattern = overlay.pattern()
        a.r = (40., 40., 4.)
        self.assertEqual(pattern[0].r, (10., 12., 0.))

    def test_computes_to_the_hologram_of_the_traps(self):
        overlay = QTrapOverlay()
        overlay.addTrap([tweezer(10, 12), QVortex(r=(30, 20, 0), ell=2, phase=0.2),
                         group(tweezer(20, 20), tweezer(30, 30))])
        o = optics()
        a = NumpyBackend().hologram(overlay.pattern(), o)
        b = ref.hologram(overlay.pattern(), o)
        self.assertLessEqual(levels(a, b).max(), 1)

    def test_can_be_computed_in_another_thread(self):
        overlay = QTrapOverlay()
        overlay.addTrap([tweezer(10, 12), tweezer(30, 20)])
        pattern, o, result = overlay.pattern(), optics(), []

        class Worker(QtCore.QThread):
            def run(self):
                result.append(NumpyBackend().hologram(pattern, o))

        worker = Worker()
        worker.start()
        worker.wait()
        self.assertEqual(len(result), 1)
        self.assertLessEqual(
            levels(result[0], ref.hologram(pattern, o)).max(), 1)


class TestTheOptionalBackendsAreLazy(unittest.TestCase):

    '''Importing the package must not import torch, numba or cupy.

    Importing them takes a second or more, and a machine that has only
    NumPy should not wait for, or fail on, the libraries it does not use.
    '''

    def run_python(self, code: str) -> str:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        done = subprocess.run(
            [sys.executable, '-c',
             f'import sys; sys.path.insert(0, {os.path.dirname(root)!r})\n'
             + code],
            capture_output=True,
            text=True,
            env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'},
            timeout=60,
        )
        self.assertEqual(done.returncode, 0, done.stderr[-500:])
        return done.stdout.strip()

    def test_importing_the_package_imports_none_of_the_libraries(self):
        out = self.run_python(
            'import QHOT.lib.holograms\n'
            'import QHOT.lib.holograms.backends as b\n'
            "print([m for m in ('torch', 'numba', 'cupy') if m in sys.modules])"
        )
        self.assertEqual(out, '[]')

    def test_a_backend_is_imported_when_it_is_asked_for(self):
        out = self.run_python(
            'from QHOT.lib.holograms.backends import NumpyBackend\n'
            'import QHOT.lib.holograms.backends as b\n'
            "print('QHOT.lib.holograms.backends._torch' in sys.modules)\n"
            'b.TorchBackend\n'
            "print('QHOT.lib.holograms.backends._torch' in sys.modules)"
        )
        self.assertEqual(out.split(), ['False', 'True'])

    def test_an_unknown_name_is_an_attribute_error(self):
        from QHOT.lib.holograms import backends
        with self.assertRaises(AttributeError):
            backends.NoSuchBackend

    def test_dir_lists_the_optional_backends(self):
        from QHOT.lib.holograms import backends
        for name in ('NumpyBackend', 'NumbaBackend', 'TorchBackend',
                     'CupyBackend'):
            self.assertIn(name, dir(backends))


class TestComponents(unittest.TestCase):

    def test_a_tweezer_is_its_own_leaf_with_its_weight(self):
        spec = tweezer(1, 1, phase=0.5, amplitude=2.).spec()
        (leaf, weight), = spec.components()
        self.assertIs(leaf, spec)
        self.assertAlmostEqual(weight, 2. * np.exp(0.5j))

    def test_a_plain_group_does_not_weight_its_members(self):
        g = group(tweezer(1, 1, phase=0., amplitude=2.),
                  tweezer(2, 2, phase=1., amplitude=3.))
        weights = [w for _, w in g.spec().components()]
        self.assertAlmostEqual(weights[0], 2.)
        self.assertAlmostEqual(weights[1], 3. * np.exp(1j))

    def test_a_composite_weights_all_its_members(self):
        c = Composite(r=(0., 0., 0.), amplitude=2., phase=0.5)
        c.addTrap([tweezer(1, 1, phase=0., amplitude=3.)])
        (_, weight), = c.spec().components()
        self.assertAlmostEqual(weight, 6. * np.exp(0.5j))

    def test_weights_multiply_through_nesting(self):
        inner = Composite(r=(0., 0., 0.), amplitude=2., phase=0.25)
        inner.addTrap([tweezer(1, 1, phase=0.25, amplitude=1.5)])
        outer = Composite(r=(0., 0., 0.), amplitude=0.5, phase=1.)
        outer.addTrap([inner])
        (_, weight), = outer.spec().components()
        self.assertAlmostEqual(weight, 1.5 * np.exp(1.5j))

    def test_an_empty_group_has_no_leaves(self):
        from QHOT.lib.traps import QTrapGroup
        self.assertEqual(list(QTrapGroup(r=(0, 0, 0)).spec().components()), [])


@unittest.skipIf(NumbaBackend is None, 'numba is not installed')
class TestNumbaBackend(TestBackend):

    BACKEND = NumbaBackend

    def families(self, count, structured):
        '''A pattern of ``count`` traps, plain or all of one structure.'''
        rng = np.random.default_rng(count)
        if structured:
            return [
                QVortex(
                    r=(rng.uniform(0, 64), rng.uniform(0, 48), 0.),
                    ell=3,
                    phase=rng.uniform(0, 6.28),
                    amplitude=rng.uniform(0.5, 2.),
                )
                for _ in range(count)
            ]
        return [
            tweezer(
                rng.uniform(0, 64),
                rng.uniform(0, 48),
                rng.uniform(-3, 3),
                rng.uniform(0, 6.28),
            )
            for _ in range(count)
        ]

    def test_either_side_of_the_limit_between_the_kernel_and_blas(self):
        limit = numba_module.FUSED_LIMIT
        for count in (1, 2, limit - 1, limit, limit + 1, 3 * limit):
            for structured in (False, True):
                with self.subTest(count=count, structured=structured):
                    pattern = specs(self.families(count, structured))
                    self.assertAgrees(
                        self.backend.hologram(pattern, self.o),
                        ref.hologram(pattern, self.o),
                    )

    def test_the_two_paths_agree_with_each_other(self):
        pattern = specs(self.families(8, True) + self.families(5, False))
        fused = self.backend.hologram(pattern, self.o)
        with patch.object(numba_module, 'FUSED_LIMIT', 0):
            blas = self.backend.hologram(pattern, self.o)
        self.assertAgrees(fused, blas)

    def test_the_quantization_matches_the_reference_at_the_edges(self):
        '''Fields on the real axis, where the phase is 0 or pi.'''
        psi = np.array([[1, -1], [1j, -1j]], dtype=np.complex64)
        self.assertLessEqual(
            levels(self.backend.quantize(psi), ref.quantize(psi)).max(),
            1,
        )

    def test_a_missing_numba_is_reported_when_the_backend_is_made(self):
        with patch.object(numba_module, 'njit', None):
            with self.assertRaises(ImportError):
                NumbaBackend()


@unittest.skipIf(NumbaBackend is None, 'numba is not installed')
class TestNumbaStructuresAreKeptByValue(TestStructuresAreKeptByValue):

    BACKEND = NumbaBackend


@unittest.skipIf(TorchBackend is None, 'torch is not installed')
class TestTorchBackend(TestBackend):

    BACKEND = TorchBackend


class TestCupyBackendOnTheCPU(TestBackend):

    '''The logic of CupyBackend, with NumPy standing in for CuPy.

    This does not test CUDA, only that the backend is right about the
    shapes, the types and what it asks of the library.
    '''

    BACKEND = CupyBackend

    def setUp(self):
        patcher = patch.object(cupy_module, 'cp', numpy_as_cupy())
        patcher.start()
        self.addCleanup(patcher.stop)
        super().setUp()

    def test_a_missing_cupy_is_reported_when_the_backend_is_made(self):
        with patch.object(cupy_module, 'cp', None):
            with self.assertRaises(ImportError):
                CupyBackend()

    def test_no_cuda_device_is_reported_when_the_backend_is_made(self):
        def no_device():
            raise RuntimeError('no device')

        with patch.object(cupy_module, 'cp', numpy_as_cupy(no_device)):
            with self.assertRaises(RuntimeError):
                CupyBackend()


class TestCupyStructuresOnTheCPU(TestStructuresAreKeptByValue):

    BACKEND = CupyBackend

    def setUp(self):
        patcher = patch.object(cupy_module, 'cp', numpy_as_cupy())
        patcher.start()
        self.addCleanup(patcher.stop)
        super().setUp()


@unittest.skipUnless(HAVE_CUPY, 'cupy and a CUDA device are not available')
class TestCupyBackend(TestBackend):

    BACKEND = CupyBackend


@unittest.skipUnless(HAVE_CUPY, 'cupy and a CUDA device are not available')
class TestCupyStructuresAreKeptByValue(TestStructuresAreKeptByValue):

    BACKEND = CupyBackend


@unittest.skipIf(TorchBackend is None, 'torch is not installed')
class TestTorchStructuresAreKeptByValue(TestStructuresAreKeptByValue):

    BACKEND = TorchBackend


@unittest.skipIf(TorchBackend is None, 'torch is not installed')
class TestTorchOnTheCPUToo(TestBackend):

    '''The same computation on the CPU, which every machine has.'''

    def setUp(self):
        self.backend = TorchBackend(device='cpu')
        self.o = optics()


if __name__ == '__main__':
    unittest.main()
