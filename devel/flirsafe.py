'''Run flirdiag modes on the Flir and put its settings back afterwards.

The Flir keeps its settings when the process ends, so the ones that a
measurement could change are read first and written back in a ``finally``.

Usage::

    python devel/flirsafe.py remote:flir --modes traps --trials 3
'''
import subprocess
import sys
from pathlib import Path

NAMES = ['AcquisitionFrameRateEnable', 'AcquisitionFrameRate',
         'ExposureTime', 'ExposureAuto', 'Gain', 'GainAuto', 'Width',
         'Height', 'OffsetX', 'OffsetY']


def read() -> dict:
    from QVideo.lib.QRemoteCamera import QRemoteCamera
    camera = QRemoteCamera('flir', only=NAMES)
    try:
        return {k: v for k, v in camera.settings.items() if k in NAMES}
    finally:
        camera.close()


def restore(saved: dict) -> None:
    from QVideo.lib.QRemoteCamera import QRemoteCamera
    camera = QRemoteCamera('flir', only=NAMES)
    try:
        # Enable first: the rate is read-only while it is off
        for key in ('AcquisitionFrameRateEnable', 'AcquisitionFrameRate'):
            camera.set(key, saved[key])
        for key, value in saved.items():
            if camera.settings.get(key) != value:
                try:
                    camera.set(key, value)
                except Exception as ex:
                    print(f'could not restore {key}: {ex}')
    finally:
        camera.close()


def main() -> None:
    saved = read()
    print('settings before:', saved, flush=True)
    try:
        here = Path(__file__).with_name('flirdiag.py')
        subprocess.run([sys.executable, str(here), *sys.argv[1:]])
    finally:
        restore(saved)
        print('settings after: ', read(), flush=True)


if __name__ == '__main__':
    main()
