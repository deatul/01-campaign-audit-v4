# Decisions

Short notes are fine. Fill this in before you submit.

- Time actually spent: 2 hours

- How many logical companies this upload represents, and why that number and not a neighbouring one: 203 logical companies. The upload contains 223 rows, but 6 have a null or blank company_id and 14 are duplicate company_id rows.

- What changed between your roadmap and what you shipped: worked on roadmap in steps, spent a lot of time on roadmap before moving forward so nothing changed in roadmap

- What you had the coding agent do, and where you overrode it: coding agent created roadmap and changes, I hade to overrode roadmap multiple times

- What your change guarantees, and what it only makes more likely: my changes gurantees that a successfully completed plan contains exactly one set of four requested assets for each of the 203 canonical companies, and give report of incomplete input, duplicate enteries & page loading errors

- What you fixed at the cause, and what you only stopped from showing: fixed cause of duplicate companies and fixed stale brand-kit and template values by always using the current request configuration, and stopped showing companies with no company_id or page loading errors

- For at least one defect: the command that demonstrated it, pasted with its output, before your fix and after:
  make audit
  Before the coverage-check fix, duplicating one company was incorrectly accepted:
  one company campaigned twice -> [true, "all 203 campaigned rows have the requested asset types"]
  After the fix:
  one company campaigned twice -> [false, {"code": "duplicate_deliverables", "message": "plan contains duplicate company assets", ...}]

- What you chose not to fix: I did not fix input with duplicate company_id but different data, or row with missing company_id

- What you are still unsure about, including anything that came up during the session and stayed open: I am still unsure whether “first valid row wins” is the desired business rule when duplicate company_id rows contain different values.
