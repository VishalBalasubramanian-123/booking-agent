# Booking Flow Design
**Front-Desk Booking & Q&A Agent — flow derived from hand-drawn diagram + session refinements**

Companion to `design_notes_escalation_model.md` (bucket definitions live there). This doc is the sequence of steps and everything that changed since the first diagram was drawn.

---

## The flow (as clarified from your diagram)

```
Customer message (query)
        │
        ▼
Time & date present in the message?
   │no                    │yes
   ▼                       ▼
Prompt customer      Agent checks calendar for
for date/time    ──▶ availability at that date/time
   │                       │
   └───loop back           ├── Not available
       to query            │      │
                            │      ▼
                            │  Inform customer: not available.
                            │  Offer a different time for the
                            │  same table, OR different tables
                            │  for the same time.
                            │      │
                            │      └──▶ loop back to query
                            │           (customer picks an alternative)
                            │
                            └── Available
                                   │
                                   ▼
                          Check KB for allergy / safety info
                          mentioned in the request
                                   │
                     ┌─────────────┴─────────────┐
                     │                            │
              KB has no info                KB has the info
              on this allergen              (bucket 2 — verify
              (bucket 3 — owner              regardless of
              decides, gets free              confidence)
              text if no good option)                │
                     │                                │
                     ▼                                ▼
          Owner notified, given            Owner notified: table,
          context + option to type         party, the specific
          a custom response                allergy fact, availability
                     │                      → Confirm / Reject
        ┌────────────┴───────────┐                    │
        │                        │           ┌────────┴────────┐
   Owner responds           No response       │                 │
   in time                  in 15–20 min      Confirm       Reject / no
        │                   window (bucket-3        │       response in
        ▼                   timeout — pick a        ▼       5 min (bucket-2
   Book table &              single number)    Book table    timeout)
   update KB                       │            & update KB       │
        │                          ▼                  │           ▼
        ▼                  Reject booking,             ▼    Reject booking,
  Give confirmation        tell customer why      Give confirmation  tell customer why
```

**Table hold mechanic (applies whenever bucket 2 or bucket 3 fires):** the table is placed on a temporary lock the moment a ping goes to the owner — same pattern as a cinema seat hold — so it isn't given away to someone else mid-decision. Customer is told something's in progress ("may take a few minutes, checking with the team") rather than left in silence.

**"Table not available" branch:** offers alternatives proactively (different time, or different table same time) instead of a flat no — this is new since the original diagram and worth keeping, it's a good example of "make the safe call, don't just say no."

---

## Changes made since the diagram was first drawn

1. **Severity gating on allergy escalation.** Not every dietary mention triggers bucket 2 — only ones with severity language ("severe," "extreme," etc.). A plain preference with no severity indicator, and a KB that confidently answers it, stays in bucket 1 (agent handles it, no owner involved). This was added specifically to stop the agent from over-escalating and defeating the "only surface for real decisions" goal.
   - **Still open:** when severity is genuinely ambiguous in the customer's wording, default to bucket 2 (fail-safe, same logic as the timeout default) rather than silently treating it as low-stakes. Implement as a structured-output classification step inside the one agent — not a second full agent — to keep scope manageable solo.

2. **New vs. returning customer table assignment.** For a new customer, table isn't something they specify upfront — the agent checks the date/time, and the *output* of that check (a list of open tables) is what gets presented for them to choose from. For a returning customer with a known preferred table: if it's free, give it to them directly (bucket 1). If it's taken, first offer the easy fallback directly to the customer (a different table that night, or their usual table on a different date) with no owner involved. Only escalate to bucket 3 — owner deciding whether to bump another party — if the customer explicitly rejects the easy alternatives and insists on that specific table/date.
   - **Still open:** what's the actual lookup key for recognizing a "returning" customer — phone, email, name, some combination? Not yet decided. Worth thinking about edge cases like a couple sharing one phone number under two names.

3. **Timeout defaults, now bucket-specific.** Bucket 2 (verification): 5-minute hold, decline by default on timeout — justified by safety (don't let a safety-relevant booking go through unsupervised). Bucket 3 (decision): longer hold, 15–20 minutes — still declines by default on timeout, but the justification here is different: avoiding a booking sitting in limbo while the owner may have already handled the situation manually outside the system.
   - **Still open:** pick one fixed number for bucket 3, not a range.

4. **Audit trail gap identified, not yet resolved.** The "what gets written down after the booking resolves" list currently only captures the booking's end state (name, date, party size, table). It's missing a record of *how* the decision was made — which bucket fired, what the owner's response was, when they responded. Given the whole reason hybrid enforcement was chosen over pure LLM judgment was auditability, this needs to be added to the schema before it actually delivers on that promise.

## Known open risks (carried forward from the escalation notes)

- **Extraction accuracy:** hard rules are only as good as the data extracted from the conversation. A misparsed party size or a missed allergy mention breaks the gate silently. Likely fix: have the agent confirm critical fields back to the customer before trusting them — not yet designed.
- **Calendar/reality drift:** if the owner assigns tables manually outside the system (e.g. seating someone they know without a formal booking), the agent's view of "available" can be wrong even for bucket-1 answers. Not yet addressed.

## Not yet started

- Full data schema (three-pass exercise — before/check/after — is partially done, needs the audit-trail fields added and a final pass to turn it into an actual table structure).
- Tool signatures for `answer_directly`, `request_verification`, `request_decision`, and the booking CRUD tools.
