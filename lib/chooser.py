'''Command-line CGH backend selection utility for QHOT applications.

Mirrors the ``choose_camera`` / ``camera_parser`` API from QVideo so
that a single ``ArgumentParser`` can carry both camera and CGH flags.
Use ``build_parser`` to get a parser with both option groups already
titled and separated.

Usage
-----
Standalone::

    from QHOT.lib import choose_cgh
    cgh = choose_cgh(shape=(512, 512))

Shared parser with titled groups::

    from QHOT.lib.chooser import build_parser, choose_cgh
    from QVideo.lib import choose_camera

    parser = build_parser()
    cgh = choose_cgh(parser, shape=slm.shape)
    cameraTree = choose_camera(parser).start()
'''
import importlib
import logging
from argparse import ArgumentParser
from typing import NamedTuple

import qtpy  # Required for Qt detection in QSLM
from QHOT.lib.holograms import CGH
from QHOT.lib.QSLM import QSLM

__all__ = 'build_parser cgh_parser choose_cgh choose_slm'.split()

logger = logging.getLogger(__name__)


class _CGHEntry(NamedTuple):
    flag: str
    module: str
    cls: str
    label: str
    help: str


_CGH_BACKENDS: dict[str, _CGHEntry] = {
    'torch': _CGHEntry('-t', 'QHOT.lib.holograms.TorchCGH', 'TorchCGH',
                       'PyTorch',
                       'PyTorch backend '
                       '(auto-selects MPS, CUDA/ROCm, or CPU)'),
    'cupy':  _CGHEntry('-u', 'QHOT.lib.holograms.cupyCGH', 'cupyCGH',
                       'CuPy',
                       'CuPy CUDA backend (NVIDIA only)'),
}

_AUTO_DETECT_ORDER = ('torch', 'cupy')


def cgh_parser(parser: ArgumentParser | None = None) -> ArgumentParser:
    '''Return a parser extended with a titled CGH backend option group.

    Adds ``-t`` (TorchCGH) and ``-u`` (cupyCGH) as a mutually
    exclusive group under a ``CGH backend`` section heading.  If
    either flag is already registered on ``parser``, the group is
    left unchanged.

    Parameters
    ----------
    parser : ArgumentParser or None
        An existing parser to extend, or ``None`` to create a new one.

    Returns
    -------
    ArgumentParser
        Parser with a ``CGH backend`` section containing::

            -t  PyTorch (MPS / CUDA / ROCm / CPU auto-select)
            -u  CuPy CUDA (NVIDIA only)

        When neither flag is given, ``choose_cgh`` probes the same
        order automatically.
    '''
    parser = parser or ArgumentParser()
    first_flag = next(iter(_CGH_BACKENDS.values())).flag
    if first_flag not in parser._option_string_actions:
        group = parser.add_argument_group('CGH backend')
        mutex = group.add_mutually_exclusive_group()
        for dest, entry in _CGH_BACKENDS.items():
            mutex.add_argument(entry.flag, dest=dest, help=entry.help,
                               action='store_true')
    return parser


def build_parser(description: str = 'QHOT holographic optical trapping'
                 ) -> ArgumentParser:
    '''Return a parser with titled camera and CGH backend option groups.

    Pre-registers all QVideo camera flags under a ``camera backend``
    section heading so that ``choose_camera`` sees them already present
    and skips its own (un-titled) group.  Then adds the CGH backend
    section via ``cgh_parser``.

    Parameters
    ----------
    description : str
        Application description shown in ``--help``.

    Returns
    -------
    ArgumentParser
        Parser with sections::

            camera backend:
                -b  Basler  -c  OpenCV  -f  Flir ...
            CGH backend:
                -t  PyTorch  -u  CuPy
    '''
    from QVideo.lib.chooser import _CAMERAS
    parser = ArgumentParser(description=description)
    cam_group = parser.add_argument_group('camera backend')
    cam_mutex = cam_group.add_mutually_exclusive_group()
    for dest, entry in _CAMERAS.items():
        cam_mutex.add_argument(entry.flag, dest=dest, help=entry.help,
                               action='store_true')
    parser.add_argument('cameraID', nargs='?', type=int, default=0,
                        help='camera ID number (default: %(default)d)')
    parser.add_argument('-s', '--fake-slm', dest='fake_slm',
                        action='store_true',
                        help='open SLM on the primary screen even when '
                             'a secondary screen is present')
    return cgh_parser(parser)


def choose_cgh(parser: ArgumentParser | None = None,
               **kwargs) -> CGH:
    '''Choose and return a CGH backend based on command-line arguments.

    When a backend flag is supplied the requested class is loaded and
    instantiated.  If loading fails (missing dependency, no GPU) a
    warning is logged and the function falls through to auto-detection.

    When no flag is given the function probes backends in priority
    order (TorchCGH → cupyCGH → CGH) and returns the first that
    succeeds.

    Parameters
    ----------
    parser : ArgumentParser or None
        Parser already extended with camera (and other) flags.  CGH
        flags are added if not already present.  Pass the same
        parser that was given to ``choose_camera`` so that all flags
        are parsed in one pass.
    **kwargs
        Forwarded verbatim to the CGH constructor (e.g.
        ``shape=(512, 512)``).

    Returns
    -------
    CGH
        An initialised CGH instance on the best available backend.
    '''
    args, _ = cgh_parser(parser).parse_known_args()

    # Explicit selection: try the requested backend, warn on failure.
    for dest, entry in _CGH_BACKENDS.items():
        if getattr(args, dest, False):
            try:
                module = importlib.import_module(entry.module)
                cls = getattr(module, entry.cls)
                instance = cls(**kwargs)
                logger.info(f'Using {entry.label} CGH backend')
                return instance
            except Exception as ex:
                logger.warning(
                    f'Could not initialise {entry.label} backend: {ex}')
            break

    # Auto-detection: probe in priority order.
    for dest in _AUTO_DETECT_ORDER:
        entry = _CGH_BACKENDS[dest]
        try:
            module = importlib.import_module(entry.module)
            cls = getattr(module, entry.cls)
            instance = cls(**kwargs)
            logger.info(f'Auto-selected {entry.label} CGH backend')
            return instance
        except Exception as ex:
            logger.debug(f'{entry.label} not available: {ex}')

    logger.info('Using CPU CGH backend')
    return CGH(**kwargs)


def choose_slm(parser: ArgumentParser | None = None) -> QSLM:
    '''Return an SLM instance, optionally forced to the primary screen.

    Reads the ``-s``/``--fake-slm`` flag from the shared argument
    parser.  Pass the same ``parser`` used for camera and CGH selection
    so that all flags are parsed in one pass.

    Parameters
    ----------
    parser : ArgumentParser or None
        Parser already extended with other flags, or ``None`` to use
        the ``build_parser`` default.  The ``-s``/``--fake-slm`` flag
        is added if not already present.

    Returns
    -------
    QSLM
        An SLM instance on the secondary screen (default) or on the
        primary screen if ``--fake-slm`` was supplied.
    '''
    parser = parser or ArgumentParser()
    if '-s' not in parser._option_string_actions:
        parser.add_argument('-s', '--fake-slm', dest='fake_slm',
                            action='store_true',
                            help='open SLM on the primary screen even '
                                 'when a secondary screen is present')
    args, _ = parser.parse_known_args()
    fake = getattr(args, 'fake_slm', False)
    if fake:
        logger.info('Using fake SLM (primary screen)')
    return QSLM(fake=fake)
