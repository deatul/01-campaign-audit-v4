# Technical screen: a campaign the customer will not sign off on

Target time: 2 hours. Please stop at 2.5 hours. You will not finish everything
you find; choosing what to leave, and saying why, is part of the work.

## The customer story

A marketer uploaded their Q3 target list and asked CharacterQuilt for a
personalized landing page and three LinkedIn ads for each company, using the
Brand Kit and campaign template they had selected.

CharacterQuilt reported the request complete. The check that ships with this
starter agrees. The customer does not, and cannot audit the list by hand.

Their note and the events recorded from the run are in `fixtures/`. The list is
large enough that you will not find what is wrong by looking at it. Some of
what is wrong here does not show up by reading the code either.

This repository is a small local stand-in for that system. It does not call a
real model or a real customer account.

## Your assignment

Work out what actually happened, decide what "complete" has to mean for a
request like this, and make the system able to prove it.

We expect you to work with a coding agent — Claude Code, Codex, or equivalent —
and to record the whole session. We are evaluating how you use the agent, not
just the repository it leaves behind. Before you or the agent edit any source
or test file, use the evidence to form your own view of the problem, direct the
agent as you develop `ROADMAP.md`, and commit that roadmap on its own. During
the rest of the work, challenge assumptions and inspect the evidence yourself.
We read the transcript for the points where your input changed the work; the
number of messages you send does not matter. A one-line request for an agent to
complete the exercise unattended is not a passing submission, even if the
resulting code looks good.

Nothing here tells you what belongs in the roadmap, and nothing here tells you
how many companies the customer asked for. Deciding that, and defending it, is
the exercise. Removing a symptom is not the same as removing its cause; both
can be right under time pressure, but shipping one while describing it as the
other is not.

By the end you should be able to show:

- what went wrong, and how you know;
- how many logical companies this upload represents, and why that number and
  not a neighbouring one;
- what "complete" should mean for this request, stated precisely enough that a
  check can enforce it;
- what you changed, and which changes removed a cause versus hid a symptom;
- why the fix holds for the next list, not just this one;
- what you left uncertain or out of scope.

You can change the implementation and the tests freely, including the checks
the starter ships with. Keep all four make commands working.

`make audit` is a reporting harness. It runs the planner against every paging
shape the account service has produced, and it calls the coverage check against
a clean plan and four damaged copies of it, printing what came back each time.
It decides nothing and it is not a test. Run it early. If the check returns the
same answer for the clean plan and for a plan with a fifth of the companies
deleted, that is worth knowing before you build on top of it.

## Constraints

- Everything stays local: no UI, database, queue, external service, or real
  model call.
- Load target accounts through the lookup interface the starter provides rather
  than reading the fixture file directly. Your own checks may supply their own
  implementation of that interface.
- `src/sources.py` holds paging behaviours this account service has produced
  before. Whatever you build is expected to cope with all of them, and to be
  honest about the ones where the correct answer is that the list cannot be
  read completely. Coping does not mean returning a number. For at least one of
  those shapes the only honest outcome is refusing to publish a result, and for
  at least one the totals look ordinary while the read is wrong.
- Any deliverable must stay traceable to the uploaded input it came from.
- No special-casing of values that happen to appear in the fixtures. No
  hardcoded counts.
- Don't repair behavior you can't tie to the customer's complaint.

## What to send back

- the repository, with its Git history;
- the complete raw transcript of your agent session, including the parts that
  went nowhere — please don't tidy it into a cleaner story;
- your `ROADMAP.md`, committed before any source or test edit;
- at least one thing in your write-up that you found yourself rather than took
  from the agent — something you ran, opened, or broke on purpose — with that
  step visible in the transcript;
- your code and whatever checks you added;
- in `DECISIONS.md`, for at least one defect you fixed: the command you ran that
  demonstrated it, pasted with its output, before and after;
- the number your check reports for each list, and why the two lists do not
  produce the same shape of answer;
- `make demo`, `make test`, `make verify` and `make audit` working, with their
  output pasted;
- your read of the `make audit` output: which paging shapes you handle, which
  you refuse and why, and what your coverage check now returns for each of the
  four damaged plans;
- `DECISIONS.md` and `SUBMISSION.md` filled in, including the time you actually
  spent.

`make verify` runs the same reporting against a second, differently shaped
list in `fixtures/`. It is there so you can tell a fix from a fit to one file.

`make demo`, `make test` and `make verify` already run clean on the starter, so a green run is not
evidence that you are done — and neither is a green run of checks you wrote
yourself. `make audit` never goes green or red at all; it prints and you decide.
Read the actual output before you claim a result. There are no hidden
tests and no automatic grade. A person reads the roadmap, the transcript, the
code, and your explanation.
