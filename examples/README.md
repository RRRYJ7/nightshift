# Examples

NIGHTSHIFT is not a coding tool. It is a **"done" tool**. Any goal you can
express as "these commands must exit 0" fits.

Three scenarios, each with the exact commands. The third one ships a runnable
checker so you can try it in a minute.

---

## 1. Code: ship a feature overnight

```bash
nsh init --goal "ship the CSV export endpoint with tests and docs" --deadline 06:30
nsh done add "unit tests pass"     -- python -m pytest -q
nsh done add "types check"        -- mypy src
nsh done add "the endpoint builds" -- make build
nsh done add "openapi.yaml parses" -- python scripts/validate_spec.py

nsh run --target src/export/csv.py -- python -m pytest tests/test_export.py -q
nsh tick --progress 20 --note "csv writer done, endpoint next"
nsh run --target src/api/routes.py -- make build
nsh check --all          # re-run everything, right before you sleep
nsh report
```

What the report catches that a chat summary will not: `mypy src` failing at
03:10 and never being re-run, four edits to `csv.py` with no test in between,
and a deadline that arrives with `validate_spec.py` never executed.

---

## 2. Data: a pipeline you have to trust by morning

```bash
nsh init --goal "rebuild the 2024 cohort dataset and prove it is internally consistent" \
         --deadline 07:00 \
         --non-goal "no modelling" \
         --risk "upstream API was flaky last week"

nsh done add "row count matches source"      -- python checks/rowcount.py
nsh done add "no duplicate participant ids"  -- python checks/dupes.py
nsh done add "all dates within 2024"         -- python checks/dates.py
nsh done add "the export parquet re-reads"   -- python checks/reread.py

nsh run --target pipeline/build.py -- python pipeline/build.py
nsh run --target checks/rowcount.py -- python checks/rowcount.py
nsh tick --progress 50 --note "built, three checks green, date check failing on 41 rows"
nsh step "quarantined 41 rows to rejects.csv" -e rejects.csv
nsh check --all
nsh report
```

The point is not the checks — you already had them. The point is that at 07:00
you can see *which* ones ran, *when*, and what they printed. "The dataset is
clean" becomes a claim with an evidence file attached.

---

## 3. Documents: a deliverable that must actually parse

```bash
nsh init --goal "finish the grant proposal PDF, all sections, correct template" --hours 5
nsh done add "all 9 sections present"  -- python examples/doc/check_sections.py proposal.md
nsh done add "renders to PDF"          -- pandoc proposal.md -o proposal.pdf
nsh done add "page count in 8..12"     -- python examples/doc/check_pages.py proposal.pdf
nsh done add "no TODOs left"           -- python examples/doc/check_todos.py proposal.md

nsh run --target proposal.md -- pandoc proposal.md -o proposal.pdf
nsh tick --progress 30 --note "7 of 9 sections drafted"
nsh check --all
nsh report
```

`check_todos.py` is five lines and it is the difference between "I think I
removed all the placeholders" and knowing.

---

## The rule of thumb

If you can write the sentence *"this is done when ___"*, and `___` can be a
shell command, NIGHTSHIFT applies. If `___` is a feeling, no tool will help —
including this one.
