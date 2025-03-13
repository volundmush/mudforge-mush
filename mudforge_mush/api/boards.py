from mudforge.models.characters import CharacterModel, ActiveAs
from mudforge.api.locks import HasLocks
from mudforge_mush.models.boards import BoardModel, BoardPostModel
from mudforge_mush.db.factions import get_faction

async def board_admin(active: ActiveAs, faction_id: int | None) -> bool:
    if faction_id is not None:
        faction_model = await get_faction(faction_id)
        from .factions import Faction
        faction = Faction(faction_model)
        return await faction.access(active, "bbadmin")
    return active.user.admin_level > 3

class Board(HasLocks):

    def __init__(self, model: BoardModel):
        self.model = model

    async def is_admin(self, active: ActiveAs) -> bool:
        return await board_admin(active, self.model.faction_id)

    async def check_override(self, active: ActiveAs, access_type: str) -> bool:
        if await self.is_admin(active):
            return True
        match access_type.lower():
            case "read":
                if await self.check(active, "post"):
                    return True
        return False