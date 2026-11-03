'''Does the GenTL producer wait as long as it is asked to?

harvesters waits for a frame with ``update_event_data(timeout_ms)`` in a
Python loop.  If the producer returns at once when no frame is there, the
loop spins.  This times every call, by what it returned and how long it
took, with the camera streaming at several frame rates and timeouts.

    QT_QPA_PLATFORM=offscreen python devel/gentltimeout.py flir
'''
import collections
import os
import sys
import time


def main(camera: str) -> None:
    import pyqtgraph as pg
    from harvesters.core import EventManagerNewBuffer
    from QHOT.lib import build_parser
    from QVideo.cameras.chooser import BACKENDS, choose_camera

    calls = []
    original = EventManagerNewBuffer.update_event_data

    def timed(self, timeout_ms):
        t0 = time.perf_counter()
        try:
            original(self, timeout_ms)
            outcome = 'frame'
        except Exception as error:
            outcome = type(error).__name__
            raise
        finally:
            calls.append((timeout_ms, outcome,
                          (time.perf_counter() - t0) * 1e3))
    EventManagerNewBuffer.update_event_data = timed

    sys.argv = [sys.argv[0], BACKENDS[camera].flag, '-s']
    pg.mkQApp('probe')
    tree = choose_camera(build_parser()).start()
    time.sleep(1.5)
    device = tree.camera._device

    print(f'{"setting":<24}{"calls/s":>10}{"returned":>16}'
          f'{"median ms":>11}{"max ms":>9}   (asked for)')
    for fps in (None, 30, 15):
        if fps:
            tree.camera.fps = fps
            time.sleep(1.)
        for timeout in (1, 10, 100):
            device.timeout_period_on_update_event_data_call = timeout
            time.sleep(0.5)
            calls.clear()
            time.sleep(3.)
            snapshot = list(calls)
            by = collections.defaultdict(list)
            for asked, outcome, ms in snapshot:
                by[outcome].append(ms)
            label = f'{tree.camera.actualFps:.0f} fps, wait {timeout} ms'
            for outcome, times in sorted(by.items()):
                times.sort()
                print(f'{label:<24}{len(times) / 3.:>10.0f}{outcome:>16}'
                      f'{times[len(times) // 2]:>11.3f}{times[-1]:>9.1f}'
                      f'   ({timeout} ms)')
                label = ''
    sys.stdout.flush()
    os._exit(0)


if __name__ == '__main__':
    main(sys.argv[1])
