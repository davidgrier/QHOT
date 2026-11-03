'''Is the Genicam camera doing work in the main thread?

QHOT is run with a camera.  A sampler thread looks at the Python stack of
every thread every millisecond, and the poll of the GenICam tree (a timer
of the main thread) is timed.  The report says what the main thread was
doing, in which part of the program, and what the capture thread was
doing.

Usage::

    QT_QPA_PLATFORM=offscreen python devel/flirthreads.py flir
    QT_QPA_PLATFORM=offscreen python devel/flirthreads.py flir --traps
'''
import argparse
import collections
import json
import os
import subprocess
import sys
import threading
import time

WARMUP = 1.5


def domain(stack) -> str:
    '''Name the part of the program that the innermost frames belong to.'''
    for filename, function in stack:            # innermost first
        if '/Genicam/' in filename or '/harvesters/' in filename \
                or '/genicam/' in filename:
            return 'GENICAM/harvesters'
        if '/pyqtgraph/' in filename:
            return 'pyqtgraph'
        if '/QHOT/' in filename or filename.endswith('qhot.py'):
            return 'QHOT'
        if '/QVideo/' in filename:
            return 'QVideo (not Genicam)'
    return 'other'


def worker(camera: str, traps: bool, duration: float) -> dict:
    import pyqtgraph as pg
    from qtpy import QtCore
    from QHOT.lib import build_parser, choose_cgh, choose_slm
    from QHOT.qhot import QHOT
    from QVideo.cameras.chooser import BACKENDS, choose_camera

    polls = []
    try:
        from QVideo.cameras.Genicam._tree import QGenicamTree
        original = QGenicamTree._pollCamera

        def timed(self):
            t0 = time.perf_counter()
            original(self)
            polls.append((time.perf_counter() - t0) * 1e3)
        QGenicamTree._pollCamera = timed
    except ImportError:
        pass

    sys.argv = [sys.argv[0], BACKENDS[camera].flag, '-s']
    app = pg.mkQApp('QHOT')
    parser = build_parser()
    slm = choose_slm(parser)
    cgh = choose_cgh(parser, shape=slm.shape)
    window = QHOT(choose_camera(parser).start(), slm=slm, cgh=cgh)
    window.show()

    main_ident = threading.main_thread().ident
    main_samples = collections.Counter()
    main_busy = collections.Counter()
    capture = collections.Counter()
    sampling = [False]

    def stack_of(frame):
        out = []
        while frame is not None:
            out.append((frame.f_code.co_filename, frame.f_code.co_name))
            frame = frame.f_back
        return out

    def sampler():
        me = threading.get_ident()
        while True:
            time.sleep(0.001)
            if not sampling[0]:
                continue
            for ident, frame in sys._current_frames().items():
                if ident == me:
                    continue
                stack = stack_of(frame)
                names = [f for _, f in stack]
                if ident == main_ident:
                    main_samples['all'] += 1
                    if len(stack) > 3:          # more than the event loop
                        main_busy[domain(stack)] += 1
                        if '_pollCamera' in names:
                            main_busy['  (inside the camera poll)'] += 1
                elif 'run' in names and any('QVideoSource' in fn
                                            for fn, _ in stack):
                    capture[f'{stack[0][1]} <- {stack[1][1]}'
                            if len(stack) > 1 else stack[0][1]] += 1

    threading.Thread(target=sampler, daemon=True).start()

    def addTrap():
        n = len(window.screen.overlay._traps) + 1
        window.screen.overlay.addTrap(QtCore.QPointF(200 + 5 * n, 200 + 3 * n))

    trapTimer = QtCore.QTimer()
    trapTimer.timeout.connect(addTrap)

    def start():
        polls.clear()
        sampling[0] = True
        if traps:
            trapTimer.start(100)

    def finish():
        sampling[0] = False
        total = max(main_samples['all'], 1)
        result = {
            'main_samples': total,
            'main_busy_percent': {k: 100. * v / total
                                  for k, v in main_busy.items()},
            'polls': {'count': len(polls),
                      'median_ms': sorted(polls)[len(polls) // 2]
                      if polls else 0.,
                      'max_ms': max(polls) if polls else 0.,
                      'total_ms_per_s': sum(polls) / duration},
            'capture_top': capture.most_common(6),
        }
        print('RESULT ' + json.dumps(result), flush=True)
        os._exit(0)

    QtCore.QTimer.singleShot(int(WARMUP * 1000), start)
    QtCore.QTimer.singleShot(int((WARMUP + duration) * 1000), finish)
    pg.exec()
    return {}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('camera')
    parser.add_argument('--traps', action='store_true')
    parser.add_argument('--duration', type=float, default=6.)
    parser.add_argument('--worker', action='store_true',
                        help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        worker(args.camera, args.traps, args.duration)
        return
    command = [sys.executable, os.path.abspath(__file__), args.camera,
               '--worker', '--duration', str(args.duration)]
    if args.traps:
        command.append('--traps')
    done = subprocess.run(command, capture_output=True, text=True,
                          timeout=args.duration + 60)
    for line in done.stdout.splitlines():
        if line.startswith('RESULT '):
            r = json.loads(line[7:])
            print(f"main thread, {r['main_samples']} samples "
                  f"({'with traps' if args.traps else 'video only'}):")
            for k, v in sorted(r['main_busy_percent'].items(),
                               key=lambda kv: -kv[1]):
                print(f'   {v:5.1f} % of the time in {k}')
            p = r['polls']
            print(f"camera poll: {p['count']} calls, median "
                  f"{p['median_ms']:.1f} ms, longest {p['max_ms']:.1f} ms, "
                  f"{p['total_ms_per_s']:.0f} ms of every second")
            print('capture thread, innermost frames:')
            for k, v in r['capture_top']:
                print(f'   {v:6d}  {k}')
            return
    sys.stderr.write(done.stderr[-800:])


if __name__ == '__main__':
    main()
