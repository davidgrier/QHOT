'''Measure how responsive QHOT stays with a given camera.

Each trial starts QHOT in a fresh process with the chosen camera, adds
a trap every 100 ms, and records how often frames are rendered and
holograms are computed, and how long the GUI thread goes without
serving its event loop.  Optional tweaks test remedies for a camera that
starves the GUI thread:

``nopoll``
    Stop the GenICam tree's 200 ms camera poll.
``upd<ms>``
    Set harvesters' ``timeout_period_on_update_event_data_call``.
``swi<ms>``
    Set Python's thread-switch interval to <ms> milliseconds.

Configurations are named by joining tweaks with ``+``, for example
``nopoll+swi0.5``; ``baseline`` has none.  The trials of the
configurations are interleaved so that drift affects all of them alike.

Usage
-----
::

    python devel/camerabench.py flir
    python devel/camerabench.py opencv --trials 3 --duration 8
    python devel/camerabench.py flir --configs baseline swi0.5 upd100

Set ``QT_QPA_PLATFORM=offscreen`` to leave the display alone; the
default is the real display, which includes the cost of painting.
The tweaks for GenICam do nothing for other cameras.
'''
import argparse
import json
import os
import statistics
import subprocess
import sys
import time

__all__ = ['main']

DEFAULT_CONFIGS = ['baseline', 'nopoll', 'upd100', 'swi0.5',
                   'nopoll+upd100', 'nopoll+swi0.5', 'upd100+swi0.5']
#: Time before measuring starts, for the window and camera to settle [s].
WARMUP = 1.5
METRICS = [('rendered', 'frames/s'), ('holograms', 'holo/s'),
           ('median', 'loop med ms'), ('p99', 'loop p99 ms'),
           ('max', 'loop max ms'), ('cpu', 'cpu %')]


def parse_config(name: str) -> dict:
    '''Return the tweaks that the configuration *name* asks for.'''
    options = {}
    for tweak in (name.split('+') if name != 'baseline' else []):
        if tweak == 'nopoll':
            options['poll'] = False
        elif tweak.startswith('upd'):
            options['update_ms'] = int(tweak[3:])
        elif tweak.startswith('swi'):
            options['switch_ms'] = float(tweak[3:])
        else:
            raise ValueError(f'unknown tweak {tweak!r} in {name!r}')
    return options


def worker(camera: str, config: str, duration: float) -> dict:
    '''Run QHOT with *camera* and *config*; return the measurements.'''
    import numpy as np
    import psutil
    import pyqtgraph as pg
    from qtpy import QtCore
    from QHOT.lib import build_parser, choose_cgh, choose_slm
    from QHOT.qhot import QHOT
    from QVideo.cameras.chooser import BACKENDS, choose_camera

    options = parse_config(config)
    sys.argv = [sys.argv[0], BACKENDS[camera].flag, '-s']
    app = pg.mkQApp('QHOT')
    parser = build_parser()
    slm = choose_slm(parser)
    cgh = choose_cgh(parser, shape=slm.shape)
    window = QHOT(choose_camera(parser).start(), slm=slm, cgh=cgh)
    window.show()
    tree = window.cameraTree

    if 'switch_ms' in options:
        sys.setswitchinterval(options['switch_ms'] / 1000.)
    if 'poll' in options and hasattr(tree, '_timer'):
        tree._timer.stop()
    device = getattr(tree.camera, '_device', None)
    if ('update_ms' in options
            and hasattr(device, 'timeout_period_on_update_event_data_call')):
        device.timeout_period_on_update_event_data_call = (
            options['update_ms'])

    rendered, holograms, intervals = [], [], []
    last = [time.perf_counter()]
    cpu = [None]

    def tick() -> None:
        now = time.perf_counter()
        intervals.append(now - last[0])
        last[0] = now

    def addTrap() -> None:
        n = len(window.videoScreen.overlay._traps) + 1
        window.videoScreen.overlay.addTrap(
            QtCore.QPointF(200 + 5 * n, 200 + 3 * n))

    def start() -> None:
        rendered.clear()
        holograms.clear()
        intervals.clear()
        window.videoScreen.newFrame.connect(
            lambda *_: rendered.append(time.perf_counter()))
        cgh.hologramReady.connect(
            lambda *_: holograms.append(time.perf_counter()))
        cpu[0] = (time.perf_counter(), sum(psutil.Process().cpu_times()[:2]))
        trapTimer.start(100)

    def finish() -> None:
        elapsed = time.perf_counter() - cpu[0][0]
        used = sum(psutil.Process().cpu_times()[:2]) - cpu[0][1]
        loop = np.array(intervals[1:]) * 1e3
        result = {'rendered': len(rendered) / elapsed,
                  'holograms': len(holograms) / elapsed,
                  'median': float(np.median(loop)),
                  'p99': float(np.percentile(loop, 99)),
                  'max': float(loop.max()),
                  'cpu': 100. * used / elapsed}
        print('RESULT ' + json.dumps(result), flush=True)
        os._exit(0)  # a camera may hang the usual shutdown

    ticker = QtCore.QTimer()
    ticker.timeout.connect(tick)
    ticker.start(5)
    trapTimer = QtCore.QTimer()
    trapTimer.timeout.connect(addTrap)
    QtCore.QTimer.singleShot(int(WARMUP * 1000), start)
    QtCore.QTimer.singleShot(int((WARMUP + duration) * 1000), finish)
    pg.exec()
    return {}  # pragma: no cover


def trial(camera: str, config: str, duration: float) -> dict | None:
    '''Run one trial in a fresh process; return its result or ``None``.'''
    command = [sys.executable, os.path.abspath(__file__), camera,
               '--worker', config, '--duration', str(duration)]
    try:
        done = subprocess.run(command, capture_output=True, text=True,
                              timeout=duration + 60)
    except subprocess.TimeoutExpired:
        return None
    for line in done.stdout.splitlines():
        if line.startswith('RESULT '):
            return json.loads(line[7:])
    sys.stderr.write(done.stderr[-500:])
    return None


def report(results: dict[str, list[dict]]) -> None:
    '''Print the median over trials, with the range, for each metric.'''
    names = [label for _, label in METRICS]
    print(f'\n{"configuration":<16}' + ''.join(f'{n:>16}' for n in names)
          + f'{"n":>4}')
    for config, runs in results.items():
        cells = []
        for key, _ in METRICS:
            values = [r[key] for r in runs]
            if not values:
                cells.append(f'{"-":>16}')
                continue
            low, high = min(values), max(values)
            cells.append(f'{statistics.median(values):>8.1f}'
                         f'{f" ({low:.0f}-{high:.0f})":>8}')
        print(f'{config:<16}' + ''.join(cells) + f'{len(runs):>4}')


def main() -> None:
    '''Run the trials and print a table of the results.'''
    parser = argparse.ArgumentParser(
        description='Benchmark QHOT responsiveness.')
    parser.add_argument('camera', help='QVideo backend key, e.g. flir')
    parser.add_argument('--configs', nargs='+', default=DEFAULT_CONFIGS)
    parser.add_argument('--trials', type=int, default=5)
    parser.add_argument('--duration', type=float, default=6.,
                        help='seconds measured per trial (default: 6)')
    parser.add_argument('--output', help='write the raw results as JSON')
    parser.add_argument('--worker', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        worker(args.camera, args.worker, args.duration)
        return
    for config in args.configs:
        parse_config(config)  # fail early on a typo
    results = {config: [] for config in args.configs}
    total = args.trials * len(args.configs)
    count = 0
    for _ in range(args.trials):
        for config in args.configs:
            count += 1
            print(f'[{count}/{total}] {config} ...', end=' ', flush=True)
            result = trial(args.camera, config, args.duration)
            if result is None:
                print('failed')
                continue
            print(f'{result["rendered"]:.1f} frames/s, '
                  f'loop p99 {result["p99"]:.0f} ms')
            results[config].append(result)
    report(results)
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=1)


if __name__ == '__main__':
    main()
