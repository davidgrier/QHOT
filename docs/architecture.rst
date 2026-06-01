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

Task framework — ``QHOT.lib.tasks`` / ``QHOT.tasks``
-----------------------------------------------------

The task framework provides a frame-synchronised automation layer that
sits alongside the trapping system.  Tasks are Python objects that run
one step per video frame, driven by the same ``QHOTScreen.rendered``
signal that updates the CGH.

**QTask** is the abstract base for all tasks.  Each subclass overrides
up to three lifecycle hooks:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Hook
     - When called
   * - ``initialize()``
     - Once on the first active frame (after any optional delay).
       Use it to set up trajectories, start recordings, or perform
       a one-shot action.  The previously completed blocking task is
       available via ``self.previous``.
   * - ``process(frame)``
     - Once per frame while the task is running.  ``frame`` is a
       zero-based counter.  Call ``self.finish()`` to end early.
       Never called when ``duration == 0``.
   * - ``complete()``
     - Once after the last ``process()`` call, or immediately after
       ``initialize()`` when ``duration == 0``.  Use it to store
       results for the next task.

Every task progresses through four states — ``PENDING``, ``RUNNING``,
``COMPLETED``, ``FAILED`` — and emits ``started``, ``finished``, or
``failed`` at each transition.

**QTaskManager** schedules and dispatches tasks.  It maintains two
separate execution channels:

* **Blocking queue** — tasks run one at a time in registration order.
  When a blocking task finishes, the completed task object is passed to
  the next task's ``initialize()`` via ``task.previous``, allowing
  results to flow down the queue.  The full ordered list
  (``scheduled``) is retained even after tasks complete so the
  sequence can be inspected and re-run; call ``clear()`` to discard it
  or ``restart()`` to rerun it from fresh instances.

* **Background tasks** — non-blocking tasks start immediately and run
  in parallel with the blocking queue until they finish or are stopped.
  Register with ``blocking=False``::

      manager.register(Record(dvr=dvr, nframes=300), blocking=False)
      manager.register(Move(overlay, trap, target))

If a blocking task fails, the remaining pending tasks are cleared and
logged.  Background tasks fail independently without affecting the
queue.

**Loop control.**  ``BeginRepeat`` and ``Repeat`` are bracket tasks
that repeat an arbitrary sub-sequence of the blocking queue a
configurable number of times::

    manager.register(BeginRepeat())
    manager.register(Move(overlay, trap, target))
    manager.register(SaveTraps(overlay=overlay, path='frame.json'))
    manager.register(Repeat(n=10))

When ``Repeat`` runs, it scans the schedule backwards to find its
matching ``BeginRepeat`` (handling nesting via a depth counter),
serialises the intervening tasks, and prepends ``n − 1`` fresh copies
to the front of the queue via ``manager.inject()``.  Injected tasks
are ephemeral: they are not added to ``scheduled``, so they do not
persist across ``stop()`` / ``restart()`` calls.

**Serialisation.**  ``QTask.to_dict()`` returns a plain dict with a
``'type'`` key (the class name), ``'delay'``, and all declared
parameter values.  ``QTask.from_dict()`` looks up the class name in
``QTask._registry`` and reconstructs the task.  New subclasses are
registered automatically via ``__init_subclass__``.  ``QTaskManager``
uses this for ``load()``, ``restart()``, and loop injection.

**UI widgets.**

* :class:`~QHOT.lib.tasks.QTaskManagerWidget.QTaskManagerWidget` — the
  main control panel.  Shows the blocking queue (active task in bold
  with a violet tint; completed tasks greyed; failed tasks in red) and
  a separate background-task list.  Clicking any task reveals its
  editable parameters in a
  :class:`~QHOT.lib.tasks.QTaskTree.QTaskTree` below.  Pending tasks
  can be reordered by dragging and removed via right-click or
  Delete / Backspace.  Provides Play / Pause, Stop, and Clear buttons.

* :class:`~QHOT.lib.tasks.QueueMenu.QueueMenu` — a submenu that
  populates itself from ``QTask._registry`` and calls
  ``manager.register()`` when the user picks a task type.

**Concrete task types** (``QHOT.tasks``):

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Class
     - Description
   * - :class:`~QHOT.tasks.Delay.Delay`
     - Wait a fixed number of frames before the next task starts.
   * - :class:`~QHOT.tasks.BeginRepeat.BeginRepeat`
     - Marks the start of a repeating block; paired with ``Repeat``.
   * - :class:`~QHOT.tasks.Repeat.Repeat`
     - Closes a ``BeginRepeat`` block and repeats it ``n`` times.
   * - :class:`~QHOT.tasks.AddTweezer.AddTweezer`
     - Add a tweezer at a specified position.
   * - :class:`~QHOT.tasks.ClearTraps.ClearTraps`
     - Remove all traps from the overlay.
   * - :class:`~QHOT.tasks.LoadTraps.LoadTraps`
     - Load a trap configuration from a JSON file.
   * - :class:`~QHOT.tasks.SaveTraps.SaveTraps`
     - Save the current trap configuration to a JSON file.
   * - :class:`~QHOT.tasks.Move.Move`
     - Move a single trap along a path over a number of frames.
   * - :class:`~QHOT.tasks.MoveTraps.MoveTraps`
     - Move all traps in the overlay by a common displacement.
   * - :class:`~QHOT.tasks.Snapshot.Snapshot`
     - Capture a single camera frame to a file.
   * - :class:`~QHOT.tasks.Record.Record`
     - Record a fixed number of frames as a background task.
   * - :class:`~QHOT.tasks.StartRecording.StartRecording`
     - Start the DVR as a blocking task; pairs with ``StopRecording``.
   * - :class:`~QHOT.tasks.StopRecording.StopRecording`
     - Stop the DVR; ends recording started by ``StartRecording``.

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
  ``~/.qhot/QCGHTree.toml``).

**Edit menu.**  Added programmatically by ``_setupEditMenu()`` and inserted
between the File and Tasks menus.  Contains **Undo** (Ctrl+Z / Cmd+Z),
**Redo** (Ctrl+Y / Shift+Cmd+Z), wired to the overlay's ``QUndoStack``,
and **Toggle Overlay** (Ctrl+\\ / Cmd+\\) which shows or hides the trap
overlay without removing any traps.

**Tasks menu.**  Defined in ``QHOT.ui`` and extended at runtime by
``_setupShortcuts()``:

* **Add Trap** submenu — choose a trap type to place via
  :class:`~QHOT.lib.traps.QTrapMenu.QTrapMenu`.
* **Add Tweezer** (Ctrl+T / Cmd+T) — immediately adds a
  :class:`~QHOT.traps.QTweezer.QTweezer` at the optical axis
  (``CGH.xc``, ``CGH.yc``).
* **Clear Traps** (Ctrl+Backspace / Cmd+Backspace) — removes all traps
  and clears the undo stack.

**Video tab.**  The video tab contains the camera tree and a
:class:`~QVideo.lib.QFilterRack.QFilterRack` widget (``screen.filter``).
``_addFilters()`` populates the rack at startup with four filters in
pipeline order: *Color Channel*, *Smoothing*, *Sample and Hold*, and
*Canny*.  Because ``QFilterRack`` is editable by default, users can add
further filters from the full QVideo catalogue via the **Add filter…**
button, remove any filter with its × button, and drag filters to reorder
the pipeline.  The **Export…** button saves the current enabled pipeline
as a standalone Python module.

**Keyboard shortcuts** are assigned by ``_setupShortcuts()`` on the
existing File and Tasks actions:

.. list-table::
   :header-rows: 1
   :widths: 40 30 30

   * - Action
     - Mac
     - Other
   * - Open traps
     - Cmd+O
     - Ctrl+O
   * - Save traps
     - Cmd+S
     - Ctrl+S
   * - Save traps as
     - Shift+Cmd+S
     - Ctrl+Shift+S
   * - Add tweezer at center
     - Cmd+T
     - Ctrl+T
   * - Clear all traps
     - Cmd+Backspace
     - Ctrl+Backspace
   * - Toggle overlay
     - Cmd+\\
     - Ctrl+\\
   * - Undo
     - Cmd+Z
     - Ctrl+Z
   * - Redo
     - Shift+Cmd+Z
     - Ctrl+Y

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
