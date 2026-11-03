'''Is the slowdown the interpreter lock, or the CPU?

Two counters run in the main thread, one at a time, with and without the
Flir streaming.  The Python counter needs the interpreter lock for every
step.  The NumPy counter does matrix products that release it, so only a
shortage of CPU slows it.

    QT_QPA_PLATFORM=offscreen python devel/gilvscpu.py flir
'''
import os
import sys
import time

import numpy as np


def python_counter(seconds: float) -> float:
    n, end = 0, time.perf_counter() + seconds
    while time.perf_counter() < end:
        n += 1
    return n / seconds


def numpy_counter(seconds: float) -> float:
    a = np.random.default_rng(0).random((400, 400))
    n, end = 0, time.perf_counter() + seconds
    while time.perf_counter() < end:
        a @ a
        n += 1
    return n / seconds


def main(camera: str) -> None:
    import pyqtgraph as pg
    from QHOT.lib import build_parser
    from QVideo.cameras.chooser import BACKENDS, choose_camera

    sys.argv = [sys.argv[0], BACKENDS[camera].flag, '-s']
    pg.mkQApp('probe')
    rows = [('no camera', python_counter(2.), numpy_counter(2.))]
    tree = choose_camera(build_parser()).start()
    time.sleep(1.5)
    device = getattr(tree.camera, '_device', None)
    for label, ms in (('streaming, 1 ms wait (default)', 1),
                      ('streaming, 100 ms wait', 100)):
        if device is not None:
            device.timeout_period_on_update_event_data_call = ms
        time.sleep(0.5)
        rows.append((label, python_counter(3.), numpy_counter(3.)))
    base = rows[0]
    print(f'\n{"":34}{"Python counter":>18}{"NumPy counter":>18}')
    for label, p, m in rows:
        print(f'{label:34}{100 * p / base[1]:>17.0f}%{100 * m / base[2]:>17.0f}%')
    sys.stdout.flush()
    os._exit(0)


if __name__ == '__main__':
    main(sys.argv[1])
