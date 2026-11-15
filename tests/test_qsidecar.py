'''Unit tests for the file that describes a video.'''
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
from qtpy import QtTest, QtWidgets

from QHOT.lib import QSaveFile
from QHOT.lib.QSidecar import FORMAT, QSidecar, plain
from QHOT.lib.holograms import CGH
from QHOT.lib.tasks.recording import startRecording
from QHOT.lib.traps.QTrapOverlay import QTrapOverlay
from QHOT.traps import QTrapArray, QTweezer

try:
    from recordingfixtures import RealDVRCase
except ImportError:  # run from the root of the repository
    from tests.recordingfixtures import RealDVRCase

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class FakeCamera:

    '''What the description asks of a camera.'''

    name = 'Fake camera'
    modelName = 'F-1'
    properties = {'width': None, 'exposure': None, 'gain': None}


class FakeTree:

    '''The tree of a camera: the camera, what the tree shows, and a flush.'''

    camera = FakeCamera()
    shown = {'width': 640, 'exposure': 0.01, 'gain': 3}

    def __init__(self):
        self.flushed = 0

    def flush(self):
        self.flushed += 1
        return True

    def get(self, key):
        return self.shown.get(key)


class SidecarCase(RealDVRCase):

    def setUp(self):
        super().setUp()
        home = tempfile.TemporaryDirectory()
        self.addCleanup(home.cleanup)
        with patch.object(Path, 'home', return_value=Path(home.name)):
            self.files = QSaveFile(QtWidgets.QMainWindow())
        self.tree = FakeTree()
        self.cgh = CGH(shape=(48, 64), wavelength=0.633)
        self.overlay = QTrapOverlay()
        self.overlay.addTrap(QTweezer(r=(10., 20., 5.), phase=0.))
        self.sidecar = QSidecar(self.dvr,
                                self.tree,
                                self.cgh,
                                self.overlay,
                                self.files)
        self.video = self.path('run.mkv')

    def record(self, frames=3):
        startRecording(self.dvr, self.video, 10_000)
        self.source.emit(frames)
        self.dvr.recorder.stop()

    def read(self):
        with open(self.sidecar.pathOf(self.video), 'rb') as f:
            return tomllib.load(f)


class TestWhereItIs(SidecarCase):

    def test_it_has_the_name_of_the_video(self):
        self.assertEqual(self.sidecar.pathOf('/data/video_1.mkv'),
                         '/data/video_1.toml')

    def test_it_is_written_beside_the_video(self):
        self.record()
        self.assertTrue(Path(self.path('run.toml')).exists())


class TestWhatItSays(SidecarCase):

    def setUp(self):
        super().setUp()
        self.record(3)
        self.data = self.read()

    def test_the_layout_has_a_version(self):
        self.assertEqual(self.data['format'], FORMAT)

    def test_the_video_is_named(self):
        self.assertEqual(self.data['recording']['video'], 'run.mkv')

    def test_the_time_has_an_offset_from_utc(self):
        start = self.data['recording']['start']
        self.assertIsNotNone(start.utcoffset())

    def test_the_recording_ends_after_it_starts(self):
        rec = self.data['recording']
        self.assertGreaterEqual(rec['stop'], rec['start'])
        self.assertGreaterEqual(rec['seconds'], 0.)

    def test_the_frames_that_were_written(self):
        self.assertEqual(self.data['recording']['frames'], 3)

    def test_a_recording_that_ended_as_asked_has_no_reason(self):
        self.assertNotIn('stopped', self.data['recording'])

    def test_the_versions(self):
        from QHOT import __version__
        self.assertEqual(self.data['software']['QHOT'], __version__)
        self.assertIn('QVideo', self.data['software'])

    def test_the_camera_is_described(self):
        camera = self.data['camera']
        self.assertEqual(camera['class'], 'FakeCamera')
        self.assertEqual(camera['name'], 'Fake camera')
        self.assertEqual(camera['model'], 'F-1')

    def test_the_settings_are_what_the_tree_shows(self):
        self.assertEqual(self.data['camera']['settings'],
                         {'width': 640, 'exposure': 0.01, 'gain': 3})

    def test_the_calibration(self):
        cgh = self.data['cgh']
        self.assertEqual(cgh['wavelength'], 0.633)
        self.assertEqual(cgh['shape'], [48, 64])
        self.assertEqual(cgh['backend'], 'NumpyBackend')

    def test_the_traps_at_the_start(self):
        (trap,) = self.data['traps']
        self.assertEqual(trap['type'], 'QTweezer')
        self.assertEqual((trap['x'], trap['y'], trap['z']), (10., 20., 5.))


class TestWhenItIsWritten(SidecarCase):

    def test_the_tree_is_flushed_first(self):
        self.record()
        self.assertEqual(self.tree.flushed, 1)

    def test_a_file_is_there_while_the_recording_runs(self):
        startRecording(self.dvr, self.video, 1000)
        try:
            data = self.read()
            self.assertEqual(data['recording']['video'], 'run.mkv')
            self.assertNotIn('stop', data['recording'])
        finally:
            self.dvr.recorder.stop()

    def test_the_end_is_added_when_the_recording_ends(self):
        self.record()
        self.assertIn('stop', self.read()['recording'])

    def test_the_traps_are_those_of_the_start(self):
        startRecording(self.dvr, self.video, 1000)
        self.overlay.addTrap(QTweezer(r=(1., 2., 3.), phase=0.))
        self.dvr.recorder.stop()
        self.assertEqual(len(self.read()['traps']), 1)

    def test_a_stop_that_was_not_seen_to_start_writes_nothing(self):
        self.dvr.recording.emit(False)
        self.assertFalse(Path(self.path('run.toml')).exists())

    def test_two_recordings_are_two_files(self):
        self.record()
        self.video = self.path('second.mkv')
        self.record()
        self.assertTrue(Path(self.path('run.toml')).exists())
        self.assertTrue(Path(self.path('second.toml')).exists())


class TestWhyARecordingStopped(SidecarCase):

    def test_the_reason_is_in_the_file(self):
        startRecording(self.dvr, self.video, 1000)
        self.dvr.recorder.stopped.emit('the camera was lost')
        self.dvr.recorder.stop()
        self.assertEqual(self.read()['recording']['stopped'],
                         'the camera was lost')

    def test_a_reason_is_not_kept_for_the_next_recording(self):
        startRecording(self.dvr, self.video, 1000)
        self.dvr.recorder.stopped.emit('the camera was lost')
        self.dvr.recorder.stop()
        self.video = self.path('second.mkv')
        self.record()
        self.assertNotIn('stopped', self.read()['recording'])


class TestAFileThatCannotBeWritten(SidecarCase):

    def test_it_is_reported_and_the_recording_goes_on(self):
        spy = QtTest.QSignalSpy(self.sidecar.status)
        full = patch.object(
            self.files,
            'writeToml',
            side_effect=OSError('disk full'),
        )
        with full, self.assertLogs('QHOT.lib.QSidecar', level='ERROR'):
            self.record()
        self.assertGreaterEqual(len(spy), 1)
        self.assertIn('disk full', spy[0][0])
        self.assertTrue(Path(self.video).exists())      # the video is there


class TestPlain(unittest.TestCase):

    def test_none_is_left_out(self):
        self.assertEqual(plain({'a': 1, 'b': None}), {'a': 1})

    def test_none_is_left_out_of_a_list(self):
        self.assertEqual(plain([1, None, 2]), [1, 2])

    def test_a_tuple_is_a_list(self):
        self.assertEqual(plain((1, 2)), [1, 2])

    def test_an_array_is_a_list(self):
        self.assertEqual(plain(np.array([[1, 2], [3, 4]])), [[1, 2], [3, 4]])

    def test_a_numpy_scalar_is_a_number(self):
        value = plain(np.float64(1.5))
        self.assertEqual(value, 1.5)
        self.assertIs(type(value), float)

    def test_it_goes_down_into_the_traps_of_an_array(self):
        overlay = QTrapOverlay()
        overlay.addTrap(QTrapArray(r=(10., 10., 0.), shape=(2, 2)))
        text = plain(overlay.toList())
        self.assertEqual(len(text), 1)           # and TOML can take it
        import tomlkit
        doc = tomlkit.document()
        doc['traps'] = text
        tomllib.loads(tomlkit.dumps(doc))


if __name__ == '__main__':
    unittest.main()
