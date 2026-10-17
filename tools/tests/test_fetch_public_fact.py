"""`fetch_public_fact.py` — 277 lines of SSRF defence (RULEBOOK L16) with zero retained
counter-examples until now. Closes the finding registered as OG-17-corrected /
`GAP-fetch_public_fact-SSRF-defence-untested`.

**Why this file exists.** OG-17 disposed this module `NOT_A_DEFECT` on the reasoning "this is
not a guard" — but the module's own docstring says the opposite: "Every check fails CLOSED: any
ambiguity (unresolvable host, private/loopback/link-local IP, non-http(s) scheme, redirect to a
non-allowlisted host, oversized/slow response, disallowed content-type) raises rather than
silently degrading." A guard nothing calls and nothing tests is unproven, exactly like the
`video_script.py` gap closed at OG-120 — the identical argument, just declined here first.

This file retains the five refusals that were re-derived live at HEAD, none of which need
network access: the blocked-IP check and the scheme/allowlist checks both run and raise before
any socket is opened (see `_validate_and_split` / `_resolve_pinned_ip` in `fetch_public_fact.py`
— a numeric-IP host is parsed by `socket.getaddrinfo` without a real DNS round-trip, and the
scheme/allowlist checks happen even earlier).
"""

from __future__ import annotations

import unittest

from tools.docgen.fetch_public_fact import FetchError, fetch


class SsrfDefenceRefusals(unittest.TestCase):
    """Each of these must raise ``FetchError`` and must never reach the network."""

    def test_metadata_link_local_ip_is_refused(self) -> None:
        with self.assertRaises(FetchError):
            fetch(
                "http://169.254.169.254/latest/meta-data/",
                allowlist={"169.254.169.254"},
            )

    def test_loopback_ip_is_refused(self) -> None:
        with self.assertRaises(FetchError):
            fetch("http://127.0.0.1:8080/x", allowlist={"127.0.0.1"})

    def test_rfc1918_private_ip_is_refused(self) -> None:
        with self.assertRaises(FetchError):
            fetch("http://10.0.0.5/x", allowlist={"10.0.0.5"})

    def test_non_http_scheme_is_refused(self) -> None:
        with self.assertRaises(FetchError):
            fetch("file:///etc/passwd", allowlist={"etc"})

    def test_off_allowlist_host_is_refused(self) -> None:
        with self.assertRaises(FetchError):
            fetch(
                "http://not-allowed.example.com/x",
                allowlist={"allowed.example.com"},
            )


if __name__ == "__main__":
    unittest.main()
