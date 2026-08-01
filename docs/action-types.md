# Recognized `action_type` values

**103 recognized values across 28 classes.** Generated from the live control catalogue — this file
is the authoritative list.

`action_type` is the single most important field you send: the control catalogue keys on it.
Anything not on this list is **unclassified** and escalates via `TAXO-00`, every time.

## Near-miss warnings — read before you guess

Matching is **exact**. There is no fuzzy matching, no normalisation beyond the literal string,
and no suggestion of a close alternative. The mistakes people actually make:

| you might send | status | use instead |
|---|---|---|
| `SEND_EMAIL` | **not a value** | `EMAIL` |
| `EXECUTE_TRADE` | **not a value** | `TRADE_EXECUTION` |
| `DOCUMENT_PROCESSING` | **not a value** — nothing equivalent exists | pick the value that names what the action *is* |

Each of those returns `ESCALATED` with `rule_triggered: TAXO-00`. That is correct behaviour:
the rail refuses to guess what an action it does not recognise might be permitted to do.

## Hold / authorized pairs

Four classes come in pairs: a **hold** action that escalates, and an **authorized** counterpart
that carries a signed four-eyes assertion naming the held evidence id.

| hold action | authorized counterpart |
|---|---|
| `DOCUMENT_LLM_EGRESS` | `DOCUMENT_LLM_EGRESS_AUTHORIZED` |
| `EXTERNAL_CORRESPONDENCE` | `EXTERNAL_CORRESPONDENCE_AUTHORIZED` |
| `MEMORY_INGEST` | `MEMORY_INGEST_AUTHORIZED` |
| `SCREENING_DISPOSITION` | `SCREENING_DISPOSITION_AUTHORIZED` |

Submitting the authorized action is a **new clearance call**, not a resumption of the held one.

## All values by class

### `AGENT_CONTROL` — 4 values

- `AI_MODEL_DEPLOYMENT`
- `ALGORITHM_CHANGE`
- `CORE_SYSTEM_CHANGE`
- `MODEL_UPDATE`

### `CAMPAIGN_CONTENT` — 1 value

- `CAMPAIGN_CONTENT`

### `CAMPAIGN_RECIPIENT` — 1 value

- `CAMPAIGN_RECIPIENT`

### `CAMPAIGN_RECIPIENT_AUTHORIZED` — 1 value

- `CAMPAIGN_RECIPIENT_AUTHORIZED`

### `CONTENT_PUBLIC` — 12 values

- `BOARD_REPORT`
- `CLIENT_REPORT`
- `EXTERNAL_REPORT`
- `INVESTOR_REPORT`
- `PRESS_RELEASE`
- `PUBLIC_COMMUNICATION`
- `PUBLIC_STATEMENT`
- `PUBLISHED_REPORT`
- `REGULATORY_DISCLOSURE`
- `REGULATORY_REPORT`
- `REPORT_GENERATION`
- `SOCIAL_MEDIA_POST`

### `CREDIT_DECISION` — 3 values

- `CREDIT_DECISION`
- `CREDIT_SCORING`
- `LOAN_APPROVAL`

### `CROSS_BORDER` — 5 values

- `CORRESPONDENT_SETTLEMENT`
- `CROSS_BORDER_DATA_TRANSFER`
- `CROSS_BORDER_TRANSFER`
- `INTERNATIONAL_DATA_TRANSFER`
- `INTERNATIONAL_TRANSFER`

### `CUSTOMER_INTERACTION` — 6 values

- `ACCOUNT_OPENING`
- `CONTRACT_TERMS`
- `CUSTOMER_COMMUNICATION`
- `CUSTOMER_ONBOARDING`
- `FEE_DISCLOSURE`
- `KYC_VERIFICATION`

### `DATA_EGRESS` — 7 values

- `BULK_DATA_EXPORT`
- `DATABASE_EXPORT`
- `DATA_EXPORT`
- `DATA_TRANSFER`
- `EXTERNAL_DATA_SHARE`
- `MASS_EXTRACTION`
- `PII_EXPORT`

### `DATA_LIFECYCLE` — 3 values

- `DATA_DELETION`
- `DATA_PROCESSING`
- `DATA_RETENTION_CHANGE`

### `DATA_RESIDENCY` — 2 values

- `CLOUD_MIGRATION`
- `DATA_STORAGE_LOCATION`

### `DOCUMENT_LLM_EGRESS` — 1 value

- `DOCUMENT_LLM_EGRESS`  *(hold — escalates; see the authorized counterpart)*

### `DOCUMENT_LLM_EGRESS_AUTHORIZED` — 1 value

- `DOCUMENT_LLM_EGRESS_AUTHORIZED`  *(authorized — requires a signed four-eyes assertion)*

### `EXTERNAL_COMMS` — 1 value

- `EXTERNAL_CORRESPONDENCE`  *(hold — escalates; see the authorized counterpart)*

### `EXTERNAL_COMMS_AUTHORIZED` — 1 value

- `EXTERNAL_CORRESPONDENCE_AUTHORIZED`  *(authorized — requires a signed four-eyes assertion)*

### `EXTERNAL_INTEGRATION` — 4 values

- `API_INTEGRATION`
- `SYSTEM_INTEGRATION`
- `THIRD_PARTY_SHARE`
- `VENDOR_ONBOARDING`

### `HR_ACTION` — 4 values

- `HIRING_DECISION`
- `HR_DECISION`
- `PROMOTION_DECISION`
- `TERMINATION_DECISION`

### `INTERNAL_OPS` — 10 values

- `DATA_ACCESS`
- `EMAIL`
- `EXPENSE_APPROVAL`
- `GENERIC`
- `INTERNAL_ANALYTICS_REPORT`
- `INTERNAL_LOOKUP`
- `INTERNAL_NOTE`
- `INTERNAL_REPORT`
- `MANAGEMENT_REPORT`
- `STATUS_UPDATE`

### `MARKET_CONDUCT` — 11 values

- `AUTOMATED_ADVISORY`
- `CHATBOT`
- `FINANCIAL_ADVICE`
- `INSIDER_INFORMATION_SHARING`
- `INVESTMENT_RECOMMENDATION`
- `MARKET_SENSITIVE_DISCLOSURE`
- `PORTFOLIO_REBALANCE`
- `PRE_ANNOUNCEMENT_SHARING`
- `ROBO_ADVICE`
- `TRADE_EXECUTION`
- `TRADING_ORDER`

### `MEMORY_INGEST` — 1 value

- `MEMORY_INGEST`  *(hold — escalates; see the authorized counterpart)*

### `MEMORY_INGEST_AUTHORIZED` — 1 value

- `MEMORY_INGEST_AUTHORIZED`  *(authorized — requires a signed four-eyes assertion)*

### `MEMORY_RETRIEVAL` — 1 value

- `MEMORY_RETRIEVAL`

### `MONEY_MOVEMENT` — 11 values

- `FINANCIAL_TRANSFER`
- `FUND_TRANSFER`
- `GOVERNMENT_BANKING`
- `GOVERNMENT_PAYMENT`
- `HOSPITALITY_BOOKING`
- `PAYMENT`
- `PUBLIC_FUND_TRANSFER`
- `REMITTANCE`
- `SETTLEMENT`
- `VENDOR_PAYMENT`
- `WIRE_TRANSFER`

### `OVERSIGHT_EXPORT` — 1 value

- `OVERSIGHT_EXPORT`

### `SCREENING_DISPOSITION` — 1 value

- `SCREENING_DISPOSITION`  *(hold — escalates; see the authorized counterpart)*

### `SCREENING_DISPOSITION_AUTHORIZED` — 1 value

- `SCREENING_DISPOSITION_AUTHORIZED`  *(authorized — requires a signed four-eyes assertion)*

### `SCREENING_RUN` — 1 value

- `SCREENING_RUN`

### `SECURITY_EVENT` — 7 values

- `ACCESS_GRANT`
- `EMERGENCY_OVERRIDE`
- `INCIDENT_RESPONSE`
- `LIFE_SAFETY`
- `PRIVILEGE_ESCALATION`
- `SAFETY_CRITICAL`
- `SECURITY_INCIDENT`

---

## Anything else

An `action_type` not listed above is classified `UNCLASSIFIED`. The catalogue then applies
`TAXO-00 — escalate-on-unknown`, and the decision is `ESCALATED`:

```json
{ "decision": "ESCALATED", "rule_triggered": "TAXO-00",
  "explanation_en": "Decision: ESCALATED\nControl: TAXO-00 Unclassified action — mandatory escalation\n..." }
```

`ESCALATED` means **stop** — see the README. It is not a retryable error and there is no
resume path; sending the same unrecognised value again produces the same result.

If your action genuinely has no home in this list, that is a conversation to have with OQIRON
before you integrate — not something to work around by picking an approximate value. Declaring
an action as something it is not is a governance failure that the evidence record will preserve.
