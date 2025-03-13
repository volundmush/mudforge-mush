import uuid
import pydantic
from typing import Optional

from mudforge.models.mixins import SoftDeleteMixin
from mudforge.models import fields

from .factions import FactionModel


class BoardCreate(pydantic.BaseModel):
    name: fields.name_line
    board_key: fields.name_line

class BoardModel(SoftDeleteMixin):
    board_key: str
    name: fields.name_line
    description: fields.optional_rich_text
    anonymous_name: fields.optional_name_line
    faction_id: Optional[int]
    faction_name: fields.optional_name_line
    faction_abbreviation: fields.optional_name_line
    board_order: int
    locks: fields.locks

class BoardModelPatch(pydantic.BaseModel):
    name: fields.optional_name_line = None
    description: fields.optional_rich_text = None
    anonymous_name: fields.optional_name_line = None
    board_order: Optional[int] = None
    locks: fields.optional_locks

class PostCreate(pydantic.BaseModel):
    title: fields.name_line
    body: fields.rich_text

class ReplyCreate(pydantic.BaseModel):
    body: fields.rich_text

class BoardPostModel(SoftDeleteMixin):
    post_key: str
    title: fields.name_line
    body: fields.rich_text
    spoofed_name: str
    character_id: Optional[uuid.UUID] = None
    character_name: Optional[str] = None

class BoardPostModelPatch(pydantic.BaseModel):
    title: fields.optional_name_line = None
    body: fields.optional_rich_text

