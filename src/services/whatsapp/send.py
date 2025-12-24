from typing import Awaitable, Callable, Optional

from loguru import logger
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.clients.meta import MetaClient
from src.models import (
    Contact,
    Message,
    MessageDirection,
    MessageStatus,
    Template,
    WabaPhoneNumber,
)
from src.schemas import WhatsAppMessage


class WhatsAppSenderService:
    def __init__(
        self,
        session: AsyncSession,
        meta_client: MetaClient,
        notifier: Optional[Callable[[dict], Awaitable[None]]] = None,
    ):
        self.session = session
        self.meta_client = meta_client
        self.notifier = notifier

    async def _notify(self, event_type: str, data: dict):
        if self.notifier:
            payload = {"event": event_type, "data": data}
            await self.notifier(payload)

    async def send_outbound_message(self, message: WhatsAppMessage):
        # 1. Знайти або створити контакт
        stmt_contact = select(Contact).where(
            Contact.phone_number == message.phone_number
        )
        contact = (await self.session.exec(stmt_contact)).first()

        if not contact:
            contact = Contact(phone_number=message.phone_number)
            self.session.add(contact)
            await self.session.commit()
            await self.session.refresh(contact)

        # 2. Отримати системний номер телефону (WABA Phone)
        stmt_phone = select(WabaPhoneNumber)
        waba_phone = (await self.session.exec(stmt_phone)).first()

        if not waba_phone:
            logger.error("No WABA Phone numbers found in DB.")
            return

        # 3. Обробка шаблонів
        template_db_id = None
        if message.type == "template":
            stmt_tmpl = select(Template).where(
                Template.name == message.body,
                Template.waba_id == waba_phone.waba_id,
                Template.status == "APPROVED",
            )
            template_obj = (await self.session.exec(stmt_tmpl)).first()
            if template_obj:
                template_db_id = template_obj.id

        # 4. Створити запис повідомлення (PENDING)
        db_message = Message(
            waba_phone_id=waba_phone.id,
            contact_id=contact.id,
            direction=MessageDirection.OUTBOUND,
            status=MessageStatus.PENDING,
            message_type=message.type,
            body=message.body,
            template_id=template_db_id,
        )

        self.session.add(db_message)
        await self.session.commit()
        await self.session.refresh(db_message)

        await self._notify(
            "new_message",
            {
                "id": str(db_message.id),
                "phone": message.phone_number,
                "direction": "outbound",
                "status": "pending",
                "body": message.body,
                "created_at": db_message.created_at.isoformat(),
            },
        )

        # 5. Формування Payload для Meta
        try:
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": message.phone_number,
                "type": message.type,
            }

            if message.type == "text":
                payload["text"] = {"body": message.body}
            elif message.type == "template":
                payload["template"] = {
                    "name": message.body,
                    "language": {"code": "en_US"},
                }

            # 6. Відправка запиту
            result = await self.meta_client.send_message(
                waba_phone.phone_number_id, payload
            )
            wamid = result.get("messages", [{}])[0].get("id")

            if wamid:
                db_message.wamid = wamid
                db_message.status = MessageStatus.SENT
                self.session.add(db_message)
                await self.session.commit()

                await self._notify(
                    "status_update",
                    {
                        "id": str(db_message.id),
                        "wamid": wamid,
                        "old_status": "pending",
                        "new_status": "sent",
                        "phone": message.phone_number,
                    },
                )
                logger.success(
                    f"Message sent to {message.phone_number}. WAMID: {wamid}"
                )

        except Exception as e:
            logger.exception(f"Failed to send message to {message.phone_number}")
            db_message.status = MessageStatus.FAILED
            self.session.add(db_message)
            await self.session.commit()
