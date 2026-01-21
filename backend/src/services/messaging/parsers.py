from uuid import UUID

from src.schemas import MetaMessage


def extract_message_body(msg: MetaMessage) -> str | None:
    if msg.type == "text":
        return msg.text.body
    elif msg.type == "interactive":
        if msg.interactive.type == "button_reply":
            return msg.interactive.button_reply.title
        elif msg.interactive.type == "list_reply":
            return msg.interactive.list_reply.title
    elif msg.type == "location":
        loc = msg.location
        return f"Location: {loc.name or ''} {loc.address or ''} ({loc.latitude}, {loc.longitude})".strip()
    elif msg.type == "contacts" and msg.contacts:
        c = msg.contacts[0]
        name = c.name.formatted_name if c.name else "Unknown"
        phone = (
            c.phones[0].phones[0].phone
            if c.phones and c.phones[0].phones
            else "No phone"
        )
        return f"Contact: {name} ({phone})"

    # Generic caption fallback for media
    media_obj = getattr(msg, msg.type, None)
    return getattr(media_obj, "caption", None)


def prepare_media_task(msg: MetaMessage, message_id: UUID) -> dict | None:
    """Constructs the media download task payload if applicable."""
    if msg.type not in ["image", "video", "document", "audio", "voice", "sticker"]:
        return None

    media_meta = getattr(msg, msg.type, None)
    if not media_meta:
        return None

    return {
        "message_id": str(message_id),
        "meta_media_id": media_meta.id,
        "media_type": msg.type,
        "mime_type": getattr(media_meta, "mime_type", "application/octet-stream"),
        "caption": getattr(media_meta, "caption", None),
    }
