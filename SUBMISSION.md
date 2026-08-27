# Submission

- Transcript (file or link): https://chatgpt.com/s/cx_6a8f9f687d688191b5a1748bcdc6b97f
- Is that the raw session log, or a summary written afterwards? We want the raw log, dead ends included. A tidied narrative scores lower than a messy real one.
- `make demo` output:
  PYTHONPATH=src python3 demo.py
  list : fixtures/target_accounts.json
  uploaded rows : 223
  brand kit selected on request : brand-kit-meridian-2026
  template selected on request : template-abm-q3

                                    page_size=10    page_size=25   page_size=100

  status complete complete complete
  source rows read 223 223 223
  rows campaigned 203 203 203
  invalid rows skipped 6 6 6
  duplicate rows skipped 14 14 14
  deliverables 812 812 812
  distinct company_id in plan 203 203 203
  complete flag True True True

deliverables by brand kit (page_size=25):
brand-kit-meridian-2026 812

skipped source rows (page_size=25):
source_row_id=12 missing_company_id
source_row_id=18 duplicate_company_id company_id=company-alder-health retained_source_row_id=17
source_row_id=32 duplicate_company_id company_id=company-ironwood-partners retained_source_row_id=31
source_row_id=37 missing_company_id
source_row_id=47 duplicate_company_id company_id=company-vantage-capital retained_source_row_id=46
source_row_id=61 missing_company_id
source_row_id=74 duplicate_company_id company_id=company-kestrel-robotics retained_source_row_id=73
source_row_id=98 missing_company_id
source_row_id=103 duplicate_company_id company_id=company-sable-works retained_source_row_id=102
source_row_id=104 duplicate_company_id company_id=company-sable-works retained_source_row_id=102
source_row_id=106 duplicate_company_id company_id=company-copperline-group retained_source_row_id=105
source_row_id=109 duplicate_company_id company_id=company-bright-foods retained_source_row_id=108
source_row_id=115 duplicate_company_id company_id=company-copperline-energy retained_source_row_id=114
source_row_id=149 missing_company_id
source_row_id=202 missing_company_id
source_row_id=218 duplicate_company_id company_id=company-kestrel-dynamics retained_source_row_id=111
source_row_id=219 duplicate_company_id company_id=company-harbor-group retained_source_row_id=122
source_row_id=220 duplicate_company_id company_id=company-ironwood-logistics retained_source_row_id=132
source_row_id=221 duplicate_company_id company_id=company-vantage-networks retained_source_row_id=142
source_row_id=222 duplicate_company_id company_id=company-tessellate-energy retained_source_row_id=183

coverage check returned : True
coverage check detail : {"canonical_company_count": 203, "code": "complete", "deliverable_count": 812, "message": "every canonical company has exactly the requested assets", "skipped_row_count": 20, "source_row_count": 223}

- `make test` output:
  PYTHONPATH=src python3 -m unittest discover -s tests -v
  test_all_invalid_company_id_shapes_are_reported (test_pagination.CampaignPaginationTest.test_all_invalid_company_id_shapes_are_reported) ... ok
  test_coverage_rejects_every_customer_visible_plan_mutation (test_pagination.CampaignPaginationTest.test_coverage_rejects_every_customer_visible_plan_mutation) ... ok
  test_empty_and_final_short_pages_complete (test_pagination.CampaignPaginationTest.test_empty_and_final_short_pages_complete) ... ok
  test_identical_company_rows_across_pages_are_reported_as_duplicate (test_pagination.CampaignPaginationTest.test_identical_company_rows_across_pages_are_reported_as_duplicate) ... ok
  test_identity_skips_invalid_and_later_duplicate_rows (test_pagination.CampaignPaginationTest.test_identity_skips_invalid_and_later_duplicate_rows) ... ok
  test_incomplete_and_unstable_sources_are_rejected (test_pagination.CampaignPaginationTest.test_incomplete_and_unstable_sources_are_rejected) ... ok
  test_malformed_cursor_traversals_fail_promptly (test_pagination.CampaignPaginationTest.test_malformed_cursor_traversals_fail_promptly) ... ok
  test_page_size_does_not_change_companies_or_deliverables (test_pagination.CampaignPaginationTest.test_page_size_does_not_change_companies_or_deliverables) ... ok
  test_plan_uses_request_configuration_and_records_completion_evidence (test_pagination.CampaignPaginationTest.test_plan_uses_request_configuration_and_records_completion_evidence) ... ok
  test_replayed_pages_are_idempotent (test_pagination.CampaignPaginationTest.test_replayed_pages_are_idempotent) ... ok
  test_second_list_is_page_size_invariant (test_pagination.CampaignPaginationTest.test_second_list_is_page_size_invariant) ... ok
  test_source_must_supply_snapshot_and_total (test_pagination.CampaignPaginationTest.test_source_must_supply_snapshot_and_total) ... ok
  test_supplied_evaluator_accepts_the_published_plan (test_visible.SuppliedEvaluatorSmokeTest.test_supplied_evaluator_accepts_the_published_plan) ... ok

---

Ran 13 tests in 0.078s

OK

- `make verify` output:
  PYTHONPATH=src python3 demo.py --list fixtures/second_list.json
  list : fixtures/second_list.json
  uploaded rows : 115
  brand kit selected on request : brand-kit-meridian-2026
  template selected on request : template-abm-q3

                                    page_size=10    page_size=25   page_size=100

  status complete complete complete
  source rows read 115 115 115
  rows campaigned 97 97 97
  invalid rows skipped 2 2 2
  duplicate rows skipped 16 16 16
  deliverables 388 388 388
  distinct company_id in plan 97 97 97
  complete flag True True True

deliverables by brand kit (page_size=25):
brand-kit-meridian-2026 388

skipped source rows (page_size=25):
source_row_id=4 duplicate_company_id company_id=company-windrow retained_source_row_id=3
source_row_id=12 duplicate_company_id company_id=company-sable retained_source_row_id=11
source_row_id=20 duplicate_company_id company_id=company-bramble retained_source_row_id=19
source_row_id=24 duplicate_company_id company_id=company-straddle-works retained_source_row_id=23
source_row_id=30 duplicate_company_id company_id=company-kestrel2 retained_source_row_id=29
source_row_id=38 duplicate_company_id company_id=company-pinnacle2 retained_source_row_id=37
source_row_id=46 duplicate_company_id company_id=company-wrenfield2 retained_source_row_id=45
source_row_id=51 duplicate_company_id company_id=company-straddle-works retained_source_row_id=23
source_row_id=55 duplicate_company_id company_id=company-fennel2 retained_source_row_id=54
source_row_id=63 duplicate_company_id company_id=company-talbot3 retained_source_row_id=62
source_row_id=70 missing_company_id
source_row_id=72 duplicate_company_id company_id=company-thistle3 retained_source_row_id=71
source_row_id=80 duplicate_company_id company_id=company-cinder3 retained_source_row_id=79
source_row_id=88 missing_company_id
source_row_id=89 duplicate_company_id company_id=company-ambit4 retained_source_row_id=87
source_row_id=97 duplicate_company_id company_id=company-quill4 retained_source_row_id=96
source_row_id=105 duplicate_company_id company_id=company-yarrow4 retained_source_row_id=104
source_row_id=113 duplicate_company_id company_id=company-garnet4 retained_source_row_id=112

coverage check returned : True
coverage check detail : {"canonical_company_count": 97, "code": "complete", "deliverable_count": 388, "message": "every canonical company has exactly the requested assets", "skipped_row_count": 18, "source_row_count": 115}

- `make audit` output:
  PYTHONPATH=src python3 audit.py
  ====================================================================================================
  A. every paging shape in src/sources.py
  ====================================================================================================

shape status raw invalid duplicate companies assets
TargetAccountTool complete 223 6 14 203 812
ReplayingLoader complete 223 6 14 203 812
StallingLoader rejected stalled_cursor: cursor '50' did not advance on retry
CyclingLoader rejected cursor_cycle: next cursor '25' returns to an earlier page
SilentlyShortLoader rejected incomplete_source: source terminated after 125 of 223 decl
TruncatedWithoutCursorLoader rejected missing_cursor: source reported a truncated page without a
ReorderingLoader rejected snapshot_changed: source snapshot changed from 'reordering

uploaded rows in the list: 223

==============================================================================
B. what the coverage check returns for a clean plan and four broken ones
==============================================================================

calling repair_lab.evaluate_campaign_coverage

clean plan, untouched -> [true, {"code": "complete", "message": "every canonical company has exactly the requested assets", "source_row_count": 223, "canonical_company_count":
40 companies deleted -> [false, {"code": "company_mismatch", "message": "plan companies do not exactly match canonical companies", "missing_company_ids": ["company-alder-capi
one company campaigned twice -> [false, {"code": "duplicate_deliverables", "message": "plan contains duplicate company assets", "duplicate_company_assets": [["company-alder-capital",
every brand kit wrong -> [false, {"code": "request_configuration_mismatch", "message": "deliverables do not use the campaign request configuration", "mismatched_deliverable_co
one company short an asset -> [false, {"code": "deliverable_mismatch", "message": "plan deliverables do not exactly match expected company assets", "missing_deliverable_count": 1,

This command reports. It does not grade, and it is not a test suite.

- How many companies this upload represents, and why that number: 203 logical companies. The upload contains 223 rows, but 6 have a null or blank company_id and 14 are duplicate company_id rows.
- Which paging shapes in `src/sources.py` you handle, which you refuse, and why refusing is the right answer for those: I handle normal pagination and ReplayingLoader, suppressing an exact replay while preserving the original row order. I refuse StallingLoader (stalled_cursor), CyclingLoader (cursor_cycle), SilentlyShortLoader (incomplete_source), TruncatedWithoutCursorLoader (missing_cursor), and ReorderingLoader (snapshot_changed). Refusal is correct because none of those sources can prove a stable, complete traversal; continuing could silently omit, duplicate, or reorder accounts.
- What your coverage check returns for each of the four damaged plans in `make audit`, and what you changed to make it move: It returns company_mismatch when 40 companies are deleted, duplicate_deliverables when one company is campaigned twice, request_configuration_mismatch when every brand kit is wrong, and deliverable_mismatch with one missing deliverable when a company is short one asset.
- The one thing you found yourself rather than took from the agent: I independently verified that the correct company count is 203 by reconciling all 223 input rows: 6 invalid rows and 14 duplicate-company rows must be excluded.
- The claim in this submission you are least sure of, and how you checked it: I was least sure that rejecting reordered pagination was necessary rather than merely conservative. I checked ReorderingLoader and confirmed that its snapshot changes between pages, so combining those pages cannot prove they came from one consistent result set. I also ran the audit and confirmed it is rejected with snapshot_changed.
- Time you actually spent: 2 hours
- Anything a reviewer should know before opening the repository:
