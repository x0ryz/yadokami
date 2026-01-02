import uuid

from pydantic import BaseModel, Field

from .campaigns import *
from .contacts import *
from .messages import *
from .meta import *


class WabaSyncRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
