import React, { useState, useCallback } from "react";
import { EventType } from "../../services/websocket";
import { useWSEvent } from "../../services/useWebSocket";

export function RealtimeContactList() {
  const [contacts, setContacts] = useState<any[]>([]);

  const handleUnreadChange = useCallback((data: any) => {
    setContacts((prev) =>
      prev.map((c) =>
        c.id === data.contact_id
          ? { ...c, unread_count: data.unread_count }
          : c
      )
    );
  }, []);

  const handleNewMessage = useCallback((data: any) => {
    // Move contact to top and increment unread
    setContacts((prev) => {
      const contactIndex = prev.findIndex((c) => c.phone === data.from);
      if (contactIndex > -1) {
        const contact = { ...prev[contactIndex] };
        contact.unread_count = (contact.unread_count || 0) + 1;
        contact.last_message = data.body;
        contact.last_message_at = data.created_at;

        return [
          contact,
          ...prev.slice(0, contactIndex),
          ...prev.slice(contactIndex + 1),
        ];
      }
      return prev;
    });
  }, []);

  useWSEvent(EventType.CONTACT_UNREAD_CHANGED, handleUnreadChange);
  useWSEvent(EventType.MESSAGE_RECEIVED, handleNewMessage);

  return (
    <div className="contact-list">
      {contacts.map((contact) => (
        <div key={contact.id} className="contact-item">
          <div className="contact-name">{contact.name || contact.phone}</div>
          {contact.unread_count > 0 && (
            <span className="unread-badge">{contact.unread_count}</span>
          )}
          <div className="last-message">{contact.last_message}</div>
        </div>
      ))}
    </div>
  );
}
