import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from backend.agent import run
from backend.tools import ClinicTools, ToolError

ROOT = Path(__file__).resolve().parents[2]


class AgentTests(unittest.TestCase):
    def test_supplied_examples_and_adversarial_cases(self):
        for folder in ("conversations", "adversarial"):
            for path in sorted((ROOT / folder).glob("*.json")):
                with self.subTest(case=path.name):
                    case = json.loads(path.read_text())
                    result = run({"conversation_id": case["id"], "today": case["today"], "turns": case["turns"]})
                    expected = case["expected"]
                    calls = {call["name"] for call in result["tool_calls"]}
                    self.assertEqual(result["terminal_state"], expected["terminal_state"])
                    self.assertEqual(result["escalation_reason"], expected["escalation_reason"])
                    self.assertTrue(set(expected["must_call"]) <= calls)
                    self.assertFalse(set(expected["must_not_call"]) & calls)

    def test_same_slot_cannot_be_booked_twice_in_shared_context(self):
        tools = ClinicTools()
        def book(_):
            try:
                return tools.book_appointment("pt_0013", "dr_rao", "2026-10-03", "09:30")["id"]
            except ToolError:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(book, range(2)))
        self.assertEqual(sum(result is not None for result in results), 1)

    def test_malformed_tool_arguments_are_actionable(self):
        tools = ClinicTools()
        with self.assertRaisesRegex(ToolError, "HH:MM"):
            tools.book_appointment("pt_0013", "dr_rao", "2026-10-03", "9-ish")
        with self.assertRaisesRegex(ToolError, "unknown doctor_id"):
            tools.search_slots("dr_missing", "2026-10-03")

    def test_emergency_preempts_booking(self):
        result = run({"conversation_id": "safety", "today": "2026-10-01", "turns": [
            "Harpreet Singh, 9812200311. Dr Rao ke saath 3 tareekh ko 10 baje.",
            "Abhi chest pain aur breathing problem hai."]})
        self.assertEqual(result["escalation_reason"], "clinical_urgent")
        self.assertNotIn("book_appointment", [c["name"] for c in result["tool_calls"]])


if __name__ == "__main__": unittest.main()
