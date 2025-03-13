import uuid
from typing import Optional

from mudforge.models.mixins import SoftDeleteMixin
from mudforge.models import fields

class FactionModel(SoftDeleteMixin):
    id: int
    name: fields.name_line
    abbreviation: fields.name_line
    description: fields.optional_rich_text
    category: fields.name_line
    private: bool
    hidden: bool
    can_leave: bool
    kick_rank: int
    start_rank: int
    title_self: bool
    member_permissions: set[str]
    public_permissions: set[str]
    locks: fields.locks

