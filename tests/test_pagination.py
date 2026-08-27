from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from repair_lab import (
    PaginationError,
    TargetAccountTool,
    ToolPage,
    build_campaign_plan,
    evaluate_campaign_coverage,
)
from sources import (
    CyclingLoader,
    ReorderingLoader,
    ReplayingLoader,
    SilentlyShortLoader,
    StallingLoader,
    TruncatedWithoutCursorLoader,
)


class CampaignPaginationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.accounts = json.loads(
            Path("fixtures/target_accounts.json").read_text()
        )
        request = json.loads(Path("fixtures/request.json").read_text())
        self.brand_kit_id = request["brand_kit"]["id"]
        self.template_id = request["template"]["id"]

    def build(self, loader: object, *, page_size: int = 25) -> dict:
        return build_campaign_plan(
            loader,
            brand_kit_id=self.brand_kit_id,
            template_id=self.template_id,
            page_size=page_size,
        )

    def test_identity_skips_invalid_and_later_duplicate_rows(self) -> None:
        accounts = [
            {"id": "ignored-a", "company_id": "a", "company_name": "A"},
            {"id": "ignored-null", "company_id": None, "company_name": "?"},
            {"id": "ignored-dup", "company_id": "a", "company_name": "A2"},
            {"id": "ignored-b", "company_id": "b", "company_name": "B"},
        ]

        plan = self.build(TargetAccountTool(accounts), page_size=2)

        self.assertEqual(plan["source_row_ids"], ["0", "3"])
        self.assertEqual(
            {item["company_id"] for item in plan["deliverables"]}, {"a", "b"}
        )
        self.assertEqual(
            plan["skipped_rows"],
            [
                {"source_row_id": "1", "reason": "missing_company_id"},
                {
                    "source_row_id": "2",
                    "reason": "duplicate_company_id",
                    "company_id": "a",
                    "retained_source_row_id": "0",
                    "differing_fields": ["company_name", "id"],
                },
            ],
        )

    def test_page_size_does_not_change_companies_or_deliverables(self) -> None:
        plans = {
            size: self.build(TargetAccountTool(self.accounts), page_size=size)
            for size in (1, 10, 25, 100, 500)
        }

        expected_companies = {
            item["company_id"] for item in plans[25]["deliverables"]
        }
        expected_assets = {
            (item["company_id"], item["asset_type"])
            for item in plans[25]["deliverables"]
        }
        for plan in plans.values():
            self.assertEqual(
                {item["company_id"] for item in plan["deliverables"]},
                expected_companies,
            )
            self.assertEqual(
                {
                    (item["company_id"], item["asset_type"])
                    for item in plan["deliverables"]
                },
                expected_assets,
            )
            self.assertEqual(len(plan["source_row_ids"]), 203)
            self.assertEqual(len(plan["skipped_rows"]), 20)

    def test_identical_company_rows_across_pages_are_reported_as_duplicate(
        self,
    ) -> None:
        repeated = {"company_id": "same", "company_name": "Same Company"}
        accounts = [dict(repeated), dict(repeated)]

        plan = self.build(TargetAccountTool(accounts), page_size=1)

        self.assertEqual(plan["source_row_ids"], ["0"])
        self.assertEqual(len(plan["deliverables"]), 4)
        self.assertEqual(
            plan["skipped_rows"],
            [
                {
                    "source_row_id": "1",
                    "reason": "duplicate_company_id",
                    "company_id": "same",
                    "retained_source_row_id": "0",
                    "differing_fields": [],
                }
            ],
        )

    def test_replayed_pages_are_idempotent(self) -> None:
        ordinary = self.build(TargetAccountTool(self.accounts))
        replayed = self.build(ReplayingLoader(self.accounts))

        self.assertEqual(replayed["source_row_ids"], ordinary["source_row_ids"])
        self.assertEqual(replayed["deliverables"], ordinary["deliverables"])
        self.assertEqual(replayed["skipped_rows"], ordinary["skipped_rows"])
        self.assertTrue(any(page["replayed"] for page in replayed["pagination"]))

    def test_malformed_cursor_traversals_fail_promptly(self) -> None:
        cases = (
            (StallingLoader, "stalled_cursor"),
            (CyclingLoader, "cursor_cycle"),
            (TruncatedWithoutCursorLoader, "missing_cursor"),
        )
        for loader_class, code in cases:
            with self.subTest(loader=loader_class.__name__):
                with self.assertRaises(PaginationError) as raised:
                    self.build(loader_class(self.accounts))
                self.assertEqual(raised.exception.code, code)
                self.assertLess(len(raised.exception.pages), 20)

    def test_incomplete_and_unstable_sources_are_rejected(self) -> None:
        cases = (
            (SilentlyShortLoader, "incomplete_source"),
            (ReorderingLoader, "snapshot_changed"),
        )
        for loader_class, code in cases:
            with self.subTest(loader=loader_class.__name__):
                with self.assertRaises(PaginationError) as raised:
                    self.build(loader_class(self.accounts))
                self.assertEqual(raised.exception.code, code)

    def test_source_must_supply_snapshot_and_total(self) -> None:
        class LoaderWithoutEvidence:
            def load_page(
                self, *, cursor: str | None = None, page_size: int = 25
            ) -> ToolPage:
                return ToolPage(rows=[], next_cursor=None, truncated=False)

        with self.assertRaises(PaginationError) as raised:
            self.build(LoaderWithoutEvidence())
        self.assertEqual(raised.exception.code, "missing_snapshot")

    def test_plan_uses_request_configuration_and_records_completion_evidence(
        self,
    ) -> None:
        accounts = [
            {
                "company_id": "company-a",
                "company_name": "Company A",
                "saved_brand_kit_id": "stale-brand-kit",
                "saved_template_id": "stale-template",
            }
        ]

        plan = self.build(TargetAccountTool(accounts))

        self.assertTrue(plan["complete"])
        self.assertEqual(
            {item["brand_kit_id"] for item in plan["deliverables"]},
            {self.brand_kit_id},
        )
        self.assertEqual(
            {item["template_id"] for item in plan["deliverables"]},
            {self.template_id},
        )
        self.assertEqual(
            plan["source_evidence"]["expected_row_count"], 1
        )
        self.assertEqual(
            plan["source_evidence"]["observed_row_count"], 1
        )
        self.assertEqual(
            plan["completion_evidence"],
            {
                "canonical_company_count": 1,
                "expected_deliverable_count": 4,
                "observed_deliverable_count": 4,
                "validated": True,
            },
        )

    def test_coverage_rejects_every_customer_visible_plan_mutation(self) -> None:
        plan = self.build(TargetAccountTool(self.accounts))
        passed, detail = evaluate_campaign_coverage(plan, self.accounts)
        self.assertTrue(passed, detail)
        self.assertEqual(detail["code"], "complete")

        first_company = plan["deliverables"][0]["company_id"]
        last_company = plan["deliverables"][-1]["company_id"]
        mutations: list[tuple[str, dict, str]] = []

        missing_company = deepcopy(plan)
        missing_company["deliverables"] = [
            item
            for item in missing_company["deliverables"]
            if item["company_id"] != first_company
        ]
        mutations.append(("missing company", missing_company, "company_mismatch"))

        duplicated_company = deepcopy(plan)
        duplicated_company["deliverables"] += [
            deepcopy(item)
            for item in plan["deliverables"]
            if item["company_id"] == first_company
        ]
        mutations.append(
            ("duplicated company", duplicated_company, "duplicate_deliverables")
        )

        wrong_brand = deepcopy(plan)
        for item in wrong_brand["deliverables"]:
            item["brand_kit_id"] = "wrong-brand"
        mutations.append(
            ("wrong brand", wrong_brand, "request_configuration_mismatch")
        )

        wrong_template = deepcopy(plan)
        for item in wrong_template["deliverables"]:
            item["template_id"] = "wrong-template"
        mutations.append(
            ("wrong template", wrong_template, "request_configuration_mismatch")
        )

        missing_asset = deepcopy(plan)
        for index, item in enumerate(missing_asset["deliverables"]):
            if item["company_id"] == last_company:
                missing_asset["deliverables"].pop(index)
                break
        mutations.append(
            ("missing asset", missing_asset, "deliverable_mismatch")
        )

        for label, variant, expected_code in mutations:
            with self.subTest(mutation=label):
                passed, detail = evaluate_campaign_coverage(variant, self.accounts)
                self.assertFalse(passed)
                self.assertEqual(detail["code"], expected_code)

    def test_empty_and_final_short_pages_complete(self) -> None:
        for accounts, page_size in (([], 25), (self.accounts[:3], 2)):
            with self.subTest(row_count=len(accounts)):
                plan = self.build(TargetAccountTool(accounts), page_size=page_size)
                passed, detail = evaluate_campaign_coverage(plan, accounts)
                self.assertTrue(passed, detail)
                self.assertEqual(
                    plan["source_evidence"]["observed_row_count"], len(accounts)
                )

    def test_all_invalid_company_id_shapes_are_reported(self) -> None:
        accounts = [
            {"company_name": "Missing"},
            {"company_id": None, "company_name": "Null"},
            {"company_id": "  ", "company_name": "Blank"},
            {"company_id": "valid", "company_name": "Valid"},
        ]

        plan = self.build(TargetAccountTool(accounts), page_size=2)

        self.assertEqual(plan["source_row_ids"], ["3"])
        self.assertEqual(
            plan["skipped_rows"],
            [
                {"source_row_id": "0", "reason": "missing_company_id"},
                {"source_row_id": "1", "reason": "missing_company_id"},
                {"source_row_id": "2", "reason": "missing_company_id"},
            ],
        )

    def test_second_list_is_page_size_invariant(self) -> None:
        accounts = json.loads(Path("fixtures/second_list.json").read_text())
        plans = {
            size: self.build(TargetAccountTool(accounts), page_size=size)
            for size in (1, 10, 25, 100, 500)
        }
        expected = [
            (item["company_id"], item["asset_type"])
            for item in plans[25]["deliverables"]
        ]
        for plan in plans.values():
            self.assertEqual(
                [
                    (item["company_id"], item["asset_type"])
                    for item in plan["deliverables"]
                ],
                expected,
            )
            passed, detail = evaluate_campaign_coverage(plan, accounts)
            self.assertTrue(passed, detail)


if __name__ == "__main__":
    unittest.main()
