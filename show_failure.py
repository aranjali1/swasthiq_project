"""A small, reproducible failure for the required analysis video."""
from backend.agent import run

case = {
    "conversation_id": "video_date_conflict",
    "today": "2026-10-01",
    "turns": [
        "Dr. Rao ke saath kal, 3 tareekh ko appointment chahiye. "
        "Harpreet Singh, 9812200311."
    ],
}

result = run(case)
print("Caller said: kal (2 October) and 3 tareekh (3 October).")
print("Agent outcome:", result["terminal_state"])
print("Final reply:", result["reply"])
print("Why this is wrong: the date is contradictory; the agent should clarify before booking.")
