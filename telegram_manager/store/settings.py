"""Per-admin settings: global forwarding switches and the account-number counter."""
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)

FORWARD_KEYS = ("forward_user_messages", "forward_bot_messages", "forward_channel_messages")
_MIGRATED_KEYS = (*FORWARD_KEYS, "next_account_number")


class SettingsStore:
    def __init__(self, db, default_owner_id: int) -> None:
        self._docs = db.collection("telegram_admin_settings")
        self._legacy = db.collection("telegram_settings").document("global")
        self._default_owner_id = default_owner_id
        self._cache: dict[int, dict] = {}
        self._versions: dict[int, int] = {}

    def _load_sync(self, owner_id: int) -> dict:
        snapshot = self._docs.document(str(owner_id)).get()
        if snapshot.exists:
            return snapshot.to_dict() or {}
        if owner_id == self._default_owner_id:
            # First start after the multi-admin upgrade: bring the owner's old global settings along.
            legacy = self._legacy.get()
            if legacy.exists:
                data = {k: v for k, v in (legacy.to_dict() or {}).items() if k in _MIGRATED_KEYS}
                if data:
                    self._docs.document(str(owner_id)).set(data)
                return data
        return {}

    async def _data(self, owner_id: int) -> dict:
        cached = self._cache.get(owner_id)
        if cached is not None:
            return dict(cached)
        version = self._versions.get(owner_id, 0)
        data = await asyncio.to_thread(self._load_sync, owner_id)
        if version == self._versions.get(owner_id, 0):
            self._cache[owner_id] = data
        return dict(data)

    async def _write(self, owner_id: int, values: dict) -> None:
        self._versions[owner_id] = self._versions.get(owner_id, 0) + 1
        try:
            await asyncio.to_thread(self._docs.document(str(owner_id)).set, values, merge=True)
        finally:
            self._versions[owner_id] = self._versions.get(owner_id, 0) + 1
            self._cache.pop(owner_id, None)

    async def get_forwarding(self, owner_id: int) -> dict[str, bool]:
        data = await self._data(owner_id)
        return {key: bool(data.get(key, False)) for key in FORWARD_KEYS}

    async def set_forwarding(self, owner_id: int, name: str, value: bool) -> None:
        if name not in FORWARD_KEYS:
            raise ValueError(f"Unknown forwarding setting: {name}")
        await self._write(owner_id, {name: bool(value)})

    async def get_counter(self, owner_id: int) -> int:
        try:
            return max(1, int((await self._data(owner_id)).get("next_account_number", 1)))
        except (TypeError, ValueError):
            return 1

    async def set_counter(self, owner_id: int, value: int) -> None:
        await self._write(owner_id, {"next_account_number": int(value)})
