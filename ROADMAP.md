# Campaign pagination correctness roadmap

## Goal

Build a campaign plan in which every logical company supplied by the account
page loader appears exactly once, with exactly one of each requested asset, or
refuse to publish the plan when a complete and stable read cannot be proved.

The fix must not depend on fixture-specific row counts, page sizes, ordering, or
IDs.

## Evidence and current risks

- The uploaded fixture has 223 source rows, but rows and logical companies are
  not interchangeable: some `company_id` values repeat and six rows have no
  `company_id`.
- Deduplication currently happens independently inside each page. A company
  repeated across page boundaries survives, so changing page size changes the
  plan.
- The builder trusts `truncated` and `next_cursor` without checking progress.
  Replayed pages are duplicated; stalled, cycling, or missing cursors loop; an
  early terminal page is accepted as complete; and unstable ordering can skip
  and repeat rows while producing ordinary-looking totals.
- `complete=True` is currently asserted rather than demonstrated.
- The coverage evaluator derives its expectations from the plan and ignores the
  supplied account list. It therefore cannot prove that all requested companies
  were included and cannot detect several kinds of duplication.

## Definition of complete

A plan is complete only when all of the following can be demonstrated:

1. The account source reached a valid terminal page through a finite,
   forward-progressing cursor traversal.
2. The source read is stable enough to establish the full expected set. If the
   loader contract cannot prove this, planning fails closed instead of
   publishing a partial result.
3. Every valid uploaded row is accounted for and remains traceable by its
   `source_row_id`.
4. Every resolved logical company appears exactly once in the campaign.
5. Each logical company has exactly one deliverable for every required asset
   type, and no unexpected or duplicate deliverables.
6. Every deliverable uses the brand kit and template selected in the current
   request.
7. `company_id` is the sole logical-company identity. Any row whose
   `company_id` is null, missing, or blank is skipped and reported by
   `source_row_id`; invalid values are never collapsed by converting them to
   the string `"None"`.
8. When different source rows repeat a `company_id`, the first encountered valid
   row is retained and each later row is skipped and reported as a duplicate.
   Duplicate rows do not generate additional deliverables. Page replays are
   detected before result-position IDs are assigned.
9. `source_row_id` is a collector-assigned result position, not an ID read from
   the row. For zero-based logical page number `p`, requested page size `s`, and
   zero-based index `i` within the page, it is `p * s + i`. Only accepted pages
   advance `p`, so these IDs are unique within a successful traversal.

## Implementation roadmap

### 1. Establish and document account identity

- [x] Use a non-null, non-blank `company_id` as the only canonical
      logical-company key. Do not fall back to company name, domain, or another
      field.
- [x] Skip each row with a missing, null, or blank `company_id` without rejecting
      valid rows, and report every affected `source_row_id` and reason.
- [x] Retain the first valid row encountered for each `company_id`; skip every
      later distinct source row with that `company_id` and report its
      `source_row_id`, duplicate `company_id`, and the retained row's
      `source_row_id`.
- [x] Generate deliverables only from the retained row. Conflicting fields on a
      duplicate row must be included in diagnostics but must not replace or merge
      into the retained company record.
- [x] Calculate expected logical-company counts through this identity policy,
      not through fixture-specific constants.

### 2. Make page traversal finite and observable

- [x] Move pagination into a dedicated collector with a clear success/error
      result rather than embedding it in deliverable generation.
- [x] Track every requested cursor and reject a repeated cursor, a cursor cycle,
      or a cursor that fails to advance.
- [x] Reject `truncated=True` when `next_cursor` is missing.
- [x] Apply a configurable page/request budget as a final safety boundary and
      return a pagination error when it is exhausted.
- [x] Record per-page evidence: input cursor, returned cursor, row count, stable
      page number, row positions, and terminal status. Keep this evidence with the
      plan or result so a completion decision can be explained.
- [x] Assign each accepted row a positional `source_row_id` using
      `page_number * requested_page_size + page_index`. Do not interpret an `id`
      field in the returned row as `source_row_id`.

### 3. Deduplicate globally, not per page

- [x] Detect exact page replay using the requested cursor and page-content
      fingerprint before accepting the page or assigning positional
      `source_row_id` values, so a replay is idempotent and does not duplicate work.
- [x] Maintain a separate scan-wide map keyed by canonical logical-company ID so
      the first company row is retained exactly once across all page boundaries.
- [x] Add each later source row for an existing `company_id` to the duplicate-row
      report without generating deliverables from it.
- [x] Ensure output order is deterministic but never use ordering as identity.
- [x] Verify that results are invariant across supported page sizes.

### 4. Define what the loader must guarantee

- [x] Extend the loader/page contract with enough evidence to prove a complete,
      stable scan—for example a snapshot token plus a reliable total count, or a
      server-issued traversal/version identifier.
- [x] Compare the collected accepted-row count with independent source evidence
      before declaring success; positional `source_row_id` uniqueness follows from
      the assignment rule and is not evidence that no source rows were missed.
- [x] Accept exact replayed pages only when their contents match the earlier page
      and traversal can still make progress.
- [x] Refuse stalled, cycling, truncated-without-cursor, and silently short
      traversals when completeness cannot be proved.
- [x] Refuse offset pagination over a changing ordering unless the service
      supplies snapshot consistency or a stable unique sort key. Client-side
      deduplication alone cannot recover rows that were never returned.

### 5. Generate the campaign from the canonical set

- [x] Generate deliverables only after collection and identity resolution finish
      successfully; do not publish partial output from an incomplete scan.
- [x] Include the skipped-row report in the plan result so a campaign may be
      complete for all retained valid companies without concealing invalid or
      duplicate input rows.
- [x] Create one campaign group per canonical company and exactly one record per
      required asset type.
- [x] Apply the current request's `brand_kit_id` and `template_id` uniformly.
      Do not allow stale saved account settings to override the explicit request.
- [x] Retain source-row provenance on every deliverable.
- [x] Set `complete=True` only after the independent coverage check passes;
      otherwise return a structured failure and no publishable plan.

### 6. Replace the self-referential coverage check

- [ ] Derive the expected canonical company set from independently collected
      source records, not from `plan.source_row_ids`.
- [ ] Compare exact sets and report missing, unexpected, and duplicated companies
      separately.
- [ ] Compare deliverables as a multiset keyed by `(company_id, asset_type)` so
      duplicate assets cannot disappear inside a Python `set`.
- [ ] Require exactly one of every required asset type per company.
- [ ] Validate source-row traceability, company identity, brand kit, template,
      and the completion evidence.
- [ ] Verify that every source row is represented either by a valid canonical
      company/provenance entry or by exactly one skipped-row diagnostic, including
      a distinct duplicate classification.
- [ ] Return structured diagnostics suitable for the demo and audit reports.

### 7. Add regression and property-oriented tests

- [ ] Add tests for every loader in `src/sources.py`, classifying each as safely
      recoverable or necessarily rejected.
- [ ] Assert that normal pagination yields the same canonical companies and
      deliverables for page sizes 1, 10, 25, 100, and sizes larger than the list.
- [ ] Assert that exact page replay does not duplicate source rows, companies, or
      deliverables.
- [ ] Assert prompt failure for stalled cursors, cycles, and missing cursors.
- [ ] Assert refusal for silent truncation and unstable reordering unless the
      enhanced loader contract supplies trustworthy completeness evidence.
- [ ] Test duplicate companies split across page boundaries, positional
      `source_row_id` assignment, null/missing/blank company IDs, conflicting
      records sharing a company ID, empty lists, and a final short page. Duplicate
      company rows must retain the first row, report and skip later rows, and
      produce only one company's assets.
      Each invalid company ID case must skip only the affected row, identify its
      source row and reason, and leave valid rows eligible for a complete campaign.
- [ ] Mutate a valid plan by removing or duplicating companies/assets and by
      changing brand/template IDs; every mutation must fail coverage.
- [ ] Run the same checks against `fixtures/second_list.json` to demonstrate that
      the solution generalizes beyond the reported fixture.

### 8. Update reporting and operational behavior

- [ ] Keep `make demo`, `make test`, `make verify`, and `make audit` working.
- [ ] Make demo/audit output distinguish `complete`, `rejected`, and `failed`
      rather than presenting every returned dictionary as a completed campaign.
- [ ] Report counts for source rows, canonical companies, duplicate rows merged,
      rejected identities, and generated deliverables.
- [ ] Document which historical paging shapes are handled and which are refused,
      including why refusal is the only honest outcome.
