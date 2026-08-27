from __future__ import annotations

import json
import unittest
from pathlib import Path

from repair_lab import PaginationError, TargetAccountTool, build_campaign_plan
from sources import (
    CyclingLoader,
    ReplayingLoader,
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


if __name__ == "__main__":
    unittest.main()
