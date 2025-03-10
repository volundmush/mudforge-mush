import mudforge
import typing
import uuid

from asyncpg import AsyncConnection
from fastapi import HTTPException, status

from mudforge.game.db.base import transaction, from_pool
from mudforge.game.db.models import UserModel, CharacterModel

from .models import BoardModel, PostModel

@from_pool
async def get_board_by_key(pool: AsyncConnection, board_key: str) -> BoardModel:
    query = "SELECT * FROM board_view WHERE board_key = $1"
    board_data = await pool.fetchrow(query, board_key)
    if not board_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found.")
    return BoardModel(**board_data)


@transaction
async def list_boards(conn: AsyncConnection) -> typing.AsyncGenerator[BoardModel, None]:
    query = "SELECT * FROM board_view"
    async for board_data in conn.cursor(query):
        yield BoardModel(**board_data)


@transaction
async def list_posts_for_board(conn: AsyncConnection, board: BoardModel) -> typing.AsyncGenerator[PostModel, None]:
    query = "SELECT * FROM post_view WHERE board_key = $1 ORDER BY post_order,sub_order"
    async for post_data in conn.cursor(query, board.board_key):
        yield PostModel(**post_data)