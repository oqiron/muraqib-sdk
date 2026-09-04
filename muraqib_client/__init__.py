"""MURAQIB canonical client — the single supported way for an EXTERNAL integrator to call the
MURAQIB governance rail.

Consolidates the behaviours previously spread across several internal clients: JWT exchange with
token caching and refresh-on-401; Ed25519 four-eyes assertion signing; a typed decision object.
This is the first client where JWT auth and four-eyes signing exist together.

FAIL-CLOSED, WITHOUT EXCEPTION. Every failure mode -- connection error, timeout, non-200 (including
503 environment_unresolved), malformed JSON, missing/late token, missing signing key, signing error
-- resolves to decision == UNAVAILABLE. UNAVAILABLE means NOT CLEARED: the caller must not proceed
and must not record the action as governed. There is deliberately NO "allow on failure" mode.

Transport is stdlib-only (urllib). Ed25519 signing requires the optional `cryptography` extra;
without it, four-eyes calls fail closed to UNAVAILABLE rather than being sent unsigned.
"""
import base64
import hashlib
import json
import os
import time
import urllib.error
import urllib.request

__version__ = "2.3.0"
__all__ = ["MuraqibClient", "Decision", "UNAVAILABLE", "APPROVED", "BLOCKED", "ESCALATED", "__version__"]

APPROVED    = "APPROVED"
BLOCKED     = "BLOCKED"
ESCALATED   = "ESCALATED"
UNAVAILABLE = "UNAVAILABLE"
_SERVER_DECISIONS = (APPROVED, BLOCKED, ESCALATED)

DEFAULT_URL = "https://muraqib.oqiron.ai"
DEFAULT_TIMEOUT_S = 10.0
_TOKEN_SKEW_S = 60          # refresh this long before expiry
_USER_AGENT = "muraqib-client/" + __version__

# LOAD-BEARING: byte-identical to the server-side assertion verifier.
# Changing the list, the order, or the canonicalisation below invalidates every signature.
CANONICAL_FIELDS_V2 = [
    "agent_id", "action_type", "request_ref",
    "authorizer_id", "authorizer_email", "authorizer_role",
    "authorizer_is_section_head", "maker_ids", "held_evidence_id", "ts",
]

try:                                                  # optional extra: muraqib-client[signing]
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    _HAVE_CRYPTO = True
except Exception:                                     # pragma: no cover - absence is a runtime state
    _HAVE_CRYPTO = False


class Decision(dict):
    """The result of a clearance call. Always a dict with a `decision` key; also exposes
    attribute access. NEVER raises. `governed` is True only for a real server verdict."""

    @property
    def decision(self):        return self.get("decision", UNAVAILABLE)
    @property
    def approved(self):        return self.decision == APPROVED
    @property
    def blocked(self):         return self.decision == BLOCKED
    @property
    def escalated(self):       return self.decision == ESCALATED
    @property
    def unavailable(self):     return self.decision == UNAVAILABLE
    @property
    def governed(self):
        """True iff the rail returned an authoritative verdict. False for UNAVAILABLE."""
        return self.decision in _SERVER_DECISIONS
    @property
    def evidence_id(self):     return self.get("evidence_id", "")
    @property
    def reason(self):          return self.get("reason", "")

    def __repr__(self):
        return "Decision(%s%s)" % (
            self.decision,
            (" evidence_id=%s" % self.evidence_id) if self.evidence_id else
            ((" reason=%s" % self.reason) if self.reason else ""))


def _unavailable(reason, detail=None):
    return Decision({
        "decision": UNAVAILABLE, "reason": reason, "detail": detail,
        "evidence_id": "", "requires_approval": None, "rule_triggered": "",
        "rule_name_en": "", "risk_level": "", "risk_score": None,
        "explanation_en": "", "explanation_ar": "", "safe_action": "",
        "raw_response": None,
    })


def _canonicalize(assertion, fields=CANONICAL_FIELDS_V2):
    """BYTE-IDENTICAL to the server-side assertion canonicalisation."""
    d = {}
    for k in fields:
        v = assertion.get(k, None)
        if k == "maker_ids":
            v = sorted(v) if v else []
        elif k == "held_evidence_id":
            v = v or None
        d[k] = v
    return json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


class MuraqibClient(object):
    """Canonical MURAQIB rail client.

    auth_mode:
      "jwt"      (default) exchange the API key for a short-lived JWT, cache it, refresh on 401.
      "api_key"  send the API key directly as X-API-Key (matches the in-tree product clients).

    There is no fail_safe parameter. Failure is always UNAVAILABLE.
    """

    def __init__(self, api_key=None, agent_id=None, muraqib_url=None, timeout=DEFAULT_TIMEOUT_S,
                 auth_mode="jwt", signing_key_hex=None):
        self.api_key = api_key or os.environ.get("MURAQIB_API_KEY", "")
        self.agent_id = agent_id or os.environ.get("MURAQIB_AGENT_ID", "")
        self.muraqib_url = (muraqib_url or os.environ.get("MURAQIB_URL", DEFAULT_URL)).rstrip("/")
        self.timeout = float(timeout)
        if auth_mode not in ("jwt", "api_key"):
            raise ValueError("auth_mode must be 'jwt' or 'api_key'")
        self.auth_mode = auth_mode
        # Key material is held in memory only; never logged, never echoed, never sealed.
        self._signing_key_hex = signing_key_hex or os.environ.get("MURAQIB_SIGNING_KEY", "")
        self._token = None
        self._token_exp = 0.0

    # ---------------------------------------------------------------- transport
    def _headers(self, extra=None):
        h = {"Content-Type": "application/json",
             "User-Agent": _USER_AGENT,
             "X-Muraqib-Client": _USER_AGENT}      # server may log client versions
        if extra:
            h.update(extra)
        return h

    def _request(self, method, path, body=None, headers=None):
        """-> (status:int, parsed:dict|None, error:str|None). Never raises."""
        url = self.muraqib_url + path
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, headers=self._headers(headers), method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
                status = resp.status
        except urllib.error.HTTPError as exc:                 # non-2xx WITH a body
            try:
                raw = exc.read()
            except Exception:
                raw = b""
            status = exc.code
        except urllib.error.URLError as exc:                  # DNS / refused / TLS / timeout
            return 0, None, "unreachable: %s" % type(getattr(exc, "reason", exc)).__name__
        except Exception as exc:                              # socket.timeout & anything else
            return 0, None, "transport error: %s" % type(exc).__name__
        try:
            parsed = json.loads(raw.decode("utf-8")) if raw else None
        except Exception:
            return status, None, "malformed JSON response"
        return status, parsed, None

    # ---------------------------------------------------------------- auth (masaar reference)
    def _auth_headers(self, force_refresh=False):
        """-> (headers:dict, error:str|None)."""
        if not self.api_key:
            return None, "api key not configured"
        if self.auth_mode == "api_key":
            return {"X-API-Key": self.api_key}, None
        if force_refresh or not self._token or time.time() >= (self._token_exp - _TOKEN_SKEW_S):
            status, parsed, err = self._request(
                "POST", "/api/auth/token", body={}, headers={"X-API-Key": self.api_key})
            if err:
                return None, "token exchange failed (%s)" % err
            if status != 200 or not isinstance(parsed, dict):
                return None, "token exchange failed (HTTP %s)" % status
            token = parsed.get("token") or parsed.get("access_token")
            if not token:
                return None, "token exchange response carried no token"
            self._token = token
            # honour an explicit expiry when offered; otherwise assume a conservative 15 min
            try:
                self._token_exp = time.time() + float(parsed.get("expires_in", 900))
            except Exception:
                self._token_exp = time.time() + 900
        return {"Authorization": "Bearer " + self._token}, None

    # ---------------------------------------------------------------- signing (product copies)
    def _sign_assertion(self, fields):
        """Ed25519-sign the 10-field V2 canonical assertion. Raises; callers convert to UNAVAILABLE."""
        if not _HAVE_CRYPTO:
            raise RuntimeError("signing requires the optional extra: pip install muraqib-client[signing]")
        if not self._signing_key_hex:
            raise RuntimeError("MURAQIB_SIGNING_KEY not configured")
        sk = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(self._signing_key_hex))
        ts = int(time.time())
        a = dict(fields)
        a["ts"] = ts
        msg = _canonicalize(a)
        sig = sk.sign(msg)
        pub_raw = sk.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        key_id = hashlib.sha256(pub_raw).hexdigest()[:8]
        return base64.b64encode(sig).decode("ascii"), key_id, ts, msg.decode("utf-8")

    # ---------------------------------------------------------------- the clearance call
    def clear(self, action_type, summary="", request_ref="", authorizer=None,
              held_evidence_id=None, **declaration):
        """Submit an action for clearance. Returns a Decision, ALWAYS. Never raises.

        action_type   the intrinsic action identity -- this is what the control catalogue keys on.
        authorizer    when given, this is a four-eyes AUTHORIZE: a signed 10-field V2 assertion is
                      attached. A signing failure returns UNAVAILABLE; the call is NEVER sent unsigned.
        **declaration additional declared fields (see README: these are recorded, not adjudicated).
        """
        if not self.agent_id:
            return _unavailable("agent_id not configured")
        headers, err = self._auth_headers()
        if err:
            return _unavailable(err)

        body = dict(declaration)
        body.pop("agent_id", None)                 # server binds the AUTHENTICATED identity
        body["agent_id"] = self.agent_id
        body["action_type"] = action_type
        body["summary"] = summary
        body["request_ref"] = request_ref

        if authorizer:
            fields = {
                "agent_id":                   self.agent_id,
                "action_type":                action_type,
                "request_ref":                request_ref,
                "authorizer_id":              (authorizer.get("id") or "").strip(),
                "authorizer_email":           (authorizer.get("email") or "").strip(),
                "authorizer_role":            (authorizer.get("role") or "").strip(),
                "authorizer_is_section_head": bool(authorizer.get("is_section_head", False)),
                "maker_ids":                  list(authorizer.get("maker_ids") or []),
                "held_evidence_id":           held_evidence_id or None,
            }
            try:
                sig, key_id, ts, canon = self._sign_assertion(fields)
            except Exception as exc:
                # FAIL-CLOSED: never send an authorized call unsigned.
                return _unavailable("assertion signing failed", type(exc).__name__)
            body.update(fields)
            body["held_evidence_id"] = held_evidence_id or None
            body.update({"assertion_sig": sig, "assertion_key_id": key_id,
                         "assertion_ts": ts, "assertion_body": canon})

        status, parsed, err = self._request("POST", "/api/v2/intercept", body=body, headers=headers)
        if status == 401 and self.auth_mode == "jwt":          # token rejected -> refresh once
            headers, aerr = self._auth_headers(force_refresh=True)
            if aerr:
                return _unavailable(aerr)
            status, parsed, err = self._request("POST", "/api/v2/intercept", body=body, headers=headers)

        if err:
            # err distinguishes transport failure from an unparseable body; both are not-cleared.
            return _unavailable(err if "JSON" in err else "rail unreachable", err)
        if status == 503:
            # B5b: the rail refuses when it cannot server-derive the agent's environment.
            reason = (parsed or {}).get("error") or "service unavailable"
            return _unavailable("rail refused: %s" % reason, (parsed or {}).get("detail"))
        if status != 200:
            return _unavailable("rail returned HTTP %s" % status, (parsed or {}).get("error") if parsed else None)
        if not isinstance(parsed, dict) or parsed.get("decision") not in _SERVER_DECISIONS:
            return _unavailable("malformed decision in rail response")

        out = Decision(parsed)
        out["raw_response"] = parsed
        out["reason"] = ""
        return out

    # backwards-compatible alias for the in-tree product clients' name
    clear_action = clear

    def intercept(self, action_type, summary="", request_ref="", **declaration):
        """Alias of clear() for callers who think of it as an interception point."""
        return self.clear(action_type, summary=summary, request_ref=request_ref, **declaration)

    # ---------------------------------------------------------------- read surfaces
    def verify(self, environment=None):
        """GET /api/v2/chain/verify. `environment` is 'production' | 'sandbox' | None (server default).
        An agent principal may only verify its OWN environment; a cross-environment request is
        refused 403 by the rail. Returns {"ok": bool, "summary": {...}|None, "error": str|None}.
        Never raises."""
        headers, err = self._auth_headers()
        if err:
            return {"ok": False, "summary": None, "error": err}
        path = "/api/v2/chain/verify"
        if environment:
            if environment not in ("production", "sandbox"):
                return {"ok": False, "summary": None, "error": "environment must be 'production' or 'sandbox'"}
            path += "?environment=" + environment
        status, parsed, err = self._request("GET", path, headers=headers)
        if status == 401 and self.auth_mode == "jwt":
            headers, aerr = self._auth_headers(force_refresh=True)
            if aerr:
                return {"ok": False, "summary": None, "error": aerr}
            status, parsed, err = self._request("GET", path, headers=headers)
        if err:
            return {"ok": False, "summary": None, "error": err}
        if status != 200:
            return {"ok": False, "summary": None,
                    "error": (parsed or {}).get("error") or ("HTTP %s" % status)}
        return {"ok": True, "summary": (parsed or {}).get("summary"), "error": None}

    def health(self):
        """True iff the rail answers /health with 200. Never raises."""
        status, _parsed, _err = self._request("GET", "/health")
        return status == 200
