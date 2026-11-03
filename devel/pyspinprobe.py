'''Does PySpin release the interpreter lock while it waits for a frame?

The same test as devel/gilprobe.py, with FLIR's own Python wrapper:
a counter runs in the main thread while another thread waits in
``GetNextImage``.  No camera setting is changed.

    /opt/homebrew/bin/python3.10 devel/pyspinprobe.py
'''
import statistics
import threading
import time

import PySpin


def count(seconds):
    gaps, last, end = [], time.perf_counter(), time.perf_counter() + seconds
    while last < end:
        now = time.perf_counter()
        gaps.append(now - last)
        last = now
    gaps.sort()
    return len(gaps) / seconds, gaps[len(gaps) // 2] * 1e3, gaps[-1] * 1e3


class Pinger:
    def __init__(self):
        self.request, self.response = threading.Event(), threading.Event()
        self.woke = 0.
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while True:
            self.request.wait()
            self.woke = time.perf_counter()
            self.request.clear()
            self.response.set()

    def ping(self):
        self.response.clear()
        sent = time.perf_counter()
        self.request.set()
        self.response.wait()
        return (self.woke - sent) * 1e3


def ping_median(pinger, n=40):
    times = []
    for _ in range(n):
        times.append(pinger.ping())
        time.sleep(0.02)
    return statistics.median(times), max(times)


system = PySpin.System.GetInstance()
cameras = system.GetCameras()
print('PySpin', PySpin.System.GetInstance().GetLibraryVersion().major, '| cameras:', cameras.GetSize())
if cameras.GetSize() == 0:
    cameras.Clear()
    system.ReleaseInstance()
    raise SystemExit('no camera')
cam = cameras.GetByIndex(0)
cam.Init()
name = cam.TLDevice.DeviceModelName.GetValue()
rate = cam.AcquisitionResultingFrameRate.GetValue()
print(f'camera: {name}, resulting frame rate {rate:.1f} fps')

pinger = Pinger()
base = count(2.)
idle = ping_median(pinger)

stop = threading.Event()
frames = [0]
copies = []


def acquire():
    while not stop.is_set():
        try:
            image = cam.GetNextImage(1000)
            if not image.IsIncomplete():
                t0 = time.perf_counter()
                data = image.GetNDArray()
                copies.append(time.perf_counter() - t0)
                frames[0] += 1
            image.Release()
        except PySpin.SpinnakerException:
            continue


cam.BeginAcquisition()
thread = threading.Thread(target=acquire, daemon=True)
thread.start()
time.sleep(1.5)
frames[0] = 0
copies.clear()
streaming = count(4.)
live = ping_median(pinger)
delivered = frames[0] / 4.
stop.set()
thread.join()
cam.EndAcquisition()
cam.DeInit()
del cam
cameras.Clear()
system.ReleaseInstance()

print(f'\n{"":34}{"count/s":>14}{"median gap":>12}{"longest gap":>13}')
print(f'{"no acquisition":34}{base[0]:>14,.0f}{base[1]:>9.3f} ms{base[2]:>10.1f} ms')
print(f'{"GetNextImage in another thread":34}{streaming[0]:>14,.0f}{streaming[1]:>9.3f} ms{streaming[2]:>10.1f} ms'
      f'   ({100 * streaming[0] / base[0]:.0f}% of idle; {delivered:.0f} frames/s)')
print(f'\nwake-up latency of an unrelated thread (median / max):')
print(f'   idle   {idle[0]:.3f} / {idle[1]:.3f} ms')
print(f'   live   {live[0]:.3f} / {live[1]:.3f} ms   ({live[0] / idle[0]:.1f}x)')
print(f'per-frame GetNDArray: {statistics.mean(copies) * 1e3:.3f} ms')
