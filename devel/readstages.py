'''Where does the Genicam capture thread spend its time, frame by frame?

``QGenicamCamera.read`` is run with a stopwatch around its stages: waiting
for the frame, making the image from the buffer, and giving the buffer
back.  The wait is the camera's; the rest is work that the capture thread
does with the interpreter, once for every frame.

    QT_QPA_PLATFORM=offscreen python devel/readstages.py flir
'''
import os
import sys
import time


def main(camera: str) -> None:
    import numpy as np
    import pyqtgraph as pg
    from QHOT.lib import build_parser
    from QVideo.cameras.chooser import BACKENDS, choose_camera
    from QVideo.cameras.Genicam._camera import QGenicamCamera

    stages = {'wait': [], 'image': [], 'copy': [], 'give back': []}

    def read(self):
        t0 = time.perf_counter()
        frame = None
        with self._device.fetch(timeout=1) as buffer:
            t1 = time.perf_counter()                   # the frame is here
            components = buffer.payload.components
            image = components[0]
            height, width = image.height, image.width
            channels = int(image.num_components_per_pixel)
            data = image.data
            t2 = time.perf_counter()
            frame = data.copy()
            t3 = time.perf_counter()
            self.hardwareTimestamp = buffer.timestamp_ns * 1e-9
        t4 = time.perf_counter()
        frame = frame.reshape(height, width, channels).squeeze()
        stages['wait'].append(t1 - t0)
        stages['image'].append(t2 - t1)
        stages['copy'].append(t3 - t2)
        stages['give back'].append(t4 - t3)
        return True, frame

    QGenicamCamera.read = read
    sys.argv = [sys.argv[0], BACKENDS[camera].flag, '-s']
    pg.mkQApp('probe')
    tree = choose_camera(build_parser()).start()
    time.sleep(1.5)
    tree.camera._device.timeout_period_on_update_event_data_call = 100
    time.sleep(0.5)
    for stage in stages.values():
        stage.clear()
    time.sleep(4.)
    import threading
    print('Python threads while streaming:')
    frames = sys._current_frames()
    for ident, frame in frames.items():
        names = []
        while frame is not None:
            names.append(frame.f_code.co_name)
            frame = frame.f_back
        owner = next((t.name for t in threading.enumerate()
                      if t.ident == ident), 'qt/other')
        print(f'   {owner:<24} innermost: {" <- ".join(names[:3])}')
    n = len(stages['wait'])
    shape = tree.camera.shape if hasattr(tree.camera, 'shape') else '?'
    print(f'{n / 4.:.0f} frames/s, image {shape}')
    print(f'{"stage":<12}{"mean ms":>10}{"max ms":>9}{"ms/second":>11}')
    for name, times in stages.items():
        a = np.array(times) * 1e3
        print(f'{name:<12}{a.mean():>10.3f}{a.max():>9.1f}{a.sum() / 4.:>11.0f}')
    sys.stdout.flush()
    os._exit(0)


if __name__ == '__main__':
    main(sys.argv[1])
