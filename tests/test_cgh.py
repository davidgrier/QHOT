'''Unit tests for CGH: the calibration and the pipeline.'''
import gc
import threading
import time
import unittest
from unittest.mock import patch

import numpy as np
from pyqtgraph.Qt import QtCore, QtGui, QtTest, QtWidgets

import importlib as _importlib
from QHOT.lib.holograms import NumpyBackend, Optics
from QHOT.lib.holograms import reference as ref
from QHOT.lib.holograms.CGH import CGH
_cgh_mod = _importlib.import_module('QHOT.lib.holograms.CGH')

try:
    from patterns import SHAPE, levels, optics, tweezer
except ImportError:  # run from the root of the repository
    from tests.patterns import SHAPE, levels, optics, tweezer

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class TestInit(unittest.TestCase):

    def test_default_shape(self):
        self.assertEqual(CGH().shape, (512, 512))

    def test_default_wavelength(self):
        self.assertAlmostEqual(CGH().wavelength, 1.064)

    def test_default_n_m(self):
        self.assertAlmostEqual(CGH().n_m, 1.340)

    def test_default_magnification(self):
        self.assertAlmostEqual(CGH().magnification, 100.)

    def test_default_focallength(self):
        self.assertAlmostEqual(CGH().focallength, 200.)

    def test_default_camerapitch(self):
        self.assertAlmostEqual(CGH().camerapitch, 4.8)

    def test_default_slmpitch(self):
        self.assertAlmostEqual(CGH().slmpitch, 8.)

    def test_default_scale(self):
        self.assertAlmostEqual(CGH().scale, 3.)

    def test_default_splay(self):
        self.assertAlmostEqual(CGH().splay, 0.01)

    def test_default_xs(self):
        self.assertAlmostEqual(CGH().xs, 0.)

    def test_default_ys(self):
        self.assertAlmostEqual(CGH().ys, 0.)

    def test_default_phis(self):
        self.assertAlmostEqual(CGH().phis, 8.)

    def test_default_xc(self):
        self.assertAlmostEqual(CGH().xc, 320.)

    def test_default_yc(self):
        self.assertAlmostEqual(CGH().yc, 240.)

    def test_default_zc(self):
        self.assertAlmostEqual(CGH().zc, 0.)

    def test_default_thetac(self):
        self.assertAlmostEqual(CGH().thetac, 0.)

    def test_custom_shape(self):
        self.assertEqual(CGH(shape=(256, 256)).shape, (256, 256))

    def test_custom_wavelength(self):
        self.assertAlmostEqual(CGH(wavelength=0.532).wavelength, 0.532)

    def test_custom_xc(self):
        self.assertAlmostEqual(CGH(xc=100.).xc, 100.)

    def test_no_parent_by_default(self):
        self.assertIsNone(CGH().parent())

    def test_building_it_emits_nothing(self):
        changes = []

        class Probe(CGH):
            def _changed(self):
                changes.append(1)
                super()._changed()

        Probe(xc=1., wavelength=0.5)
        self.assertEqual(changes, [])

    def test_a_calibration_only_cgh_owns_no_thread(self):
        cgh = CGH()
        self.assertIsNone(cgh._thread)
        self.assertIsNone(cgh._worker)

    def test_default_backend_is_numpy(self):
        self.assertIsInstance(CGH().backend, NumpyBackend)

    def test_given_backend_is_used(self):
        backend = NumpyBackend()
        self.assertIs(CGH(backend=backend).backend, backend)


class TestSetattr(unittest.TestCase):

    def setUp(self):
        self.cgh = CGH()
        self.spy = QtTest.QSignalSpy(self.cgh.recalculate)

    def test_xc_emits_recalculate(self):
        self.cgh.xc = 100.
        self.assertEqual(len(self.spy), 1)

    def test_yc_emits_recalculate(self):
        self.cgh.yc = 100.
        self.assertEqual(len(self.spy), 1)

    def test_zc_emits_recalculate(self):
        self.cgh.zc = 10.
        self.assertEqual(len(self.spy), 1)

    def test_thetac_emits_recalculate(self):
        self.cgh.thetac = 45.
        self.assertEqual(len(self.spy), 1)

    def test_wavelength_emits_recalculate(self):
        self.cgh.wavelength = 0.532
        self.assertEqual(len(self.spy), 1)

    def test_shape_emits_recalculate(self):
        self.cgh.shape = (256, 256)
        self.assertEqual(len(self.spy), 1)

    def test_unrelated_attr_does_not_emit(self):
        self.cgh._custom = 42
        self.assertEqual(len(self.spy), 0)

    def test_same_value_does_not_emit(self):
        self.cgh.wavelength = self.cgh.wavelength
        self.assertEqual(len(self.spy), 0)

    def test_same_shape_does_not_emit(self):
        self.cgh.shape = self.cgh.shape
        self.assertEqual(len(self.spy), 0)


class TestProperties(unittest.TestCase):

    def setUp(self):
        self.cgh = CGH()
        self.props = self.cgh.properties

    def test_returns_list(self):
        self.assertIsInstance(self.props, list)

    def test_contains_shape(self):
        self.assertIn('shape', self.props)

    def test_contains_all_calibration_attrs(self):
        for name in CGH._fields:
            self.assertIn(name, self.props)

    def test_length(self):
        self.assertEqual(len(self.props), len(CGH._fields))


class TestSettings(unittest.TestCase):

    def setUp(self):
        self.cgh = CGH()

    def test_returns_dict(self):
        self.assertIsInstance(self.cgh.settings, dict)

    def test_keys_match_fields(self):
        self.assertEqual(set(self.cgh.settings.keys()), set(CGH._fields))

    def test_values_match_attrs(self):
        for key, value in self.cgh.settings.items():
            self.assertEqual(value, getattr(self.cgh, key))

    def test_setter_updates_attr(self):
        self.cgh.settings = {'wavelength': 0.532}
        self.assertAlmostEqual(self.cgh.wavelength, 0.532)

    def test_setter_multiple_attrs(self):
        self.cgh.settings = {'xc': 100., 'yc': 200.}
        self.assertAlmostEqual(self.cgh.xc, 100.)
        self.assertAlmostEqual(self.cgh.yc, 200.)

    def test_setter_emits_recalculate_once(self):
        spy = QtTest.QSignalSpy(self.cgh.recalculate)
        self.cgh.settings = {'xc': 100., 'yc': 200., 'wavelength': 0.5}
        self.assertEqual(len(spy), 1)

    def test_setter_with_nothing_new_emits_nothing(self):
        spy = QtTest.QSignalSpy(self.cgh.recalculate)
        self.cgh.settings = self.cgh.settings
        self.assertEqual(len(spy), 0)

    def test_setter_unknown_key_does_not_raise(self):
        try:
            with self.assertLogs('QHOT.lib.holograms.CGH', level='WARNING'):
                self.cgh.settings = {'nonexistent': 42}
        except Exception as e:
            self.fail(f'settings setter raised unexpectedly: {e}')

    def test_setter_unknown_key_logs_warning(self):
        with patch.object(_cgh_mod, 'logger') as mock_logger:
            self.cgh.settings = {'nonexistent': 42}
            mock_logger.warning.assert_called_once()


class TestDerivedProperties(unittest.TestCase):

    def setUp(self):
        self.cgh = CGH(shape=(480, 640))

    def test_height(self):
        self.assertEqual(self.cgh.height, 480)

    def test_width(self):
        self.assertEqual(self.cgh.width, 640)

    def test_rc_type(self):
        self.assertIsInstance(self.cgh.rc, QtGui.QVector3D)

    def test_rc_values(self):
        cgh = CGH(xc=10., yc=20., zc=5.)
        self.assertAlmostEqual(cgh.rc.x(), 10.)
        self.assertAlmostEqual(cgh.rc.y(), 20.)
        self.assertAlmostEqual(cgh.rc.z(), 5.)

    def test_wavenumber(self):
        cgh = CGH(wavelength=1.0, n_m=1.0)
        self.assertAlmostEqual(cgh.wavenumber, 2.*np.pi)

    def test_wavenumber_scales_with_n_m(self):
        cgh1 = CGH(n_m=1.0)
        cgh2 = CGH(n_m=2.0)
        self.assertAlmostEqual(cgh2.wavenumber, 2.*cgh1.wavenumber)

    def test_qprp_positive(self):
        self.assertGreater(CGH().qprp, 0.)

    def test_qpar_positive(self):
        self.assertGreater(CGH().qpar, 0.)

    def test_qpar_less_than_qprp(self):
        cgh = CGH()
        self.assertLess(cgh.qpar, cgh.qprp)

    def test_follow_the_calibration(self):
        before = self.cgh.qprp
        self.cgh.magnification = 50.
        self.assertAlmostEqual(self.cgh.qprp, 2. * before)


class TestOptics(unittest.TestCase):

    def test_is_the_optics_of_the_calibration(self):
        cgh = CGH(thetac=12., xc=33.)
        self.assertIsInstance(cgh.optics, Optics)
        self.assertEqual(cgh.optics.settings, cgh.settings)

    def test_is_the_same_value_until_the_calibration_changes(self):
        cgh = CGH()
        first = cgh.optics
        self.assertIs(cgh.optics, first)
        cgh.xc = 99.
        self.assertIsNot(cgh.optics, first)
        self.assertEqual(cgh.optics.xc, 99.)

    def test_a_taken_snapshot_does_not_change(self):
        cgh = CGH(xc=10.)
        snapshot = cgh.optics
        cgh.xc = 20.
        cgh.settings = {'wavelength': 0.5}
        self.assertEqual(snapshot.xc, 10.)
        self.assertAlmostEqual(snapshot.wavelength, 1.064)


class SlowBackend(NumpyBackend):

    '''A backend that takes its time and says what it did.'''

    def __init__(self, delay=0.15, fail=0):
        super().__init__()
        self.delay, self.fail = delay, int(fail)
        self.threads, self.patterns, self.optics = [], [], []
        self.running = self.most_running = 0
        self.lock = threading.Lock()

    def hologram(self, pattern, optics):
        with self.lock:
            self.running += 1
            self.most_running = max(self.most_running, self.running)
        try:
            self.threads.append(threading.current_thread())
            self.patterns.append(pattern)
            self.optics.append(optics)
            time.sleep(self.delay)
            if self.fail > 0:
                self.fail -= 1
                raise RuntimeError('no hologram today')
            return super().hologram(pattern, optics)
        finally:
            with self.lock:
                self.running -= 1


def wait_for(spy, count, timeout=5000):
    '''Run the event loop until the spy has caught ``count`` signals.'''
    waited = 0
    while len(spy) < count and waited < timeout:
        QtTest.QTest.qWait(10)
        waited += 10
    return len(spy) >= count


class PipelineCase(unittest.TestCase):

    def make(self, backend=None, **kwargs):
        cgh = CGH(**{**dict(shape=SHAPE, xc=32., yc=24.), **kwargs},
                  backend=backend)
        self.addCleanup(cgh.stop)
        self.ready = QtTest.QSignalSpy(cgh.hologramReady)
        self.failed = QtTest.QSignalSpy(cgh.computeFailed)
        return cgh

    def pattern(self, *xs):
        return tuple(tweezer(x, 20 + x % 7).spec() for x in xs)


class TestPipeline(PipelineCase):

    def test_computes_the_hologram_of_a_pattern(self):
        cgh = self.make().start()
        pattern = self.pattern(10, 30, 50)
        cgh.compute(pattern)
        self.assertTrue(wait_for(self.ready, 1))
        h = np.array(self.ready[0][0])
        self.assertEqual(h.dtype, np.uint8)
        expected = ref.hologram(pattern, cgh.optics)
        self.assertLessEqual(levels(h, expected).max(), 1)

    def test_an_empty_pattern(self):
        cgh = self.make().start()
        cgh.compute(())
        self.assertTrue(wait_for(self.ready, 1))
        self.assertTrue((np.array(self.ready[0][0]) == 127).all())

    def test_computes_in_a_thread_of_its_own(self):
        backend = SlowBackend(delay=0.01)
        cgh = self.make(backend).start()
        cgh.compute(self.pattern(10))
        self.assertTrue(wait_for(self.ready, 1))
        self.assertIsNot(backend.threads[0], threading.main_thread())

    def test_returns_before_the_hologram_is_done(self):
        cgh = self.make(SlowBackend(delay=0.3)).start()
        t0 = time.perf_counter()
        cgh.compute(self.pattern(10))
        self.assertLess(time.perf_counter() - t0, 0.1)
        self.assertEqual(len(self.ready), 0)
        self.assertTrue(wait_for(self.ready, 1))

    def test_holograms_arrive_in_the_thread_that_asked(self):
        cgh = self.make().start()
        where = []
        cgh.hologramReady.connect(
            lambda *_: where.append(threading.current_thread()))
        cgh.compute(self.pattern(10))
        wait_for(self.ready, 1)
        self.assertIs(where[0], threading.main_thread())

    def test_requests_before_start_wait_for_it(self):
        cgh = self.make()
        cgh.compute(self.pattern(10))
        QtTest.QTest.qWait(100)
        self.assertEqual(len(self.ready), 0)
        cgh.start()
        self.assertTrue(wait_for(self.ready, 1))

    def test_can_be_restarted(self):
        cgh = self.make().start()
        cgh.compute(self.pattern(10))
        wait_for(self.ready, 1)
        cgh.stop()
        cgh.stop()
        cgh.start()
        cgh.compute(self.pattern(20))
        self.assertTrue(wait_for(self.ready, 2))

    def test_start_returns_itself_and_emits_recalculate_once(self):
        cgh = self.make()
        spy = QtTest.QSignalSpy(cgh.recalculate)
        self.assertIs(cgh.start(), cgh)
        self.assertEqual(len(spy), 1)

    def test_stop_does_not_raise_without_start(self):
        CGH().stop()


class TestLatestWins(PipelineCase):

    def test_one_hologram_at_a_time(self):
        backend = SlowBackend(delay=0.05)
        cgh = self.make(backend).start()
        for n in range(6):
            cgh.compute(self.pattern(10 + n))
            QtTest.QTest.qWait(5)
        wait_for(self.ready, 2)
        QtTest.QTest.qWait(200)
        self.assertEqual(backend.most_running, 1)

    def test_only_the_newest_of_the_waiting_requests_is_computed(self):
        backend = SlowBackend(delay=0.2)
        cgh = self.make(backend).start()
        patterns = [self.pattern(10 + n) for n in range(6)]
        for pattern in patterns:
            cgh.compute(pattern)
        self.assertTrue(wait_for(self.ready, 2))
        QtTest.QTest.qWait(300)
        self.assertEqual(len(self.ready), 2)
        self.assertEqual(backend.patterns, [patterns[0], patterns[-1]])

    def test_the_last_hologram_is_of_the_last_pattern(self):
        cgh = self.make(SlowBackend(delay=0.1)).start()
        patterns = [self.pattern(10 + 8 * n) for n in range(4)]
        for pattern in patterns:
            cgh.compute(pattern)
        wait_for(self.ready, 2)
        QtTest.QTest.qWait(300)
        last = np.array(self.ready[len(self.ready) - 1][0])
        self.assertLessEqual(
            levels(last, ref.hologram(patterns[-1], cgh.optics)).max(), 1)

    def test_a_request_while_idle_is_computed_at_once(self):
        backend = SlowBackend(delay=0.01)
        cgh = self.make(backend).start()
        for n in range(3):
            cgh.compute(self.pattern(10 + n))
            self.assertTrue(wait_for(self.ready, n + 1))
        self.assertEqual(len(backend.patterns), 3)


class TestSnapshots(PipelineCase):

    def test_the_calibration_is_captured_when_it_is_asked_for(self):
        backend = SlowBackend(delay=0.2)
        cgh = self.make(backend).start()
        pattern = self.pattern(10, 30)
        old = cgh.optics
        cgh.compute(pattern)
        cgh.xc = 20.
        cgh.thetac = 15.
        self.assertTrue(wait_for(self.ready, 1))
        self.assertIs(backend.optics[0], old)
        self.assertEqual(backend.optics[0].xc, 32.)

    def test_a_waiting_request_keeps_the_calibration_it_was_made_with(self):
        backend = SlowBackend(delay=0.2)
        cgh = self.make(backend).start()
        cgh.compute(self.pattern(10))
        QtTest.QTest.qWait(30)
        cgh.xc = 40.
        cgh.compute(self.pattern(20))
        cgh.xc = 50.
        wait_for(self.ready, 2)
        self.assertEqual(backend.optics[1].xc, 40.)

    def test_the_new_calibration_reaches_the_next_hologram(self):
        cgh = self.make(SlowBackend(delay=0.01)).start()
        pattern = self.pattern(10, 30)
        cgh.compute(pattern)
        wait_for(self.ready, 1)
        cgh.thetac = 20.
        cgh.compute(pattern)
        wait_for(self.ready, 2)
        a, b = (np.array(self.ready[n][0]) for n in (0, 1))
        self.assertGreater(levels(a, b).max(), 1)
        self.assertLessEqual(
            levels(b, ref.hologram(pattern, cgh.optics)).max(), 1)


class TestShutdown(unittest.TestCase):

    '''A pipeline must not leave its thread running when it is gone.

    A thread that is still running while Python shuts down made the
    process abort now and then, so a program that forgets ``stop()`` must
    still end cleanly.
    '''

    def started(self):
        return CGH(shape=SHAPE, xc=32., yc=24.).start()

    def test_the_finalizer_stops_the_thread(self):
        cgh = self.started()
        thread = cgh._thread
        self.assertTrue(thread.isRunning())
        cgh._finalizer()    # what runs when Python exits
        self.assertFalse(thread.isRunning())

    def test_a_dropped_pipeline_stops_its_thread(self):
        cgh = self.started()
        thread = cgh._thread
        del cgh
        gc.collect()
        self.assertFalse(thread.isRunning())

    def test_stopping_it_retires_the_finalizer(self):
        cgh = self.started()
        finalizer = cgh._finalizer
        cgh.stop()
        self.assertFalse(finalizer.alive)

    def test_a_restarted_pipeline_is_finalized_too(self):
        cgh = self.started()
        cgh.stop()
        cgh.start()
        thread = cgh._thread
        self.assertTrue(cgh._finalizer.alive)
        cgh._finalizer()
        self.assertFalse(thread.isRunning())


class TestFailure(PipelineCase):

    def test_the_reason_is_reported(self):
        cgh = self.make(SlowBackend(delay=0.01, fail=1)).start()
        cgh.compute(self.pattern(10))
        self.assertTrue(wait_for(self.failed, 1))
        self.assertEqual(self.failed[0][0], 'no hologram today')
        self.assertEqual(len(self.ready), 0)

    def test_the_traceback_of_a_failure_is_logged(self):
        cgh = self.make(SlowBackend(delay=0.01, fail=1)).start()
        with self.assertLogs('QHOT.lib.holograms.QHologramWorker',
                             level='ERROR') as logs:
            cgh.compute(self.pattern(10))
            wait_for(self.failed, 1)
        self.assertIsNotNone(logs.records[0].exc_info)
        self.assertIn('no hologram today', str(logs.records[0].exc_info[1]))

    def test_a_failure_does_not_block_the_next_request(self):
        cgh = self.make(SlowBackend(delay=0.01, fail=1)).start()
        cgh.compute(self.pattern(10))
        wait_for(self.failed, 1)
        cgh.compute(self.pattern(20))
        self.assertTrue(wait_for(self.ready, 1))

    def test_a_waiting_request_is_computed_after_a_failure(self):
        cgh = self.make(SlowBackend(delay=0.1, fail=1)).start()
        cgh.compute(self.pattern(10))
        cgh.compute(self.pattern(20))
        self.assertTrue(wait_for(self.ready, 1))
        self.assertEqual(len(self.failed), 1)

    def test_an_unknown_kind_is_reported_not_raised(self):
        from QHOT.lib.traps import TrapSpec
        cgh = self.make().start()
        cgh.compute((TrapSpec(kind='NoSuchTrap', r=(0., 0., 0.)),))
        self.assertTrue(wait_for(self.failed, 1))
        self.assertIn('NoSuchTrap', self.failed[0][0])


if __name__ == '__main__':
    unittest.main()
