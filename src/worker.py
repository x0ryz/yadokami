import asyncio

import httpx
from faststream import Context, ContextRepo, FastStream
from faststream.redis import RedisBroker
from sqlmodel import select

from src.config import settings
from src.database import async_session_maker
from src.logger import setup_logging
from src.models import (
    Contact,
    Message,
    MessageDirection,
    MessageStatus,
    WabaAccount,
    WabaPhoneNumber,
    WebhookLog,
    get_utc_now,
)
from src.schemas import WabaSyncRequest, WebhookEvent, WhatsAppMessage

logger = setup_logging()

broker = RedisBroker(settings.REDIS_URL)
app = FastStream(broker)


@app.on_startup
async def setup_http_client(context: ContextRepo):
    client = httpx.AsyncClient(
        timeout=10.0,
        headers={
            "Authorization": f"Bearer {settings.META_TOKEN}",
            "Content-Type": "application/json",
        },
    )

    context.set_global("http_client", client)
    logger.info("HTTPX Client initialized")


@app.after_shutdown
async def close_http_client(context: ContextRepo):
    client = context.get("http_client")
    if client:
        await client.aclose()
        logger.info("HTTPX Client closed")


async def send_whatsapp_message(payload: WhatsAppMessage, client: httpx.AsyncClient):
    url = f"{settings.META_URL}/{settings.META_PHONE_ID}/messages"

    if payload.type == "text":
        data = {
            "messaging_product": "whatsapp",
            "to": payload.phone,
            "type": "text",
            "text": {"body": payload.body},
        }
    else:
        data = {
            "messaging_product": "whatsapp",
            "to": payload.phone,
            "type": "template",
            "template": {"name": payload.body, "language": {"code": "en_US"}},
        }

    resp = await client.post(url, json=data)
    resp.raise_for_status()
    return resp.json()


async def fetch_waba_account_info(waba_id: str, client: httpx.AsyncClient):
    """Fetch WABA account information from Meta Graph API."""
    url = f"{settings.META_URL}/{waba_id}"
    params = {"fields": "name,account_review_status,business_verification_status"}

    resp = await client.get(url, params=params)
    resp.raise_for_status()
    return resp.json()


async def fetch_waba_phone_numbers(waba_id: str, client: httpx.AsyncClient):
    """Fetch WABA phone numbers from Meta Graph API."""
    url = f"{settings.META_URL}/{waba_id}/phone_numbers"

    resp = await client.get(url)
    resp.raise_for_status()
    return resp.json()


@broker.subscriber("whatsapp_messages")
async def handle_messages(
    message: WhatsAppMessage, client: httpx.AsyncClient = Context("http_client")
):
    with logger.contextualize(request_id=message.request_id):
        logger.info(f"Received message request for phone: {message.phone}")

        async with async_session_maker() as session:
            stmt_contact = select(Contact).where(Contact.phone_number == message.phone)
            contact = (await session.exec(stmt_contact)).first()
            if not contact:
                contact = Contact(phone_number=message.phone)
                session.add(contact)
                await session.commit()
                await session.refresh(contact)

            stmt_phone = select(WabaPhoneNumber).where(
                WabaPhoneNumber.phone_number_id == settings.META_PHONE_ID
            )
            waba_phone = (await session.exec(stmt_phone)).first()

            if not waba_phone:
                logger.error("WABA Phone not found in DB. Run sync first.")
                return

            db_message = Message(
                waba_phone_id=waba_phone.id,
                contact_id=contact.id,
                direction=MessageDirection.OUTBOUND,
                status=MessageStatus.PENDING,
                body=message.body,
            )
            session.add(db_message)
            await session.commit()
            await session.refresh(db_message)

            try:
                result = await send_whatsapp_message(message, client)

                wamid = result.get("messages", [{}])[0].get("id")
                if wamid:
                    db_message.wamid = wamid
                    db_message.status = MessageStatus.SENT
                    session.add(db_message)
                    await session.commit()

                logger.success(f"Message sent. WAMID: {wamid}")

            except Exception as e:
                logger.exception(f"Failed to send message to {message.phone}")
                db_message.status = MessageStatus.FAILED
                session.add(db_message)
                await session.commit()


@broker.subscriber("sync_account_data")
async def handle_account_sync(
    message: WabaSyncRequest, client: httpx.AsyncClient = Context("http_client")
):
    request_id = message.request_id

    with logger.contextualize(request_id=request_id):
        logger.info("Starting sync from database...")

        async with async_session_maker() as session:
            result = await session.exec(select(WabaAccount))
            waba_account = result.first()

            if not waba_account:
                logger.warning("No WABA accounts found in the database.")
                return

            current_waba_id = waba_account.waba_id
            logger.info(f"Syncing WABA account ID: {current_waba_id}")

        try:
            account_info = await fetch_waba_account_info(current_waba_id, client)

            waba_account.name = account_info.get("name")
            waba_account.account_review_status = account_info.get(
                "account_review_status"
            )
            waba_account.business_verification_status = account_info.get(
                "business_verification_status"
            )

            session.add(waba_account)
            await session.commit()
            await session.refresh(waba_account)

            phones_data = await fetch_waba_phone_numbers(current_waba_id, client)

            for item in phones_data.get("data", []):
                p_id = item.get("id")

                stmt_phone = select(WabaPhoneNumber).where(
                    WabaPhoneNumber.phone_number_id == p_id
                )
                res_phone = await session.exec(stmt_phone)
                phone_obj = res_phone.first()

                if not phone_obj:
                    phone_obj = WabaPhoneNumber(
                        waba_id=waba_account.id,
                        phone_number_id=p_id,
                        display_phone_number=item.get("display_phone_number"),
                        status=item.get("code_verification_status"),
                        quality_rating=item.get("quality_rating"),
                        messaging_limit_tier=item.get("messaging_limit_tier"),
                    )
                else:
                    phone_obj.status = item.get("code_verification_status")
                    phone_obj.quality_rating = item.get("quality_rating")
                    phone_obj.messaging_limit_tier = item.get("messaging_limit_tier")
                    phone_obj.updated_at = get_utc_now()

                session.add(phone_obj)

            await session.commit()
            logger.success(f"Synced account '{waba_account.name}' and its phones.")
        except Exception as e:
            logger.exception(f"Failed to sync WABA ID {current_waba_id}")


@broker.subscriber("raw_webhooks")
async def handle_raw_webhook(event: WebhookEvent):
    data = event.payload

    async with async_session_maker() as session:
        try:
            log_entry = WebhookLog(payload=data)
            session.add(log_entry)
            await session.commit()
        except Exception as e:
            logger.error(f"Database error saving webhook log: {e}")

        try:
            for entry in data.get("entry", []):
                for change in entry.get("changes", []):
                    value = change.get("value", {})

                    if "statuses" in value:
                        for status_update in value["statuses"]:
                            wamid = status_update.get("id")
                            new_status_str = status_update.get("status")

                            status_map = {
                                "sent": MessageStatus.SENT,
                                "delivered": MessageStatus.DELIVERED,
                                "read": MessageStatus.READ,
                                "failed": MessageStatus.FAILED,
                            }
                            new_status = status_map.get(new_status_str)

                            if wamid and new_status:
                                stmt = select(Message).where(Message.wamid == wamid)
                                db_msg = (await session.exec(stmt)).first()
                                if db_msg:
                                    db_msg.status = new_status
                                    session.add(db_msg)
                                    logger.info(
                                        f"Updated status for {wamid} to {new_status}"
                                    )

                    if "messages" in value:
                        metadata = value.get("metadata", {})
                        phone_number_id = metadata.get("phone_number_id")

                        stmt_phone = select(WabaPhoneNumber).where(
                            WabaPhoneNumber.phone_number_id == phone_number_id
                        )
                        waba_phone = (await session.exec(stmt_phone)).first()

                        if not waba_phone:
                            logger.warning(f"Unknown WABA phone ID: {phone_number_id}")
                            continue

                        for msg in value["messages"]:
                            wamid = msg.get("id")
                            from_phone = msg.get("from")
                            msg_type = msg.get("type")

                            body_text = ""
                            if msg_type == "text":
                                body_text = msg.get("text", {}).get("body", "")
                            else:
                                body_text = f"[{msg_type} message]"

                            stmt_contact = select(Contact).where(
                                Contact.phone_number == from_phone
                            )
                            contact = (await session.exec(stmt_contact)).first()
                            if not contact:
                                contact = Contact(
                                    phone_number=from_phone,
                                    name=msg.get("profile", {}).get("name"),
                                )
                                session.add(contact)
                                await session.commit()
                                await session.refresh(contact)

                            stmt_dup = select(Message).where(Message.wamid == wamid)
                            if (await session.exec(stmt_dup)).first():
                                continue

                            new_msg = Message(
                                waba_phone_id=waba_phone.id,
                                contact_id=contact.id,
                                direction=MessageDirection.INBOUND,
                                status=MessageStatus.RECEIVED,
                                body=body_text,
                                wamid=wamid,
                            )
                            session.add(new_msg)
                            logger.info(f"Saved inbound message from {from_phone}")

            await session.commit()

        except Exception as e:
            logger.exception("Error processing webhook payload")
