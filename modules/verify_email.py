"""
Free, best-effort email verification.

There is no fully free way to guarantee an inbox is real at scale — paid
services (NeverBounce, ZeroBounce, Hunter's verifier) do a live SMTP
handshake and score deliverability. What we CAN do for free, and what
catches the large majority of fake/broken addresses, is:

  1. Syntax check
  2. Confirm the domain actually has mail servers (MX record lookup)

This is what populates the "email_status" column. Treat "valid_domain"
as "worth sending to", not "guaranteed delivered".
"""

import re

import dns.resolver
import requests

import config

EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")

_zb_cache = {}


def _zerobounce_verify(email: str) -> str:
    """Optional paid verification. Returns 'valid_domain', 'no_mail_server',
    or falls back to None on any error so the caller can use the free check."""
    if email in _zb_cache:
        return _zb_cache[email]
    try:
        resp = requests.get(
            "https://api.zerobounce.net/v2/validate",
            params={"api_key": config.EMAIL_VERIFY_API_KEY, "email": email},
            timeout=10,
        )
        resp.raise_for_status()
        status = resp.json().get("status", "")
        result = "valid_domain" if status == "valid" else "no_mail_server"
        _zb_cache[email] = result
        return result
    except Exception as e:
        print(f"  [verify] ZeroBounce failed for {email}, falling back to MX check: {e}")
        return None


def _has_mx_record(domain: str, mx_cache: dict) -> bool:
    """mx_cache is state["mx_cache"] - persisted to state.json between runs,
    so we never re-look-up the same domain's MX records twice, ever."""
    if domain in mx_cache:
        return mx_cache[domain]
    try:
        answers = dns.resolver.resolve(domain, "MX", lifetime=6)
        ok = len(answers) > 0
    except Exception:
        ok = False
    mx_cache[domain] = ok
    return ok


def verify(email: str, mx_cache: dict) -> str:
    """Returns one of: 'invalid_syntax', 'no_mail_server', 'valid_domain'.
    mx_cache should be state["mx_cache"] so lookups persist across runs."""
    if not EMAIL_RE.match(email):
        return "invalid_syntax"

    if config.EMAIL_VERIFY_PROVIDER == "zerobounce" and config.EMAIL_VERIFY_API_KEY:
        result = _zerobounce_verify(email)
        if result is not None:
            return result
        # fall through to free check on any API failure

    domain = email.split("@", 1)[1]
    return "valid_domain" if _has_mx_record(domain, mx_cache) else "no_mail_server"
