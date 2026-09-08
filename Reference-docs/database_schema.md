# Database Schema — Front-Desk Booking Agent
**Final schema from the design session. SQL/relational, chosen for structural consistency and enforceable relationships between tables.**

Companion to `design_notes_escalation_model.md` (bucket logic) and `booking_flow_design.md` (sequence/flow). This is the persistence layer underneath both.

---

## Tables

### customer
| column | notes |
|---|---|
| cust_id (PK) | |
| cust_name | |
| cust_phone_number | identity key for recognizing returning customers |
| cust_email | |
| is_deleted | soft delete |
| created_at_timestamp | |

### session
| column | notes |
|---|---|
| session_id (PK) | |
| cust_id (FK → customer) | many sessions per customer |
| created_at_timestamp | |

### conversation
One row per message — split out from session because a session has *many* messages, and each needs its own place in the sequence (matters for tracing exactly which message triggered an escalation).

| column | notes |
|---|---|
| conv_id (PK) | |
| session_id (FK → session) | many messages per session |
| conversation | message content |
| by_who | `user` / `assistant` |
| timestamp | needed to reconstruct message order |

### reservation
| column | notes |
|---|---|
| reservation_id (PK) | |
| session_id (FK → session) | |
| availability | result of the initial availability check |
| confirmed_declined | final resolved outcome |
| reason | why it was declined (owner missed the message, table unavailable, etc.) |
| party_size | |
| date | |
| time | |
| allergy_info | |
| table_number | assigned once a table is chosen, not a customer-supplied input |
| start_time_hold_reserve | when the temporary hold on this table began |
| end_time_hold_reserve | when the hold expires (5 min for verification, 15–20 min for decision) |

### escalation
One row per bucket-2 or bucket-3 event. No row exists for bucket-1 (autonomous) resolutions, by definition — no owner involvement means nothing to log here.

| column | notes |
|---|---|
| escalation_id (PK) | |
| reservation_id (FK → reservation) | |
| session_id (FK → session) | kept alongside reservation_id as a deliberate denormalization, avoids an extra join to find "which session" |
| bucket | verification / decision — determines timeout window and UI shape |
| owners_answer | confirm/reject or free-text, depending on bucket |
| created_at | when the ping was sent |
| responded_at | when the owner actually responded (nullable — stays empty if it timed out) |

### restaurant_info
| column | notes |
|---|---|
| rest_id (PK) | |
| rest_name | |
| rest_location | |
| address | |
| city | |
| country | |
| pincode | |
| restaurant_KB_id (FK → restaurant_kb) | |

### restaurant_kb (vector store)
| column | notes |
|---|---|
| restaurant_KB_id (PK) | |
| restaurant_kb_doc | source document |
| restaurant_kb_vector | embedding, used for RAG-style Q&A over hours/menu/policies |

---

## Relationships

- customer **1:M** session
- session **1:M** conversation
- session **1:M** reservation
- session **1:M** escalation
- restaurant_info **1:M** restaurant_kb

Foreign keys sit on the "many" side in every case above — this was fixed iteratively during the session (customer/session, session/escalation, and finally session/conversation each had the FK on the wrong side initially).

## What this schema is built to support

- The three-bucket escalation model, including which bucket fired and how long the owner took to respond (or didn't).
- The table hold/timeout mechanic, with distinct windows per bucket.
- Duplicate-booking detection (same identity + date/time, checked once name/phone/email are collected, before final confirmation).
- An actual audit trail — not just that a booking happened, but why, and traceable back to the specific message that triggered it.

## Still open (not schema issues, implementation-level)

- Pydantic-style validation layer between what the LLM extracts and what gets written here — discussed, not yet designed in detail (distinguishing type coercion from confirming factual correctness with the customer).
- Tool signatures (`answer_directly`, `request_verification`, `request_decision`, booking CRUD) — next natural step, should map closely onto this schema.
