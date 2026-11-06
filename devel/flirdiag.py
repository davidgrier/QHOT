'''Find out which part of QHOT makes the GUI thread slow with a camera.

Each trial runs QHOT in a fresh process with the chosen camera, in one
mode, and records how long the GUI thread goes without serving its event
loop (the lag that a user feels), how often frames are rendered, and how
often holograms are computed.  The modes isolate the parts:

``traps``
    A trap is added every 100 ms: the load of ``camerabench.py``.
``idle``
    The video runs and nothing happens to the traps.
``hidden``
    Traps are added with the overlay hidden: no overlay is drawn.
``nodisplay``
    Traps are added, and the camera streams, but its frames are not
    shown: the camera and its thread load the process, and nothing is
    drawn for the video.
``nodisplay+idle``
    The camera streams and nothing is shown or changed.

Tweaks, joined with ``+``: ``swi<ms>`` sets Python's thread-switch
interval, and ``nopoll`` stops the camera tree's 200 ms poll.

Usage::

    QT_QPA_PLATFORM=offscreen python devel/flirdiag.py flir
    python devel/flirdiag.py opencv --trials 3 --duration 6
'''
import argparse
import json
import os
import statistics
import subprocess
import sys
import time

DEFAULT_MODES = ['traps', 'idle', 'hidden', 'nodisplay', 'nodisplay+idle']
WARMUP = 1.5
REMOTE_ONLY = {'flir': ['Width', 'Height', 'OffsetX', 'OffsetY',
                        'ExposureTime', 'Gain', 'AcquisitionFrameRate',
                        'AcquisitionResultingFrameRate',
                        'AcquisitionFrameRateEnable']}
METRICS = [('rendered', 'frames/s'), ('delivered', 'delivered/s'),
           ('holograms', 'holo/s'), ('median', 'loop med ms'),
           ('p99', 'loop p99 ms'), ('max', 'loop max ms'), ('cpu', 'cpu %')]


def worker(camera: str, mode: str, duration: float) -> dict:
    '''Run QHOT with *camera* in *mode*; return the measurements.'''
    import numpy as np
    import psutil
    import pyqtgraph as pg
    from qtpy import QtCore
    from QHOT.lib import QSLM, build_parser, choose_cgh, choose_slm
    from QHOT.qhot import QHOT
    from QVideo.cameras.chooser import BACKENDS, choose_camera

    flags = mode.split('+')
    for flag in flags:
        if flag.startswith('buf'):          # buffers announced to the producer
            from harvesters.core import Harvester
            create, count = Harvester.create, int(flag[3:])

            def make(self, *args, _create=create, _count=count, **kwargs):
                acquirer = _create(self, *args, **kwargs)
                acquirer.num_buffers = _count
                return acquirer
            Harvester.create = make
    full = camera.startswith('remotetree:')     # as 'qhot -fr' builds it
    remote = camera.startswith('remote:') or full
    flag = '' if remote or camera == 'gil' else BACKENDS[camera].flag
    sys.argv = [sys.argv[0], flag, '-s']
    sys.argv = [a for a in sys.argv if a]
    app = pg.mkQApp('QHOT')
    parser = build_parser()
    slm = choose_slm(parser)
    cgh = choose_cgh(parser, shape=slm.shape)
    if full:                    # a process of its own, the real tree
        from QVideo.cameras.chooser import make_tree
        from QVideo.lib.QRemoteCamera import QRemoteCamera
        key = camera.split(':', 1)[1]
        tree = make_tree(key, QRemoteCamera(key)).start()
    elif remote:                # a process of its own, a generic tree
        from QVideo.lib import QCameraTree
        from QVideo.lib.QRemoteCamera import QRemoteCamera
        key = camera.split(':', 1)[1]
        only = REMOTE_ONLY.get(key)
        tree = QCameraTree(QRemoteCamera(key, only=only)).start()
    elif camera == 'gil':       # holds the GIL in this process
        from QVideo.lib import QCameraTree
        from gilcamera import GilNoiseCamera
        tree = QCameraTree(GilNoiseCamera()).start()
    else:
        tree = choose_camera(parser).start()
    if (camera != 'noise' and not camera.endswith(':noise')
            and type(tree.camera).__name__ == 'QNoiseCamera'):
        sys.exit(f'{camera}: fell back to the noise camera')
    window = QHOT(tree, slm=slm, cgh=cgh)
    window.show()
    screen = window.screen

    events = {}
    sizes = []

    class Counter(QtCore.QObject):
        names = {QtCore.QEvent.Type.Resize: 'resize',
                 QtCore.QEvent.Type.LayoutRequest: 'layout',
                 QtCore.QEvent.Type.UpdateRequest: 'update',
                 QtCore.QEvent.Type.Paint: 'paint',
                 QtCore.QEvent.Type.Move: 'move'}

        def eventFilter(self, obj, event):
            name = self.names.get(event.type())
            if name:
                events[name] = events.get(name, 0) + 1
                if name == 'resize' and obj is window and len(sizes) < 12:
                    sizes.append((event.size().width(), event.size().height()))
            return False

    counter = Counter()
    app.installEventFilter(counter)

    calls = {}
    sizes_min = []

    def spy(obj, name, label):
        original = getattr(obj, name)

        def wrapper(*args, **kw):
            calls[label] = calls.get(label, 0) + 1
            if label == 'fit' and len(sizes_min) < 6:
                sizes_min.append((screen.minimumSize().width(),
                                  screen.minimumSize().height(),
                                  window.minimumSizeHint().height(),
                                  window.sizeHint().height(),
                                  window.height()))
            return original(*args, **kw)
        setattr(obj, name, wrapper)
    spy(window, 'resize', 'window.resize')
    spy(window, '_constrainAspectRatio', 'constrain')
    spy(window, '_resetCorrections', 'pauseReset')
    trace = []
    inner = window._constrainAspectRatio

    def traced():
        if len(trace) < 14:
            trace.append((window.width(), window.height(),
                          screen.width(), len(window._requested)))
        return inner()
    window._constrainAspectRatio = traced
    orig_resize = window.resizeEvent

    def resized(event):
        s = event.size()
        if (s.width(), s.height()) != window._expected:
            calls['foreignResize'] = calls.get('foreignResize', 0) + 1
            if 'why' not in calls:
                import traceback
                lay = window.centralWidget().layout() if hasattr(
                    window, 'centralWidget') and window.centralWidget() else None
                calls['why'] = 1
                print('WHY stack:', ' <- '.join(
                    f'{f.name}:{f.lineno}' for f in
                    traceback.extract_stack()[-8:]))
                print('WHY sizes: window min', window.minimumSize(),
                      'max', window.maximumSize(),
                      'minHint', window.minimumSizeHint(),
                      'hint', window.sizeHint(),
                      'screen min', screen.minimumSize(),
                      'screen max', screen.maximumSize(),
                      'screen size', screen.size(),
                      'screen hfw(1148)', screen.heightForWidth(1148),
                      'chrome', window._chromeHeight,
                      'cam hint', screen.sizeHint(),
                      'layout hfw', lay.hasHeightForWidth() if lay else None)
            if len(trace) < 14:
                trace.append(('foreign', s.width(), s.height(),
                              window._expected))
        return orig_resize(event)
    window.resizeEvent = resized
    spy(screen, '_fitToVideo', 'fit')
    spy(screen, 'updateShape', 'updateShape')

    rendered, holograms, delivered, intervals = [], [], [], []
    last = [time.perf_counter()]
    cpu = [None]

    for flag in flags:
        if flag.startswith('swi'):          # the GIL changes hands this often
            sys.setswitchinterval(float(flag[3:]) / 1000.)
        elif flag == 'nopoll' and hasattr(window.cameraTree, '_timer'):
            window.cameraTree._timer.stop()  # the 200 ms poll of the camera
        elif flag.startswith('upd'):        # harvesters: poll for an event
            device = getattr(window.cameraTree.camera, '_device', None)
            device.timeout_period_on_update_event_data_call = int(flag[3:])
    if 'hidden' in flags:
        screen.overlaysVisible = False
    if 'nodisplay' in flags:
        screen._relay.newFrame.disconnect(screen.setImage)

    def tick() -> None:
        now = time.perf_counter()
        intervals.append(now - last[0])
        last[0] = now

    def addTrap() -> None:
        n = len(screen.overlay._traps) + 1
        screen.overlay.addTrap(QtCore.QPointF(200 + 5 * n, 200 + 3 * n))

    def start() -> None:
        events.clear()
        rendered.clear()
        holograms.clear()
        delivered.clear()
        intervals.clear()
        screen.newFrame.connect(lambda *_: rendered.append(1))
        screen._relay.newFrame.connect(lambda *_: delivered.append(1))
        cgh.hologramReady.connect(lambda *_: holograms.append(1))
        cpu[0] = (time.perf_counter(), sum(psutil.Process().cpu_times()[:2]))
        if 'idle' not in flags:
            trapTimer.start(100)

    def finish() -> None:
        elapsed = time.perf_counter() - cpu[0][0]
        used = sum(psutil.Process().cpu_times()[:2]) - cpu[0][1]
        loop = np.array(intervals[1:]) * 1e3
        print('EVENTS', json.dumps(events), 'window resizes', sizes)
        print('CALLS', json.dumps(calls), 'fit(minW,minH,hintMinH,hintH,h)',
              sizes_min)
        print('TRACE', trace)
        print('RESULT ' + json.dumps({
            'rendered': len(rendered) / elapsed,
            'delivered': len(delivered) / elapsed,
            'holograms': len(holograms) / elapsed,
            'median': float(np.median(loop)),
            'p99': float(np.percentile(loop, 99)),
            'max': float(loop.max()),
            'cpu': 100. * used / elapsed}), flush=True)
        os._exit(0)             # a camera may hang the usual shutdown

    ticker = QtCore.QTimer()
    ticker.timeout.connect(tick)
    ticker.start(5)
    trapTimer = QtCore.QTimer()
    trapTimer.timeout.connect(addTrap)
    QtCore.QTimer.singleShot(int(WARMUP * 1000), start)
    QtCore.QTimer.singleShot(int((WARMUP + duration) * 1000), finish)
    pg.exec()
    return {}


def trial(camera: str, mode: str, duration: float) -> dict | None:
    command = [sys.executable, os.path.abspath(__file__), camera,
               '--worker', mode, '--duration', str(duration)]
    try:
        done = subprocess.run(command, capture_output=True, text=True,
                              timeout=duration + 60)
    except subprocess.TimeoutExpired:
        return None
    for line in done.stdout.splitlines():
        if line.startswith('RESULT '):
            return json.loads(line[7:])
    sys.stderr.write(done.stderr[-600:])
    return None


def report(results: dict) -> None:
    names = [label for _, label in METRICS]
    print(f'\n{"mode":<16}' + ''.join(f'{n:>14}' for n in names) + f'{"n":>4}')
    for mode, runs in results.items():
        cells = []
        for key, _ in METRICS:
            values = [r[key] for r in runs]
            cells.append(f'{statistics.median(values):>14.1f}' if values
                         else f'{"-":>14}')
        print(f'{mode:<16}' + ''.join(cells) + f'{len(runs):>4}')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('camera', help='QVideo backend key, e.g. flir')
    parser.add_argument('--modes', nargs='+', default=DEFAULT_MODES)
    parser.add_argument('--trials', type=int, default=3)
    parser.add_argument('--duration', type=float, default=6.)
    parser.add_argument('--worker', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        worker(args.camera, args.worker, args.duration)
        return
    results = {m: [] for m in args.modes}
    for i in range(args.trials):                 # interleaved, against drift
        for mode in args.modes:
            r = trial(args.camera, mode, args.duration)
            print(f'[{i + 1}/{args.trials}] {mode:<16}' +
                  (f'{r["rendered"]:5.1f} fr/s, loop med {r["median"]:5.1f}, '
                   f'p99 {r["p99"]:6.1f} ms' if r else 'FAILED'), flush=True)
            if r:
                results[mode].append(r)
    report(results)


if __name__ == '__main__':
    main()
