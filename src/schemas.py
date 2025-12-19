import uuid
from pydantic import BaseModel


class WhatsAppMessage(BaseModel):
    phone: str
    request_id: str = str(uuid.uuid4())
