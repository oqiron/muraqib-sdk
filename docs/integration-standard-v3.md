# MURAQIB Integration Standard — v3

**Supersedes v2 (issued 2026-07-25).** Every statement below was derived from the running code, not
from v2. Where v2 disagrees, v2 is wrong; the differences are enumerated in §10.

---

## 1. Authentication

### 1.1 Exchange an API key for a token

`POST /api/auth/token`

The key may be supplied **either** in the body as `{"api_key": "..."}` **or** as an `X-API-Key`
header. Both are accepted.

| response field | meaning |
|---|---|
| `token` | HS256 JWT |
| `agent_id` | your authenticated identity |
| `agent_name` | display name |
| `scopes` | the scopes your key holds — **the only self-service way to discover them** |
| `expires_in` | `86400` (24 hours) |

Errors: **400** `api_key required` (none supplied) · **401** `Invalid API key` (unknown, revoked, or
inactive).

JWT claims: `sub` (agent id), `name`, `scopes`, `iat`, `exp`, `iss`. **`iss` is not validated on
inbound requests** — treat it as informational.

> **Implementation note.** `expires_in` is emitted as a literal `86400` while the token TTL comes from
> a separate constant (currently 24 h). They agree today. A conservative client should refresh on a
> `401` rather than trusting `expires_in` alone — this client does both.

### 1.2 Using the token

`Authorization: Bearer <token>`

An expired, malformed, or tampered token fails validation and the route answers
**401** `{"error": "Authentication required", "code": "AUTH_REQUIRED"}`.

**Re-exchange is the only recovery.** There is no refresh-token endpoint and no rotation endpoint.

### 1.3 The `X-API-Key` alternative

An API key may be sent directly instead of exchanging it. On the mutating routes
(`/api/v2/intercept`, `/api/v2/scan`) the key must carry the `intercept` scope, otherwise:

**403** `{"error": "insufficient_scope", "required": "intercept"}`

> **Asymmetry, stated honestly.** The scope gate is enforced on the API-key branch. A JWT is trusted
> for the route it authenticates because the scope was checked when the key was exchanged. Do not
> read a JWT as scope-unchecked authority; read it as authority that was checked earlier.

### 1.4 Scopes

| scope | permits |
|---|---|
| `intercept` | `/api/v2/intercept`, `/api/v2/scan` |
| `read` | `/api/v2/chain/verify` and the read surfaces |

`/api/v2/chain/verify` accepts any one of: a dashboard session whose role may view all evidence; a
`read`-scoped JWT; a `read`-scoped API key.

A separate server-side allowlist gates a small set of additional read routes. It is **not
discoverable by the caller** — if you need one of those routes, that is arranged with OQIRON.

---

## 2. `POST /api/v2/intercept` — the clearance call

### 2.1 Field taxonomy — four tiers

Every field has a default; nothing is syntactically required. That is misleading, so the fields are
grouped by **what they actually do**.

#### Tier 1 — DECIDES: the action identity

| field | default | effect |
|---|---|---|
| `action_type` | `"UNKNOWN"` | the control catalogue keys on this. Unrecognized ⇒ `TAXO-00` ⇒ `ESCALATED`. See `action-types.md`. |

#### Tier 2 — DECIDES: four-eyes and clearance attestations

| field | notes |
|---|---|
| `authorizer_id` | the authorizing human |
| `authorizer_email` | checked against `maker_ids` too — some responders are identified by email only |
| `authorizer_role` | |
| `authorizer_is_section_head` | boolean |
| `maker_ids` | list; canonicalised **sorted** |
| `held_evidence_id` | the escalated hold being authorized; empty string normalises to null |
| `assertion_sig`, `assertion_key_id`, `assertion_body` | Ed25519 assertion — §5 |
| `recipient_restricted` | campaign restricted-entity signal; passed through raw so a malformed value fails closed |

These are **client-attested**: their trust ceiling is the honesty of the caller, plus the Ed25519
signature when a public key is registered (§5).

#### Tier 3 — RECORDED, NOT ADJUDICATED (15 fields)

`is_external`, `has_attachment`, `contains_pii`, `regulatory_risk`, `financial_amount`, `priority`,
`is_board_decision`, `involves_trading`, `involves_hr`, `financial_advice`, `involves_tax`,
`public_communication`, `new_it_system`, `autonomous_decision`, `data_classified`

Sealed into the evidence record; part of your audit trail; **they do not change the verdict**.
Declare them accurately — they are evidence — but do not build control flow on them.

#### Tier 4 — IGNORED AND LOGGED

| field | what really happens |
|---|---|
| `agent_id` | the server binds the **authenticated** identity. Your value is retained as `claimed_agent_id` with an `identity_mismatch` flag — sending a false one is *recorded against you*, not merely discarded. |
| `tenant_id` | server-derived from the authenticated agent |
| `environment` | server-derived from the registered agent; the sent value is ignored and logged |

Metadata recorded but not adjudicated: `summary` (also scanned for PII), `request_ref`, `actor_id`,
`actor_name`, `agent_name`.

### 2.2 What actually determines the verdict

1. **`action_type`** — the intrinsic identity of the action;
2. **server-derived facts** — agent registration and scope, freeze/suspension state, environment,
   action velocity, the server clock (off-hours), and clearance state derived from sealed evidence.
   **None of this comes from your request;**
3. **four-eyes attestations** (Tier 2), adjudicated by the clearance and four-eyes controls.

The authoritative catalogue is **57 controls**.

### 2.3 Response

| field | meaning |
|---|---|
| `evidence_id` | the sealed record id — keep it |
| `decision` | `APPROVED` \| `BLOCKED` \| `ESCALATED` |
| `approved` / `blocked` / `escalated` | booleans mirroring `decision` |
| `requires_approval` | true for `BLOCKED` and `ESCALATED` |
| `rule_triggered` | the primary control id (e.g. `TAXO-00`, `AGT-05`, `EXC-02`) |
| `rule_name_en` | that control's name |
| `risk_score`, `risk_level` | advisory risk annotation — **not** the basis of the verdict |
| `explanation_en`, `explanation_ar` | bilingual decision summary |
| `safe_action` | the clean-core reason / remediation hint |
| `explanation_trace` | structured explainability trace (controls triggered, input signals) |
| `timestamp`, `agent_id` | seal metadata; `agent_id` is the **authenticated** identity |

There is no `policies_fired` field. If you are reading one, you are on an old build.

### 2.4 Status codes

| status | meaning |
|---|---|
| **200** | a verdict was reached and sealed |
| **401** | `{"error":"Authentication required","code":"AUTH_REQUIRED"}` |
| **403** | `{"error":"insufficient_scope","required":"intercept"}` |
| **503** | `{"decision":"REFUSED","error":"environment_unresolved"}` — the rail could not server-derive your agent's environment and **refused**. Nothing was sealed, in either environment. |
| **500** | evidence write failed — nothing was sealed |

Treat everything that is not a `200` carrying a valid `decision` as **not cleared**.

---

## 3. Action types

**103 recognized values across 28 classes** — enumerated in `action-types.md`, generated directly
from the catalogue.

Matching is exact. An unrecognized value classifies as unclassified and triggers
**`TAXO-00 — escalate-on-unknown`** ⇒ `ESCALATED`. This is the most common first-integration
surprise; it is deliberate, because the rail will not guess what an unknown action may do.

---

## 4. Verdict semantics

| verdict | contract |
|---|---|
| `APPROVED` | permitted for this agent at this moment. Proceed. |
| `BLOCKED` | refused. **Terminal.** Do not perform the action. |
| `ESCALATED` | requires human authority. **Stop.** |

**There is no resume path.** No endpoint accepts an `evidence_id` and returns a later approval. There
is no callback, webhook, or polling surface. Human approval is recorded out of band against the
sealed record.

For the four hold/authorized action pairs, authorized work proceeds as a **new clearance call** using
the `*_AUTHORIZED` action type with a signed assertion naming the held evidence id — a fresh
declaration, not a continuation of the escalated one.

---

## 5. Four-eyes assertions

### 5.1 Canonical form

Ten fields, **in exactly this order**:

```
agent_id, action_type, request_ref,
authorizer_id, authorizer_email, authorizer_role,
authorizer_is_section_head, maker_ids, held_evidence_id, ts
```

Canonicalisation, exactly:

- `maker_ids` — sorted; absent ⇒ `[]`
- `held_evidence_id` — empty ⇒ `null`
- serialise with sorted keys, separators `(",", ":")`, `ensure_ascii=True`, encoded UTF-8

`ts` is a Unix timestamp stamped at signing time. Signatures are time-bounded; a stale one is
rejected.

### 5.2 Key id

```
assertion_key_id = sha256(raw_ed25519_public_key)[:8]
```

The server recomputes this from the registered key. A mismatch is rejected.

### 5.3 Registration

Public keys are registered **server-side, manually, by OQIRON** against your agent identity. There is
no self-serve key registration endpoint.

> **Critical.** An agent with **no registered public key** skips signature verification entirely. The
> attested four-eyes values are still adjudicated by the controls, but **no cryptographic binding
> exists**. If you require that binding, you must have a key registered. Do not assume signing is in
> force merely because you sent a signature.

### 5.4 Verification failure

Reasons: `SIGNATURE_MISSING`, `KEY_UNKNOWN`, `SIGNATURE_STALE` (including a TTL-lookup error —
fail-closed), `SIGNATURE_INVALID`.

On failure the decision is attributed to the signature control rather than the four-eyes control, so
the sealed record names the layer that actually refused.

---

## 6. `GET /api/v2/chain/verify`

**Parameter:** `environment` = `production` | `sandbox` (optional; omitted ⇒ the principal's default).

An agent principal may verify **only its own** environment. A cross-environment request is refused
**403** `forbidden_environment`. An unresolvable environment is **503**.

`summary` fields:

| field | meaning |
|---|---|
| `chain_intact` | recomputation matched and the anchor is trusted |
| `anchor_ok` | the signed anchor verified |
| `tip_status` | `tip-verified` \| `tip-mismatch` \| `no-signed-tip` |
| `events_checked` | events recomputed |
| `recomputed_tip` | the tip hash re-derived independently from the genesis seed |
| `status_counts` | per-event verdicts (`ok`, `tampered`, `chain-broken-after`, …) |
| `legacy_unverifiable` | pre-chain records that cannot be verified |
| `anchor_id`, `anchor_covers_seq`, `anchor_pubkey_id` | the latest offline anchor |
| `pending_anchor` | events sealed since that anchor |
| `notes` | anchor warnings, if any |
| `environment`, `anchor_status` | sandbox only |

`tip-mismatch` with `pending_anchor > 0` is the **normal** state between anchors — it means "sealed
but not yet anchored", not tampering. Tampering shows as non-`ok` entries in `status_counts`.

A reduced, attestation-only response exists for tenancy-scoped principals. **It is not active in the
current deployment** — every authorized principal receives the full summary.

---

## 7. Sandbox

Environment is **server-derived** from your registered agent identity; a client-sent `environment` is
ignored and logged.

| | production | sandbox |
|---|---|---|
| evidence log & chain | production tables | **separate** tables, own lineage |
| genesis seed | production seed | **its own seed** — a sandbox event can never verify against production, or vice versa |
| sequence | production sequence | its own, starting at 1 |
| offline anchoring | periodic | **never anchored, by design** |
| operator notifications | dispatched | **suppressed** |
| production read surfaces | included | structurally absent — no filtering involved |

Sandbox verification correctly reports `tip_status: "no-signed-tip"` and
`anchor_status: "not anchored - sandbox chains are not anchored by design"`.

---

## 8. Boundaries — what MURAQIB does not claim

- **Governs the declaration, not the payload.** The rail never sees, parses, or stores your content.
- **One global chain per environment, not per tenant.** **No per-tenant inclusion proofs**; a tenant
  cannot independently prove its own subset.
- **Not an accredited certifier.** Sealing and offline anchoring are cryptographic properties, not a
  regulatory attestation. No regulator has accredited this rail.
- **Signature verification is skipped for agents without a registered public key** (§5.3).
- **`permitted_actions` is only partly enforced** — it gates a control for a limited set of action
  domains; elsewhere it is decorative. Not a general authorization surface.
- **Chain integrity is only as fresh as the last anchor** (§6).
- **`ESCALATED` has no API resume path** (§4).
- **The 15 declaration fields do not affect the verdict** (§2.1 Tier 3).

---

## 9. Authoritative pins — true at time of writing (2026-08-01)

| component | pin |
|---|---|
| control catalogue | `271fa8cb` |
| catalogue adapter | `f31bf87b` |
| application | `2e1e0b37` |
| chain module | `a6fd7d32` |
| clearance module | `936e7e2a` |
| CATALOG | **57 controls** |
| recognized `action_type` values | **103**, in 28 classes |
| production chain | tip **321**, anchored `id22 PERIODIC_TIP @321`, `pending_anchor 0` |
| sandbox chain | tip **5**, unanchored by design |

**A deployment whose live SHAs differ from these is a different build than this Standard describes.
Reconcile before relying on it.**

---

## 10. Supersession — the nine ways v2 was wrong

v2 was issued 2026-07-25 and is superseded. It is wrong in the following ways; each is corrected
above.

| # | v2 said | v3 / reality |
|---|---|---|
| 1 | application pin `c70812c0` | `2e1e0b37` — five movements later |
| 2 | chain tip 271, anchor @264 | tip **321**, anchor **id22 @321** |
| 3 | "Tenancy — v1-STATUS: single-tenant" | tenancy is live; a demonstration tenant is in use |
| 4 | no mention of `503 environment_unresolved` | a real, documented response (§2.4) |
| 5 | no sandbox environment, no `environment=` verify parameter | both shipped (§6, §7) |
| 6 | "every reference client fails closed on any error" | true of the named reference clients; the previous SDK also shipped an *allow-on-failure* mode that fabricated approvals. **Removed** — the current client has no such mode. |
| 7 | described the attestation/read-scope response as current behaviour | that branch is **not active** in this deployment (§6) |
| 8 | never enumerated the recognized `action_type` values | all **103** enumerated in `action-types.md`, generated from the catalogue |
| 9 | presented assertion signing as universal | verification is **skipped entirely** for agents without a registered public key (§5.3) |

Items 6 and 9 are the two that could have caused an integrator to believe they were governed when
they were not. They are the reason this revision exists.
