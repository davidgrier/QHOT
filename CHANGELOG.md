# Changelog

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
