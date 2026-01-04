import React, { useState, useEffect, useCallback } from "react";
import { apiClient } from "../api";
import {
  Contact,
  MessageResponse,
  MessageDirection,
  MessageStatus,
} from "../types";
import ContactList from "../components/contacts/ContactList";
import ChatWindow from "../components/contacts/ChatWindow";
import { useWSEvent } from "../services/useWebSocket";
import { EventType } from "../services/websocket";

const ContactsPage: React.FC = () => {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
  const [messages, setMessages] = useState<MessageResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  // Завантаження контактів при старті
  useEffect(() => {
    loadContacts();
  }, []);

  // Коли обираємо контакт - завантажуємо повідомлення і скидаємо лічильник локально
  useEffect(() => {
    if (selectedContact) {
      // 1. Локально скидаємо unread_count (візуально)
      setContacts((prev) =>
        prev.map((c) =>
          c.id === selectedContact.id ? { ...c, unread_count: 0 } : c,
        ),
      );

      // 2. Завантажуємо історію
      loadMessages(selectedContact.id);
    }
  }, [selectedContact]);

  // --- WebSocket Handlers ---

  const handleNewMessage = useCallback(
    (data: any) => {
      console.log("WS: New message received:", data);

      const msgPhone = data.phone || data.from || data.phone_number;
      const msgContactId = data.contact_id;

      // Визначаємо тип повідомлення
      const msgType = data.type || data.message_type || "text";
      const isMedia = [
        "image",
        "video",
        "document",
        "audio",
        "sticker",
      ].includes(msgType);

      // Перевіряємо, чи це повідомлення для поточного чату
      const isForCurrentChat =
        selectedContact &&
        ((msgContactId && msgContactId === selectedContact.id) ||
          (msgPhone && msgPhone === selectedContact.phone_number));

      const direction =
        data.direction ||
        (data.from ? MessageDirection.INBOUND : MessageDirection.OUTBOUND);

      if (isForCurrentChat) {
        // 1. ВАЖЛИВО: Якщо це вхідне повідомлення у відкритому чаті - позначаємо як прочитане на бекенді
        if (direction === MessageDirection.INBOUND) {
          apiClient.markContactAsRead(selectedContact.id).catch(console.error);
        }

        // 2. Оновлюємо список повідомлень
        setMessages((prev) => {
          if (!Array.isArray(prev)) return [data];
          // Запобігаємо дублікатам
          if (prev.some((m) => m.id === data.id)) return prev;

          const newMessage: MessageResponse = {
            id: data.id,
            wamid: data.wamid,
            direction: direction,
            status: data.status || MessageStatus.RECEIVED,
            message_type: msgType,
            body: data.body,
            created_at: data.created_at || new Date().toISOString(),
            media_files: data.media_files || [],
          };

          return [...prev, newMessage].sort(
            (a, b) =>
              new Date(a.created_at || 0).getTime() -
              new Date(b.created_at || 0).getTime(),
          );
        });

        // ХАК: Якщо це медіа, але файлів немає (бекенд ще качає) - оновлюємо чат через 2 сек
        if (isMedia && (!data.media_files || data.media_files.length === 0)) {
          console.log("WS: Media message without files. Scheduling refresh...");
          setTimeout(() => {
            if (selectedContact) {
              loadMessages(selectedContact.id);
            }
          }, 2000);
        }
      }

      // 3. Оновлюємо список контактів (прев'ю, час, лічильник)
      setContacts((prev) => {
        const updated = prev.map((contact) => {
          const isMatch =
            (msgContactId && contact.id === msgContactId) ||
            (msgPhone && contact.phone_number === msgPhone);

          if (isMatch) {
            return {
              ...contact,
              last_message_at: data.created_at || new Date().toISOString(),
              last_message_body:
                data.body || (isMedia ? `[${msgType}]` : data.body),
              last_message_status: data.status,
              last_message_direction: direction,
              // Якщо чат відкритий - не збільшуємо лічильник
              unread_count: isForCurrentChat
                ? 0
                : (contact.unread_count || 0) + 1,
            };
          }
          return contact;
        });

        // Сортуємо: нові зверху
        return updated.sort((a, b) => {
          const dateA = new Date(a.last_message_at || 0).getTime();
          const dateB = new Date(b.last_message_at || 0).getTime();
          return dateB - dateA;
        });
      });
    },
    [selectedContact],
  );

  const handleMessageStatusUpdate = useCallback((data: any) => {
    // 1. Отримуємо новий статус
    const newStatus = data.new_status || data.status;
    if (!newStatus) return;

    // 2. Оновлюємо статус повідомлення в чаті
    setMessages((prev) => {
      if (!Array.isArray(prev)) return [];
      return prev.map((msg) => {
        const isMatch =
          (data.id && msg.id === data.id) ||
          (data.message_id && msg.id === data.message_id) ||
          (data.wamid && msg.wamid === data.wamid);

        if (isMatch) {
          return {
            ...msg,
            status: newStatus,
            wamid: data.wamid || msg.wamid,
          };
        }
        return msg;
      });
    });

    // 3. Оновлюємо статус останнього повідомлення в списку контактів
    setContacts((prev) =>
      prev.map((contact) => {
        const isContactMatch =
          data.contact_id && contact.id === data.contact_id;
        const isPhoneMatch = data.phone && contact.phone_number === data.phone;

        if (isContactMatch || isPhoneMatch) {
          return {
            ...contact,
            last_message_status: newStatus,
          };
        }
        return contact;
      }),
    );
  }, []);

  const handleContactUnreadChanged = useCallback(
    (data: any) => {
      setContacts((prev) =>
        prev.map((contact) => {
          if (contact.id === data.contact_id) {
            // Якщо це поточний активний контакт - ігноруємо збільшення лічильника (або ставимо 0)
            if (selectedContact && selectedContact.id === contact.id) {
              return { ...contact, unread_count: 0 };
            }
            return { ...contact, unread_count: data.unread_count };
          }
          return contact;
        }),
      );
    },
    [selectedContact],
  );

  // Підписки на події
  useWSEvent(EventType.NEW_MESSAGE, handleNewMessage);
  useWSEvent(EventType.STATUS_UPDATE, handleMessageStatusUpdate);
  useWSEvent(EventType.MESSAGE_SENT, handleMessageStatusUpdate);
  useWSEvent(EventType.MESSAGE_DELIVERED, handleMessageStatusUpdate);
  useWSEvent(EventType.MESSAGE_READ, handleMessageStatusUpdate);
  useWSEvent(EventType.MESSAGE_FAILED, handleMessageStatusUpdate);
  useWSEvent(EventType.CONTACT_UNREAD_CHANGED, handleContactUnreadChanged);

  // --- API Calls ---

  const loadContacts = async () => {
    try {
      setLoading(true);
      const data = await apiClient.getContacts();
      setContacts(Array.isArray(data) ? data : []);
    } catch (error: any) {
      console.error("Помилка завантаження контактів:", error);
    } finally {
      setLoading(false);
    }
  };

  const loadMessages = async (contactId: string) => {
    try {
      setMessagesLoading(true);
      const data = await apiClient.getChatHistory(contactId);
      setMessages(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error("Помилка завантаження повідомлень:", error);
      setMessages([]);
    } finally {
      setMessagesLoading(false);
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      loadContacts();
      return;
    }
    try {
      setLoading(true);
      const results = await apiClient.searchContacts({ q: searchQuery });
      setContacts(Array.isArray(results) ? results : []);
    } catch (error) {
      console.error("Помилка пошуку:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleSendMessage = async (phone: string, text: string) => {
    try {
      await apiClient.sendMessage({ phone, text, type: "text" });
      // Повідомлення додасться через WebSocket (handleNewMessage)
    } catch (error) {
      console.error("Помилка відправки повідомлення:", error);
      alert("Не вдалося відправити повідомлення");
    }
  };

  return (
    <div className="h-[calc(100vh-8rem)] flex flex-col">
      <div className="mb-4">
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Пошук контактів..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyPress={(e) => e.key === "Enter" && handleSearch()}
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={handleSearch}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Пошук
          </button>
        </div>
      </div>

      <div className="flex-1 flex gap-4 overflow-hidden">
        <div className="w-1/3 border border-gray-200 rounded-lg bg-white overflow-hidden flex flex-col">
          <div className="p-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-800">Контакти</h2>
          </div>
          {loading ? (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-gray-500">Завантаження...</div>
            </div>
          ) : (
            <ContactList
              contacts={contacts}
              selectedContact={selectedContact}
              onSelectContact={setSelectedContact}
            />
          )}
        </div>

        <div className="flex-1 border border-gray-200 rounded-lg bg-white overflow-hidden flex flex-col">
          {selectedContact ? (
            <ChatWindow
              contact={selectedContact}
              messages={messages}
              loading={messagesLoading}
              onSendMessage={handleSendMessage}
            />
          ) : (
            <div className="flex-1 flex items-center justify-center text-gray-500">
              Оберіть контакт для перегляду чату
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ContactsPage;
