from __future__ import annotations

from collections import Counter


class LanguageLock:
    def __init__(self, preferred: str = "auto", threshold: int = 3) -> None:
        self.preferred = preferred
        self.threshold = threshold
        self._votes: Counter[str] = Counter()
        self._locked: str | None = None

    @property
    def locked_language(self) -> str | None:
        if self.preferred != "auto":
            return self.preferred
        return self._locked

    def observe(self, language: str) -> str | None:
        if self.preferred != "auto":
            return self.preferred
        if self._locked:
            return self._locked
        if not language:
            return None
        self._votes[language] += 1
        most_common = self._votes.most_common(1)
        if most_common and most_common[0][1] >= self.threshold:
            self._locked = most_common[0][0]
        return self._locked
