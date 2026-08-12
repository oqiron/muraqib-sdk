# muraqib-client

**MURAQIB is a clearance rail for AI agents.** Before your agent performs a consequential action, it
declares that action to MURAQIB and receives a verdict — approved, blocked, or escalated to a human.
Every verdict is written to a cryptographically sealed, hash-chained evidence record that is
periodically anchored with an offline signature, so what your agent was permitted to do is provable
after the fact.

This is the canonical Python client.

---

# Quickstart

Follow these five steps in order. They take about five minutes.

## Step 1 — What OQIRON sends you

**There is no self-serve signup.** Contact OQIRON. You will be sent:

| you receive | what it looks like |
|---|---|
| **a key file** | a plain-text file containing **one line**, starting with `mrq_`, about 47 characters, no trailing newline |
| **an agent identity** | a string such as `SANDBOX-ACME-001` — registered on our side, with its environment already set |

Save the key file somewhere your code can read it — for example `./muraqib.key` — and keep it out of
version control. Treat it exactly like a password: never commit it, never log it, never paste it into
a ticket.

Your environment (production or sandbox), your scopes, and your tenant are **server-side properties
of the identity you were issued**. You do not choose them and cannot change them from the client.

## Step 2 — Create and activate a virtual environment

> **These are shell commands. Run them in your terminal.**

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell):**

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
```

Your prompt should now begin with `(.venv)`. **Do not skip the activation line** — without it, `pip`
installs into your system Python and the next step appears to succeed while `import muraqib_client`
fails.

## Step 3 — Install the client

> **Shell commands, in the same activated terminal.**

```bash
pip install git+https://github.com/oqiron/muraqib-sdk.git@v2.0.0
```

Only if you will perform four-eyes authorized actions (most integrations do not — see
[Four-eyes](#four-eyes-authorized-actions)), install the signing extra instead:

```bash
pip install "muraqib-client[signing] @ git+https://github.com/oqiron/muraqib-sdk.git@v2.0.0"
```

Check it worked:

```bash
python -c "import muraqib_client; print(muraqib_client.__version__)"
```

## Step 4 — Point the script at your credentials

> **Shell commands. Replace both values with what OQIRON sent you.**

```bash
export MURAQIB_AGENT_ID="SANDBOX-ACME-001"     # <-- REPLACE with YOUR agent identity
export MURAQIB_KEY_FILE="./muraqib.key"        # <-- REPLACE with the path to YOUR key file
```

On Windows PowerShell:

```powershell
$env:MURAQIB_AGENT_ID = "SANDBOX-ACME-001"     # <-- REPLACE
$env:MURAQIB_KEY_FILE = ".\muraqib.key"        # <-- REPLACE
```

## Step 5 — Your first cleared action

> **This is Python, not shell.** Save the block below to a file named **`first_call.py`**, then run
> it with `python first_call.py` in the same terminal where you did steps 2–4.

```python
import os
import sys

from muraqib_client import MuraqibClient

agent_id = os.environ.get("MURAQIB_AGENT_ID")
key_file = os.environ.get("MURAQIB_KEY_FILE")

if not agent_id or not key_file:
    sys.exit("Set MURAQIB_AGENT_ID and MURAQIB_KEY_FILE first (see step 4).")

with open(key_file) as f:
    api_key = f.read().strip()          # the file holds one line beginning mrq_

client = MuraqibClient(
    api_key=api_key,
    agent_id=agent_id,
    muraqib_url="https://muraqib.oqiron.ai",
    auth_mode="api_key",
)

print("rail reachable:", client.health())

decision = client.clear(
    action_type="EMAIL",                          # must be a recognized value - see docs/action-types.md
    summary="First integration test from the quickstart",
    request_ref="QUICKSTART-001",                 # your own correlation id
)

print("decision   :", decision.decision)
print("governed   :", decision.governed)
print("evidence_id:", decision.evidence_id)
print("control    :", decision.get("rule_triggered") or "(none)")
print("explanation:", decision.get("explanation_en"))

if not decision.governed:
    # UNAVAILABLE - the rail did not adjudicate. Never proceed on this.
    print("NOT CLEARED. reason:", decision.reason)
    sys.exit(1)

if decision.approved:
    print("APPROVED - you may perform the action.")
elif decision.blocked:
    print("BLOCKED - do not perform the action.")
    print("why:", decision.get("safe_action"))
elif decision.escalated:
    print("ESCALATED - stop. A human must review evidence", decision.evidence_id)
    print("There is no resume path; see the README.")
```

Run it:

```bash
python first_call.py
```

You should see a `decision` of `APPROVED`, `BLOCKED`, or `ESCALATED`, and an `evidence_id`. That
record is now sealed into the chain. **You have completed an integration.**

---

# READ THIS FIRST

Four things surprise every new integrator.

### 1. `ESCALATED` means STOP. There is no resume path.

`ESCALATED` is not "pending" and not "retry later". **The API has no endpoint that resumes an
escalated action.** There is no callback, no webhook, and no polling endpoint that later flips to
approved. Do not write code that waits for one.

The action stops. A human reviews the sealed evidence record out of band. If the work is to proceed,
it proceeds as a **new** clearance call — and for the four hold/authorized action pairs, that new call
uses the `*_AUTHORIZED` action type with a signed four-eyes assertion. A fresh declaration, not a
continuation.

### 2. `action_type` must be one of the 103 recognized values

The full list is in **[docs/action-types.md](docs/action-types.md)**. Matching is exact — no fuzzy
matching, no nearest-neighbour suggestion. An unrecognized value escalates via
**`TAXO-00 — escalate-on-unknown`**.

| you might send | reality |
|---|---|
| `SEND_EMAIL` | not a value — use `EMAIL` |
| `EXECUTE_TRADE` | not a value — use `TRADE_EXECUTION` |
| `DOCUMENT_PROCESSING` | not recognized at all |

**If your first call escalates with `TAXO-00`, this is almost always why.**

### 3. Fifteen declaration fields are recorded but do NOT affect the verdict

`is_external`, `has_attachment`, `contains_pii`, `regulatory_risk`, `financial_amount`, `priority`,
`is_board_decision`, `involves_trading`, `involves_hr`, `financial_advice`, `involves_tax`,
`public_communication`, `new_it_system`, `autonomous_decision`, `data_classified`

They are sealed into the evidence record and form part of your audit trail. **None of them changes
the decision.** Setting `contains_pii=True` will not cause a block; omitting `financial_amount` will
not avoid one. Declare them accurately — they are evidence — but do not build control flow on them.

**What actually decides:** `action_type`; server-derived facts about your agent (registration, scope,
freeze state, environment, action velocity, the server clock); and the four-eyes attestations.

### 4. `UNAVAILABLE` means not-cleared. Never proceed.

Every client-side failure — unreachable rail, timeout, non-200, malformed response, missing
credential, signing failure — resolves to `decision == "UNAVAILABLE"`. It is **not** a soft failure
and **not** a degraded pass.

Always branch on `decision.governed`, which is `True` only for a real `APPROVED` / `BLOCKED` /
`ESCALATED` verdict from the rail. There is no "allow on failure" mode in this client, and one will
not be added.

---

## Reading the `Decision` object

`Decision` subclasses `dict`. **Eight fields are available as attributes; everything else must be
read with `[...]` or `.get(...)`.**

```python
# Attributes - these eight work:
decision.decision        # "APPROVED" | "BLOCKED" | "ESCALATED" | "UNAVAILABLE"
decision.approved        # bool
decision.blocked         # bool
decision.escalated       # bool
decision.unavailable     # bool
decision.governed        # bool - True only for a real rail verdict
decision.evidence_id     # str
decision.reason          # str - why it is UNAVAILABLE ("" otherwise)

# Everything else is a dict key. Attribute access RAISES AttributeError:
decision["rule_triggered"]          # correct
decision.get("explanation_en")      # correct (safe if absent)
decision.get("safe_action")         # correct
decision.get("risk_level")          # correct

decision.rule_triggered             # WRONG - AttributeError
decision.safe_action                # WRONG - AttributeError
```

Prefer `.get("...")` over `["..."]` for anything you did not just receive — an `UNAVAILABLE` result
carries a reduced field set.

## What each verdict means, and what to do

| verdict | meaning | your next action |
|---|---|---|
| `APPROVED` | permitted for this agent, at this moment | proceed; keep `evidence_id` |
| `BLOCKED` | refused. Terminal. | do not perform it; `decision.get("safe_action")` explains why |
| `ESCALATED` | requires human authority | **stop**; hand `evidence_id` to a human; no resume path |
| `UNAVAILABLE` | the rail did not adjudicate (client-side) | **stop**; print `decision.reason`; fix and re-call |

`requires_approval` is `true` for both `BLOCKED` and `ESCALATED`.

---

# Troubleshooting

### `SSLCertVerificationError: unable to get local issuer certificate` (macOS)

**This is your machine, not MURAQIB.** Python installed from python.org on macOS ships without a
usable CA certificate store, so *every* HTTPS call from that interpreter fails the same way — the
rail is reachable and healthy.

Fix it once:

```bash
open "/Applications/Python 3.12/Install Certificates.command"
```

Adjust the version number to match your Python (`ls /Applications | grep Python`). Or, equivalently:

```bash
pip install --upgrade certifi
```

Then re-run `python first_call.py`. If you still see it, your network may be intercepting TLS with a
corporate proxy — that is a question for your IT team, not for OQIRON.

### `ModuleNotFoundError: No module named 'muraqib_client'`

You installed into a different interpreter than the one you are running. Almost always a missing
`source .venv/bin/activate` (step 2). Check with:

```bash
which python && python -c "import muraqib_client, sys; print(sys.executable)"
```

### `decision` is `UNAVAILABLE` and I do not know why

**`UNAVAILABLE` always carries a `reason`.** Print it:

```python
print(decision.reason)                 # e.g. "rail returned HTTP 401"
print(decision.get("detail"))          # extra context when there is any
```

| `reason` you will see | what it means |
|---|---|
| `api key not configured` | your key file was empty or unreadable |
| `unreachable: ...` | DNS, refused connection, or TLS failure — see the SSL entry above |
| `rail returned HTTP 401` | the key is wrong, revoked, or inactive |
| `rail returned HTTP 403` | your key lacks the `intercept` scope |
| `rail refused: environment_unresolved` | your agent identity is not resolvable server-side — contact OQIRON |
| `malformed JSON response` | something between you and the rail is rewriting responses (proxy?) |
| `assertion signing failed` | four-eyes call without the `[signing]` extra or without a signing key |

### Every call returns `ESCALATED` with `TAXO-00`

Your `action_type` is not one of the 103 recognized values. See
[docs/action-types.md](docs/action-types.md). This is the single most common first-run issue.

### `400 Bad Request` when calling `/api/auth/token` directly

The endpoint requires a JSON body even when the key is in the header — send at least `{}`. This
client already does; you only hit this when hand-rolling curl.

---

## Sandbox vs production

Your environment is **server-derived from your registered agent identity**. The client sends nothing;
if you send an `environment` field it is ignored and logged.

| | production | sandbox |
|---|---|---|
| evidence chain | the production chain | a **separate** chain, own lineage and seed |
| offline anchoring | periodically anchored | **never anchored, by design** |
| operator notifications | dispatched | **suppressed** |
| visibility | production reads | structurally invisible to production reads |

`verify(environment="sandbox")` reports `tip_status: "no-signed-tip"` and
`anchor_status: "not anchored - sandbox chains are not anchored by design"`. **That is not a defect.**

An agent may verify only its **own** environment; asking for the other is refused
(`403 forbidden_environment`).

## Four-eyes authorized actions

Requires the `[signing]` extra **and** a public key registered on our side. Without a registered key
your assertion is not signature-checked at all — see the boundaries below.

> **Python** — same pattern as `first_call.py`.

```python
decision = client.clear(
    "EXTERNAL_CORRESPONDENCE_AUTHORIZED",
    request_ref="REQ-2026-0142",
    held_evidence_id="EVD-XXXXXXXX",              # the escalated hold this authorizes
    authorizer={"id": "u-8812", "email": "head@acme.example",
                "role": "SECTION_HEAD", "is_section_head": True,
                "maker_ids": ["u-4410"]},
)
```

`MURAQIB_SIGNING_KEY` (hex Ed25519 private key) is read from the environment. Key material stays in
memory — never logged, never echoed, never sealed.

## API reference

| method | returns | raises |
|---|---|---|
| `clear(action_type, summary, request_ref, authorizer=None, held_evidence_id=None, **declaration)` | `Decision` | never |
| `intercept(...)` / `clear_action(...)` | aliases of `clear` | never |
| `verify(environment=None)` | `{"ok", "summary", "error"}` | never |
| `health()` | `bool` | never |

The only raise in the client is construction with an invalid `auth_mode`. **No call path raises** —
failures are values, because an exception is easy to catch-and-continue and a governance failure must
not be.

**Auth.** `auth_mode="jwt"` (default) exchanges your API key for a 24-hour token, caches it, and
re-exchanges once on a `401`. `auth_mode="api_key"` sends the key directly on every request — simpler,
and what the quickstart uses. There is no refresh token; re-exchange is the only recovery.

## Boundaries — what MURAQIB does not do

- **It governs the declaration, not the payload.** The rail never sees, parses, or stores your
  content. An approval says the *declared* action was permitted; it says nothing about the bytes you
  then send.
- **One global chain per environment — not per tenant.** There are **no per-tenant inclusion
  proofs**. A tenant cannot independently prove its own subset of the chain.
- **Not an accredited certifier.** Evidence is sealed and offline-anchored. That is a cryptographic
  property, not a regulatory attestation, and no regulator has accredited it.
- **Signature verification is skipped for agents without a registered public key.** If your identity
  has no key registered, four-eyes fields you send are **not signature-checked** — the attested
  values are still adjudicated, but no cryptographic binding exists.
- **`permitted_actions` is only partly enforced.** It gates a control for a small set of action
  domains; elsewhere it is decorative. Not a general authorization surface.
- **Chain integrity is only as fresh as the last anchor.** Between anchors, `pending_anchor > 0` and
  `tip_status` reads `tip-mismatch`. Expected, not tampering.
- **`ESCALATED` has no API resume path.**

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
