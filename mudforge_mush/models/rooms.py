import pydantic
import typing
import uuid
from datetime import datetime, timedelta, timezone
from mudforge.game.locks import HasLocks, OptionalLocks
from mudforge.models.characters import ActiveAs, name_line, SoftDeleteMixin

from mudforge.models import validators, fields

from pydantic import BaseModel
from typing import Annotated, Optional

async def board_admin(acting: ActiveAs, faction_id: int | None) -> bool:
    if faction_id is not None:
        from .factions import get_membership, get_faction
        faction = await get_faction(faction_id)
        return await faction.check_permission(acting, "bbadmin")
    return acting.user.admin_level > 4

class BoardModel(SoftDeleteMixin, HasLocks):
    board_key: str
    name: fields.name_line
    description: fields.optional_rich_text = None
    anonymous_name: fields.optional_name_line = None
    faction_id: Optional[int] = None
    board_order: int

    async def is_admin(self, acting: ActiveAs) -> bool:
        return await board_admin(acting, self.faction_id)

    async def check_override(self, acting: ActiveAs, access_type: str) -> bool:
        """
        Admins can do anything.
        Anyone who can post can also read.
        """
        if (admin := await self.is_admin(acting)):
            return True
        match access_type.lower():
            case "read":
                return await self.evaluate_lock(acting, "post")

        return False


class PostModel(SoftDeleteMixin):
    post_key: str
    title: name_line
    body: str
    spoofed_name: str
    character_id: typing.Optional[uuid.UUID] = None
    character_name: typing.Optional[str] = None