import React, { useState, useCallback } from "react";
import { EventType } from "../../services/websocket";
import { useWSEvent } from "../../services/useWebSocket";

export function MessageStatusTracker() {
  const [messages, setMessages] = useState<Map<string, any>>(new Map());

  const handleMessageStatus = useCallback((data: any) => {
    setMessages((prev) => {
      const updated = new Map(prev);
      updated.set(data.message_id, {
        ...updated.get(data.message_id),
        ...data,
        last_updated: new Date(),
      });
      return updated;
    });
  }, []);

  useWSEvent(EventType.MESSAGE_SENT, handleMessageStatus);
  useWSEvent(EventType.MESSAGE_DELIVERED, handleMessageStatus);
  useWSEvent(EventType.MESSAGE_READ, handleMessageStatus);
  useWSEvent(EventType.MESSAGE_FAILED, handleMessageStatus);

  return (
    <div className="message-tracker">
      <h3>Recent Messages ({messages.size})</h3>
      <ul>
        {Array.from(messages.values()).map((msg) => (
          <li key={msg.message_id}>
            <span className={`status-badge ${msg.status}`}>
              {msg.status}
            </span>
            {msg.phone} - {msg.wamid}
          </li>
        ))}
      </ul>
    </div>
  );
}
