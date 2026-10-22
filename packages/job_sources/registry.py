"""Reusable adapter interface. Approval and ownership are enforced by JobService."""

from dataclasses import dataclass

from . import adapters
from .adapters import Posting
from .catalog import ADAPTERS


@dataclass(frozen=True)
class JobSourceAdapter:
    source_name: str

    def search(self, board: str, company: str, credentials: dict, rate: dict, cursor=0):
        return adapters.fetch(self.source_name, board, company, credentials, rate, cursor=cursor)

    def normalize(self, data: dict, company: str) -> Posting:
        return adapters.convert(self.source_name, data, company)

    def get_job(
        self, identifier: str, board: str, company: str, credentials: dict, rate: dict
    ) -> Posting | None:
        rows, _, _ = self.search(board, company, credentials, rate)
        return next((row for row in rows if row.external_id == identifier), None)

    def health_check(self, credentials: dict, required: list[str]) -> str:
        return "configuration_required" if any(not credentials.get(key) for key in required) else "configured"


class SourceRegistry:
    """Static implementation inventory paired with persisted SourcePolicy records."""

    adapters = {name: JobSourceAdapter(name) for name in ADAPTERS}

    @classmethod
    def get(cls, name: str) -> JobSourceAdapter:
        return cls.adapters[name]
