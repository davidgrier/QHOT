# Changelog

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
