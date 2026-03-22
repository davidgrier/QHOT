Architecture
============

QHOT is organized into four layers.  Each layer depends only on the
layers below it.

.. code-block:: text

   ┌──────────────────────────────────────────────────┐
   │  QHOT  (main window, QHOT.ui)                    │  application layer
   ├──────────────────┬───────────────────────────────┤
   │  QCGHTree        │  QHOTScreen  QSLMWidget        │  UI layer
   │                  │  QSaveFile   QSLM              │
   ├──────────────────┴───────────────────────────────┤
   │  CGH  (QThread)                                  │  computation layer
   ├──────────────────────────────────────────────────┤
   │  QTrap / QTrapGroup / QTrapOverlay               │  trap layer
   └──────────────────────────────────────────────────┘

Trap layer — ``QHOT.lib.traps``
--------------------------------

:class:`~QHOT.lib.traps.QTrap.QTrap` is the abstract base for all optical
traps.  Each trap holds a 3D position ``r``, an ``amplitude``, a ``phase``,
and a ``locked`` flag.  It emits ``changed`` whenever a positional or
structural property is updated.  When ``locked`` is ``True`` the overlay
silently ignores move, scroll, and rotate gestures on that trap.

:class:`~QHOT.lib.traps.QTrapGroup.QTrapGroup` provides recursive grouping.
Translating a group moves all contained traps together and emits ``changed``
once on the group, so the CGH can update only the group's displacement cache
(one outer product) without recomputing every leaf individually.
Rotating a group updates every child position in place and calls
``_broadcastChanged()`` to emit ``changed`` from each descendant in turn,
ensuring that all per-trap and per-group CGH caches are invalidated correctly.

:class:`~QHOT.lib.traps.QTrapOverlay.QTrapOverlay` is a
``pyqtgraph.ScatterPlotItem`` that renders each trap as a colored spot and
dispatches mouse and scroll-wheel events to add, remove, select, drag, group,
rotate, lock, and break traps.  Every interactive gesture pushes an undoable
command onto an embedded ``QUndoStack`` so that all operations can be reversed
with Ctrl+Z / Cmd+Z.

**Serialization.**  Every trap class implements ``to_dict()``, which returns a
plain ``dict`` containing a ``'type'`` key (the class name), all registered
properties, and ``'locked': True`` when the trap is locked (omitted otherwise
to keep JSON compact).  :class:`~QHOT.lib.traps.QTrapGroup.QTrapGroup` adds a
``'children'`` list; :class:`~QHOT.traps.QTrapArray.QTrapArray` overrides
this to omit the auto-generated children and instead stores the ``mask``.
``QTrapOverlay.save(path)`` and ``QTrapOverlay.load(path)`` write and read
these dicts as a JSON array.

**Undo/redo commands** (``QHOT.lib.traps.commands``).
Each interactive gesture is wrapped in a ``QUndoCommand`` subclass and pushed
onto the overlay's ``QUndoStack``:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Command
     - Action
   * - ``AddTrapCommand``
     - Add a ``QTweezer`` at a given position.
   * - ``RemoveTrapCommand``
     - Remove a top-level trap or group.
   * - ``MoveCommand``
     - Move a trap or group (pre-executed; first redo is a no-op).
   * - ``RotateCommand``
     - Rotate a group (pre-executed; stores before/after position snapshots).
   * - ``WheelCommand``
     - Scroll a trap's z-coordinate; consecutive scrolls on the same group
       are merged into a single undo entry.
   * - ``LockCommand``
     - Toggle the locked state of a trap or group; undo and redo are both
       a toggle.

New trap types are registered automatically via
:meth:`QTrap.__init_subclass__ <QHOT.lib.traps.QTrap.QTrap.__init_subclass__>`,
which inserts every subclass into ``QTrap._registry`` at class-definition time.
``load()`` dispatches on the ``'type'`` key using this registry, so custom trap
classes are supported without any changes to the overlay — they just need to be
imported before ``load()`` is called.

Computation layer — ``QHOT.lib.holograms.CGH``
-----------------------------------------------

:class:`~QHOT.lib.holograms.CGH.CGH` computes phase holograms in a
``QThread``.  Calibration attributes (pixel pitch, wavelength, focal length,
camera rotation, etc.) are set via ``__setattr__``, which automatically
triggers ``updateGeometry`` or ``updateTransformationMatrix`` and emits
``recalculate``.

Per-trap complex displacement fields are cached in a ``WeakKeyDictionary``
and invalidated selectively when a trap's position or structure changes,
so only modified traps are recomputed on each frame.  Trap groups share a
single accumulated field that is updated in place by a phase-shift broadcast
on each group translation.

When the field accumulation is complete, :meth:`~QHOT.lib.holograms.CGH.CGH.compute`
quantizes the phase to uint8 and emits ``hologramReady``.

UI layer
--------

:class:`~QHOT.lib.QHOTScreen.QHOTScreen` subclasses
``QVideo.lib.QVideoScreen`` to add a
:class:`~QHOT.lib.traps.QTrapOverlay.QTrapOverlay` rendered on top of the
live camera feed.  It translates Qt mouse and wheel events into the overlay's
coordinate system and forwards them for trap interaction.

:class:`~QHOT.lib.holograms.QCGHTree.QCGHTree` is a
``pyqtgraph.ParameterTree`` widget that exposes every CGH calibration
attribute as an editable spin box.  Writing to any parameter directly
updates the corresponding ``CGH`` attribute.

:class:`~QHOT.lib.QSLM.QSLM` manages the SLM display window on a secondary
screen and exposes a ``setData`` slot that accepts a uint8 phase array.
:class:`~QHOT.lib.QSLMWidget.QSLMWidget` shows a preview of the current
hologram inside the main window.

Application layer — ``QHOT.qhot``
----------------------------------

:class:`~QHOT.qhot.QHOT` loads ``QHOT.ui`` and wires all subsystems
together via Qt signals.

**File menu.**  The File menu is organized into three groups:

* **Open / Save / Save As** — trap configuration (``.json``).  ``saveTraps()``
  saves to the previously used path if one exists; otherwise it behaves like
  ``saveTrapsAs()``.  File I/O is delegated to
  :class:`~QHOT.lib.QSaveFile.QSaveFile`.
* **Export** submenu — camera images and SLM hologram patterns.
* **Preferences** submenu — CGH calibration settings (saved to
  ``~/.pyfab/QCGHTree.toml``).

**Edit menu.**  Added programmatically by ``_setupEditMenu()`` and inserted
between the File and Tasks menus.  Contains **Undo** (Ctrl+Z / Cmd+Z) and
**Redo** (Ctrl+Y / Shift+Cmd+Z), wired to the overlay's ``QUndoStack``.

**Central signal flow:**

1. ``QTrapOverlay`` emits ``trapAdded`` / ``trapRemoved`` → the group's
   ``changed`` signal and each leaf's ``changed`` signal are connected to
   ``_scheduleCompute``.
2. Each video frame triggers ``_onFrame``, which emits
   ``_computeRequested`` if traps have changed and no compute is pending.
3. ``CGH.compute`` runs in a ``QThread`` and emits ``hologramReady``.
4. ``hologramReady`` updates ``QSLM``, the ``QSLMWidget`` preview, and
   clears the pending flag so the next frame may trigger another compute.

Concrete trap types
-------------------

The :mod:`QHOT.traps` package provides ready-to-use trap classes:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Class
     - Description
   * - :class:`~QHOT.traps.QTweezer.QTweezer`
     - Single Gaussian tweezer
   * - :class:`~QHOT.traps.QVortex.QVortex`
     - Laguerre-Gaussian vortex beam
   * - :class:`~QHOT.traps.QRingTrap.QRingTrap`
     - Ring-shaped optical trap
   * - :class:`~QHOT.traps.QTrapArray.QTrapArray`
     - Rectangular grid of tweezers with optional mask and position jitter
   * - :class:`~QHOT.traps.QLetterArray.QLetterArray`
     - Single dot-matrix character rendered as tweezers
   * - :class:`~QHOT.traps.QTextArray.QTextArray`
     - String of ``QLetterArray`` characters
