# Front-Desk Booking & Q&A Agent — 32-Day Build Plan
**Agents for Humans Hackathon — Professional Agents Track**

## The idea, in one line
An agent that sits on a small restaurant or boutique hotel's inbound channel (SMS/chat), answers routine customer questions instantly, books what it can confidently book, and escalates to the owner only when a real decision is needed.

## Why this idea
- Matches the Professional Agents track's own example almost verbatim: "a shop owner answering the same booking questions all day."
- Works for two verticals (restaurants and small hotels) off one core engine, without extra build cost.
- Core loop (RAG + tool-calling + confidence-based escalation) is achievable and demoable within 32 days — lower technical risk than options requiring live third-party integrations (PMS systems, multi-vendor booking APIs) or fuzzy judgment calls (contract scope-drift detection) that are harder to make look reliable on stage.

---

## Architecture

**Model:** Claude via Amazon Bedrock (Strands Agents SDK default provider).

**Core components:**
1. **Business knowledge base** — hours, menu/services, pricing, policies for the demo business persona. Small enough to load directly into context or as a lightweight retrieval tool; no need for a heavy vector DB at this scale.
2. **Booking store** — SQLite or in-memory table representing tables/rooms and time slots, exposed to the agent as custom Strands tools: `check_availability`, `create_booking`, `modify_booking`, `cancel_booking`.
3. **Escalation logic** — an `escalate_to_owner(reason, context)` tool the agent calls when it hits a case outside its confidence bounds (party size over capacity, request outside hours, complaint/refund language, repeated failed attempts, anything ambiguous). Logs a pending decision and notifies the owner.
4. **Owner interface** — minimal dashboard or SMS/email thread where the owner approves, declines, or replies to an escalation; the agent relays the resolution back to the customer automatically.
5. **Channel integration** — Twilio SMS webhook is the most demoable and realistic entry point for a small shop (a real phone number customers text). A web chat widget is a lower-effort fallback if Twilio setup eats too much time.
6. **Memory** — Bedrock AgentCore Memory for per-customer conversation history, so returning customers keep context across messages.
7. **Deployment** — Strands agent wrapped and deployed to Bedrock AgentCore Runtime as a managed HTTPS endpoint; AgentCore Gateway can expose the booking tool/calendar API cleanly.

```
Customer (SMS/chat)
      │
      ▼
Twilio/Webhook ──▶ AgentCore Runtime (Strands Agent)
                         │
             ┌───────────┼────────────┐
             ▼           ▼            ▼
     Knowledge base  Booking tools  escalate_to_owner
     (hours/menu/     (check/create/    │
      policies)        modify/cancel)   ▼
                                   Owner dashboard/SMS
                                         │
                                         ▼
                              Resolution relayed to customer
```

---

## Week 1 (Days 1–7): Foundation

- **Day 1–2:** AWS account setup, request the $50 hackathon AWS credits (Resources tab — do this immediately, approval can lag), enable Bedrock model access for Claude, install Strands Agents SDK. Pick the demo business persona — recommend starting with **one restaurant** (e.g., a fictional trattoria) for the first working version. Write out its knowledge base: hours, menu, policies, seating capacity.
- **Day 3–4:** Build the core Strands agent — system prompt + business knowledge loaded into context. Test plain Q&A in a CLI loop ("are you open Sunday," "do you have a vegan option") before adding any tools.
- **Day 5–7:** Build the booking store and tools (`check_availability`, `create_booking`, `modify_booking`, `cancel_booking`) against SQLite. Test the agent actually reasoning through "table for 4 at 7pm Friday" end to end, including a real create in the store.

## Week 2 (Days 8–14): Escalation logic + channel integration

- **Day 8–9:** Define the escalation boundary explicitly (this is the heart of the pitch): what counts as "safe to handle autonomously" vs. "needs the owner." Implement `escalate_to_owner` — logs the pending decision, notifies the owner.
- **Day 10–11:** Build the minimal owner-side interface (simple web dashboard, or just SMS/email replies) with approve/decline/custom-reply actions. Wire the resolution back into the customer conversation.
- **Day 12–14:** Stand up the real channel — Twilio number + webhook → your agent endpoint → Twilio reply. Test with real texts from your own phone.

## Week 3 (Days 15–21): AgentCore deployment + robustness

- **Day 15–16:** Deploy to Bedrock AgentCore Runtime as an HTTPS endpoint. Wire up AgentCore Memory for per-customer thread history.
- **Day 17–18:** Route the booking tool through AgentCore Gateway (or a real calendar API, e.g. Google Calendar) for a more credible integration story.
- **Day 19–21:** Edge-case hardening — ambiguous requests, concurrent customers, double-booking race conditions, off-topic messages, and basic prompt-injection resistance (important since this is a customer-facing, publicly reachable channel).

## Week 4 (Days 22–28): Second vertical + polish

- **Day 22–23:** Swap in a second persona — a boutique hotel (room types, check-in/out times, amenities) — reusing the same engine, to prove the "one agent, two verticals" pitch.
- **Day 24–25:** Add basic observability/eval (AgentCore's built-in evaluation tooling) — build a small test set of routine questions and measure what percent the agent resolves correctly without escalation. This number goes straight into your pitch.
- **Day 26–28:** UI polish for the demo — clean up the chat/SMS thread presentation and the owner dashboard. Script the two demo sequences you'll film: (1) a run of routine questions answered instantly, (2) a case that triggers escalation, gets an owner decision, and relays back.

## Final stretch (Days 29–32): Submission

- **Day 29:** Record the demo video.
- **Day 30:** Write the build story for builder.aws.com (bonus points per the hackathon rules) — cover the architecture choices and how Strands + AgentCore were used.
- **Day 31:** Devpost submission — writeup, screenshots, architecture diagram, clean repo + README.
- **Day 32:** Buffer day for last-minute fixes or a demo re-record.

---

## Notes
- If you have teammates, parallelize Week 2 (escalation logic) and Week 3 (deployment/hardening) rather than doing them sequentially — that's the biggest schedule compression available.
- Request AWS credits on Day 1, not later — approval and Bedrock model access can take time you don't want to lose mid-build.
- The single most important thing to get right for judging is the escalation boundary (Day 8–9) — that's the whole "runs in the background, surfaces only for real decisions" story the brief is scoring on. Everything else is in service of making that boundary look smart on demo day.

## Sources
- [Strands Agents — Get Started](https://strandsagents.com/docs/user-guide/quickstart/overview/)
- [AWS ML Blog — Strands Agents SDK: A Technical Deep Dive](https://aws.amazon.com/blogs/machine-learning/strands-agents-sdk-a-technical-deep-dive-into-agent-architectures-and-observability/)
- [Deploying Strands Agents to Amazon Bedrock AgentCore Runtime](https://strandsagents.com/docs/user-guide/deploy/deploy_to_bedrock_agentcore/)
- [Amazon Bedrock AgentCore — Overview](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html)
- [Amazon Bedrock AgentCore is now generally available](https://aws.amazon.com/about-aws/whats-new/2025/10/amazon-bedrock-agentcore-available)
