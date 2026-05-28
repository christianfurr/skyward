"""Skyward Family Access login flow.

The Skyward login endpoint (`skyporthttp.w`) returns a caret-delimited string
embedded in `<li>...</li>` tags. We parse out the auth tokens, then POST them
to `sfhome01.w` to materialize an authenticated session. Subsequent page
requests must carry these tokens as form data and/or query parameters; the
`SkywardSession` returned here owns an `httpx.Client` whose cookie jar has been
warmed up by the second POST.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx

from .exceptions import AuthError

DEFAULT_TIMEOUT = 30.0


@dataclass
class SkywardSession:
    base_url: str
    client: httpx.Client
    encses: str
    sessionid: str
    params: dict[str, str] = field(default_factory=dict)

    def auth_form(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        """Build the form body for an authenticated page-load POST.

        Page-load endpoints (sfhome01.w, sfgradebook001.w, sfattendance001.w,
        etc.) only need `sessionid` + `encses`. The full param bundle is for
        session finalization and AJAX endpoints that want `dwd`/`wfaacl`.
        """
        body = {"sessionid": self.sessionid, "encses": self.encses}
        if extra:
            body.update(extra)
        return body

    def xhr_form(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        """Form body for AJAX endpoints (httploader.p?file=...).

        These need the page-context tokens (`dwd`, `wfaacl`) plus session ids.
        """
        body = {
            "sessionid": self.sessionid,
            "encses": self.encses,
            "dwd": self.params.get("dwd", ""),
            "wfaacl": self.params.get("wfaacl", ""),
        }
        if extra:
            body.update(extra)
        return body

    def close(self) -> None:
        self.client.close()


def _parse_login_response(text: str) -> list[str]:
    text = text.strip()
    if not text:
        raise AuthError("Empty login response from Skyward (possible transient failure)")
    if "Invalid login" in text or "invalid login" in text.lower():
        raise AuthError("Invalid Skyward username or password")
    if "<li>" not in text:
        raise AuthError(f"Unexpected login response shape: {text[:200]!r}")
    inner = text.replace("<li>", "").replace("</li>", "").strip()
    tokens = inner.split("^")
    if len(tokens) < 15:
        raise AuthError(f"Malformed login token string ({len(tokens)} parts): {text[:200]!r}")
    return tokens


def login(
    base_url: str,
    username: str,
    password: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
) -> SkywardSession:
    """Authenticate to Skyward and return a ready-to-use session.

    `base_url` should be the path through `wsEAplus`, e.g.
    `https://skystu.jordan.k12.ut.us/scripts/wsisa.dll/WService=wsEAplus`.
    """
    base_url = base_url.rstrip("/")
    client = httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        headers={
            "User-Agent": "skyward-client/0.1 (+https://github.com/christianfurr/skyward)",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )

    login_payload = {
        "requestAction": "eel",
        "codeType": "tryLogin",
        "codeValue": username,
        "login": username,
        "password": password,
    }
    try:
        r1 = client.post(f"{base_url}/skyporthttp.w", data=login_payload)
    except httpx.RequestError as e:
        client.close()
        raise AuthError(f"Network error contacting Skyward: {e}") from e

    if r1.status_code != 200:
        client.close()
        raise AuthError(f"Login POST returned HTTP {r1.status_code}")

    try:
        tokens = _parse_login_response(r1.text)
    except AuthError:
        client.close()
        raise

    auth_params = {
        "dwd": tokens[0],
        "web-data-recid": tokens[1],
        "wfaacl-recid": tokens[2],
        "wfaacl": tokens[3],
        "nameid": tokens[4],
        "duserid": tokens[5],
        "User-Type": tokens[6],
        "enc": tokens[13],
    }
    encses = tokens[14]
    sessionid = f"{tokens[1]}\x15{tokens[2]}"  # Skyward joins recids with literal 0x15 byte
    next_url_path = tokens[7] or "sfhome01.w"

    finalize_url = f"{base_url}/{next_url_path}"
    finalize_payload = {**auth_params, "encses": encses, "sessionid": sessionid}
    try:
        r2 = client.post(finalize_url, data=finalize_payload)
    except httpx.RequestError as e:
        client.close()
        raise AuthError(f"Network error finalizing session: {e}") from e

    if r2.status_code != 200:
        client.close()
        raise AuthError(f"Session-finalize POST returned HTTP {r2.status_code}")
    if "Invalid" in r2.text and len(r2.text) < 500:
        client.close()
        raise AuthError("Session finalize rejected by Skyward")

    return SkywardSession(
        base_url=base_url,
        client=client,
        encses=encses,
        sessionid=sessionid,
        params=auth_params,
    )
