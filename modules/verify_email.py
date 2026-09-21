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

EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")

_mx_cache = {}


def _has_mx_record(domain: str) -> bool:
    if domain in _mx_cache:
        return _mx_cache[domain]
    try:
        answers = dns.resolver.resolve(domain, "MX", lifetime=6)
        ok = len(answers) > 0
    except Exception:
        ok = False
    _mx_cache[domain] = ok
    return ok


def verify(email: str) -> str:
    """Returns one of: 'invalid_syntax', 'no_mail_server', 'valid_domain'"""
    if not EMAIL_RE.match(email):
        return "invalid_syntax"
    domain = email.split("@", 1)[1]
    return "valid_domain" if _has_mx_record(domain) else "no_mail_server"
