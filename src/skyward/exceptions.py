class SkywardError(RuntimeError):
    pass


class AuthError(SkywardError):
    pass


class NotLoggedIn(SkywardError):
    pass


class ScrapeError(SkywardError):
    def __init__(self, message: str, url: str | None = None, snippet: str | None = None) -> None:
        parts = [message]
        if url:
            parts.append(f"url={url}")
        if snippet:
            parts.append(f"snippet={snippet[:200]!r}")
        super().__init__(" | ".join(parts))
        self.url = url
        self.snippet = snippet
