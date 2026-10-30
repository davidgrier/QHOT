# Changelog

## [Unreleased]

### Breaking
- Public methods and properties of Qt classes are `camelCase`, as in QVideo
  and as Qt names its own: `to_dict`, `from_dict`, `to_list`, `from_list`,
  `active_raw`, `queue_size` and `wait_for_camera` are now `toDict`,
  `fromDict`, `toList`, `fromList`, `activeRaw`, `queueSize` and
  `waitForCamera`.  The files that QHOT saves are unchanged.
- `QTaskManager` no longer takes the screen: its clock is the public slot
  `step()`, and the window connects `screen.rendered` to it.  The overlay
  is therefore a plain argument of the manager, and not also a property of
  the screen that it was given.
- `QueueMenu` no longer has `overlay`, `cgh` and `dvr`: it needs only the
  manager, which owns the resources that tasks work with.
- All the resources of `QTaskManager` are required (`overlay`, `cgh`, `dvr`,
  `save`, and the new `image`, the live video image): QHOT is a program that
  has them all, and not a library that may lack any.  A task is given the
  ones that it lacks when the manager takes it.
- `Snapshot` no longer needs an `image`: it saves the live image that the
  manager provides.  It was offered in the Queue menu although it could not
  be queued.
- The position of `AddTweezer`, if not set, is the optical axis of the CGH
  that the task works with, looked up when it is read.  (It was fixed when
  the task was made, before the manager had given the task its CGH.)
- The `parameters` of a task, and the tables of a trap overlay, are
  immutable (a tuple) or annotated `ClassVar`.

### Changed
- The overlay of traps says when its pattern changes: `QTrapOverlay.patternChanged`
  is emitted when a trap or a group changes, or traps are added or removed
  (tests check that it is, for every operation, whenever `pattern()` differs).
  A subgroup reports its changes through the group above it, so a change
  at any depth reaches the top, and a change of structure (`structureChanged`,
  now declared by every trap) is also `changed`.
- `CGH.follow(source)` keeps the hologram of a source of patterns up to date:
  it requests one when the pattern or the calibration changed, no more often
  than `CGH.INTERVAL` (15 ms), while the pipeline runs.  The window no longer
  watches every trap, nor owns the timer (`QHOT.COMPUTE_INTERVAL` is
  `CGH.INTERVAL`): it connects the overlay to the CGH.
- Failures of a task or of the hologram computation are logged with their
  traceback.
- `QTrapOverlay.undoStack` is public, and `Repeat` uses
  `QTaskManager.scheduled`, so neither reaches into private attributes.
- `ruff` also enforces single quotes, class attributes, quoted annotations
  and stale `noqa` comments.

### Fixed
- A task that was queued from the Queue menu was not given the file helper,
  so `SaveTraps` had nothing to save with.  The manager now gives every
  task that it takes (`register`, `load` and `inject`) the resources that
  the task lacks, in one place, and a resource that a task was given
  explicitly is its own.
- A `CGH` that was running when the program ended without an event loop
  (a script or notebook that did not call `stop()`) could abort the
  process while Python shut down, in about one run in fifty.  The thread
  of a pipeline is now stopped when the pipeline is dropped or the
  interpreter exits.

## [2.0.0] — 2026-10-29

**Every wheel published from 1.4.2 to 1.5.0 is missing most of the package**
(`lib`, `traps` and `tasks`), so `pip install QHOT` gave a program that
could not be imported.  2.0.0 is the first release that installs and runs
from PyPI; do not use 1.4.2 to 1.5.0.

This release changes the hologram pipeline and the names of modules.
`TorchCGH`, `cupyCGH` and `QTrapSync` are removed, `CGH.compute` takes a
pattern, and QHOT needs QVideo 4.11 or later and Python 3.11 or later.
The CuPy backend is experimental: it has not yet been run on a CUDA machine.

### Added
- `reference.hologram(pattern, optics)` (`lib/holograms/reference.py`):
  the algorithm of linear superposition stated as plainly as possible,
  in double precision, with no caching.  A trap's field is its complex
  amplitude times its displacement `D(r)` times its structuring field;
  a group's structuring field is the superposition of its members',
  recursively.  It is the standard that the engines are tested against.
- `Optics` and `Geometry` (`lib/holograms/optics.py`): the calibration as
  an immutable value, with the map to the SLM plane (`toSLM`) and the
  phasors that move a focus (`phasors`); `Geometry` (the angle and radial wavenumber of the
  SLM plane) is all that a trap is given to make its structure.
- `TrapSpec` (`lib/traps/trapspec.py`) and `QTrap.spec()`: a snapshot of a
  trap, or of a group with all its members, as a plain, hashable value.
- Plain groups and composites.  A plain group is a way to handle traps
  together: a member has the same amplitude in it as alone, so that its
  traps mix with others on an equal footing, and the group has no
  amplitude or phase of its own.  Its trap panel no longer offers them and
  its saved form no longer contains them (older files still load).  A
  composite, a group that is used as a single trap, has an amplitude and a
  phase of its own, to mix it with other traps: a class of composites sets
  `composite = True`.  No class does yet, and the old engine does not apply
  a composite's weight; the reference does.
- Backends that compute holograms from a pattern (`Backend`,
  `NumpyBackend`, `TorchBackend`, in `lib/holograms/backends/`), tested against the
  reference.  The fields of plain tweezers are summed as one matrix
  product of phasors; traps with the same structure are summed first and
  the structure applied once; groups are flattened by their amplitudes.
  Nothing is cached between holograms but the structuring fields, kept by
  value (kind of trap and parameters), so nothing can go stale.
  `TorchBackend` computes everything on the device, quantization included,
  and works on Apple GPUs (MPS), CUDA and the CPU.
- `NumbaBackend` (`-j`): CPU backend with compiled, parallel kernels that
  add a few traps to the field and take the phase in one pass over memory
  each; the matrix product of many traps is left to BLAS.  About four times
  faster than NumPy at 1920x1080 and as accurate.  `pip install
  "QHOT[numba]"`.
- `CupyBackend` (`-u`): the same computation on an NVIDIA GPU with CuPy.
  It has been tested against the reference only with a NumPy stand-in for
  CuPy, which checks its logic but not CUDA, and so is never chosen
  automatically.
- `QTrapOverlay.pattern()`: a snapshot of the traps as a tuple of specs,
  safe to hand to another thread.  `TrapSpec.components()` yields the
  traps of a spec with their complex amplitudes, and `Optics.toSLM`
  accepts an array of positions.
- `QTrap.structuringField(geometry, **params)`: a trap makes its own
  structuring field from the geometry and its parameters
  (`structureParams`), as a function of values.  `QVortex` and
  `QRingTrap` define it; their `structure(cgh)` now defers to it.

- A splash screen (`lib/splash.py`): the fringes of a particle's hologram,
  the name and the version, and a message that says what is happening.
  Copied and adapted from QVideo, where it is private.
- `QCameraOpener` (`lib/QCameraOpener.py`): opens the camera in a thread, so
  that a slow camera does not freeze the splash screen.  The SLM and the
  hologram engine are made while the camera opens, so a slow camera costs
  less of the start-up time.  If no camera opens, the program says why and
  exits.

### Changed
- **The hologram pipeline is rebuilt.**  `CGH` now holds the calibration
  and runs the compute thread itself; the computing is done by a
  `Backend`.  `CGH.compute(pattern)` returns at once and takes the
  pattern of an overlay (`QTrapOverlay.pattern()`); the hologram arrives
  as `hologramReady`, or the reason there is none as `computeFailed`.
  One hologram is computed at a time and only the newest waiting request
  is kept.  The pattern and the calibration (`CGH.optics`) are plain
  values captured at the request, so the thread that computes never reads
  anything that the interface edits: there are no locks, no replicas of
  the traps and no caches to invalidate.  A hologram is computed from
  scratch each time, which the matrix-product backends do faster than the
  old engine summed its caches.
- Holograms are requested by a timer of their own
  (`QHOT.COMPUTE_INTERVAL`, 15 ms), not by the video.  A trap now takes
  effect at once however slowly the camera delivers frames, and with the
  video stopped.  `QHOTScreen.rendered` still drives the tasks.
- `choose_cgh` and the command line choose a backend: `-t` PyTorch, `-j`
  numba, `-n` NumPy, `-u` CuPy.  An unavailable one falls back with a
  warning.  By default PyTorch is used if it is installed, even without a
  GPU, then numba, and NumPy otherwise.  `choose_backend` returns just the
  backend.
- A hologram that cannot be computed no longer stops all later holograms:
  the status bar shows the reason, and the next change asks again.

- The public API of the library is documented, and a test keeps it so
  (`tests/test_docstrings.py`).  The docstrings carry the physics, with the
  equations in `.. math::` blocks, and the documentation builds without
  warnings.

- A lint job in CI, `ruff check` with pyflakes, bugbear and the 79-column
  limit, as in QVideo.  The 8 findings are fixed, and `main()` no longer
  describes the hologram backends that were removed.
- Arguments of definitions and calls are laid out either all on one line or
  one to a line, throughout the code, and a test (`tests/test_style.py`)
  keeps them so.  As in QVideo, a definition aligns its parameters under
  the first; a call aligns them or hangs them with a trailing comma.

- **Modules are named as in QVideo**: a module that holds a Qt class keeps the
  name of the class, and every other module has a short lowercase name.  The
  backends are the package `QHOT.lib.holograms.backends`, whose private
  modules (`_numpy.py`, `_numba.py`, `_torch.py`, `_cupy.py`, `_base.py`)
  are imported through the package, and the optional ones only when they
  are asked for, so that importing QHOT does not import torch, numba or
  cupy.  `QHOT.lib.holograms.Optics` is now `...optics`,
  `QHOT.lib.traps.TrapSpec` is `...trapspec`, and `QHOT.lib.letterSymbol` is
  `...lettersymbol`.  The names of the classes are the same, and
  `from QHOT.lib.holograms import Optics, Backend, NumpyBackend` still works.

### Removed
- `TorchCGH` and `cupyCGH` (replaced by `TorchBackend` and
  `CupyBackend`), `QTrapSync` and the replicas, the per-trap caches and
  their invalidation, and `CGH.compute(traps)` on live traps, `fieldOf`,
  `transform`, `window`, `quantize`, `bless` and the geometry arrays.
- `QVortex.structure(cgh)` and `QRingTrap.structure(cgh)`: use
  `structuringField(geometry, **params)`.

- `Record`, `StartRecording` and `StopRecording` drive the recorder of the
  DVR widget (`dvr.recorder`) instead of clicking its buttons.  A click
  takes effect a moment later, does nothing when the button is disabled,
  and could open a dialog that stopped an unattended run.  Now a
  recording that cannot start fails the task, and with it the queue, with
  the reason in the status bar: there is no camera, a video is playing, a
  recording is already running, the extension of the file cannot be
  written, or the file exists.  The new parameter `overwrite` (default
  `False`) allows replacing a file; before, the widget asked.
- The tasks keep `filename`, `nframes` and `nskip` themselves; they no
  longer write them into the DVR widget, which only shows the name of the
  file being recorded.  A saved queue therefore keeps a blank file name
  as blank, meaning the name that the widget shows when the task runs.
- A `Record` task that is aborted, for example by stopping the queue,
  stops its recording.

### Fixed
- **The wheel was missing most of the program.**  Since 1.4.2 the package
  list in `pyproject.toml` named only `QHOT`, so `pip install QHOT` installed
  a package without `lib`, `traps` and `tasks`, and the program could not
  import its own library (`No module named 'QHOT.lib'`).  Every release from
  1.4.2 to 1.5.0 is affected.  All the packages are listed, a test
  (`tests/test_packaging.py`) fails when a package directory is not in the
  list, and a CI job builds the wheel, installs it in a clean environment and
  imports the program from outside the checkout.
- The splay correction counted `zc` twice: it grew with the depth from
  the focal plane minus `zc` again.  It now follows the depth from the
  focal plane, in `CGH.transform` and in `Optics.toSLM`.  Nothing
  changes while `zc` is 0, its default.
- A saved queue that contains a `StartRecording` task could not be
  loaded: the task wrote into the DVR widget before the queue gave it one.
- Detaching a trap from a group left the cached structure of the group
  stale, so that the hologram was wrong over nearly all of the SLM.
- Moving a group and then changing one of its members (or a nested
  group) recomputed the structure of the group from cached fields of the
  other members at their old places, giving phase errors of tens of
  levels.  Both are gone with the caches: nothing can go stale.

## [1.5.0] — 2026-10-27

### Changed
- Require QVideo >= 4.9.0.  The filter rack now owns a pipeline that the
  screen displays, and DVR playback switches the rack's source.
- Require Python >= 3.11 (a QVideo 4.9 requirement); Python 3.10 is no
  longer supported.

### Fixed
- `QHOTScreen.setImage` accepts the `FrameInfo` passed by `QVideoScreen`,
  fixing a `TypeError` when a throttled frame was displayed.

## [1.4.2] — 2026-04-15

### Fixed
- `pyproject.toml`: replaced `packages.find` with `where = [".."]` (which
  registered the package at the parent directory and polluted `sys.path` with
  all sibling projects) with the explicit `package-dir = {"QHOT" = "."}` /
  `packages = ["QHOT"]` form used by QInstrument.  Corrected `package-data`
  glob from the literal `"QHOT.ui"` to `"*.ui"`.

## [1.4.0] — 2026-03-22

### Added
- Trap locking: hold **Ctrl+Alt** (Control+Option on macOS) and left-click
  a trap to lock it in place.  Click again to unlock.
- `QTrap.locked` property (default ``False``).  Locked traps display with
  the ``STATIC`` (white) brush and cannot be moved, scrolled, or rotated
  via mouse gestures.  The lock state is serialized in saved JSON files.
- `LockCommand`: undoable toggle in `lib/traps/commands.py`; undo and redo
  both toggle the locked state, so Ctrl+Z restores the previous lock state.
- ``QTrapGroup.to_dict()`` now delegates to ``super().to_dict()`` so any
  future additions to ``QTrap.to_dict()`` are automatically inherited.

### Changed
- `selectGroup`, `startRotation`, and `wheel` all skip locked traps/groups
  without consuming the event, so clicks on locked traps still return
  ``True`` (no rubber-band fallback).
- `_addTrap` and `_rebuildSpots` use the ``STATIC`` brush for locked
  traps so the visual state survives remove/add undo cycles.

## [1.3.0] — 2026-03-22

### Added
- Undo/redo support for all interactive trap operations.  Ctrl+Z / Ctrl+Y
  (or ⌘Z / ⇧⌘Z on macOS) now undo and redo the most recent action.
- `lib/traps/commands.py`: five `QUndoCommand` subclasses that implement
  the undo/redo logic:
    - `AddTrapCommand` — add a `QTweezer` at a given position.
    - `RemoveTrapCommand` — remove a top-level trap or group.
    - `MoveCommand` — move a trap group (pre-executed; first redo is a no-op).
    - `RotateCommand` — rotate a trap group (pre-executed; stores
      before/after snapshots and uses `QTrapGroup.rotate(0., snapshot)` to
      restore positions exactly).
    - `WheelCommand` — scroll a trap's z-coordinate; consecutive wheel
      events on the same group are merged into a single undo entry.
- `QTrapOverlay._undoStack`: a `QUndoStack` owned by each overlay.
- `QTrapOverlay._addTrap()` / `QTrapOverlay._removeTrap()`: private helpers
  that perform the actual registration / deregistration logic; the public
  `addTrap` and `removeTrap` methods now delegate to these when called
  programmatically, and push undo commands when called interactively.
- `QTrapOverlay._move_origin` / `QTrapOverlay._rotation_angle`: new state
  variables used to detect actual movement before pushing an undo command.
- Edit menu in the main window with **Undo** and **Redo** actions wired to
  the overlay's undo stack; inserted between the File and Tasks menus.
- `_onTrapRemoved` in `QHOT` now disconnects `_scheduleCompute` from removed
  traps' signals to prevent duplicate connections during undo/redo cycles.

## [1.2.0] — 2026-03-22

### Added
- Interactive group rotation: hold **Alt** and left-drag any trap in a group
  to rotate the entire outermost group around its center.  The rotation angle
  is determined by the angle from the group center to the cursor, computed
  absolutely from a snapshot of child positions taken at press time (no
  floating-point drift).  Sub-group centers are updated recursively.  Traps
  display the *selected* (pink) visual state during the drag.
- `QTrapGroup._snapshot()`: records `{id(child): _r.copy()}` for all
  descendants, used to seed rotation without cumulative drift.
- `QTrapGroup._rotateSilently()`: applies an in-place rotation to all
  descendants without emitting any signals.
- `QTrapGroup._broadcastChanged()`: emits `changed` from every descendant
  (leaves first, then sub-groups, then self) so that the CGH displacement-
  field caches are correctly invalidated after rotation.
- `QTrapGroup.rotate(angle, snapshot)`: public method combining the above;
  called by `QTrapOverlay` on every mouse-move event during a rotation drag.
- `QTrapOverlay.startRotation()`: begins rotation mode and is registered as
  the handler for the **Alt + left drag** gesture.

### Fixed
- Group rotation now correctly updates the hologram on the SLM.  Previously,
  `rotate()` only emitted `group.changed`, which cleared `_field_cache[group]`
  but left `_structure_cache[group]` and every `_field_cache[leaf]` stale.
  The CGH reused the old cached values and produced an unchanged hologram.
  `_broadcastChanged()` ensures all relevant cache entries are invalidated.

---

## [1.1.0] — 2026-03-22

### Added
- `TorchCGH`: PyTorch-accelerated CGH backend.  Automatically selects the
  best available device — Apple Silicon MPS, NVIDIA/AMD CUDA/ROCm, or CPU
  fallback.  Install with `pip install QHOT[torch]`.
- `lib/chooser.py`: `choose_cgh()` auto-detects and instantiates the best
  available CGH backend; `cgh_parser()` registers `-t` (TorchCGH) and `-u`
  (cupyCGH) CLI flags; `build_parser()` combines CGH and camera backend
  flags into titled argument groups compatible with `QVideo.lib.chooser`.
- `__version__` is now sourced from installed package metadata via
  `importlib.metadata`, keeping `pyproject.toml` as the single source of
  truth.

### Fixed
- Trap spots in a group now translate correctly when the group is dragged.
  `_onGroupChanged` was only connected in `addTrap`; groups created by
  rubber-band selection (`_finalizeSelection`) and by `breakGroup` (inner
  group promotion) were missing the connection.

### Changed
- `CGH._connectTrap()` extracted as a shared helper so `TorchCGH.fieldOf`
  no longer duplicates the weakref+partial signal-wiring block.
- `@classmethod` removed from `coverage.exclude_lines`; `example()` methods
  removed from all CGH modules, eliminating the need for that broad exclusion.

---

## [1.0.0] — 2026-03-15

### Added
- Initial public release on PyPI under the name **QHOT**
  (renamed from the internal project name QFab).
- GPLv3 license.
- Sphinx documentation published to ReadTheDocs.

---

## [0.1.0] — 2026-03-14

### Added
- `QTrapArray`: rectangular grid of optical tweezers with optional boolean mask
  and per-trap Gaussian position jitter (`fuzz` parameter)
- `QLetterArray`: single dot-matrix character (A-Z, a-z, 0-9, space) rendered
  as an array of tweezers using a 5×7 bitmap font
- `QTextArray`: multi-character text string composed of `QLetterArray` instances
- Lowercase glyph set for `QLetterArray` (distinct from uppercase)
- `reshaping` / `reshaped` signals on `QTrapArray` and `QTextArray` to bracket
  trap-population changes
- Pre-push git hook running the full unit-test suite before every `git push`
- `pyproject.toml` packaging metadata and `qhot` entry-point script
- Comprehensive unit-test suite (~700 tests) covering all trap classes,
  overlay, CGH, SLM, save/restore, and UI widgets

### Changed
- `QTrapOverlay.removeTrap` now iterates `group.leaves()` instead of direct
  children, correctly handling nested trap groups such as `QTextArray`

### Fixed
- Mask shape validation in `QTrapArray.__init__` now raises `ValueError`
  immediately rather than deferring to the setter
- `QHOTScreen._overlayPos` now works across PyQt5 builds where `pos()` is
  absent from `QWheelEvent` or `position()` is absent from `QMouseEvent`;
  wheel-scroll z-axis movement restored
- Five broken `traptab.html` links in `traphowto.html` corrected to
  `trapstab.html`
- `recordhowto.html` link typo `videotab.htm` → `videotab.html`
- Trap creation gesture documented as Shift+left-click (was incorrectly
  stated as right-click)
- Selected-trap marker color documented as pink (was incorrectly stated
  as red)
- `index.html` dead link to non-existent SLM tab removed

### Added
- `QSLMWidget`: in-app preview of the hologram currently displayed on the
  physical SLM, with white background, interactive zoom and pan, and
  visibility-gated rendering (skips updates while the tab is hidden,
  renders the cached frame when the tab is first shown)
- `slmtab.html` help page documenting the SLM preview and its mouse controls
- `videofilters.html` help page documenting the four display filters
- `videocamera.html` cross-reference to the display-filters panel
- `trapstab.html` descriptions of all six trap types and their properties
