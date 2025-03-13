from pydantic import Field
import datetime
from mudforge.events.base import EventBase
from rich.markup import escape

class _BoardEvent(EventBase):
    happened_at: datetime.datetime = Field(default_factory=datetime.datetime.now)
    board_key: str
    board_name: str
    faction_name: str | None

    def format_message(self, message: str):
        escaped_message = escape(message)
        fac_header = f"[Faction BBS-{self.faction_name}]" if self.faction_name else '[BBS]'
        return f"[bold]{escape(fac_header)}[/] {self.board_key} ({self.board_name}): {escaped_message}"


class BoardCreate(_BoardEvent):
    enactor: str

    async def handle_event(self, conn: "BaseConnection"):
        await conn.send_rich(self.format_message(f"Created by {self.enactor}."))


class BoardDelete(_BoardEvent):
    enactor: str

    async def handle_event(self, conn: "BaseConnection"):
        await conn.send_rich(self.format_message(f"Deleted by {self.enactor}."))


class BoardUpdate(_BoardEvent):
    enactor: str
    changes: dict[str, tuple[str | None, str | None]]

    async def handle_event(self, conn: "BaseConnection"):
        change_str = ", ".join([f"{k} changed from {v[0]} to {v[1]}" for k, v in self.changes.items()])
        await conn.send_rich(self.format_message(f"Updated by {self.enactor}. {change_str}."))


class _PostEvent(_BoardEvent):
    post_key: str
    post_title: str
    post_body: str
    character_name: str | None
    poster_name: str


class BoardPostCreate(_PostEvent):

    async def handle_event(self, conn: "BaseConnection"):
        await conn.send_rich(self.format_message(f"{self.poster_name} posted {self.post_key} '{self.post_title}'."))


class BoardReplyCreate(_PostEvent):

    async def handle_event(self, conn: "BaseConnection"):
        await conn.send_rich(self.format_message(f"{self.character_name} replied with {self.post_key} '{self.post_title}'."))

class BoardPostDelete(_PostEvent):
    enactor: str

    async def handle_event(self, conn: "BaseConnection"):
        await conn.send_rich(self.format_message(f"Post {self.post_key} '{self.post_title}' deleted by {self.enactor}."))


class BoardPostUpdate(_PostEvent):
    enactor: str
    changes: dict[str, tuple[str | None, str | None]]

    async def handle_event(self, conn: "BaseConnection"):
        change_str = ", ".join([f"{k} changed from {v[0]} to {v[1]}" for k, v in self.changes.items()])
        await conn.send_rich(self.format_message(f"Post {self.post_key} '{self.post_title}' updated by {self.enactor}. {change_str}."))