class MetaPayloadBuilder:
    """Static builder class for constructing Meta API request payloads."""

    @staticmethod
    def build_text_message(
        to_phone: str,
        body: str,
        context_wamid: str | None = None,
    ) -> dict:
        """
        Build a text message payload.

        Args:
            to_phone: Recipient phone number
            body: Message text content
            context_wamid: Optional WAMID of message being replied to

        Returns:
            dict: Meta API payload
        """
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_phone,
            "type": "text",
            "text": {"body": body},
        }

        if context_wamid:
            payload["context"] = {"message_id": context_wamid}

        return payload

    @staticmethod
    def build_template_message(
        to_phone: str,
        template_name: str,
        language_code: str = "en_US",
        context_wamid: str | None = None,
    ) -> dict:
        """
        Build a template message payload.

        Args:
            to_phone: Recipient phone number
            template_name: Name of the approved template
            language_code: Template language code
            context_wamid: Optional WAMID of message being replied to

        Returns:
            dict: Meta API payload
        """
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_phone,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
            },
        }

        if context_wamid:
            payload["context"] = {"message_id": context_wamid}

        return payload

    @staticmethod
    def build_media_message(
        to_phone: str,
        media_type: str,
        media_id: str,
        caption: str | None = None,
    ) -> dict:
        """
        Build a media message payload.

        Args:
            to_phone: Recipient phone number
            media_type: Type of media (image, video, audio, document, voice, sticker)
            media_id: Meta media ID from upload
            caption: Optional caption (supported for image, video, document)

        Returns:
            dict: Meta API payload
        """
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_phone,
            "type": media_type,
            media_type: {
                "id": media_id,
            },
        }

        # Add caption if provided and supported by media type
        if caption and media_type in ["image", "video", "document"]:
            payload[media_type]["caption"] = caption

        return payload

    @staticmethod
    def build_reaction_message(
        to_phone: str,
        target_wamid: str,
        emoji: str = "",
    ) -> dict:
        """
        Build a reaction message payload.

        Args:
            to_phone: Recipient phone number
            target_wamid: WAMID of the message to react to
            emoji: Emoji to react with (empty string to remove reaction)

        Returns:
            dict: Meta API payload
        """
        return {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_phone,
            "type": "reaction",
            "reaction": {
                "message_id": target_wamid,
                "emoji": emoji,
            },
        }
