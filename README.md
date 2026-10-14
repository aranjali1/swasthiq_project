# Sunrise Clinic front desk

This is a small, deterministic front desk agent over the synthetic `clinic.json` data. It has a Python REST API, six clinic tools, and a React review UI with a handoff queue and conversation detail. The UI follows the two layouts in the brief; the data shown is from the supplied example conversations.

Live app: [swasthiq-front-desk.onrender.com](https://swasthiq-front-desk.onrender.com). It runs on Render's free plan, so the first request after inactivity can be slow.

## Run

From the repository root:

```bash
./run.sh
```

This installs frontend dependencies on the first run, builds the React app, and starts the API and UI at `http://localhost:8000`. It needs Python 3.9+, Node.js, and npm. No API key is needed. For manual development, run `npm run dev` in `frontend/` and `python3 -m backend.server` in the repository root.

`Dockerfile` builds the same frontend and API for a container host. The local command binds to localhost; the container command binds to the host-provided network interface.

## Evaluation API

`POST /agent/run` accepts:

```json
{"conversation_id":"cv_0001","today":"2026-10-01","turns":["Dr. Rao ke saath appointment chahiye.","3 tareekh subah. Harpreet Singh, 9812200311."]}
```

The response follows `schema.md`: `conversation_id`, ordered `tool_calls`, `terminal_state`, `escalation_reason`, `patient_id`, `appointment_id`, `reply`, and `metrics`. Bad request bodies return HTTP 400 with an actionable `error`. `GET /api/examples` supports the review UI and is outside the evaluation endpoint.

The six tool methods live in `backend/tools.py`: `lookup_patient`, `search_slots`, `book_appointment`, `reschedule_appointment`, `cancel_appointment`, and `escalate_to_human`. Writes are locked and recheck availability. Each HTTP run loads a fresh clinic snapshot, as the supplied harness requires. The tool layer never calls a language model.

## Model and efficiency

**Model used: none.** I chose a bounded deterministic parser and policy instead of an LLM call. That keeps actions repeatable, avoids a key dependency, and lets the tool layer be the only source for patient, slot, and appointment facts. The `tokens` metric is therefore **0 for every conversation**. `latency_ms` measures the policy and tool work in process. The table is one local run; values vary with machine load and are not a hosted latency claim.

| Conversation | Tokens | Latency (ms) |
|---|---:|---:|
| cv_0001 | 0 | 8 |
| cv_0002 | 0 | 2 |
| cv_0003 | 0 | 2 |
| cv_0004 | 0 | 1 |
| cv_0005 | 0 | 1 |
| cv_0006 | 0 | 2 |
| cv_0007 | 0 | 1 |
| cv_0008 | 0 | 1 |
| cv_0009 | 0 | 1 |
| cv_0010 | 0 | 1 |
| cv_0011 | 0 | 1 |
| cv_0012 | 0 | 2 |
| cv_0013 | 0 | 1 |
| cv_0014 | 0 | 1 |
| cv_0015 | 0 | 2 |

The policy scans the full fixed script for urgent symptoms before any mutation. It then handles advice requests, injected administrative instructions, identity and guardian checks, date/time corrections, and booking operations. This approach has a known vocabulary limit: a novel phrasing outside its patterns may need a new rule. See `DECISIONS.md`.

## Checks

```bash
python3 -m unittest discover -s backend/tests -v
python3 runner.py --repeat 3
python3 runner.py --dir adversarial --out results/adversarial --repeat 3
```

On this checkout, all **15 supplied scripts** and **8 adversarial scripts** matched their expected terminal states and required/forbidden tool sets. Both groups had stable fingerprints across three runs. The tests also cover a concurrent same-slot race, malformed tool arguments, and an emergency that interrupts booking.

## Repository map

- `backend/`: API, conversation policy, tool layer, tests.
- `frontend/`: React application and build configuration.
- `adversarial/`: eight original scripts in the supplied format.
- `AI_TRANSCRIPT.txt`: the actual user prompt given to the coding assistant.
- `DECISIONS.md`: data and brief ambiguities, choices, and limits.
- `VIDEO_GUIDE.md`: a three-minute failure analysis outline for recording.
- `show_failure.py`: prints a reproducible date-conflict failure for that video.

The UI's Resolve control changes local review state only. The assignment's API contract does not include a persisted handoff queue or resolution endpoint.
