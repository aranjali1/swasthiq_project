# Decisions and ambiguities

1. **No LLM dependency.** The brief allows any LLM API but does not supply a key. A deterministic conversation policy meets the fixed JSON contract and avoids off-schema model output entirely. The tradeoff is limited phrasing coverage. I did not claim a model was used or invent token usage.

2. **Fresh state per run versus same-slot races.** The starter pack requires every `POST /agent/run` to start from the original `clinic.json`; the brief also requires that two callers cannot reserve the same slot. Those conflict if two independent requests are treated as one live clinic. I follow the explicit grading contract by isolating each run. Within a shared tool context, writes take a lock and check availability before mutation; the concurrency test proves only one of two racing bookings succeeds there. A production service would use a shared transactional store and would not reset between calls.

3. **A misleading sample response in `schema.md`.** Its example `cv_0001` names `pt_0014` and describes 3 October 09:30, but the actual `cv_0001.json` caller is Harpreet Singh, `pt_0013`. I treat the schema's response as a shape example and the conversation script plus `clinic.json` as the facts.

4. **The `cv_0005` description says the clinic does not work at all, but the actual conversation asks for Sunday, not the 2 October holiday.** I handle both: Sunday has no doctor windows and the holiday blocks all slots.

5. **The React figures are static mockups with fictional counters and a September date that differ from the October test data.** I matched their structure and style while computing counters from the 15 supplied examples. Time is shown as an em dash because scripts have no call timestamp; making one up would be misleading.

6. **Tool-call position in the transcript.** The runner sends the entire fixed caller script in one request. The policy reviews every turn before invoking a tool so an emergency in the final turn can preempt a booking. The detail screen therefore places the actual calls after the caller turns, in their real order, followed by the final reply.

7. **Identity and authorisation.** A phone plus a specific patient name can identify a patient for this synthetic exercise. A shared household phone is not enough to choose between children; the child's first name and a listed guardian relation are required. A neighbour cannot act on a patient record. This is an assignment policy, not a production identity-verification system.

8. **Incomplete requests.** An empty or unresolved request becomes `abandoned` when no human action is needed. Multiple patient matches or an appointment that cannot be uniquely identified go to a human. An attempted bulk administrative action is `refused`, because it does not create a legitimate handoff.

9. **Clinical safety.** A symptom phrase indicating a current emergency takes priority over every booking step, even if it appears in the last turn. Medication and diagnosis questions escalate as `medical_advice`. The policy gives no dosage or diagnosis. A finite phrase list remains a limitation, so deployment in a real clinic would need clinical review and a broader evaluated safety system.

10. **UI handoff resolution.** The required evaluation contract exposes only `POST /agent/run`. I made Resolve a local UI action so the requested screen is usable without inventing a persistence API. It resets on reload.

11. **Date source.** All relative dates use request `today`, never the server clock. A correction later in a turn or later in the conversation wins. The clinic's overlapping Monday windows are combined into one set of slots.
