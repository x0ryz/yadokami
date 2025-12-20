import uuid
from pydantic import BaseModel
from typing import Literal


class WhatsAppMessage(BaseModel):
    phone: str
    type: Literal["text", "template"]
    body: str
    request_id: str = str(uuid.uuid4())


class WabaSyncRequest(BaseModel):
    request_id: str = str(uuid.uuid4())