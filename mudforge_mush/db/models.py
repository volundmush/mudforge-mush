import pydantic
import typing
import uuid
from datetime import datetime, timedelta, timezone
from mudforge.game.locks import HasLocks, OptionalLocks
from mudforge.game.db.models import ActiveAs, name_line, SoftDeleteMixin

from mudforge import validators, fields

from pydantic import BaseModel
from typing import Annotated, Optional


