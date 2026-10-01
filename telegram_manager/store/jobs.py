"""Daily broadcast job: one per admin."""
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


class JobStore:
    def __init__(self, db, default_owner_id: int) -> None:
        self._col = db.collection("telegram_daily_jobs")
        self._legacy = db.collection("telegram_settings").document("daily_job")
        self._default_owner_id = default_owner_id

    def _list_sync(self) -> list[tuple[int, dict]]:
        found: dict[int, dict] = {}
        for snapshot in self._col.stream():
            try:
                found[int(snapshot.id)] = snapshot.to_dict() or {}
            except ValueError:
                continue
        if self._default_owner_id not in found:
            legacy = self._legacy.get()
            if legacy.exists and legacy.to_dict():
                # Single-admin era job: it becomes the owner's job.
                found[self._default_owner_id] = legacy.to_dict()
                self._col.document(str(self._default_owner_id)).set(legacy.to_dict())
                self._legacy.delete()
        return sorted(found.items())

    async def list_all(self) -> list[tuple[int, dict]]:
        return await asyncio.to_thread(self._list_sync)

    async def save(self, owner_id: int, data: dict) -> None:
        await asyncio.to_thread(self._col.document(str(owner_id)).set, data)

    async def delete(self, owner_id: int) -> None:
        await asyncio.to_thread(self._col.document(str(owner_id)).delete)
