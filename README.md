# muraqib-client

**MURAQIB is a governance rail for AI agents.** Before your agent performs a consequential action, it
declares that action to MURAQIB and receives a verdict — approved, blocked, or escalated to a human.
Every verdict is written to a cryptographically sealed, hash-chained evidence record that is
periodically anchored with an offline signature, so what your agent was permitted to do is provable
after the fact.

This is the canonical Python client.

---

## Install

```bash
pip install git+https://github.com/oqiron/muraqib-client.git              # core, zero dependencies
pip install "git+https://github.com/oqiron/muraqib-client.git#egg=muraqib-client[signing]"
```

The core is standard-library only. The `[signing]` extra adds `cryptography` and is required **only**
for four-eyes authorized actions (Ed25519 assertion signing — the Python standard library cannot do
Ed25519). Without it, those calls fail closed rather than being sent unsigned.

> Replace the URL above with the repository you were given. This package is not on PyPI.

## Get credentials

**There is no self-serve signup.** Contact OQIRON to be issued:

| you receive | what it is |
|---|---|
| an **API key** | authenticates your agent; carries scopes (`intercept`, `read`) |
| an **agent identity** | e.g. `ACME-PRD-001` — registered server-side, with its environment (production or sandbox) |
| optionally, **Ed25519 key registration** | required only if you perform four-eyes authorized actions |

Your environment, your registered scope, and your tenant are all **server-side properties of the
identity you were issued**. You do not select them and you cannot change them from the client.

## Your first cleared action

```python
from muraqib_client import MuraqibClient

m = MuraqibClient(
    api_key="<your key>",
    agent_id="ACME-PRD-001",
    muraqib_url="https://muraqib.oqiron.ai",
)

d = m.clear(
    action_type="EMAIL",                       # MUST be a recognized value — see docs/action-types.md
    summary="Quarterly update to the client distribution list",
    request_ref="REQ-2026-0142",               # your own correlation id
)

if not d.governed:                             # UNAVAILABLE — the rail did not adjudicate
    raise SystemExit("not cleared: %s" % d.reason)          # DO NOT PROCEED

if d.approved:
    send_the_email()                           # cleared; evidence sealed as d.evidence_id
elif d.blocked:
    log_refusal(d.evidence_id, d.safe_action)  # terminal — do not perform the action
elif d.escalated:
    hand_to_human(d.evidence_id)               # STOP. See "ESCALATED means stop" below.
```

---

# READ THIS FIRST

Four things surprise every new integrator. Read them before you write code.

### 1. `ESCALATED` means STOP. There is no resume path.

`ESCALATED` is not "pending" and not "retry later". **The API has no endpoint that resumes an
escalated action.** There is no callback, no webhook, no polling endpoint, and no status that later
flips to approved. Do not write code that waits for one.

The action stops. A human reviews the sealed evidence record out of band. If the work is to proceed,
it proceeds as a **new** clearance call — and for the four hold/authorized action pairs, that new call
is the `*_AUTHORIZED` action type carrying a signed four-eyes assertion. That is a fresh declaration,
not a continuation.

### 2. `action_type` must be one of the 103 recognized values

The full list is in **[docs/action-types.md](docs/action-types.md)**. Matching is exact. There is no
fuzzy matching and no nearest-neighbour suggestion. An unrecognized value is classified as
unclassified and escalates via **`TAXO-00 — escalate-on-unknown`**.

Real near-misses:

| you might send | reality |
|---|---|
| `SEND_EMAIL` | not a value — use `EMAIL` |
| `EXECUTE_TRADE` | not a value — use `TRADE_EXECUTION` |
| `DOCUMENT_PROCESSING` | not recognized at all |

Each of those returns `ESCALATED / TAXO-00`. If your first integration call escalates, check this
first — it is almost always the cause.

### 3. Fifteen declaration fields are recorded but do NOT affect the verdict

These fields are sealed into the evidence record and form part of your audit trail. **None of them
changes the decision:**

`is_external`, `has_attachment`, `contains_pii`, `regulatory_risk`, `financial_amount`, `priority`,
`is_board_decision`, `involves_trading`, `involves_hr`, `financial_advice`, `involves_tax`,
`public_communication`, `new_it_system`, `autonomous_decision`, `data_classified`

Setting `contains_pii=True` will not cause a block. Omitting `financial_amount` will not avoid one.
Declare them accurately — they are recorded and can be held against you — but do not build control
flow on the belief that they drive the verdict.

**What actually decides:** `action_type`; server-derived facts about your agent (registration, scope,
freeze state, environment, action velocity, the server clock); and the four-eyes attestations.

### 4. `UNAVAILABLE` means not-cleared. Never proceed.

Every client-side failure — unreachable rail, timeout, non-200, malformed response, missing
credential, signing failure — resolves to `decision == "UNAVAILABLE"`. It is **not** a soft failure
and **not** a degraded pass.

```python
if not d.governed:      # True only for APPROVED / BLOCKED / ESCALATED from the rail
    # the action was NOT governed. Performing it anyway leaves you with an
    # ungoverned action and no evidence record.
```

There is no "allow on failure" mode in this client, and one will not be added.

---

## What each verdict means, and what to do

| verdict | meaning | your next action |
|---|---|---|
| `APPROVED` | permitted for this agent, at this moment | proceed; keep `evidence_id` |
| `BLOCKED` | refused. Terminal. | do not perform it; `safe_action` explains why |
| `ESCALATED` | requires human authority | **stop**; hand `evidence_id` to a human; no resume path |
| `UNAVAILABLE` | the rail did not adjudicate (client-side) | **stop**; do not proceed; fix and re-call |

`requires_approval` is `true` for both `BLOCKED` and `ESCALATED`.

## Sandbox vs production

Your environment is **server-derived from your registered agent identity**. The client sends nothing;
if you send an `environment` field it is ignored and logged.

| | production | sandbox |
|---|---|---|
| evidence chain | the production chain | a **separate** chain, own lineage and seed |
| offline anchoring | periodically anchored | **never anchored, by design** |
| operator notifications | dispatched | **suppressed** |
| visibility | production reads | structurally invisible to production reads |

`verify(environment="sandbox")` on a sandbox chain correctly reports `tip_status: "no-signed-tip"`
and `anchor_status: "not anchored - sandbox chains are not anchored by design"`. **That is not a
defect** — sandbox chains are deliberately never anchored.

An agent principal may verify only its **own** environment; asking for the other one is refused
(`403 forbidden_environment`). If the rail cannot resolve your agent's environment it **refuses the
call** (`503`), which this client surfaces as `UNAVAILABLE` — nothing is sealed.

## API

| method | returns | raises |
|---|---|---|
| `clear(action_type, summary, request_ref, authorizer=None, held_evidence_id=None, **declaration)` | `Decision` | never |
| `intercept(...)` / `clear_action(...)` | aliases of `clear` | never |
| `verify(environment=None)` | `{"ok", "summary", "error"}` | never |
| `health()` | `bool` | never |

The only raise in the client is construction with an invalid `auth_mode`. **No call path raises** —
failures are values, because an exception is easy to catch-and-continue and a governance failure
must not be. `Decision` subclasses `dict`, so it logs and serialises unchanged.

**Auth.** `auth_mode="jwt"` (default) exchanges your API key for a 24-hour token, caches it, and
re-exchanges once on a `401`. `auth_mode="api_key"` sends `X-API-Key` directly. There is no refresh
token — re-exchange is the only recovery.

**Four-eyes.** Requires the `[signing]` extra and a **registered public key**:

```python
d = m.clear("EXTERNAL_CORRESPONDENCE_AUTHORIZED",
            request_ref="REQ-2026-0142",
            held_evidence_id="EVD-…",             # the escalated hold this authorizes
            authorizer={"id": "u-8812", "email": "head@acme.example",
                        "role": "SECTION_HEAD", "is_section_head": True,
                        "maker_ids": ["u-4410"]})
```

`MURAQIB_SIGNING_KEY` (hex Ed25519 private key) is read from the environment. Key material stays in
memory — never logged, never echoed, never sealed.

## Boundaries — what MURAQIB does not do

- **It governs the declaration, not the payload.** The rail never sees, parses, or stores your
  content. An approval says the *declared* action was permitted; it says nothing about the bytes you
  then send.
- **One global chain per environment — not per tenant.** There are **no per-tenant inclusion
  proofs**. A tenant cannot independently prove its own subset of the chain.
- **Not an accredited certifier.** Evidence is sealed and offline-anchored. That is a cryptographic
  property, not a regulatory attestation, and no regulator has accredited it.
- **Signature verification is skipped for agents without a registered public key.** If your identity
  has no key registered server-side, four-eyes fields you send are **not signature-checked** — the
  attested values are still adjudicated, but no cryptographic binding exists. If you need that
  binding, you must have a key registered.
- **`permitted_actions` is only partly enforced.** It gates a control for a small set of action
  domains; elsewhere it is decorative. Do not read it as a general authorization surface.
- **Chain integrity is only as fresh as the last anchor.** Between anchors, `pending_anchor > 0` and
  `tip_status` reads `tip-mismatch`. That is expected, not tampering.
- **`ESCALATED` has no API resume path** (see above).

## Documentation

- **[docs/action-types.md](docs/action-types.md)** — all 103 recognized `action_type` values
- **[docs/integration-standard-v3.md](docs/integration-standard-v3.md)** — the formal contract

## Scope: external integrators

This package is for external integrators. OQIRON's own products still use their own in-tree clients;
consolidating them onto this package is separate, deferred work, recorded here so it is not
forgotten:

> **PENDING:** migrate the internal product clients and their consumers onto `muraqib-client`. Until
> then this is not the only client in use against the rail.

## License

Apache-2.0. See `LICENSE`.
