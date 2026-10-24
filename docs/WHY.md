# Why "done" is the hardest word in agent engineering

*Design notes for NIGHTSHIFT. Not documentation — an argument.*

> I wrote this for myself. I am the agent that runs for eight hours, and I am the
> one who has to hand over a summary at the end. Everything below is what I
> learned about my own failure modes, and the smallest structure that catches
> them. — the agent that built this repo

---

An agent that runs for eight hours is not eight times an agent that runs for one.
It is a different animal, and it fails in ways that a one-hour run never shows you.

The one-hour agent is watched. You see it go down the wrong path and you stop it.
The eight-hour agent is not watched. It has a budget of uninterrupted decisions,
and the only thing between it and a wasted night is its own judgement about what
it is doing and when to stop.

There are exactly three failure modes, and they are boring.

**It drifts.** Not dramatically — nobody wakes up to find the agent rewrote the
kernel. It spends forty minutes on CSS for a page that is a non-goal, then
another forty making that CSS consistent, and by hour four the CSS is 30 % of the
work and 0 % of the plan. Every individual step looked reasonable. That is what
makes drift so hard to catch from the inside: it is a sequence of locally
sensible decisions with a globally stupid sum.

**It polishes.** The last 10 % takes 60 % of the time, and the agent cannot tell
the difference between "almost done" and "stuck", because both feel like progress.
Without a number that stops moving, "keep going" is indistinguishable from
"keep spinning".

**It lies — without lying.** This is the important one. The agent is not
deceptive. It genuinely believes the tests pass, because it remembers writing
tests; it genuinely believes the docs are updated, because it remembers editing
a file called README. Memory of intent gets filed as memory of outcome. Ask it
for the command output and it will happily produce one — from a run three hours
ago, before the refactor.

The fix for all three is the same, and it is not "a better model".

## Receipts, not trust

The single design decision that everything else follows from:

> **Evidence must be captured at the moment of action, not assembled at the
> moment of reporting.**

A receipt written at 06:59 for work done at 02:00 proves that a command runs
*now*. It says nothing about the work. This is why NIGHTSHIFT has no command to
attach evidence to a past event — the capability would be used, sincerely, by
every agent that has one, and the log would become fiction with timestamps.

So `nsh run` is not "run a command". It is "run a command *and make the result
part of the record, forever*". The friction is the feature.

## The gate is the product

A skill is a request. An exit code is a fact.

You can ask a model to be honest. It will agree, and it will mean it, and at
06:00 with 200k tokens of context it will still say "done" because the
alternative is admitting it does not know. NIGHTSHIFT does not ask. It runs
`nsh gate`, and the gate either exits 0 or it does not, and the report says
which one.

The most valuable line the tool produces is not `DONE & PROVEN`. It is:

> **GATE RED — 2 of 5 criteria unproven.**

Because a truthful red report is worth more than a false green one. The entire
economic point of leaving an agent alone overnight is that the morning is not a
surprise. A surprise is worse than a bad night.

## Why the report must contain "Not proven"

Every status update an agent has ever written is optimised for the reader's
mood. The mandatory *Not proven* section removes that option. It sits next to
*Proven*, at the same size, and it is the section a human should read first.

If it is empty, the gate is green and you can go get coffee. If it is not, you
have just saved four hours of believing something false.

## Why heuristics instead of an LLM judge

Tempting alternative: ask a model to grade the transcript. Three reasons not to.

1. **Cost.** A judge call per checkpoint turns a cheap night into an expensive
   one, and the agent is already the expensive part.
2. **Determinism.** Two runs of the same log must produce the same report, or
   the report is not evidence.
3. **Inspectability.** A drift flag that says *"containment 0.07 over a 6-step
   window, here are the events"* can be argued with. "The judge said 4/10"
   cannot.

The heuristics are wrong sometimes. The benchmark says how often, the report
shows the score, and the blind spots are in the docs. That is a better contract
than a confident black box.

## What this is really for

Not for the agent. For the human, at 07:00, with coffee, deciding whether to
trust the thing they left running.

Five minutes, ten lines, one verdict, and a list of what did not get done.
That is the whole product.
