Writing a task queue
====================

A *task queue* is a list of things for QHOT to do, one after another:
clear the traps, add a tweezer, wait, move it, record, take a picture.
The queue is a text file in `TOML <https://toml.io>`_, so you can write it
in any editor, with comments, and open it with **File > Open Queue**.
**File > Save Queue** writes the tasks that are waiting to run in the same
form, so a queue that you built with the menu is a starting point for one
that you edit.

An example
----------

.. literalinclude:: examples/queue.toml
   :language: toml

How a queue is written
----------------------

* Each task is a ``[[tasks]]`` table.  The tasks run in the order that they
  are written.
* ``type`` is the name of the task, spelled as in the table below.
* The other keys are the parameters of the task.  A parameter that is left
  out has its default.  Numbers are numbers (``x = 320``, ``step = 0.5``),
  and text is in quotes (``filename = "run1.mkv"``).
* Every task also takes ``delay``, the number of frames to wait before it
  starts, and the default is 0.
* A ``#`` begins a comment.
* A queue that is opened is added to the end of the tasks that are waiting,
  and QHOT is paused, so that you can look at it before it runs.

The tasks
---------

.. list-table::
   :header-rows: 1
   :widths: 18 40 42

   * - ``type``
     - What it does
     - Parameters
   * - ``AddTweezer``
     - Adds one tweezer.
     - ``x``, ``y`` [pixels]: where.  If left out, the optical axis of the
       CGH.
   * - ``BeginRepeat``
     - Marks the start of a block to repeat.
     - none
   * - ``Repeat``
     - Repeats the tasks since ``BeginRepeat``.
     - ``n``: how many times the block runs in all (default 1).
   * - ``ClearTraps``
     - Removes every trap.
     - none
   * - ``Delay``
     - Waits.
     - ``frames``: how many frames of video (default 30).
   * - ``Move``
     - Moves the marked traps so that their centroid reaches a place.
     - ``x``, ``y``, ``z`` [pixels]: the place.  ``step``: the most that
       it moves in a frame (default 1).
   * - ``MoveTraps``
     - Moves every trap by a displacement.
     - ``dx``, ``dy``, ``dz`` [pixels]: how far (default 0).  ``step``:
       the most that it moves in a frame (default 1).
       ``selected_only``: move only the selected traps (default false).
   * - ``LoadTraps``
     - Replaces the traps with those in a file that File > Save Traps or
       ``SaveTraps`` wrote.
     - ``filename``: the file.
   * - ``SaveTraps``
     - Saves the traps to a file.
     - ``filename``: the file.  If left out, a file with a timestamped
       name in the data directory.
   * - ``Snapshot``
     - Saves the video image to a file.
     - ``filename``: the file.  If left out, a file named from ``prefix``
       (default ``"snapshot"``) and the time.
   * - ``StartRecording``
     - Starts recording the video, and goes on to the next task.
     - ``filename``, ``nframes`` (most frames to record, default 10000),
       ``nskip`` (frames between recorded ones, default 1),
       ``overwrite`` (default false).
   * - ``StopRecording``
     - Stops the recording.
     - none
   * - ``Record``
     - Records the video for as long as the task lasts.
     - ``filename``, ``nframes`` (how many frames; 0, the default, is
       until the task is stopped), ``overwrite`` (default false).

When something is wrong
-----------------------

QHOT says what is wrong in the status bar, and does not open the queue, so
nothing runs half-written:

* a misspelled task: ``unknown task type: 'Dely'``;
* a misspelled parameter: ``got an unexpected keyword argument 'frame'``;
* a table with no ``type``: ``a task needs a 'type'``;
* a file with no ``[[tasks]]``: ``the file has no [[tasks]] tables``;
* a fault in the TOML itself, with the line where TOML found it.
