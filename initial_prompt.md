# Initial Prompt for Claude Code

Paste this as your first message after running `claude` in the project root.

---

Read `@CLAUDE.md` and `@docs/product_spec.md` carefully before responding. The spec is the
source of truth for what we're building; CLAUDE.md is how we're building it.

We are at Phase 0/1 of the milestone plan in spec §10. Before any feature work, I need
us to do four things in order:

**1. Confirm your understanding.** Summarize back to me, in 5 bullet points or fewer:
   - What the executor must do on a signal
   - Why we're trying Path A before Path B
   - The non-negotiable rules from CLAUDE.md
   - Which open questions in spec §11 would block Phase 2 if not answered
   - Any contradiction or ambiguity between the spec and CLAUDE.md that I should
     resolve before we move on

Do NOT proceed to step 2 until I confirm your summary is correct.

**2. Propose a stack and project structure.** Constraints:
   - Must support a long-lived webhook receiver (for Path B fallback)
   - Must have a mature Alpaca SDK client
   - Must be cheap to host (target: free tier on Railway or Render)
   - Must be testable without hitting the live Alpaca API
   - I am a bootcamp grad comfortable in the terminal but weak on
     deployment/hosting. Pick boring, well-documented tech.

   Give me the proposal with reasoning — what you'd pick for language, web framework,
   data layer (do we even need one yet?), test framework, deploy target, and config
   management. Tell me what you'd defer until later. Wait for me to approve before
   scaffolding.

**3. Scaffold the project — minimum viable skeleton only.** Once I approve the stack:
   - Create the directory structure
   - Create `.gitignore`, `.env.example`, and `README.md`
   - Install dependencies and lock them
   - Write ONE smoke test that calls Alpaca's paper API `/v2/account` endpoint and
     prints the account number and buying power. That's it. This is our
     "hello world" — it proves the connection works end-to-end and that secrets
     are loading correctly.
   - Show me the commands to run it.

   Do NOT scaffold the webhook receiver, the trade journal, the heartbeat job,
   or any strategy logic in this step. We don't yet know if we need them.

**4. Walk me through Phase 1 of the spec.** Once the smoke test passes, write me
   a checklist (in a new file `docs/phase1_path_a_test_plan.md`) of every concrete
   step needed to determine whether TradingView's native Alpaca integration can
   fire automated trades from a strategy script. Include what to look for, what
   screenshots to capture, and what "Path A works" vs "Path A doesn't work"
   look like in terms of observable evidence.

A few standing instructions for the whole project:

- If a task is ambiguous, ask one specific clarifying question rather than guessing.
- If you're about to write more than ~30 lines of code without me confirming the
  direction, stop and check first.
- When you touch any code path that constructs an Alpaca order, write the test
  before the implementation. Mock the Alpaca client.
- Never commit `.env` or anything matching `*.key`, `*.pem`, `secrets.*`.
- If you find yourself wanting to reimplement any of the scoring logic from
  spec §5-§7, stop. That's a sign we've drifted into the wrong path.

Start with step 1.
