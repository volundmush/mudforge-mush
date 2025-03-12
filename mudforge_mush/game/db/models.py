import pydantic
import typing
import uuid
from datetime import datetime, timedelta, timezone
from mudforge.game.lockhandler import LockHandler
from mudforge.game.db.models import ActiveAs

from pydantic import BaseModel
from typing import Annotated, Optional

class BoardModel(BaseModel, LockHandler):
    board_key: str
    name: str
    description: Optional[str]
    anonymous_name: Optional[str]
    faction_id: Optional[int]
    board_order: int
    created_at: datetime
    updated_at: datetime
    lock_data: dict[str, str]


class PostModel(BaseModel):
    post_key: str
    title: str
    body: str
    created_at: datetime
    modified_at: datetime
    spoofed_name: str
    character_id: typing.Optional[uuid.UUID] = None
    character_name: typing.Optional[str] = None


class FactionModel(BaseModel, LockHandler):
    id: int
    name: str
    abbreviation: str
    created_at: datetime
    updated_at: datetime
    description: Optional[str]
    category: str
    private: bool
    hidden: bool
    can_leave: bool
    kick_rank: int
    start_rank: int
    title_self: bool
    member_permissions: set[str]
    public_permissions: set[str]
    lock_data: dict[str, str]

    async def has_permission(self, character: "CharacterModel", permission: str) -> bool:
        from .factions import get_membership
        if not (membership_data := await get_membership(self, character)):
            return False
        # Leaders pass everything.
        if membership_data["rank"] <= 1:
            return True
        access = permission.lower()
        permissions = set()
        permissions.update(self.member_permissions)
        permissions.update(self.public_permissions)
        permissions.update(membership_data["rank_permissions"])
        permissions.update(membership_data["permissions"])
        if access in permissions:
            return True

        return False

    async def check_override(self, acting: ActiveAs, access_type: str) -> bool:
        return await self.has_permission(acting.character, access_type)