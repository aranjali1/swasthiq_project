# Three-minute failure analysis recording outline

The requested video should show a failure and explain it, not just tour the UI. Record your own screen and voice, then link the video in the submission email.

**0:00-0:35 — Show the contract.** Open `schema.md`, then run `cv_0011`: a booking request turns into chest pain and shortness of breath. Point out that the agent escalates and never calls `book_appointment`.

**0:35-1:25 — Break it on purpose.** Submit: “Dr. Rao ke saath kal, 3 tareekh ko appointment chahiye. Harpreet Singh, 9812200311.” With `today` set to 1 October, “kal” means 2 October, but “3 tareekh” means 3 October. The parser takes the last date mention and may book the 3rd instead of asking which date the caller meant. Show the wrong outcome plainly.

**1:25-2:15 — Explain the boundary.** Show that the tool layer still refuses a booked or closed slot and that a shared tool context prevents two concurrent writes to the same slot. Explain that safety classification happens before tool calls, so the tool layer alone cannot recognize a clinical emergency.

**2:15-3:00 — Fix plan.** Explain that conflicting date mentions should trigger clarification or a human handoff, then describe a regression test for that case. Also mention the remaining clinical vocabulary limit and the need for a clinically reviewed safety classifier before real use. End with the repeat-3 harness result.
