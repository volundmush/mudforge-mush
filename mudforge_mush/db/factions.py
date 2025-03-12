import mudforge
import typing
import uuid

from asyncpg import Connection, exceptions
from fastapi import HTTPException, status

from mudforge.game.db.base import transaction, from_pool, stream
from mudforge.game.db.models import UserModel, CharacterModel, ActiveAs

from .models import FactionModel

@from_pool
async def get_faction(conn: Connection, faction_id: int) -> FactionModel:
    query = "SELECT * FROM factions WHERE id = $1 LIMIT 1"
    faction_data = await conn.fetchrow(query, faction_id)
    if not faction_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Faction not found.")
    return FactionModel(**faction_data)

@from_pool
async def find_faction(conn: Connection, name: str) -> FactionModel:
    query = "SELECT * FROM factions WHERE name = $1 LIMIT 1"
    faction_data = await conn.fetchrow(query, name)
    if not faction_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Faction not found.")
    return FactionModel(**faction_data)

@from_pool
async def find_faction_abbreviation(conn: Connection, abbreviation: str) -> FactionModel:
    query = "SELECT * FROM factions WHERE abbreviation = $1 LIMIT 1"
    faction_data = await conn.fetchrow(query, abbreviation)
    if not faction_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Faction not found.")
    return FactionModel(**faction_data)


@from_pool
async def get_membership(conn: Connection, faction: FactionModel, character: CharacterModel) -> dict | None:
    query = "SELECT * from faction_members_view WHERE faction_id = $1 AND character_id = $2 LIMIT 1"
    membership_data = await conn.fetchrow(query, faction.id, character.id)
    return membership_data