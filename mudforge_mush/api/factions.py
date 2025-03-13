from mudforge.models.characters import CharacterModel, ActiveAs
from mudforge.api.locks import HasLocks
from mudforge_mush.models.factions import FactionModel
from mudforge_mush.db.factions import get_membership


class Faction(HasLocks):

    def __init__(self, model: FactionModel):
        self.model = model

    async def has_permission(self, character: CharacterModel, permission: str) -> bool:
        if not (membership_data := await get_membership(self.model, character)):
            return False
        # Leaders pass everything.
        if membership_data["rank"] <= 1:
            return True
        access = permission.lower()
        permissions = set()
        permissions.update(self.model.member_permissions)
        permissions.update(self.model.public_permissions)
        permissions.update(membership_data["rank_permissions"])
        permissions.update(membership_data["permissions"])
        if access in permissions:
            return True

        return False

    async def check_override(self, acting: ActiveAs, access_type: str) -> bool:
        return await self.has_permission(acting.character, access_type)