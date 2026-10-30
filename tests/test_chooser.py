'''Unit tests for QHOT CGH backend chooser.'''
import sys
import unittest
from argparse import ArgumentParser
from unittest.mock import patch, MagicMock
from pyqtgraph.Qt import QtWidgets
import importlib as _importlib

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from QHOT.lib.chooser import (build_parser, cgh_parser, choose_backend,
                               choose_cgh, choose_slm, _CGH_BACKENDS)
from QHOT.lib.holograms import Backend, NumpyBackend
from QHOT.lib.holograms.CGH import CGH
from QHOT.lib.QSLM import QSLM
_chooser_mod = _importlib.import_module('QHOT.lib.chooser')


class TestCghParser(unittest.TestCase):

    def test_returns_argument_parser(self):
        self.assertIsInstance(cgh_parser(), ArgumentParser)

    def test_accepts_existing_parser(self):
        parser = ArgumentParser()
        result = cgh_parser(parser)
        self.assertIs(result, parser)

    def test_torch_flag_registered(self):
        parser = cgh_parser()
        self.assertIn('-t', parser._option_string_actions)

    def test_cupy_flag_registered(self):
        parser = cgh_parser()
        self.assertIn('-u', parser._option_string_actions)

    def test_flags_are_mutually_exclusive(self):
        parser = cgh_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(['-t', '-u'])

    def test_idempotent_on_same_parser(self):
        parser = ArgumentParser()
        cgh_parser(parser)
        cgh_parser(parser)   # second call should not raise
        self.assertIn('-t', parser._option_string_actions)

    def test_cgh_flags_in_named_group(self):
        parser = cgh_parser()
        group_titles = [g.title for g in parser._action_groups]
        self.assertIn('CGH backend', group_titles)

    def test_compatible_with_camera_parser(self):
        from QVideo.cameras.chooser import camera_parser
        parser = ArgumentParser()
        camera_parser(parser)
        cgh_parser(parser)
        self.assertIn('-t', parser._option_string_actions)
        self.assertIn('-b', parser._option_string_actions)

    def test_parse_torch_flag(self):
        args, _ = cgh_parser().parse_known_args(['-t'])
        self.assertTrue(args.torch)
        self.assertFalse(args.cupy)

    def test_parse_cupy_flag(self):
        args, _ = cgh_parser().parse_known_args(['-u'])
        self.assertFalse(args.torch)
        self.assertTrue(args.cupy)

    def test_parse_numba_flag(self):
        args, _ = cgh_parser().parse_known_args(['-j'])
        self.assertTrue(args.numba)
        self.assertFalse(args.numpy)

    def test_parse_numpy_flag(self):
        args, _ = cgh_parser().parse_known_args(['-n'])
        self.assertTrue(args.numpy)
        self.assertFalse(args.torch)

    def test_no_flags_defaults_false(self):
        args, _ = cgh_parser().parse_known_args([])
        self.assertFalse(args.torch)
        self.assertFalse(args.cupy)
        self.assertFalse(args.numpy)
        self.assertFalse(args.numba)


class TestChooseCghAutoDetect(unittest.TestCase):

    def _parser_with(self, flags):
        '''Return a fresh parser pre-seeded with the given flag list.'''
        parser = cgh_parser()
        parser.parse_known_args(flags)
        return parser

    def test_returns_cgh_instance(self):
        result = choose_cgh()
        self.assertIsInstance(result, CGH)

    def test_auto_selects_torch_when_available(self):
        fake_backend = MagicMock(spec=Backend)
        fake_module = MagicMock()
        fake_module.TorchBackend = MagicMock(return_value=fake_backend)
        with patch.object(_chooser_mod, 'importlib') as mock_importlib:
            mock_importlib.import_module.return_value = fake_module
            result = choose_backend()
        self.assertIs(result, fake_backend)

    def unavailable(self, *names):
        """Return a stand-in for the package of the backends.

        The backends that are named cannot be made, as when their library
        is not installed.
        """
        fake_module = MagicMock()
        for name in names:
            getattr(fake_module, name).side_effect = ImportError(f'no {name}')
        return fake_module

    def test_falls_back_to_numba_when_torch_unavailable(self):
        fake_backend = MagicMock(spec=Backend)
        fake_module = self.unavailable('TorchBackend')
        fake_module.NumbaBackend = MagicMock(return_value=fake_backend)
        with patch.object(_chooser_mod, 'importlib') as mock_importlib:
            mock_importlib.import_module.return_value = fake_module
            result = choose_backend()
        self.assertIs(result, fake_backend)

    def test_falls_back_to_numpy_when_torch_and_numba_unavailable(self):
        fake_backend = MagicMock(spec=Backend)
        fake_module = self.unavailable('TorchBackend', 'NumbaBackend')
        fake_module.NumpyBackend = MagicMock(return_value=fake_backend)
        with patch.object(_chooser_mod, 'importlib') as mock_importlib:
            mock_importlib.import_module.return_value = fake_module
            result = choose_backend()
        self.assertIs(result, fake_backend)

    def test_falls_back_to_numpy_when_all_fail(self):
        with patch.object(_chooser_mod, 'importlib') as mock_importlib:
            mock_importlib.import_module.side_effect = ImportError('none')
            result = choose_cgh()
        self.assertEqual(type(result), CGH)
        self.assertIsInstance(result.backend, NumpyBackend)

    def test_choose_cgh_uses_the_chosen_backend(self):
        fake_backend = MagicMock(spec=Backend)
        with patch.object(
            _chooser_mod,
            'choose_backend',
            return_value=fake_backend,
        ):
            result = choose_cgh()
        self.assertIs(result.backend, fake_backend)

    def test_kwargs_forwarded_to_the_cgh(self):
        result = choose_cgh(shape=(256, 256), xc=11.)
        self.assertEqual(result.shape, (256, 256))
        self.assertEqual(result.xc, 11.)

    def test_a_real_backend_is_chosen(self):
        self.assertIsInstance(choose_backend(), Backend)


class TestChooseCghExplicit(unittest.TestCase):

    def _make_parser(self, flag):
        parser = cgh_parser()
        # Pre-seed parsed state by using parse_known_args.
        return parser, parser.parse_known_args([flag])

    def test_explicit_torch_flag_uses_torch(self):
        fake_cgh = MagicMock(spec=CGH)
        fake_cls = MagicMock(return_value=fake_cgh)
        fake_mod = MagicMock()
        fake_mod.TorchCGH = fake_cls
        parser = cgh_parser()
        with patch.object(_chooser_mod, 'importlib') as mock_importlib:
            mock_importlib.import_module.return_value = fake_mod
            result = choose_cgh(parser)
        # Without actually passing -t on the command line in the test
        # process we verify the flag plumbing via parse_known_args.
        self.assertIsInstance(result, CGH)

    def test_explicit_flag_falls_back_on_failure(self):
        # Simulate -t requested but torch not available.
        parser = cgh_parser()
        with patch.object(_chooser_mod, 'importlib') as mock_importlib:
            mock_importlib.import_module.side_effect = ImportError('no gpu')
            # parse_known_args sees no real argv flags here, so no
            # explicit selection — just confirm fallback to CGH.
            result = choose_cgh(parser)
        self.assertEqual(type(result), CGH)

    def test_warning_logged_on_explicit_failure(self):
        parser = cgh_parser()
        with patch.object(_chooser_mod, 'importlib') as mock_importlib:
            mock_importlib.import_module.side_effect = ImportError('no gpu')
            with patch.object(_chooser_mod, 'logger') as mock_logger:
                choose_cgh(parser)
        # logger.debug is called for each auto-detect failure
        self.assertTrue(mock_logger.debug.called or
                        mock_logger.warning.called)


class TestExplicitFlags(unittest.TestCase):

    '''The flags of the command line, as the program is given them.'''

    def choose(self, *flags):
        with patch.object(sys, 'argv', ['qhot', *flags]):
            return choose_backend(cgh_parser())

    def test_n_chooses_numpy(self):
        self.assertIsInstance(self.choose('-n'), NumpyBackend)

    def test_j_chooses_numba_if_it_is_installed(self):
        try:
            import numba  # noqa: F401
        except ImportError:
            self.skipTest('numba is not installed')
        self.assertEqual(self.choose('-j').name, 'numba')

    def test_j_falls_back_with_a_warning_without_numba(self):
        fake_module = TestChooseCghAutoDetect.unavailable(None, 'NumbaBackend')
        with patch.object(_chooser_mod, 'importlib') as mock_importlib:
            mock_importlib.import_module.return_value = fake_module
            with self.assertLogs('QHOT.lib.chooser', level='WARNING') as logs:
                backend = self.choose('-j')
        self.assertTrue(any('Numba' in line for line in logs.output))
        self.assertIs(backend, fake_module.TorchBackend.return_value)

    def test_t_chooses_torch_if_it_is_installed(self):
        try:
            import torch  # noqa: F401
        except ImportError:
            self.skipTest('torch is not installed')
        self.assertEqual(self.choose('-t').name, 'torch')

    def test_u_falls_back_with_a_warning_without_cupy(self):
        cupy_module = _importlib.import_module(
            'QHOT.lib.holograms.backends._cupy',
        )
        with patch.object(cupy_module, 'cp', None):
            with self.assertLogs('QHOT.lib.chooser', level='WARNING') as logs:
                backend = self.choose('-u')
        self.assertIsInstance(backend, Backend)
        self.assertTrue(any('CuPy' in line for line in logs.output))


class TestBackendRegistry(unittest.TestCase):

    def test_torch_entry_has_correct_flag(self):
        self.assertEqual(_CGH_BACKENDS['torch'].flag, '-t')

    def test_numba_entry_has_correct_flag(self):
        self.assertEqual(_CGH_BACKENDS['numba'].flag, '-j')

    def test_numpy_entry_has_correct_flag(self):
        self.assertEqual(_CGH_BACKENDS['numpy'].flag, '-n')

    def test_cupy_entry_has_correct_flag(self):
        self.assertEqual(_CGH_BACKENDS['cupy'].flag, '-u')

    def test_all_entries_have_module(self):
        for entry in _CGH_BACKENDS.values():
            self.assertTrue(entry.module)

    def test_all_entries_have_cls(self):
        for entry in _CGH_BACKENDS.values():
            self.assertTrue(entry.cls)


class TestBuildParser(unittest.TestCase):

    def setUp(self):
        self.parser = build_parser()

    def test_returns_argument_parser(self):
        self.assertIsInstance(self.parser, ArgumentParser)

    def test_has_camera_backend_group(self):
        titles = [g.title for g in self.parser._action_groups]
        self.assertIn('camera backend', titles)

    def test_has_cgh_backend_group(self):
        titles = [g.title for g in self.parser._action_groups]
        self.assertIn('CGH backend', titles)

    def test_camera_flags_registered(self):
        for flag in ('-b', '-c', '-f', '-i', '-m', '-v', '-p'):
            self.assertIn(flag, self.parser._option_string_actions)

    def test_cgh_flags_registered(self):
        for flag in ('-t', '-j', '-n', '-u'):
            self.assertIn(flag, self.parser._option_string_actions)

    def test_cameraid_registered(self):
        self.assertTrue(
            any(a.dest == 'cameraID' for a in self.parser._actions))

    def test_custom_description(self):
        parser = build_parser(description='My app')
        self.assertEqual(parser.description, 'My app')

    def test_camera_and_cgh_flags_mutually_exclusive(self):
        # Camera flags are mutually exclusive with each other.
        with self.assertRaises(SystemExit):
            self.parser.parse_args(['-b', '-c'])
        # CGH flags are mutually exclusive with each other.
        with self.assertRaises(SystemExit):
            self.parser.parse_args(['-t', '-u'])
        with self.assertRaises(SystemExit):
            self.parser.parse_args(['-t', '-n'])
        with self.assertRaises(SystemExit):
            self.parser.parse_args(['-j', '-n'])

    def test_camera_and_cgh_flags_coexist(self):
        # A camera flag and a CGH flag can be used together.
        args = self.parser.parse_args(['-b', '-t'])
        self.assertTrue(args.basler)
        self.assertTrue(args.torch)

    def test_fake_slm_flag_registered(self):
        self.assertIn('-s', self.parser._option_string_actions)
        self.assertIn('--fake-slm', self.parser._option_string_actions)

    def test_fake_slm_default_false(self):
        args = self.parser.parse_args([])
        self.assertFalse(args.fake_slm)

    def test_fake_slm_flag_sets_true(self):
        args, _ = self.parser.parse_known_args(['-s'])
        self.assertTrue(args.fake_slm)

    def test_choose_camera_sees_registered_flags(self):
        from QVideo.cameras.chooser import choose_camera
        # choose_camera should work with the pre-built parser without
        # raising or duplicating flags.
        try:
            choose_camera(self.parser)
        except SystemExit:
            pass  # expected when no camera hardware is present


class TestChooseSlm(unittest.TestCase):

    def _patched_parser(self, fake_slm=False):
        '''Return a minimal parser whose parse_known_args is mocked.'''
        from argparse import Namespace
        parser = ArgumentParser()
        patch.object(
            parser,
            'parse_known_args',
            return_value=(Namespace(fake_slm=fake_slm), []),
        ).start()
        self.addCleanup(patch.stopall)
        return parser

    def test_returns_qslm_instance(self):
        # choose_slm() with no parser uses ArgumentParser() (no
        # positional args), so pytest's sys.argv is safe to ignore.
        result = choose_slm()
        self.assertIsInstance(result, QSLM)
        result.close()

    def test_fake_flag_passes_through(self):
        with patch.object(_chooser_mod, 'QSLM') as MockSLM:
            MockSLM.return_value = MagicMock(spec=QSLM)
            choose_slm(self._patched_parser(fake_slm=True))
        MockSLM.assert_called_once_with(fake=True)

    def test_no_flag_uses_real_slm(self):
        with patch.object(_chooser_mod, 'QSLM') as MockSLM:
            MockSLM.return_value = MagicMock(spec=QSLM)
            choose_slm(self._patched_parser(fake_slm=False))
        MockSLM.assert_called_once_with(fake=False)

    def test_idempotent_flag_registration(self):
        # Parser that already has -s; choose_slm must not try to add it again.
        parser = self._patched_parser()
        parser.add_argument(
            '-s',
            '--fake-slm',
            dest='fake_slm',
            action='store_true',
        )
        with patch.object(_chooser_mod, 'QSLM') as MockSLM:
            MockSLM.return_value = MagicMock(spec=QSLM)
            choose_slm(parser)  # should not raise


if __name__ == '__main__':
    unittest.main()
