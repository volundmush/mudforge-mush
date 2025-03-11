import mudforge
import typing
import uuid

from asyncpg import Connection, exceptions
from fastapi import HTTPException, status


from mudforge.game.db.base import transaction, from_pool, stream
from mudforge.game.db.models import UserModel, CharacterModel

from .models import BoardModel, PostModel, FactionModel

@from_pool
async def get_board_by_key(pool: Connection, board_key: str) -> BoardModel:
    query = "SELECT * FROM board_view WHERE board_key = $1"
    board_data = await pool.fetchrow(query, board_key)
    if not board_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found.")
    return BoardModel(**board_data)


@stream
async def list_boards(conn: Connection) -> typing.AsyncGenerator[BoardModel, None]:
    query = "SELECT * FROM board_view"
    async for board_data in conn.cursor(query):
        yield BoardModel(**board_data)


@stream
async def list_posts_for_board(conn: Connection, board: BoardModel) -> typing.AsyncGenerator[PostModel, None]:
    query = "SELECT * FROM post_view WHERE board_key = $1 ORDER BY post_order,sub_order"
    async for post_data in conn.cursor(query, board.board_key):
        yield PostModel(**post_data)

@transaction
async def create_board(conn: Connection, faction: FactionModel | None, board_order: int, board_name: str) -> BoardModel:
    faction_id = faction.id if faction else None
    try:
        board_row = await conn.fetchrow("INSERT INTO boards (faction_id, board_order, name) VALUES ($1, $2, $3) RETURNING *", faction_id, board_order, board_name)
    except exceptions.UniqueViolationError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Board using that Faction and Order already exists.")
    return BoardModel(**board_row)

@from_pool
async def get_post_by_key(conn: Connection, board: BoardModel, post_key: str) -> PostModel:
    query = "SELECT * FROM post_view WHERE board_key = $1 AND post_key = $2"
    post_data = await conn.fetchrow(query, board.board_key, post_key)
    if not post_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found.")
    return PostModel(**post_data)

@transaction
async def create_post(conn: Connection, board: BoardModel, post, user: UserModel) -> PostModel:
    max_order = await conn.fetchval("SELECT MAX(post_order) FROM posts WHERE board_id = $1", board.id)
    post_data = await conn.fetchrow("INSERT INTO posts (board_id, title, body, post_order, sub_order, user_id) VALUES ($1, $2, $3, $4, $5, $6) RETURNING *", board.id, post.title, post.body, max_order + 1, 0, post.user_id)
    read = await conn.fetchrow("INSERT INTO post_reads (post_id, user_id) VALUES ($1, $2) RETURNING *", post_data["id"], user.id)
    post_data = await conn.fetchrow("SELECT * FROM post_view WHERE id = $1", post_data["id"])
    return PostModel(**post_data)

@transaction
async def create_reply(conn: Connection, board: BoardModel, post: PostModel, reply, user: UserModel) -> PostModel:
    sub_order = await conn.fetchval("SELECT MAX(sub_order) FROM posts WHERE board_id = $1 AND post_order = $2", board.id, post.post_order)
    post_data = await conn.fetchrow("INSERT INTO posts (board_id, title, body, post_order, sub_order, user_id) VALUES ($1, $2, $3, $4, $5, $6) RETURNING *", board.id, f"RE: {post.title}", reply.body, post.post_order, sub_order + 1, user.id)
    read = await conn.fetchrow("INSERT INTO post_reads (post_id, user_id) VALUES ($1, $2) RETURNING *", post_data["id"], user.id)
    post_data = await conn.fetchrow("SELECT * FROM post_view WHERE id = $1", post_data["id"])
    return PostModel(**post_data)

