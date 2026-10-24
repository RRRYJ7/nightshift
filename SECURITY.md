# Security

NIGHTSHIFT is a local, offline tool. It has no network code, no daemon, no
authentication and no service to compromise. That removes most of the usual
attack surface and leaves three things worth writing down.

## 1. The report renders untrusted text

`nsh report` renders event intents, evidence labels, target paths and criterion
text into HTML. Everything is passed through `html.escape`, and the SVG helpers
escape `<title>` content. If you find a way to get script into a report, that is
a security bug — please report it.

The report has no JavaScript and makes no network requests, so the worst case
for an escaping bug is a hostile link or a broken layout, not code execution.

## 2. The log is data, not a sandbox

`.nightshift/events.jsonl` is a text file produced by an agent that already had
shell access to your machine. Treat it like any other untrusted input:

- `nsh report` reads it and renders it;
- `nsh gate` reads it and decides whether to exit 0.

An agent can append a fake `check` event. It cannot hide that it did — the log is
append-only and every event is timestamped — but nothing here *prevents* it.
The gate is a memory aid for an honest agent and a paper trail for a dishonest
one; it is not an enclave.

If you need stronger guarantees, run the checks yourself on a clean checkout:

```bash
git stash && nsh check --all && git stash pop
```

## 3. Captured output may contain secrets

`nsh run` captures stdout and stderr into `.nightshift/evidence/`. If a command
prints a token, that token is now in a file that is easy to commit by accident.

- Add `.nightshift/evidence/` to `.gitignore` if your commands can print secrets.
- Or keep the log out of version control entirely; it works fine as a local file.

There is no redaction feature, deliberately: a redaction pass that silently drops
the wrong line would undermine the point of the evidence.

## Reporting

Open a regular issue for anything in categories 1 and 3. For something you
believe is exploitable, email the address in the repository profile instead of
opening a public issue, and give me a week before disclosure.
