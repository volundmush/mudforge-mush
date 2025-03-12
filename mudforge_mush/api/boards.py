from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional
from pydantic import BaseModel

import re
import typing
import mudforge

import uuid

from fastapi import APIRouter, Depends, Body, HTTPException, status, Request


from mudforge.game.api.utils import (
    get_current_user,
    get_acting_character,
    streaming_list
)


from mudforge.game.db.models import UserModel, CharacterModel, ActiveAs

from ..db.models import (
    BoardModel,
    PostModel,
    FactionModel,
    board_admin
)

from ..db import boards as boards_db, factions as factions_db

router = APIRouter()

RE_BOARD_ID = re.compile(r"^(?P<abbr>[a-zA-Z]+)?(?P<order>\d+)$")


class BoardCreate(BaseModel):
    name: str
    board_key: str


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
    board = await boards_db.create_board(faction, order, board.name)
    return board



@router.patch("/{board_key}", response_model=BoardModel)
async def update_board(
    board_key: str,
    patch: Annotated[boards_db.PatchBoardModel, Body()],
    user: Annotated[UserModel, Depends(get_current_user)],
    character_id: uuid.UUID,
):
    acting = await get_acting_character(user, character_id)
    board = await boards_db.get_board_by_key(board_key)
    if not await board.is_admin(acting):
        raise HTTPException(
            status_code=403, detail="You do not have permission to update this board."
        )
    board = await boards_db.update_board(board, patch)
    return board

@router.delete("/{board_key}", response_model=BoardModel)
async def delete_board(user: Annotated[UserModel, Depends(get_current_user)],
                       board_key: str,
                       character_id: uuid.UUID):
    acting = await get_acting_character(user, character_id)
    board = await boards_db.get_board_by_key(board_key)
    if not await board.is_admin(acting):
        raise HTTPException(
            status_code=403, detail="You do not have permission to update this board."
        )
    board = await boards_db.delete_board(board)
    return board
    

@router.get("/", response_model=typing.List[BoardModel])
async def list_boards(
    user: Annotated[UserModel, Depends(get_current_user)], character_id: uuid.UUID
):
    acting = await get_acting_character(user, character_id)

    async def board_filter():
        async for board in boards_db.list_boards():
            if await board.access(acting, "read"):
                yield board

    return streaming_list(board_filter())


@router.get("/{board_key}", response_model=BoardModel)
async def get_board(
    board_key: str,
    user: Annotated[UserModel, Depends(get_current_user)],
    character_id: uuid.UUID,
):
    acting = await get_acting_character(user, character_id)
    board = await boards_db.get_board_by_key(board_key)
    if not await board.access(acting, "read"):
        raise HTTPException(
            status_code=403, detail="You do not have permission to read this board."
        )
    return board


@router.get("/{board_key}/posts", response_model=list[PostModel])
async def list_posts(
    board_key: str,
    user: Annotated[UserModel, Depends(get_current_user)],
    character_id: uuid.UUID,
):
    acting = await get_acting_character(user, character_id)
    board = await boards_db.get_board_by_key(board_key)
    admin = await board.access(acting, "admin")
    if not admin and not await board.access(acting, "read"):
        raise HTTPException(
            status_code=403, detail="You do not have permission to read this board."
        )

    posts = boards_db.list_posts_for_board(board)

    if board.anonymous_name:
        if not admin:
            async def transform_posts():
                async for post in posts:
                    post.spoofed_name = board.anonymous_name
                    post.character_id = None
                    post.character_name = None
                    yield post
            
            return streaming_list(transform_posts())
        else:
            async def transform_posts():
                async for post in posts:
                    post.spoofed_name = f"{board.anonymous_name} ({post.spoofed_name})"
                    yield post
            return streaming_list(transform_posts())
    
    return streaming_list(posts)


@router.get("/{board_key}/posts/{post_key}", response_model=PostModel)
async def get_post(
    board_key: str,
    post_key: str,
    user: Annotated[UserModel, Depends(get_current_user)],
    character_id: uuid.UUID,
):
    acting = await get_acting_character(user, character_id)
    board = await boards_db.get_board_by_key(board_key)
    admin = await board.access(acting, "admin")
    if not admin and not await board.access(acting, "read"):
        raise HTTPException(
            status_code=403, detail="You do not have permission to read this board."
        )
    post = await boards_db.get_post_by_key(board, post_key)

    if board.anonymous_name:
        if not admin:
            post.spoofed_name = board.anonymous_name
            post.character_id = None
            post.character_name = None
        else:
            post.spoofed_name = f"{board.anonymous_name} ({post.spoofed_name})"
    return post


class PostCreate(BaseModel):
    title: str
    body: str


@router.post("/{board_key}/posts", response_model=PostModel)
async def create_post(
    board_key: str,
    post: PostCreate,
    user: Annotated[UserModel, Depends(get_current_user)],
    character_id: uuid.UUID,
):
    acting = await get_acting_character(user, character_id)
    board = await boards_db.get_board_by_key(board_key)
    if not await board.access(acting, "post"):
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to write to this board.",
        )
    post = await boards_db.create_post(board, post, user)
    return post


class ReplyCreate(BaseModel):
    body: str


@router.post("/{board_key}/posts/{post_key}", response_model=PostModel)
async def create_reply_post(
    board_key: str,
    post_key: str,
    reply: ReplyCreate,
    user: Annotated[UserModel, Depends(get_current_user)],
    character_id: uuid.UUID,
):
    acting = await get_acting_character(user, character_id)
    board = await boards_db.get_board_by_key(board_key)
    if not await board.access(acting, "post"):
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to write to this board.",
        )
    post = await boards_db.get_post_by_key(board, post_key)
    reply = await boards_db.create_reply(board, post, reply, user)
    return reply
