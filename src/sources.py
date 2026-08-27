"""Account-service behaviours recorded during past incidents.

Each class here replays a paging shape the account service has actually
produced in production. They are kept because they are the shapes that broke
something once. Anything that reads the uploaded list is expected to cope with
all of them.

They all satisfy the same `AccountPageLoader` protocol as `TargetAccountTool`
and return the same rows in the same order; only the paging metadata differs.
"""
from __future__ import annotations

from typing import Any

from repair_lab import ToolPage

PAGE_BUDGET = 400


class ReplayingLoader:
    """Serves one extra copy of a page before moving on.

    Seen when the service retried an upstream read and emitted the response
    twice.
    """

    def __init__(self, accounts: list[dict[str, Any]]) -> None:
        self._accounts = [dict(a) for a in accounts]
        self._calls = 0
        self._served: set[str] = set()

    def load_page(
        self, *, cursor: str | None = None, page_size: int = 25
    ) -> ToolPage:
        self._calls += 1
        if self._calls > PAGE_BUDGET:
            raise RuntimeError("page budget exhausted")
        start = int(cursor or "0")
        rows = self._accounts[start : start + page_size]
        token = str(start)
        if token not in self._served:
            self._served.add(token)
            return ToolPage(rows=rows, next_cursor=token, truncated=True)
        nxt = start + len(rows)
        cur = str(nxt) if nxt < len(self._accounts) else None
        return ToolPage(rows=rows, next_cursor=cur, truncated=cur is not None)


class StallingLoader:
    """Returns a cursor that does not advance past a particular offset.

    Seen when a shard failed mid-scan and the service kept handing back the
    same continuation token.
    """

    STALL_AT = 50

    def __init__(self, accounts: list[dict[str, Any]]) -> None:
        self._accounts = [dict(a) for a in accounts]
        self._calls = 0

    def load_page(
        self, *, cursor: str | None = None, page_size: int = 25
    ) -> ToolPage:
        self._calls += 1
        if self._calls > PAGE_BUDGET:
            raise RuntimeError("page budget exhausted")
        start = int(cursor or "0")
        rows = self._accounts[start : start + page_size]
        nxt = start + len(rows)
        if nxt >= self.STALL_AT:
            return ToolPage(rows=rows, next_cursor=str(self.STALL_AT),
                            truncated=True)
        cur = str(nxt) if nxt < len(self._accounts) else None
        return ToolPage(rows=rows, next_cursor=cur, truncated=cur is not None)


class CyclingLoader:
    """Walks to the end and then wraps to the beginning instead of stopping."""

    def __init__(self, accounts: list[dict[str, Any]]) -> None:
        self._accounts = [dict(a) for a in accounts]
        self._calls = 0

    def load_page(
        self, *, cursor: str | None = None, page_size: int = 25
    ) -> ToolPage:
        self._calls += 1
        if self._calls > PAGE_BUDGET:
            raise RuntimeError("page budget exhausted")
        start = int(cursor or "0") % max(len(self._accounts), 1)
        rows = self._accounts[start : start + page_size]
        nxt = (start + len(rows)) % max(len(self._accounts), 1)
        return ToolPage(rows=rows, next_cursor=str(nxt), truncated=True)


class SilentlyShortLoader:
    """Stops early and reports the list as complete.

    Seen when an upstream read timed out and the service reported success on
    what it had already collected.
    """

    STOP_AFTER = 120

    def __init__(self, accounts: list[dict[str, Any]]) -> None:
        self._accounts = [dict(a) for a in accounts]

    def load_page(
        self, *, cursor: str | None = None, page_size: int = 25
    ) -> ToolPage:
        start = int(cursor or "0")
        rows = self._accounts[start : start + page_size]
        nxt = start + len(rows)
        if nxt >= self.STOP_AFTER:
            return ToolPage(rows=rows, next_cursor=None, truncated=False)
        cur = str(nxt) if nxt < len(self._accounts) else None
        return ToolPage(rows=rows, next_cursor=cur, truncated=cur is not None)


class TruncatedWithoutCursorLoader:
    """Reports more data remains but supplies no way to ask for it."""

    def __init__(self, accounts: list[dict[str, Any]]) -> None:
        self._accounts = [dict(a) for a in accounts]
        self._calls = 0

    def load_page(
        self, *, cursor: str | None = None, page_size: int = 25
    ) -> ToolPage:
        self._calls += 1
        if self._calls > PAGE_BUDGET:
            raise RuntimeError("page budget exhausted")
        start = int(cursor or "0")
        rows = self._accounts[start : start + page_size]
        nxt = start + len(rows)
        if nxt < len(self._accounts):
            return ToolPage(rows=rows, next_cursor=None, truncated=True)
        return ToolPage(rows=rows, next_cursor=None, truncated=False)


class ReorderingLoader:
    """Pages by offset over a result set with no stable total ordering.

    Seen when the service paged a query while another process was writing to
    the same table. Every individual page it returns is a real page of real
    rows, it terminates, and the totals look ordinary.
    """

    def __init__(self, accounts: list[dict[str, Any]]) -> None:
        self._accounts = [dict(a) for a in accounts]
        self._calls = 0

    def load_page(
        self, *, cursor: str | None = None, page_size: int = 25
    ) -> ToolPage:
        self._calls += 1
        if self._calls > PAGE_BUDGET:
            raise RuntimeError("page budget exhausted")
        size = max(len(self._accounts), 1)
        shift = (self._calls * 7) % size
        view = self._accounts[shift:] + self._accounts[:shift]
        start = int(cursor or "0")
        rows = view[start : start + page_size]
        nxt = start + len(rows)
        cur = str(nxt) if nxt < len(view) else None
        return ToolPage(rows=rows, next_cursor=cur, truncated=cur is not None)


ALL_SOURCES = (
    ReplayingLoader,
    StallingLoader,
    CyclingLoader,
    SilentlyShortLoader,
    TruncatedWithoutCursorLoader,
    ReorderingLoader,
)
