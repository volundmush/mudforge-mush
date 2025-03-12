import mudforge
import typing
import uuid
import pydantic
from typing import Optional
from rich.markup import MarkupError
from rich.text import Text
from asyncpg import Connection, exceptions
from fastapi import HTTPException, status


from mudforge.game.db.base import transaction, from_pool, stream
from mudforge.game.db.models import UserModel, CharacterModel
from mudforge.game.locks import OptionalLocks
from mudforge import validators, fields

from .models import BoardModel, PostModel, FactionModel, str_line

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

class PatchBoardModel(OptionalLocks):
    name: fields.optional_name_line = None
    description: fields.optional_rich_text = None
    anonymous_name: fields.optional_name_line = None
    board_order: Optional[int] = None
    

@transaction
async def update_board(conn: Connection, board: BoardModel, patch: PatchBoardModel):
    patch_data = patch.model_dump(exclude_unset=True)
    if not patch_data:
        return  # Nothing to update

    if "name" in patch_data:
        await conn.execute("UPDATE boards SET name=$1 WHERE board_id=$2", patch.name, board.id)
        board.name = patch.name

    if "description" in patch_data:
        if patch.description is not None:
            try:
                desc = Text.from_markup(patch.description)
            except MarkupError as e:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid markup in description: {e}")
            await conn.execute("UPDATE boards SET description=$1 WHERE board_id=$2", patch.description, board.id)
        else:
            await conn.execute("UPDATE boards SET description=NULL WHERE board_id=$1", board.id)
        board.description = patch.description
    
    if "anonymous_name" in patch_data:
        if patch.anonymous_name is not None:
            await conn.execute("UPDATE boards SET anonymous_name=$1 WHERE board_id=$2", patch.anonymous_name, board.id)
        else:
            await conn.execute("UPDATE boards SET anonymous_name=NULL WHERE board_id=$1", board.id)
        board.anonymous_name = patch.anonymous_name
    
    if "board_order" in patch_data:
        try:
            await conn.execute("UPDATE boards SET board_order=$1 WHERE board_id=$2", patch.board_order, board.id)
        except exceptions.UniqueViolationError as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Board using that Faction and Order already exists.")
        board.board_order = patch.board_order
    
    if "lock_data" in patch_data:
        if patch.lock_data is not None:
            for k, v in patch.lock_data.items():
                await board.validate_lock(k, v)
            await conn.execute("UPDATE boards SET lock_data=$1 WHERE board_id=$2", patch.lock_data, board.id)
        else:
            await conn.execute("UPDATE boards SET lock_data=json_object() WHERE board_id=$1", board.id)
        board.lock_data = patch.lock_data
    
    # Update the updated_at timestamp
    await conn.execute("UPDATE boards SET updated_at=now() WHERE board_id=$1", board.id)

@transaction
async def delete_board(conn: Connection, board: BoardModel):
    await conn.execute("UPDATE boards SET deleted_at=now() WHERE board_id=$1", board.id)
    board_data = await conn.fetchrow("SELECT * FROM board_view WHERE board_id = $1", board.id)
    return BoardModel(**board_data)

