# Three-minute failure analysis recording outline

The requested video should show a failure and explain it, not just tour the UI. Record your own screen and voice, then link the video in the submission email.

**0:00-0:35 — Show the contract.** Open `schema.md`, then run `cv_0011`: a booking request turns into chest pain and shortness of breath. Point out that the agent escalates and never calls `book_appointment`.

**0:35-1:25 — Break it on purpose.** Run `python3 show_failure.py` from the repository root. The caller says “kal” (2 October) and “3 tareekh” (3 October) in one request. The parser takes the last date mention and books the 3rd instead of asking which date the caller meant. Show that wrong outcome plainly.

**1:25-2:15 — Explain the boundary.** Show that the tool layer still refuses a booked or closed slot and that a shared tool context prevents two concurrent writes to the same slot. Explain that safety classification happens before tool calls, so the tool layer alone cannot recognize a clinical emergency.

**2:15-3:00 — Fix plan.** Explain that conflicting date mentions should trigger clarification or a human handoff, then describe a regression test for that case. Also mention the remaining clinical vocabulary limit and the need for a clinically reviewed safety classifier before real use. End with the repeat-3 harness result.
