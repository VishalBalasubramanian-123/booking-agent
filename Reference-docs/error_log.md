# Error Log

Running list of every real error hit during implementation/testing, what caused it, and what fixed it. Companion to `decision_log.md` (which covers design decisions and narrates the earlier bug-fixing passes in more prose form) — this file is the quick-scan version: one entry per error, newest at the bottom. Entries for `check_availability`/`check_booking`/`cancel_booking`'s early bugs are only summarized here since `decision_log.md` already covers them in full detail.

---

### 1. `check_availability` — maintenance/lookahead/closing-time bugs
- **Error:** wrong results shape from the maintenance-window branch; lookahead conflict-checking silently non-functional (comparing candidates on one day against bookings on a different day).
- **Cause:** several — `.append([...])` instead of `.extend([...])`, a stray double `datetime.combine()`, `get_closing_time`/`_find_next_free_start` anchored to the wrong date in the 2-day lookahead loop, maintenance not re-checked for lookahead days.
- **Fix:** see `decision_log.md`'s `check_availability` section for the full list.
- **Status:** Fixed.

### 2. `check_booking` — list/dict + timedelta bugs
- **Error:** `TypeError`s and wrong-shaped responses.
- **Cause:** `get_booking_status` returns a list, indexed like a dict; `occupancy_end_time` subtraction attempted between incompatible `time`/`datetime` types.
- **Fix:** see `decision_log.md`'s `check_booking` section.
- **Status:** Fixed.

### 3. `cancel_booking` — filter + guard bugs
- **Error:** update never matched any row; `TypeError` on a `None` booking.
- **Cause:** `update_status` had `.eq("session_id", ...)` duplicated instead of one call being `.eq("reservation_id", ...)`; missing/malformed not-found guard.
- **Fix:** see `decision_log.md`'s `cancel_booking` section.
- **Status:** Fixed.

### 4. `_bucket_gate` return values didn't match the DB enum
- **Error:** every bucket-2 (allergy) escalation would fail at the database level — `bucket` column is `ENUM ('auto', 'verification', 'decision')`, but `_bucket_gate` returned `"bucket 1"`/`"bucket 2"`.
- **Cause:** enum values chosen without checking they matched the actual Postgres enum defined in `db/schema.sql`.
- **Fix:** `_bucket_gate` now returns `"auto"`/`"verification"`; `reserve_table`'s branch condition and `test_bucket_gate` updated to match.
- **Status:** Fixed.

### 5. `reserve_table`: `table_id` referenced before assignment
- **Error:** `UnboundLocalError: local variable 'table_id' referenced before assignment`.
- **Cause:** a `table_id is None` guard was added *above* the line that actually assigns `table_id = get_table_id(table_number)`.
- **Fix:** reordered — assign first, then guard.
- **Status:** Fixed.

### 6. `resolve_verification`: default-argument ordering
- **Error:** `SyntaxError: parameter without a default follows parameter with a default`.
- **Cause:** `answer: str | None = None` given a default while `reason: str` (right after it) had none.
- **Fix:** dropped the unnecessary default from `answer` — it was never actually meant to be optional (the body calls `.strip()` on it unconditionally).
- **Status:** Fixed.

### 7. `verification_to_human`/`reserve_table` argument-count mismatch
- **Error:** `TypeError: verification_to_human() takes 3 positional arguments but 4 were given`.
- **Cause:** `verification_to_human`'s signature dropped the unused `reason` param, but `reserve_table`'s call site wasn't updated to match.
- **Fix:** call site updated to 3 args.
- **Status:** Fixed.

### 8. `handler.py` `ACTIONS` referencing a deleted function
- **Error:** would have crashed the *entire* Lambda handler on import (`AttributeError`), not just one action.
- **Cause:** `"decision_to_human": booking.decision_to_human` left in `ACTIONS` after `decision_to_human` was commented out of `booking.py` (bucket-3 deferred).
- **Fix:** removed the stale entry.
- **Status:** Fixed.

### 9. `handler.py` missing `create_session`/`check_KB` registrations
- **Error:** `ValueError: Unknown action: create_session` / `check_KB`.
- **Cause:** both tools existed on the `agent.py`/business-logic side but were never added to `ACTIONS`.
- **Fix:** registered both (`check_KB` pointed at `kb.check_KB` directly, not through `booking.py`, since `booking.py` never actually exposed it).
- **Status:** Fixed.

### 10. `handler.py` referencing `booking.get_restaurant_name`/`booking.create_session`
- **Error:** would have been `AttributeError` on import (caught in review before ever deploying).
- **Cause:** those functions live in `shared/queries.py`, and `booking.py` never imported them — `handler.py` assumed they were reachable via `booking.*`.
- **Fix:** `handler.py` imports `shared.queries` directly and points those two entries at `queries.get_restaurant_name`/`queries.create_session` instead, since they're plain reads/writes with no real "booking" business logic to go through `booking.py` for.
- **Status:** Fixed.

### 11. `agent.py`: `time` module shadowed by `datetime.time`
- **Error:** would have crashed `_watch_verification`'s `time.sleep(...)` the first time the background watcher thread ran (`AttributeError: type object 'time' has no attribute 'sleep'`) — found while writing `test_agent.py`, before ever hitting it live.
- **Cause:** `import time` (module) immediately followed by `from datetime import ..., time, ...` (class), silently overwriting the name.
- **Fix:** deleted the unused `datetime` import line entirely — nothing in `agent.py` used `date`/`timedelta`/`datetime` as values, only as (harmless) parameter names elsewhere.
- **Status:** Fixed.

### 12. Raw `date`/`time`/`datetime` objects passed into Supabase `.insert()`
- **Error:** not hit live, but a known-broken pattern — Python `date`/`time`/`datetime` objects aren't JSON-serializable, and `book_table` was passing them straight into an `.insert()` call.
- **Cause:** no explicit conversion before the insert.
- **Fix:** `book_table` now calls `.isoformat()` on `date`, `time`, `occupancy_end_time`, and the two hold-window timestamps before inserting.
- **Status:** Fixed.

### 13. RLS silently blocking reads via the publishable/anon Supabase key
- **Error:** `get_restaurant_name()`/`get_tables()` returning empty results (`None`/`[]`) with no error at all, both locally and through the deployed Lambda — despite real data existing in the tables (confirmed via the Supabase dashboard).
- **Cause:** `SUPABASE_KEY` was the `sb_publishable_` (anon) key; Row Level Security silently filters out rows that key has no policy granting access to, rather than erroring.
- **Fix:** switched `SUPABASE_KEY` (local `.env` and later the deployed Lambda's own env var) to the `sb_secret_` (service role) key — a deliberate choice for `tools_lambda` specifically, since it's a trusted backend-only component never exposed to any client, not a blanket RLS bypass recommendation for public-facing keys.
- **Status:** Fixed (granular per-table RLS policies considered as a more least-privilege alternative, explicitly deferred as a later hardening pass, not a blocker).

### 14. Deployed Lambda's env vars stale after the local key swap
- **Error:** `agent.py` startup crash: `KeyError: 0` on `_session[0]["session_id"]`.
- **Cause:** the Lambda's own environment variables were only set once, before the `.env` key swap in #13 — so `create_session()` running *inside* the Lambda still used the old publishable key, hit an RLS policy violation on the `session` INSERT (unlike a blocked SELECT, an RLS-blocked INSERT raises a real Postgres error), and the Lambda returned an error-payload dict (`{"errorMessage": ..., ...}`) instead of the expected list — `_session[0]` then failed with `KeyError: 0` since a dict has no key `0`.
- **Fix:** re-ran `aws lambda update-function-configuration` with the current `.env` values so the deployed Lambda's env matches local.
- **Status:** Fixed.

### 15. `check_availability` response not JSON-serializable through the real Lambda
- **Error:** `FunctionError: "Unhandled"` — `"Unable to marshal response: Object of type date is not JSON serializable"`. Surfaced live as the model apologizing for "a technical issue" mid-conversation and falling back to unrelated questions.
- **Cause:** `check_availability`'s response dicts contain raw `date`/`time` objects (e.g. `{"table": 5, "available": True, "date": date(...), "time": time(...)}`) — fine for mocked unit tests, but AWS Lambda auto-JSON-encodes the handler's return value, and plain `date`/`time` objects aren't serializable. Same underlying issue as #12, on the response side instead of the request side.
- **Fix:** `_json_safe(value)` added to `handler.py` — one recursive conversion choke point applied right before `handler()` returns (dates/times → ISO strings, `timedelta` → seconds, recurses through dicts/lists/tuples). Tests added in `test_handler.py`.
- **Note:** this fix was written once already, reverted on the assumption it might be unreviewed/unnecessary churn, then re-written after live reproduction proved it was a real, necessary bug — see `decision_log.md` for the fuller "near-miss" writeup.
- **Status:** Fixed, verified against the real deployed Lambda.

### 16. Bad deploy zip — dependencies missing after a `build/` rebuild
- **Error:** would have broken the Lambda entirely (`ModuleNotFoundError: No module named 'supabase'`) had it been deployed — caught before deploying, by noticing the zip was 8.4KB instead of the expected ~9MB.
- **Cause:** `build/` was wiped and recreated (`rm -rf build && mkdir build`) before re-zipping, but the `pip install --platform manylinux2014_x86_64 ...` step was skipped that time — only the source code got copied in, no dependencies.
- **Fix:** re-ran the full install step before re-zipping and redeploying.
- **Status:** Fixed (self-caught, no live impact).

### 17. System prompt: model asking for contact info before checking availability
- **Error:** not a crash — a behavior bug. Guest gave date+time+party size in one message; model asked for name/phone before ever calling `check_availability`, contradicting the prompt's own explicit ordering rule.
- **Cause:** the "don't ask for contact info before checking availability" instruction sat several paragraphs away from the "check availability once you have date/time/party" instruction, in a long policy block — easy for the model to deprioritize when a guest provides everything in one dense message.
- **Fix:** restructured `system_prompt.md`'s "Booking & Confirmation" section into an explicit numbered sequence at the top, with direct language ("call check_availability immediately — even if the guest also gave other details... in the same message").
- **Status:** Fixed, confirmed working in a follow-up test conversation.

### 18. Model hallucinating table attributes not present in tool output
- **Error:** model described available tables as "all indoor tables" — `check_availability`'s response never includes a `table_type` field at all.
- **Cause:** no grounded data available, model filled the gap with a plausible-sounding guess, violating the prompt's own "do not guess or invent details" instruction.
- **Fix:** addressed via #20's prompt fix (general "relay tool output verbatim, don't invent" rule). `table_type` still isn't surfaced in `check_availability`'s response — could still be added later as a root-cause fix, but the prompt rule should stop the fabrication either way.
- **Status:** Fixed (prompt-level; revisit surfacing real `table_type` data if it recurs).

### 19. Bedrock `ValidationException` — on-demand invocation not supported for the Claude model
- **Error:** `ValidationException: Invocation of model ID anthropic.claude-haiku-4-5-20251001-v1:0 with on-demand throughput isn't supported. Retry your request with the ID or ARN of an inference profile that contains this model.`
- **Cause:** some newer Bedrock models can only be invoked via an inference profile, not a bare on-demand model ID. The already-working Nova model's `model_id` (`"us.amazon.nova-2-lite-v1:0"`) already demonstrates the required pattern — the `us.` prefix is an inference-profile ID, not part of the model name.
- **Fix:** proposed, not yet applied — prefix the Claude model ID the same way: `"us.anthropic.claude-haiku-4-5-20251001-v1:0"`.
- **Status:** Open.

### 20. Model stating a fabricated "next available time" instead of the tool's real value
- **Error:** after table 6 was booked for Oct 5 2026 12:00 PM (90-min occupancy → free again at 1:30 PM), a second conversation asking about the same slot was told *"table 6 becomes available 30 minutes later (12:30 PM)"* — not possible given the booking.
- **Cause:** same root behavior as #18. Verified via direct, read-only `check_availability` invoke against the real Lambda: the backend correctly returned `"next_available_time": "2026-10-05T13:30:00"`. The model never received "12:30 PM" from any tool — it invented that number composing its reply instead of relaying the tool's actual value. `_find_next_free_start`/`check_availability` themselves are correct; confirmed no code bug.
- **First attempted fix (did not hold):** a prompt-level "relay tool output verbatim, never estimate" rule in `system_prompt.md`, using this exact scenario as its worked example. Re-tested with the identical conversation — model produced almost the same wrong answer again. Confirmed via a second direct Lambda invoke that the backend was still correct, ruling out a data explanation. The failure is specifically that relaying `next_available_time` correctly requires the model to extract the time portion of an ISO timestamp and convert 24h→12h — real computation — and its wrong answer (a suspiciously round "30 minutes later") looks like pattern-matching on typical reservation-slot increments rather than actually doing that conversion. A prompt instruction alone wasn't reliable enough to stop it.
- **Actual fix (code-level):** `tools_lambda/tools/booking.py` now computes human-readable strings itself and hands them to the model as `*_display` companion fields (`next_available_time_display`, `date_display`, `time_display`, `total_time_display`, `alternatives[].display`, `window_display`) — same principle as `_bucket_gate` elsewhere in this project: don't trust the model with computation it doesn't need to do. `alternatives` also restructured from `(date, datetime)` tuples to dicts, consistent with every other branch's shape. `agent.py`'s tool docstrings and the system prompt both reinforce using these fields verbatim, but the code change (removing the need to compute at all) is what actually fixes it, not the reinforcement alone.
- **Status:** Open — the display-field fix is deployed and verified correct at the data level, but a fresh live conversation re-test showed the model *still* stating a wrong value ("12:30 PM") that matches neither the raw field nor the correct display field. This is a step worse than originally diagnosed: it's not that the model had to compute something and got it wrong, the correct pre-computed string was sitting right there and it still wasn't used. Structured logging (#22) was added specifically to get direct visibility into this on the next occurrence, instead of needing manual Lambda invokes to compare. Current leading theory: a model reliability ceiling, not a data/prompt problem — worth testing against a stronger model once available.

### 21. No "today's date" grounding — model guesses a year when one isn't given
- **Error:** guest said "october 5" with no year; model resolved it to **2024** (a year in the past relative to both real time and this project's simulated "today," 2026-09-20) and additionally mislabeled the day of week ("Saturday" — Oct 5 2026 is actually a Monday).
- **Cause:** `agent.py`'s `SYSTEM_PROMPT_TEMPLATE.format(restaurant_name=_restaurant_name)` only ever injects the restaurant's name — nothing anywhere gives the model the actual current date. With no anchor, resolving a year-less date is unconstrained guessing.
- **Fix:** `agent.py` now computes `_today = date.today().strftime(...)` at startup and injects it into the system prompt, same pattern as `restaurant_name`. `system_prompt.md` states "Today's date is {today}" up front, plus explicit guidance to resolve a year-less date against it (nearest upcoming occurrence) rather than leaving that inference implicit.
- **Status:** Fixed (agent-side prompt-only change, no redeploy needed). Live re-test with a year-less date still worth doing to fully confirm.

### 24. `check_KB`/`update_KB` — Bedrock `ValidationException`, "2 schema violations found"
- **Error:** `bedrock.invoke_model(...)` in `tools_lambda/tools/kb.py` failed: `Malformed input request: 2 schema violations found, please reformat your input and try again.`
- **Cause:** `model_id = "amazon.titan-embed-text-v1"` (Titan Embeddings **V1**, the documented/committed model matching the `restaurant_kb.embedding VECTOR(1536)` column), but the request payload included `"dimensions": 1536, "normalize": True` — those are **Titan Embeddings V2**-only fields; V1's request schema only accepts `inputText`. Two extra, unrecognized fields lines up exactly with "2 schema violations." Both `check_KB` and `update_KB` had the identical broken payload shape.
- **Fix:** dropped `dimensions`/`normalize` from both payloads — `{"inputText": ...}` only. Not a reason to switch to V2 instead: V1 is the committed model, and switching would mean re-embedding all existing KB content (V1/V2 embeddings aren't cosine-comparable across versions).
- **Status:** Fixed, `tests/test_kb.py` (6 tests) still passing.

### 25. `restaurant_kb` had no content for opening/closing hours; `THRESHOLD` too strict once added
- **Error:** guest asked "what is the opening and closing hours" / "when does the restaurant open and close" — model correctly said it didn't know. `check_KB` returned `[]` both times.
- **Cause, part 1:** `restaurant_kb` genuinely had no row about hours (5 existing rows: menu, parking, dress code, kids, payment). The old hardcoded hours line in `system_prompt.md` had been removed (it was stale/wrong relative to real `restaurant_info` values) with nothing replacing it — so there was no path anywhere for the model to answer this. Decided to add hours as KB content (reusing the existing `check_KB` mechanism, same as other FAQ topics) rather than a prompt injection — doesn't conflict with the earlier "`closing_hours` bypasses `check_KB`" decision, which was specifically about `check_availability`'s own internal correctness-critical comparison, not guest-facing FAQ answers. New row inserted, embedded via `update_KB()` (which also retroactively embedded the other 5 rows — turns out `update_KB()` had never successfully run before, due to the same #24 payload bug).
- **Cause, part 2:** even after adding and embedding the row, `check_KB` still returned `[]`. Checked raw similarity scores directly (bypassing the threshold): the new row was the clear top match (0.52-0.57 across two different phrasings, next-best always well below at 0.41-0.46) — but `THRESHOLD = 0.75` was filtering out a genuinely correct, clearly-best match. Titan V1 similarity scores for short-query-vs-longer-content pairs apparently sit in a lower absolute range than 0.75 assumes, even for strong true positives.
- **Fix:** `THRESHOLD` lowered to `0.50` in `tools_lambda/tools/kb.py`, verified to correctly include the hours match on two different real phrasings while still excluding the other 4 unrelated rows on both. Noted as a rough calibration from two data points, not a rigorous one — proper tuning belongs to the project's already-scoped-but-not-built RAGAS eval work.
- **Status:** Fixed, verified against the real deployed Lambda (`check_KB` now returns the hours row with `similarity: 0.5227`).

### 26. `reserve_table` never re-checked availability before writing — real double-booking risk
- **Error:** live conversation booked table 6 for Oct 5 2026 12:00 PM (party of 6). A later conversation asked for "a table" (no specific number), was correctly told table 6 was unavailable (with tables 7/8 offered instead) — but the underlying concern raised was whether the system would actually stop a booking attempt for table 6 at that exact conflicting slot if one were made. It wouldn't have: confirmed `reserve_table` had no conflict check at all.
- **Cause:** `reserve_table` only ever called `get_table_id(table_number)` — which confirms table 6 *exists*, not that it's *free*. Nothing in `reserve_table` called `get_existing_bookings`/`_windows_overlap`, the exact conflict-detection logic `check_availability` already uses. The two functions were completely disconnected: `check_availability` is advisory (informs the model), but the actual write path (`reserve_table`) trusted whatever `table_number` it was given with zero re-verification. This was a known, explicitly-flagged-but-never-resolved gap from `reserve_table`'s original design (`decision_log.md`: *"whether `reserve_table` re-verifies availability itself before inserting (race condition since time may have passed since the guest's original `check_availability` call)"*).
- **Why this is a real, not just theoretical, bug:** `check_availability`'s answer is only a snapshot at the moment it's called. Between that call and the later `reserve_table` call (after the guest gives name/phone), a *different guest in a different session* could book the same table/slot — both guests could see "available," both could successfully call `reserve_table`, and the table ends up double-booked despite every individual check having been correct when it ran. Conversational ordering (check before reserve) doesn't prevent this — it's a classic check-then-act race condition, and the "pending + hold window" lock in `get_existing_bookings` was already correctly designed to prevent it, but only `check_availability` was ever reading that lock — `reserve_table` never consulted it.
- **Fix:** new `_table_has_conflict(table_id, date, requested_start, requested_end)` in `tools_lambda/tools/booking.py`, reusing the existing `get_existing_bookings`/`_windows_overlap` logic. Called inside `reserve_table` immediately after `table_id` is resolved, before any customer lookup or DB write — rejects with a clear message (`"Table X is no longer available at that time — please check availability again."`) if a real conflict is found, instead of silently double-booking.
- **Status:** Fixed. Verified against the real deployed Lambda: booking table 6 for the already-taken Oct 5 12:00 PM slot is now correctly rejected with no DB writes; booking a genuinely free slot still succeeds normally. `tests/test_booking.py` covers the rejection case (asserts `get_customer`/`book_table` are never called) alongside the existing reservation tests, all updated to mock `get_existing_bookings` accordingly. 76 tests passing.

### 27. Model said "confirmed" in its own opening line while correctly showing "Pending" below
- **Error:** after a nut-allergy booking (correctly routed to bucket 2, `status: "pending"`), the live reply opened with *"Excellent! Your reservation is **confirmed**!"* — then correctly listed *"**Status:** Pending"* a few lines later, in the same message. Self-contradictory within one reply.
- **Cause:** a different failure shape than #18/#20/#21 — those were the model computing or inventing a wrong *value*. Here the model correctly used `status: "pending"` for the details list, but separately generated a generic "booking succeeded" celebratory opener — seemingly a default "reservation completed" tone applied because the tool call itself completed without error, not conditioned on the actual `status` value it used correctly two lines later.
- **Why this one matters more than the cosmetic hallucinations:** telling a guest their allergy-flagged booking is "confirmed" undermines the entire point of the bucket-2 review — a guest could reasonably stop paying attention or show up expecting a guaranteed table the owner might still decline.
- **Fix:** same principle as the `*_display` fields, applied to status framing instead of raw values — `reserve_table` now returns a `status_message` field (`STATUS_MESSAGES` dict in `tools_lambda/tools/booking.py`, keyed by the real `status`), a ready-to-use sentence with nothing left for the model to compose. `agent.py`'s `reserve_table` docstring and `system_prompt.md`'s verbatim-relay rule both updated to say: use `status_message` verbatim, don't independently compose a confirmed/success tone just because the call succeeded.
- **Status:** Fixed at the data layer, verified against the real deployed Lambda (`status: "pending"` correctly pairs with the pending `status_message`). Live conversational re-test still worth doing to confirm the model actually uses the field this time, given prompt-reinforced fixes haven't always held earlier this session.

### 28. Phase 6 (hold-expiry sweep) was built and tested but never actually deployed
- **Error:** a nut-allergy test booking (reservation 7) sat at `pending` long past its 5-minute hold window — nothing ever declined it.
- **Cause:** not a code bug — `scheduler_lambda/sweep.py`'s `decline_expired_reservations()` was fully built and unit-tested (`tests/test_scheduler.py`, passing all session) but had never been deployed as an actual Lambda function, and no EventBridge schedule had ever been created to trigger it. Confirmed via `aws lambda list-functions`/`aws events list-rules` (read-only): only `booking-agent-tools` existed; no scheduler function, no rule. The fail-closed enforcement this project's whole bucket-2 design depends on had never once executed against the real database — every earlier "hold expired" scenario this session just silently stayed pending forever.
- **Fix:** deployed `booking-agent-scheduler` as its own Lambda (same dependency-bundling approach as `booking-agent-tools`, reusing its IAM role — no Bedrock permission needed, this function never touches Bedrock). Created EventBridge rule `booking-agent-hold-expiry-sweep` (`rate(1 minute)`), granted it invoke permission, wired it as the Lambda's target.
- **Status:** Fixed. Verified via a manual invoke: correctly declined reservation 7 (`reason: "No response from the owner within the hold window"`), confirmed directly against Supabase. EventBridge rule/permission/target all reported success (`FailedEntryCount: 0`) but an automatic (non-manual) triggered tick wasn't directly observed in the same session due to the 1-minute schedule not having elapsed yet at verification time — worth a follow-up CloudWatch check (`/aws/lambda/booking-agent-scheduler`) a few minutes later to fully confirm.

### 22. No visibility into tool-call requests/responses (observability gap, not a bug)
- **Symptom:** diagnosing #20 required manually re-invoking the Lambda by hand each time to compare what the model *should* have seen against what it actually said — no way to see what the model actually sent/received in a live conversation.
- **Fix:** `agent.py`'s `_invoke_tool` now prints `[TOOL CALL]`/`[TOOL RESULT]` for every request/response, and the CLI loop prints `[GUEST INPUT]`/`[MODEL REPLY]`. `tools_lambda/handler.py`'s `handler()` now logs one JSON line per action (parameters, result, latency_ms) to CloudWatch. Closes the "basic structured observability" item already scoped in `decision_log.md`.
- **Status:** Fixed (infrastructure, not itself a bug fix — but directly needed to make progress on #20).

### 23. `session.customer_id` never backfilled after a booking
- **Error:** every row in the `session` table showed `customer_id: NULL`, including sessions where a real booking (and therefore a real `customer` record) had already been completed.
- **Cause:** `create_session()` runs before any customer info is known (by design — many sessions never identify a customer at all, so the column has to be nullable), but nothing ever performed the follow-up write once `reserve_table` *did* resolve a customer. `insert_customer(...)`'s return value (including the new row's `customer_id`) was discarded entirely, and there was no `UPDATE session SET customer_id = ...` anywhere in the codebase. This was a known, explicitly-deferred gap from when the column was first made nullable, not a new regression.
- **Fix:** new `update_session_customer(session_id, customer_id)` in `shared/queries.py`; `reserve_table` now resolves `customer_id` from either `get_customer`'s existing row or `insert_customer`'s newly-created row, then calls it.
- **Status:** Fixed, verified against the real deployed Lambda (`session_id: 15` correctly shows `customer_id: 3` after a live test booking).
