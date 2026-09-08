# Design Notes — Escalation Model
**Front-Desk Booking & Q&A Agent**

Starter notes from the architecture mentoring session. Keep expanding this yourself as you build — treat it as your running decision log, not a finished spec.

## The three buckets

1. **Agent decides on its own** — the answer is certain and the stakes are low. No human involved.
   - Examples: business hours, "no room tonight" (calendar is full), closing-time cutoffs.

2. **Owner verification (yes/no)** — the agent is confident it knows the answer, but the consequence of being wrong is severe enough (safety, trust, legal exposure) that a human must actively sign off before it's final.
   - Trigger is unconditional on confidence — fires even when the knowledge base is fresh and certain, because the trigger is *stakes*, not *certainty*.
   - Example: a confirmed allergy checked against a KB fact the agent already trusts.

3. **Owner decides (choices + free text)** — no single correct answer; multiple real paths exist and only the owner's judgment can weigh them. Agent presents context, suggested options where relevant, plus a free-text field for cases where the owner doesn't have a ready-made answer either (e.g. an allergen not covered anywhere in the KB — owner has to go find out, not pick from a menu).
   - Example: party of 20 against a max table size of 8 (real tradeoff: rearrange tables vs. decline). Also covers "info not in KB" cases via the free-text option, rather than needing a fourth bucket.

## How we got here

Started by sorting examples on whether the answer happened to be "no" — that conflated two different problems. The real split: is the agent just retrieving a fact with nothing to weigh (bucket 1), confirming something high-stakes it already believes (bucket 2), or facing a genuine tradeoff with no single right answer (bucket 3)?

The allergy case forced the sharpest distinction: same certainty level as a plain KB lookup, but still escalated — because "how sure am I" (confidence) and "how bad is it if I'm wrong" (stakes) are two separate axes, not one. A thing can be 100% certain and still need a human sign-off if the cost of being wrong is high enough.

## Architecture decision: hybrid enforcement

- **Pure LLM judgment** — rejected. Not fully deterministic (same input can classify differently across runs/model updates), and a public-facing conversational agent is an attack surface for prompt injection.
- **Pure hard-coded rules** — rejected. At that point it's a rules engine with a chat UI, not an agent.
- **Hybrid (chosen)** — the LLM extracts structured facts from the conversation (party size, allergy mention, requested time, etc.). A separate deterministic check, sitting in code *before* any booking tool is allowed to execute, decides which bucket applies based on those extracted facts.
- Pattern name: **"the LLM proposes, the system disposes."** Model handles language and extraction; code handles enforcement. The model can't talk its way around a rule that isn't part of the conversation it's having.

## Known open risk (not yet solved — carry this forward)

The hard rule is only as good as the extracted data feeding it. `party_size > capacity` is airtight *if* party size was extracted correctly — but a misheard or misparsed number, or an allergy mentioned in passing three messages back, breaks the gate silently (garbage in, garbage out). Likely direction: have the agent explicitly confirm critical extracted fields back to the customer before they're trusted ("just to confirm, that's a table for 20?") — not yet designed.

## Bucket 2 notification design (resolved)

- **Ping content:** table number, party details, the specific allergy/safety fact, and current availability — all in one message, with a binary Confirm/Reject action. Goal: owner can respond in ~5 seconds with no follow-up question needed.
- **Table hold:** when a verification ping goes out, the table is placed on a temporary hold (reservation lock with TTL, same pattern as cinema/event seat holds) — not released to other customers while awaiting the owner's response.
- **Timeout default:** 5-minute window. If the owner doesn't respond in time, the hold expires and the booking is **declined by default** — not auto-confirmed. This preserves the reason verification existed in the first place (safety-critical, shouldn't go through unsupervised); an unattended timeout must fail safe, not fail open.
- **Customer-facing wait state:** customer is told something is happening ("may take 5 minutes, checking with the team for confirmation") rather than left in silence during the hold window.

## Next open question

Not yet started: what data does the agent need to extract from the conversation to drive each of the three bucket tools (`answer_directly`, `request_verification`, `request_decision`) — i.e. the booking/reservation data schema itself.
