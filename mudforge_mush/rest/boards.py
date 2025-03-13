
from typing import Annotated
from pydantic import BaseModel

import re
import typing
import mudforge

import uuid

from fastapi import APIRouter, Depends, Body, HTTPException, status
from fastapi.responses import StreamingResponse

from mudforge.utils import subscription, queue_iterator

from mudforge.rest.utils import (
    get_current_user,
    get_acting_character,
    streaming_list
)

from mudforge.models.users import UserModel
from mudforge.models.characters import CharacterModel, ActiveAs
from mudforge.db.characters import list_online

from mudforge_mush.models.boards import (BoardModel, BoardPostModel, BoardCreate, BoardPostModelPatch,
                                         BoardModelPatch, PostCreate, ReplyCreate)
from mudforge_mush.api.boards import Board, board_admin
from mudforge_mush.events import boards as ev_boards

from mudforge_mush.db import boards as boards_db, factions as factions_db

router = APIRouter()

RE_BOARD_ID = re.compile(r"^(?P<abbr>[a-zA-Z]+)?(?P<order>\d+)$")

@router.post("/", response_model=BoardModel)
async def create_board(
    board: Annotated[BoardCreate, Body()],
    user: Annotated[UserModel, Depends(get_current_user)],
    character_id: uuid.UUID,
):
    acting = await get_acting_character(user, character_id)
    if not (matched := RE_BOARD_ID.match(board.board_key)):
        raise HTTPException(status_code=400, detail="Invalid board ID format.")
    order = int(matched.group("order"))
    faction = None
    faction_id = None

    if abbr := matched.group("abbr"):
        faction = await factions_db.find_faction_abbreviation(abbr)
        faction_id = faction.id
    if not await board_admin(acting, faction_id):
        raise HTTPException(
            status_code=403, detail="You do not have permission to create a board."
        )
    board_row = await boards_db.create_board(faction, order, board.name)

    notification = ev_boards.BoardCreate(board_key=board_row.board_key, board_name=board_row.name,
                                         faction_name=faction.name if faction else None,
                                         enactor=acting.character.name)
    online = await list_online()
    for act in online:
        if await board_admin(act, faction_id):
            await mudforge.EVENT_HUB.send(act.character.id, notification)

    return board_row


@router.patch("/{board_key}", response_model=BoardModel)
async def update_board(
    board_key: str,
    patch: Annotated[BoardModelPatch, Body()],
    user: Annotated[UserModel, Depends(get_current_user)],
    character_id: uuid.UUID,
):
    acting = await get_acting_character(user, character_id)
    board_model = await boards_db.get_board_by_key(board_key)
    board = Board(board_model)
    if not await board.is_admin(acting):
        raise HTTPException(
            status_code=403, detail="You do not have permission to update this board."
        )
    board_changed = await boards_db.update_board(board_model, patch)

    changes = dict()

    if board_changed is not board_model:
        patch_data = patch.model_dump(exclude_unset=True)
        for key, value in patch_data.items():
            if (old := getattr(board_model, key)) != value:
                changes[key] = (str(old), value)

    notification = ev_boards.BoardUpdate(board_key=board_model.board_key, board_name=board_model.name, faction_name=board_model.faction_name,
                                         enactor=acting.character.name, changes=changes)
    online = await list_online()
    for act in online:
        if await board.access(act, "read"):
            await mudforge.EVENT_HUB.send(act.character.id, notification)

    return board_changed

@router.delete("/{board_key}", response_model=BoardModel)
async def delete_board(user: Annotated[UserModel, Depends(get_current_user)],
                       board_key: str,
                       character_id: uuid.UUID):
    acting = await get_acting_character(user, character_id)
    board_model = await boards_db.get_board_by_key(board_key)
    board = Board(board_model)
    if not await board.is_admin(acting):
        raise HTTPException(
            status_code=403, detail="You do not have permission to delete this board."
        )
    board_model = await boards_db.delete_board(board_model)

    notification = ev_boards.BoardDelete(board_key=board_model.board_key, board_name=board_model.name,
                                         faction_name=board_model.faction_name, enactor=acting.character.name)

    online = await list_online()
    for act in online:
        if await board.access(act, "read"):
            await mudforge.EVENT_HUB.send(act.character.id, notification)

    return board_model
    

@router.get("/", response_model=typing.List[BoardModel])
async def list_boards(
    user: Annotated[UserModel, Depends(get_current_user)], character_id: uuid.UUID
):
    acting = await get_acting_character(user, character_id)

    async def board_filter():
        async for board_model in boards_db.list_boards():
            board = Board(board_model)
            if await board.access(acting, "read"):
                yield board_model

    return streaming_list(board_filter())


@router.get("/{board_key}", response_model=BoardModel)
async def get_board(
    board_key: str,
    user: Annotated[UserModel, Depends(get_current_user)],
    character_id: uuid.UUID,
):
    acting = await get_acting_character(user, character_id)
    board_model = await boards_db.get_board_by_key(board_key)
    board = Board(board_model)
    if not await board.access(acting, "read"):
        raise HTTPException(
            status_code=403, detail="You do not have permission to read this board."
        )
    return board_model


@router.get("/{board_key}/posts", response_model=list[BoardPostModel])
async def list_posts(
    board_key: str,
    user: Annotated[UserModel, Depends(get_current_user)],
    character_id: uuid.UUID,
):
    acting = await get_acting_character(user, character_id)
    board_model = await boards_db.get_board_by_key(board_key)
    board = Board(board_model)
    admin = await board.access(acting, "admin")
    if not admin and not await board.access(acting, "read"):
        raise HTTPException(
            status_code=403, detail="You do not have permission to read this board."
        )

    posts = boards_db.list_posts_for_board(board_model)

    if board_model.anonymous_name:
        if not admin:
            async def transform_posts():
                async for post in posts:
                    post.spoofed_name = board_model.anonymous_name
                    post.character_id = None
                    post.character_name = None
                    yield post
            
            return streaming_list(transform_posts())
        else:
            async def transform_posts():
                async for post in posts:
                    post.spoofed_name = f"{board_model.anonymous_name} ({post.spoofed_name})"
                    yield post
            return streaming_list(transform_posts())
    
    return streaming_list(posts)


@router.get("/{board_key}/posts/{post_key}", response_model=BoardPostModel)
async def get_post(
    board_key: str,
    post_key: str,
    user: Annotated[UserModel, Depends(get_current_user)],
    character_id: uuid.UUID,
):
    acting = await get_acting_character(user, character_id)
    board_model = await boards_db.get_board_by_key(board_key)
    board = Board(board_model)
    admin = await board.access(acting, "admin")
    if not admin and not await board.access(acting, "read"):
        raise HTTPException(
            status_code=403, detail="You do not have permission to read this board."
        )
    post = await boards_db.get_post_by_key(board_model, post_key)

    if board_model.anonymous_name:
        if not admin:
            post.spoofed_name = board_model.anonymous_name
            post.character_id = None
            post.character_name = None
        else:
            post.spoofed_name = f"{board_model.anonymous_name} ({post.spoofed_name})"
    return post





@router.post("/{board_key}/posts", response_model=BoardPostModel)
async def create_post(
    board_key: str,
    post: PostCreate,
    user: Annotated[UserModel, Depends(get_current_user)],
    character_id: uuid.UUID,
):
    acting = await get_acting_character(user, character_id)
    board_model = await boards_db.get_board_by_key(board_key)
    board = Board(board_model)
    if not await board.access(acting, "post"):
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to write to this board.",
        )
    post_model = await boards_db.create_post(board_model, post, user)

    notification = ev_boards.BoardPostCreate(board_key=board_model.board_key, board_name=board_model.name,
                                             faction_name=board_model.faction_name, enactor=acting.character.name,
                                             poster_name=post_model.spoofed_name, post_title=post.title,
                                             post_key=post_model.post_key)
    notification_admin = notification.copy()
    notification_admin.character_name = post_model.character_name

    online = await list_online()
    for act in online:
        admin = await board.access(act, "admin")
        if admin:
            await mudforge.EVENT_HUB.send(act.character.id, notification_admin)
            continue
        if await board.access(act, "read"):
            await mudforge.EVENT_HUB.send(act.character.id, notification)

    broadcaster = mudforge.BROADCASTERS["boards"]
    await broadcaster.broadcast(notification)

    return post





@router.post("/{board_key}/posts/{post_key}", response_model=BoardPostModel)
async def create_reply_post(
    board_key: str,
    post_key: str,
    reply: ReplyCreate,
    user: Annotated[UserModel, Depends(get_current_user)],
    character_id: uuid.UUID,
):
    acting = await get_acting_character(user, character_id)
    board_model = await boards_db.get_board_by_key(board_key)
    board = Board(board_model)
    if not await board.access(acting, "post"):
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to write to this board.",
        )
    post = await boards_db.get_post_by_key(board, post_key)
    reply_model = await boards_db.create_reply(board_model, post, reply, user)

    notification = ev_boards.BoardReplyCreate(board_key=board_model.board_key, board_name=board_model.name,
                                             faction_name=board_model.faction_name, enactor=acting.character.name,
                                             poster_name=reply_model.spoofed_name, post_title=post.title,
                                             post_key=reply_model.post_key)
    notification_admin = notification.copy()
    notification_admin.character_name = reply_model.character_name

    online = await list_online()
    for act in online:
        admin = await board.access(act, "admin")
        if admin:
            await mudforge.EVENT_HUB.send(act.character.id, notification_admin)
            continue
        if await board.access(act, "read"):
            await mudforge.EVENT_HUB.send(act.character.id, notification)

    return reply

@router.delete("/{board_key}/posts/{post_key}", response_model=BoardPostModel)
async def delete_post(
    board_key: str,
    post_key: str,
    user: Annotated[UserModel, Depends(get_current_user)],
    character_id: uuid.UUID,
):
    acting = await get_acting_character(user, character_id)
    board_model = await boards_db.get_board_by_key(board_key)
    board = Board(board_model)
    if not await board.access(acting, "admin"):
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to delete this post.",
        )
    post = await boards_db.get_post_by_key(board_model, post_key)
    post_model = await boards_db.delete_post(post)

    notification = ev_boards.BoardPostDelete(board_key=board_model.board_key, board_name=board_model.name,
                                             faction_name=board_model.faction_name, enactor=acting.character.name,
                                             poster_name=post_model.spoofed_name, post_title=post.title,
                                             post_key=post_model.post_key)

    notification_admin = notification.copy()
    notification_admin.character_name = post_model.character_name

    online = await list_online()
    for act in online:
        admin = await board.access(act, "admin")
        if admin:
            await mudforge.EVENT_HUB.send(act.character.id, notification_admin)
            continue
        if await board.access(act, "read"):
            await mudforge.EVENT_HUB.send(act.character.id, notification)

    return post_model

@router.patch("/{board_key}/posts/{post_key}", response_model=BoardPostModel)
async def update_post(
    board_key: str,
    post_key: str,
    patch: Annotated[BoardPostModelPatch, Body()],
    user: Annotated[UserModel, Depends(get_current_user)],
    character_id: uuid.UUID,
):
    acting = await get_acting_character(user, character_id)
    board_model = await boards_db.get_board_by_key(board_key)
    board = Board(board_model)
    if not await board.access(acting, "admin"):
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to update this post.",
        )
    post = await boards_db.get_post_by_key(board_model, post_key)
    post = await boards_db.update_post(post, patch)

    notification = BoardPostNotification(board=board, post=post, message="Post updated.")
    broadcaster = mudforge.BROADCASTERS["boards"]
    await broadcaster.broadcast(notification)

    return post