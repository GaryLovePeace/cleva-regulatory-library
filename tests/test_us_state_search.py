from __future__ import annotations

import unittest

from search import build_query_variants, detect_query_intent, resolve_jurisdictions
from source_registry import all_domains, filtered_sources
from us_state_sources import US_STATE_NAMES, state_domains


class USStateRoutingTests(unittest.TestCase):
    def test_all_states_and_dc_present(self) -> None:
        self.assertEqual(len(US_STATE_NAMES), 51)
        self.assertIn("California", US_STATE_NAMES)
        self.assertIn("District of Columbia", US_STATE_NAMES)

    def assert_bill(self, query: str, state: str, citation: str) -> None:
        intent = detect_query_intent(query)
        self.assertEqual(intent.kind, "us_state_bill")
        self.assertEqual(intent.state, state)
        self.assertEqual(intent.citation, citation)
        self.assertEqual(resolve_jurisdictions(query, ["US Federal", "US States"]), ["US States"])

    def test_common_bill_formats(self) -> None:
        examples = [
            ("California SB343 recyclable labels", "California", "SB 343"),
            ("Minnesota HF 3911 packaging", "Minnesota", "HF 3911"),
            ("Iowa SF 550", "Iowa", "SF 550"),
            ("Maine LD1541 PFAS", "Maine", "LD 1541"),
            ("Nebraska LB 123", "Nebraska", "LB 123"),
            ("New York A1234", "New York", "A 1234"),
            ("New Jersey S 5678", "New Jersey", "S 5678"),
            ("Massachusetts H. 321", "Massachusetts", "H 321"),
            ("Texas HB 3", "Texas", "HB 3"),
            ("District of Columbia B25-0123", "District of Columbia", "B 25-0123"),
        ]
        for query, state, citation in examples:
            with self.subTest(query=query):
                self.assert_bill(query, state, citation)

    def test_state_hint_supports_bill_only_query(self) -> None:
        intent = detect_query_intent("HB 1234 packaging", "Texas")
        self.assertEqual(intent.kind, "us_state_bill")
        self.assertEqual(intent.state, "Texas")
        self.assertEqual(intent.citation, "HB 1234")

    def test_missing_state_is_not_searched_as_exact_bill(self) -> None:
        intent = detect_query_intent("HB 1234 packaging")
        self.assertEqual(intent.kind, "us_state_bill_missing_state")

    def test_state_domain_filter(self) -> None:
        domains = all_domains(
            ["US States"], scope="official", topic="Packaging / PPWR / EPR", selected_states=["Texas"]
        )
        self.assertIn("capitol.texas.gov", domains)
        self.assertIn("tceq.texas.gov", domains)
        self.assertNotIn("leginfo.legislature.ca.gov", domains)

    def test_every_state_has_legislature_and_environment_source(self) -> None:
        for state in US_STATE_NAMES:
            with self.subTest(state=state):
                self.assertGreaterEqual(len(state_domains(state)), 2)
                rows = filtered_sources(["US States"], selected_states=[state])
                official_state_rows = [row for row in rows if row.get("state") == state and row.get("is_official")]
                self.assertTrue(any(row.get("level") == "A" for row in official_state_rows))
                self.assertTrue(any(row.get("level") == "B" for row in official_state_rows))

    def test_exact_variant_contains_state_and_citation(self) -> None:
        variants = build_query_variants("Washington SB 5284", "All", "quick")
        self.assertEqual(variants, ['"SB 5284" "Washington"'])


if __name__ == "__main__":
    unittest.main()
