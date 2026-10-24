# A real (small) shift

The rest of `examples/` describes scenarios. This directory **is** one.

It is a 20-line module with a unicode bug, and the `.nightshift/` next to it is
the real, append-only log of the shift that fixed it — not a scripted demo:

1. the plan: two command-checkable criteria;
2. the first `nsh run` of the test suite, captured with **exit 1**;
3. the fix — replacing an ascii-only regex with an `isalnum()` scan;
4. the second `nsh run`, green;
5. two checkpoints, `nsh check --all`, `nsh gate`, `nsh verify`, `nsh report`.

You can replay the whole thing — from the repository root, with no install:

```bash
python -m nightshift --dir examples/sample-shift/.nightshift verify
python -m nightshift --dir examples/sample-shift/.nightshift report --open
python -m nightshift --dir examples/sample-shift/.nightshift status
```

Or, if you installed the CLI, just `cd examples/sample-shift && nsh verify`.

Or prove it from scratch — the log is append-only, so the failing run is still
in there:

```bash
grep '"exit": 1' .nightshift/events.jsonl
```

The fix itself is unremarkable. What is remarkable is that a year from now,
without asking anyone, you can tell whether the work actually happened: the
first test run exited 1, the second exited 0, and both outputs are hashed on
disk.
