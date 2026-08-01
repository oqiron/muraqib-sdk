# muraqib-client

Canonical Python client for the **MURAQIB** AI-governance rail.

```bash
pip install muraqib-client              # clearance, verify, health — stdlib only
pip install muraqib-client[signing]     # + Ed25519 four-eyes assertion signing
```

```python
from muraqib_client import MuraqibClient

m = MuraqibClient(api_key="...", agent_id="ACME-PRD-001",
                  muraqib_url="https://muraqib.oqiron.ai")

d = m.clear("SEND_EMAIL", summary="Quarterly update to the client list",
            request_ref="REQ-2026-0142")

if not d.governed:          # UNAVAILABLE — the rail did not adjudicate
    raise SystemExit("not cleared: %s" % d.reason)   # DO NOT PROCEED
if d.approved:
    send_the_email()
```

---

## Read this before you integrate

### 1. The declared risk flags do **not** affect the verdict
The rail accepts a number of declared fields — `financial_amount`, `contains_pii`, `is_external`,
`priority`, `regulatory_risk`, `involves_trading`, `involves_hr`, `financial_advice`, `involves_tax`,
`public_communication`, `new_it_system`, `autonomous_decision`, `is_board_decision`,
`data_classified`. **None of them changes the decision.**

The authoritative control catalogue adjudicates on exactly three things:

1. **`action_type`** — the intrinsic identity of the action;
2. **server-derived facts** — your agent's registration, scope, freeze state, environment,
   action velocity, the server clock (off-hours). Never anything you send;
3. **four-eyes attestations** — the signed authorizer/maker assertion (below).

Declared flags are **recorded in the evidence record**, so they are part of the audit trail and can
be held against you — but they are not the basis of the verdict. Do not build logic on the belief
that setting `contains_pii=True` will cause a block, and do not assume omitting it avoids one.

### 2. MURAQIB governs the declaration, not the payload
The rail never sees, parses or stores your actual content. It governs **what you declared you were
about to do**. Clearance is not content inspection; an approved decision says the declared action
was permitted for that agent at that moment, nothing about the bytes you subsequently send.

### 3. `UNAVAILABLE` means **not cleared**
Every failure mode resolves to `decision == "UNAVAILABLE"`:

| condition | result |
|---|---|
| connection refused / DNS / TLS failure | `UNAVAILABLE` |
| timeout | `UNAVAILABLE` |
| any non-200 (incl. `503 environment_unresolved`) | `UNAVAILABLE` |
| malformed or unparseable JSON | `UNAVAILABLE` |
| missing / rejected credential | `UNAVAILABLE` |
| missing signing key, or `[signing]` extra not installed | `UNAVAILABLE` |
| Ed25519 signing error | `UNAVAILABLE` (the call is **never sent unsigned**) |

**It is never safe to proceed on `UNAVAILABLE`.** It is not a soft failure, not a degraded pass, and
not something to retry-then-ignore. The action was not governed; if you perform it anyway, you have
an ungoverned action and no evidence record. Use `decision.governed` — `True` only for a real
`APPROVED` / `BLOCKED` / `ESCALATED` verdict from the rail.

**There is no `fail_safe="allow"`.** Earlier internal clients offered a mode that fabricated an
`APPROVED` result when the rail was unreachable. That branch does not exist here and will not be
added. A governance client that invents approvals is not a governance client.

### 4. Sandbox: the client sends nothing
Environment (production vs sandbox) is **server-derived** from your registered agent. The rail
ignores and logs any `environment` field a client sends. Sandbox agents seal to a separate chain
with its own lineage, never anchored, structurally invisible to production reads.

Two consequences: you do not select your environment — registration does; and if the rail cannot
resolve your agent's environment it **refuses the call** (`503`), which this client surfaces as
`UNAVAILABLE`. The one place `environment` *is* a real parameter is `verify()`, where an agent
principal may verify only its own environment's chain (a cross-environment request is refused 403).

### 5. Four-eyes assertions need the signing extra
Authorized-class actions carry a signed 10-field V2 canonical assertion. The Python standard library
cannot do Ed25519, so signing lives behind `pip install muraqib-client[signing]` (adds
`cryptography`). Everything else remains dependency-free. Without the extra, a four-eyes call
returns `UNAVAILABLE` — it is never downgraded to an unsigned call.

```python
d = m.clear("EXTERNAL_CORRESPONDENCE_AUTHORIZED",
            request_ref="REQ-2026-0142",
            held_evidence_id="EVD-…",
            authorizer={"id": "u-8812", "email": "head@acme.example",
                        "role": "SECTION_HEAD", "is_section_head": True,
                        "maker_ids": ["u-4410"]})
```

`MURAQIB_SIGNING_KEY` (hex Ed25519 private key) is read from the environment. Key material is held
in memory only — never logged, never echoed, never sealed.

---

## API

| method | returns | raises |
|---|---|---|
| `clear(action_type, summary, request_ref, authorizer=None, held_evidence_id=None, **declaration)` | `Decision` | never |
| `intercept(...)` | alias of `clear` | never |
| `clear_action(...)` | alias of `clear` (in-tree client compatibility) | never |
| `verify(environment=None)` | `{"ok", "summary", "error"}` | never |
| `health()` | `bool` | never |

**Exception surface:** the only thing that raises is `MuraqibClient(...)` construction, and only on
programmer error (`auth_mode` not in `{"jwt","api_key"}`). No call path raises — failures are values,
not exceptions, because an exception is easy to catch-and-continue and a governance failure must not
be. `Decision` is a `dict` subclass, so it survives `json.dumps` and logging unchanged.

**Authentication.** `auth_mode="jwt"` (default) exchanges your API key for a short-lived token,
caches it, and refreshes once on a `401`. `auth_mode="api_key"` sends `X-API-Key` directly.

**Versioning.** The client sends `X-Muraqib-Client: muraqib-client/<version>` on every request so the
rail can log client versions. `muraqib_client.__version__` is the constant.

---

## Provenance — what came from where

This client consolidates six divergent in-tree copies:

| source | contributed |
|---|---|
| the MASSAR coordinator client | JWT exchange, token caching, refresh-on-401, `UNAVAILABLE` discipline (reference implementation) |
| `mizan` / `maarifa` / `midad` / `rabt` product clients | Ed25519 four-eyes signing, `CANONICAL_FIELDS_V2`, never-send-unsigned rule, stdlib-only transport |
| the legacy MURAQIB SDK | typed decision object, `health()` |
| — dropped — | `fail_safe="allow"` (silent approval on unreachable rail) |

**This is the first client in which JWT authentication and four-eyes signing exist together.**

`CANONICAL_FIELDS_V2` and `_canonicalize()` are **byte-identical** to the server's
`assertion_verifier`. Changing the field list, its order, or the JSON separators invalidates every
signature the rail will accept.

## Scope: external integrators only

This package is for **external integrators**. The six in-tree copies listed above are still in use by
their own products and have **not** been migrated to this client. That consolidation is a separate,
deliberately deferred piece of work — recorded here so it is not forgotten:

> **PENDING:** migrate the MASSAR coordinator client, the per-product clients
> and the legacy MURAQIB SDK (9 internal consumers) onto `muraqib-client`. Until then,
> internal products continue to use their own clients and this package is not the only client in play.

## License

Apache-2.0. See `LICENSE`.
