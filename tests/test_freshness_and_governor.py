from __future__ import annotations

import unittest
from datetime import datetime, timezone

from search import (
    SEARCH_GOAL_LATEST,
    SearchResult,
    _score_result,
    build_query_variants,
    detect_query_intent,
    freshness_for_range,
    preview_search_plan,
)


class FreshnessAndGovernorTests(unittest.TestCase):
    def test_gb_clp_latest_expands_to_source_update_queries(self) -> None:
        variants = build_query_variants(
            "GB CLP",
            "Chemicals / REACH / RoHS / PFAS",
            "quick",
            search_goal=SEARCH_GOAL_LATEST,
        )
        joined = "\n".join(variants).lower()
        self.assertIn("gb clp", joined)
        self.assertIn("hse", joined)
        self.assertIn(str(datetime.now(timezone.utc).year), joined)
        self.assertGreaterEqual(len(variants), 2)

    def test_freshness_mapping(self) -> None:
        self.assertEqual(freshness_for_range("30d"), "pm")
        self.assertEqual(freshness_for_range("1y"), "py")
        self.assertIn("to", freshness_for_range("90d") or "")
        self.assertIsNone(freshness_for_range("all"))

    def test_governor_and_topic_are_bound_together(self) -> None:
        intent = detect_query_intent("California Governor PFAS")
        self.assertEqual(intent.kind, "governor_topic")
        self.assertEqual(intent.state, "California")
        self.assertIn("governor", intent.required_terms)
        self.assertIn("pfas", intent.required_terms)

        plan = preview_search_plan(
            "California Governor PFAS",
            ["US States"],
            search_mode="quick",
            topic="Chemicals / REACH / RoHS / PFAS",
            search_goal=SEARCH_GOAL_LATEST,
            time_range="1y",
        )
        self.assertTrue(plan["actual_queries"])
        for actual in plan["actual_queries"]:
            lowered = actual.lower()
            self.assertIn("governor", lowered)
            self.assertIn("pfas", lowered)

    def test_recent_hse_update_beats_old_uk_law_for_latest_goal(self) -> None:
        query = "GB CLP"
        intent = detect_query_intent(query)
        recent = SearchResult(
            title="Changes to the GB CLP Regulation - updated guidance",
            url="https://www.hse.gov.uk/chemical-classification/legal/changes-gb-clp-regulation.htm",
            snippet="Official HSE update on GB CLP changes and implementation.",
            published_date=f"{datetime.now(timezone.utc).year}-05-20",
        )
        old = SearchResult(
            title="The Chemicals (Hazard Information and Packaging for Supply) Regulations 2009",
            url="https://www.legislation.gov.uk/uksi/2009/716/contents",
            snippet="Historic chemicals regulations.",
            published_date="2009-04-06",
        )
        recent_score, _ = _score_result(
            recent,
            query,
            ["UK"],
            "Chemicals / REACH / RoHS / PFAS",
            intent,
            SEARCH_GOAL_LATEST,
        )
        old_score, _ = _score_result(
            old,
            query,
            ["UK"],
            "Chemicals / REACH / RoHS / PFAS",
            intent,
            SEARCH_GOAL_LATEST,
        )
        self.assertGreater(recent_score, old_score)


if __name__ == "__main__":
    unittest.main()
