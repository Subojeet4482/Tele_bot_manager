"""Fake Firestore and fake Telegram updates for the tests."""
from __future__ import annotations

import itertools
from types import SimpleNamespace

_ids = itertools.count(1)


class FakeSnap:
    def __init__(self, doc_id, data):
        self.id = doc_id
        self.exists = data is not None
        self._data = data

    def to_dict(self):
        return dict(self._data) if self._data is not None else None


class FakeDoc:
    def __init__(self, coll, doc_id):
        self._coll = coll
        self.id = doc_id

    def get(self):
        return FakeSnap(self.id, self._coll.docs.get(self.id))

    def set(self, data, merge=False):
        if merge and self.id in self._coll.docs:
            self._coll.docs[self.id].update(data)
        else:
            self._coll.docs[self.id] = dict(data)

    def update(self, values):
        self._coll.docs[self.id].update(values)

    def delete(self):
        self._coll.docs.pop(self.id, None)


class FakeColl:
    def __init__(self):
        self.docs: dict[str, dict] = {}

    def document(self, doc_id=None):
        return FakeDoc(self, doc_id or f"doc{next(_ids):04d}")

    def order_by(self, field):
        coll = self

        class Query:
            def stream(self_inner):
                rows = sorted(coll.docs.items(), key=lambda kv: kv[1].get(field) or 0)
                return [FakeSnap(k, v) for k, v in rows]

        return Query()

    def stream(self):
        return [FakeSnap(k, v) for k, v in self.docs.items()]


class FakeDB:
    def __init__(self):
        self.colls: dict[str, FakeColl] = {}

    def collection(self, name):
        return self.colls.setdefault(name, FakeColl())


# ---- fake Telegram objects -----------------------------------------------------------------
class FakeMessage:
    def __init__(self, text=None, chat_id=1):
        self.text = text
        self.replies: list[tuple[str, object]] = []
        self.deleted = False
        self.reply_to_message = None
        self.message_id = next(_ids)

    async def reply_text(self, text, reply_markup=None, **kwargs):
        self.replies.append((text, reply_markup))

    async def delete(self):
        self.deleted = True


class FakeQuery:
    def __init__(self, data):
        self.data = data
        self.message = FakeMessage()
        self.edits: list[tuple[str, object]] = []
        self.answers: list[tuple] = []

    async def answer(self, text=None, show_alert=False):
        self.answers.append((text, show_alert))

    async def edit_message_text(self, text, reply_markup=None):
        self.edits.append((text, reply_markup))


class FakeUpdate:
    def __init__(self, user_id=1, text=None, data=None, chat_type="private"):
        self.effective_user = SimpleNamespace(id=user_id, full_name=f"User {user_id}")
        self.effective_chat = SimpleNamespace(type=chat_type, id=user_id)
        self.message_reaction = None
        if data is not None:
            self.callback_query = FakeQuery(data)
            self.effective_message = self.callback_query.message
        else:
            self.callback_query = None
            self.effective_message = FakeMessage(text)

    def last(self):
        """(text, markup) of the latest thing the bot showed."""
        if self.callback_query is not None:
            return self.callback_query.edits[-1]
        return self.effective_message.replies[-1]


class FakeBot:
    def __init__(self):
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, chat_id, text, **kwargs):
        self.sent.append((chat_id, text))
        return SimpleNamespace(message_id=next(_ids))

    async def send_sticker(self, chat_id, sticker, **kwargs):
        self.sent.append((chat_id, "<sticker>"))
        return SimpleNamespace(message_id=next(_ids))

    async def get_chat(self, user_id):
        return SimpleNamespace(full_name=f"Name {user_id}", username=None)


class FakeContext:
    def __init__(self, bot=None):
        self.user_data: dict = {}
        self.bot = bot or FakeBot()


def buttons(markup):
    return [b for row in markup.inline_keyboard for b in row]


def find(markup, needle):
    """The button whose text contains `needle` (or whose callback data equals it)."""
    for button in buttons(markup):
        if needle in button.text or button.callback_data == needle:
            return button
    raise AssertionError(f"no button {needle!r} in {[b.text for b in buttons(markup)]}")
