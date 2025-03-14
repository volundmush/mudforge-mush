import mudforge
import typing
from typing import Optional
from rich.markup import MarkupError
from rich.text import Text
from asyncpg import Connection, exceptions
from fastapi import HTTPException, status

from mudforge.db.base import transaction, from_pool, stream
from mudforge.models.users import UserModel
from mudforge.models.characters import CharacterModel
from mudforge.models import validators, fields

from mudforge_mush.models.boards import BoardModel, BoardPostModel, BoardModelPatch, BoardPostModelPatch
from mudforge_mush.models.factions import FactionModel


@from_pool
async def get_board_by_key(pool: Connection, board_key: str) -> BoardModel:
    query = "SELECT * FROM board_view WHERE board_key = $1 AND deleted_at IS NULL"
    board_data = await pool.fetchrow(query, board_key)
    if not board_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found.")
    return BoardModel(**board_data)

@stream
async def list_boards(conn: Connection) -> typing.AsyncGenerator[BoardModel, None]:
    query = "SELECT * FROM board_view WHERE deleted_at IS NULL"
    async for board_data in conn.cursor(query):
        yield BoardModel(**board_data)


@stream
async def list_posts_for_board(conn: Connection, board: BoardModel) -> typing.AsyncGenerator[BoardPostModel, None]:
    query = "SELECT * FROM board_post_view_full WHERE board_key = $1 ORDER BY post_order,sub_order"
    async for post_data in conn.cursor(query, board.board_key):
        yield BoardPostModel(**post_data)

@transaction
async def create_board(conn: Connection, faction: FactionModel | None, board_order: int, board_name: str) -> BoardModel:
    faction_id = faction.id if faction else None
    try:
        board_row = await conn.fetchrow("INSERT INTO boards (faction_id, board_order, name) VALUES ($1, $2, $3) RETURNING *", faction_id, board_order, board_name)
    except exceptions.UniqueViolationError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Board using that Faction and Order already exists.")
    board_row = await conn.fetchrow("SELECT * FROM board_view WHERE id = $1", board_row["id"])
    return BoardModel(**board_row)

@from_pool
async def get_post_by_key(conn: Connection, board: BoardModel, post_key: str) -> BoardPostModel:
    query = "SELECT * FROM board_post_view_full WHERE board_key = $1 AND post_key = $2"
    post_data = await conn.fetchrow(query, board.board_key, post_key)
    if not post_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found.")
    return BoardPostModel(**post_data)

@transaction
async def create_post(conn: Connection, board: BoardModel, post, user: UserModel) -> BoardPostModel:
    max_order = await conn.fetchval("SELECT MAX(post_order) FROM board_posts WHERE board_id = $1", board.id)
    post_data = await conn.fetchrow("INSERT INTO board_posts (board_id, title, body, post_order, sub_order, user_id) VALUES ($1, $2, $3, $4, $5, $6) RETURNING *", board.id, post.title, post.body, max_order + 1, 0, post.user_id)
    read = await conn.fetchrow("INSERT INTO board_posts_read (post_id, user_id) VALUES ($1, $2) RETURNING *", post_data["id"], user.id)
    post_data = await conn.fetchrow("SELECT * FROM board_post_view WHERE id = $1", post_data["id"])
    return BoardPostModel(**post_data)

@transaction
async def create_reply(conn: Connection, board: BoardModel, post: BoardPostModel, reply, user: UserModel) -> BoardPostModel:
    sub_order = await conn.fetchval("SELECT MAX(sub_order) FROM board_posts WHERE board_id = $1 AND post_order = $2", board.id, post.post_order)
    post_data = await conn.fetchrow("INSERT INTO board_posts (board_id, title, body, post_order, sub_order, user_id) VALUES ($1, $2, $3, $4, $5, $6) RETURNING *", board.id, f"RE: {post.title}", reply.body, post.post_order, sub_order + 1, user.id)
    read = await conn.fetchrow("INSERT INTO board_posts_read (post_id, user_id) VALUES ($1, $2) RETURNING *", post_data["id"], user.id)
    post_data = await conn.fetchrow("SELECT * FROM board_post_view WHERE id = $1", post_data["id"])
    return BoardPostModel(**post_data)


@transaction
async def update_board(conn: Connection, board: BoardModel, patch: BoardModelPatch) -> BoardModel:
    patch_data = patch.model_dump(exclude_unset=True)
    if not patch_data:
        return board # Nothing to update

    if "name" in patch_data:
        await conn.execute("UPDATE boards SET name=$1 WHERE board_id=$2", patch.name, board.id)

    if "description" in patch_data:
        await conn.execute("UPDATE boards SET description=$1 WHERE board_id=$2", patch.description, board.id)
    
    if "anonymous_name" in patch_data:
        await conn.execute("UPDATE boards SET anonymous_name=$1 WHERE board_id=$2", patch.anonymous_name, board.id)
    
    if "board_order" in patch_data:
        try:
            await conn.execute("UPDATE boards SET board_order=$1 WHERE board_id=$2", patch.board_order, board.id)
        except exceptions.UniqueViolationError as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Board using that Faction and Order already exists.")
    
    if "lock_data" in patch_data:
        if patch.lock_data is not None:
            await conn.execute("UPDATE boards SET lock_data=$1 WHERE board_id=$2", patch.lock_data, board.id)
        else:
            await conn.execute("UPDATE boards SET lock_data=json_object() WHERE board_id=$1", board.id)
    
    # Update the updated_at timestamp
    await conn.execute("UPDATE boards SET updated_at=now() WHERE board_id=$1", board.id)
    return board

@transaction
async def delete_board(conn: Connection, board: BoardModel) -> BoardModel:
    await conn.execute("UPDATE boards SET deleted_at=now() WHERE board_id=$1", board.id)
    board_data = await conn.fetchrow("SELECT * FROM board_view WHERE board_id = $1", board.id)
    return BoardModel(**board_data)


@transaction
async def delete_post(conn: Connection, post: BoardPostModel) -> BoardPostModel:
    await conn.execute("UPDATE board_posts SET deleted_at=now() WHERE post_id=$1", post.id)
    post_data = await conn.fetchrow("SELECT * FROM board_post_view WHERE id = $1", post.id)
    return BoardPostModel(**post_data)

@transaction
async def update_post(conn: Connection, post: BoardPostModel, patch: BoardPostModelPatch) -> BoardPostModel:
    patch_data = patch.model_dump(exclude_unset=True)
    if not patch_data:
        return post

    if "title" in patch_data:
        await conn.execute("UPDATE board_posts SET title=$1 WHERE post_id=$2", patch.title, patch.id)

    if "body" in patch_data:
        await conn.execute("UPDATE board_posts SET body=$1 WHERE post_id=$2", patch.body, patch.id)

    # Update the updated_at timestamp
    await conn.execute("UPDATE board_posts SET updated_at=now() WHERE post_id=$1", patch.id)
    post_data = await conn.fetchrow("SELECT * FROM board_post_view WHERE id = $1", patch.id)
    return BoardPostModel(**post_data)