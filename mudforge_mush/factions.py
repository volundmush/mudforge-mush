from mudforge.game.locks import HasLocks, OptionalLocks
from mudforge.models import validators, fields
from mudforge.models.mixins import SoftDeleteMixin
from mudforge.models.characters import CharacterModel, ActiveAs



from pydantic import BaseModel
from typing import Annotated, Optional


class FactionModel(SoftDeleteMixin):
    id: int
    name: fields.name_line
    abbreviation: fields.name_line
    description: fields.optional_rich_text
    category: fields.name_line
    private: bool
    hidden: bool
    can_leave: bool
    kick_rank: int
    start_rank: int
    title_self: bool
    member_permissions: set[str]
    public_permissions: set[str]

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
    
    async def check_permission(self, acting: ActiveAs, permission: str) -> bool:
        if acting.user.admin_level > 4:
            return True
        return await self.has_permission(acting.character, permission)

    async def check_override(self, acting: ActiveAs, access_type: str) -> bool:
        return await self.has_permission(acting.character, access_type)