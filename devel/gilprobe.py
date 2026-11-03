'''Does waiting for a Flir frame release the interpreter lock?

A pure-Python counter runs in the main thread.  How fast it counts, and
the longest it is kept waiting, say whether the capture thread lets other
Python threads run while it waits for a frame.  There is no GUI work and
no trap: only the counter and the camera.

    QT_QPA_PLATFORM=offscreen python devel/gilprobe.py flir
'''
import os
import sys
import time

FPS = (100, 60, 30, 15)


def measure(seconds: float) -> tuple[float, float, float]:
    '''Count for *seconds*; return iterations/s, median and max gap [ms].'''
    gaps = []
    n = 0
    start = last = time.perf_counter()
    while True:
        now = time.perf_counter()
        gaps.append(now - last)
        last = now
        n += 1
        if now - start > seconds:
            break
    gaps.sort()
    return n / (now - start), gaps[len(gaps) // 2] * 1e3, gaps[-1] * 1e3


def main(camera: str) -> None:
    import pyqtgraph as pg
    from QHOT.lib import build_parser
    from QVideo.cameras.chooser import BACKENDS, choose_camera

    sys.argv = [sys.argv[0], BACKENDS[camera].flag, '-s']
    pg.mkQApp('probe')
    rows = []
    base = measure(2.)
    rows.append(('no camera', *base))
    tree = choose_camera(build_parser()).start()
    time.sleep(1.5)
    rows.append((f'streaming at {tree.camera.actualFps:.0f} fps',
                 *measure(3.)))
    for fps in FPS:
        tree.camera.fps = fps
        time.sleep(1.)
        rows.append((f'streaming at {tree.camera.actualFps:.0f} fps',
                     *measure(3.)))
    print(f'\n{"":34}{"count/s":>14}{"median gap":>13}{"longest gap":>13}')
    for label, rate, median, longest in rows:
        print(f'{label:34}{rate:>14,.0f}{median:>10.3f} ms{longest:>10.1f} ms'
              f'   ({100 * rate / base[0]:.0f}% of no camera)')
    sys.stdout.flush()
    os._exit(0)             # a camera may hang the usual shutdown


if __name__ == '__main__':
    main(sys.argv[1])
