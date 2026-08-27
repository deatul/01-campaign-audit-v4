# CharacterQuilt technical screen: audit a campaign you cannot check by hand

Read [TASK.md](TASK.md) — it has the whole assignment.

## Setup

Python 3.11 or newer. Nothing to install.

## Commands

```bash
make demo    # run the customer's request and print the result
make test    # run the visible test
make verify  # the same reporting against a second, differently shaped list
make audit   # report against every recorded paging shape, and show what the
             # coverage check returns for a clean plan and four broken ones
```

`make audit` reaches no conclusion and passes or fails nothing. It is there so
you can look at behaviour instead of reasoning about it.

## Files

- `TASK.md` — the assignment.
- `fixtures/request.json` — the customer's request.
- `fixtures/target_accounts.json` — the list they uploaded.
- `fixtures/customer_report.txt` — what they told support afterwards.
- `fixtures/failure-traces.jsonl` — events recorded during the run.
- `src/repair_lab.py` — the starter implementation.
- `src/sources.py` — paging shapes the account service has produced before.
- `tests/test_visible.py` — one visible test, not a full specification.
- `demo.py` — what `make demo` runs.
- `audit.py` — what `make audit` runs.
- `DECISIONS.md`, `SUBMISSION.md` — fill these in before you send the packet
  back.
