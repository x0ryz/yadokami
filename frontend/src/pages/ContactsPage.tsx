import React, { useState, useEffect, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { apiClient } from "../api";
import {
  Contact,
  MessageResponse,
  MessageDirection,
  MessageStatus,
  Tag,
  TagCreate,
  TagUpdate,
} from "../types";
import ContactList from "../components/contacts/ContactList";
import ChatWindow from "../components/contacts/ChatWindow";
import TagFilter from "../components/contacts/TagFilter";
import { useWSEvent } from "../services/useWebSocket";
import { EventType } from "../services/websocket";

const ContactsPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();

  // --- State ---
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
  const [messages, setMessages] = useState<MessageResponse[]>([]);

  const [loading, setLoading] = useState(true);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  // Теги та фільтрація
  const [availableTags, setAvailableTags] = useState<Tag[]>([]);
  const [selectedFilterTags, setSelectedFilterTags] = useState<string[]>([]);

  // --- Initial Load ---
  useEffect(() => {
    loadTags();
    loadContacts();
  }, []);

  // Перезавантаження контактів при зміні фільтру тегів
  useEffect(() => {
    // Якщо користувач шукає текстом, ми поки що ігноруємо фільтр тегів
    // (або можна комбінувати, залежить від бекенду, тут пріоритет у пошуку)
    if (!searchQuery) {
      loadContacts();
    }
  }, [selectedFilterTags]);

  // Синхронізація URL -> вибраний контакт
  useEffect(() => {
    const contactIdFromUrl = searchParams.get("contact_id");
    if (contactIdFromUrl && contacts.length > 0 && !selectedContact) {
      const contact = contacts.find((c) => c.id === contactIdFromUrl);
      if (contact) {
        setSelectedContact(contact);
      }
    }
  }, [contacts, searchParams, selectedContact]);

  // Обробник вибору контакту з оновленням URL
  const handleSelectContact = (contact: Contact) => {
    setSelectedContact(contact);
    setSearchParams({ contact_id: contact.id });
  };

  // Завантаження чату при виборі контакту
  useEffect(() => {
    if (selectedContact) {
      // 1. Локально скидаємо unread_count
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
      const msgType = data.type || data.message_type || "text";
      const isMedia = [
        "image",
        "video",
        "document",
        "audio",
        "sticker",
      ].includes(msgType);

      const isForCurrentChat =
        selectedContact &&
        ((msgContactId && msgContactId === selectedContact.id) ||
          (msgPhone && msgPhone === selectedContact.phone_number));

      const direction =
        data.direction ||
        (data.from ? MessageDirection.INBOUND : MessageDirection.OUTBOUND);

      if (isForCurrentChat) {
        if (direction === MessageDirection.INBOUND) {
          apiClient.markContactAsRead(selectedContact.id).catch(console.error);
        }

        setMessages((prev) => {
          if (!Array.isArray(prev)) return [data];
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
            reply_to_message_id: data.reply_to_message_id,
            reaction: data.reaction,
          };

          return [...prev, newMessage].sort(
            (a, b) =>
              new Date(a.created_at || 0).getTime() -
              new Date(b.created_at || 0).getTime(),
          );
        });

        if (isMedia && (!data.media_files || data.media_files.length === 0)) {
          setTimeout(() => {
            if (selectedContact) {
              loadMessages(selectedContact.id);
            }
          }, 2000);
        }
      }

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
              unread_count: isForCurrentChat
                ? 0
                : (contact.unread_count || 0) + 1,
            };
          }
          return contact;
        });

        return updated.sort((a, b) => {
          // NULLS LAST логіка для сортування на клієнті
          const dateA = a.last_message_at
            ? new Date(a.last_message_at).getTime()
            : 0;
          const dateB = b.last_message_at
            ? new Date(b.last_message_at).getTime()
            : 0;

          // Спочатку за unread_count, потім за датою
          if (a.unread_count !== b.unread_count) {
            return b.unread_count - a.unread_count;
          }
          return dateB - dateA;
        });
      });
    },
    [selectedContact],
  );

  const handleMessageStatusUpdate = useCallback((data: any) => {
    const newStatus = data.new_status || data.status;
    if (!newStatus) return;

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

  const handleMessageReaction = useCallback((data: any) => {
    setMessages((prev) =>
      prev.map((msg) => {
        if (msg.id === data.message_id) {
          return { ...msg, reaction: data.reaction };
        }
        return msg;
      }),
    );
  }, []);

  // Підписки на події
  useWSEvent(EventType.NEW_MESSAGE, handleNewMessage);
  useWSEvent(EventType.STATUS_UPDATE, handleMessageStatusUpdate);
  useWSEvent(EventType.MESSAGE_SENT, handleMessageStatusUpdate);
  useWSEvent(EventType.MESSAGE_DELIVERED, handleMessageStatusUpdate);
  useWSEvent(EventType.MESSAGE_READ, handleMessageStatusUpdate);
  useWSEvent(EventType.MESSAGE_FAILED, handleMessageStatusUpdate);
  useWSEvent(EventType.CONTACT_UNREAD_CHANGED, handleContactUnreadChanged);
  useWSEvent(EventType.MESSAGE_REACTION, handleMessageReaction);

  // --- API Calls ---

  const loadContacts = async () => {
    try {
      setLoading(true);
      // Передаємо selectedFilterTags у запит
      const data = await apiClient.getContacts(50, 0, selectedFilterTags);
      setContacts(Array.isArray(data) ? data : []);
    } catch (error: any) {
      console.error("Помилка завантаження контактів:", error);
    } finally {
      setLoading(false);
    }
  };

  const loadTags = async () => {
    try {
      const tags = await apiClient.getTags();
      setAvailableTags(tags);
    } catch (error) {
      console.error("Помилка завантаження тегів:", error);
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
      // Якщо пошук порожній, завантажуємо звичайний список (з урахуванням фільтрів тегів)
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

  const handleSendMessage = async (
    phone: string,
    text: string,
    replyToId?: string,
  ) => {
    try {
      await apiClient.sendMessage({
        phone,
        text,
        type: "text",
        reply_to_message_id: replyToId,
      });
    } catch (error) {
      console.error("Помилка відправки повідомлення:", error);
      alert("Не вдалося відправити повідомлення");
    }
  };

  const handleSendMedia = async (
    phone: string,
    file: File,
    caption?: string,
  ) => {
    try {
      await apiClient.sendMediaMessage(phone, file, caption);
    } catch (error) {
      console.error("Помилка відправки медіа:", error);
      alert("Не вдалося відправити файл");
    }
  };

  // --- Tag Management ---

  const handleCreateTag = async (data: TagCreate) => {
    try {
      await apiClient.createTag(data);
      await loadTags();
    } catch (error) {
      console.error("Помилка створення тегу:", error);
      alert("Не вдалося створити тег");
    }
  };

  const handleDeleteTag = async (tagId: string) => {
    try {
      await apiClient.deleteTag(tagId);
      await loadTags();

      // Оновлюємо контакти, бо в них міг бути видалений тег
      await loadContacts();

      // Якщо обраний контакт мав цей тег, треба його оновити локально
      if (selectedContact) {
        const updatedTags = selectedContact.tags.filter((t) => t.id !== tagId);
        setSelectedContact({ ...selectedContact, tags: updatedTags });
      }
    } catch (error) {
      console.error("Помилка видалення тегу:", error);
    }
  };

  const handleUpdateContactTags = async (tagIds: string[]) => {
    if (!selectedContact) return;

    try {
      const updatedContact = await apiClient.updateContact(selectedContact.id, {
        tag_ids: tagIds,
      });

      // MERGE логіка: зберігаємо обчислювані поля зі старого об'єкта
      const mergedContact = {
        ...updatedContact,
        last_message_body: selectedContact.last_message_body,
        last_message_at: selectedContact.last_message_at,
        last_message_status: selectedContact.last_message_status,
        last_message_direction: selectedContact.last_message_direction,
        unread_count: selectedContact.unread_count,
      };

      setSelectedContact(mergedContact);

      setContacts((prev) =>
        prev.map((c) => {
          if (c.id === updatedContact.id) {
            return {
              ...updatedContact,
              // Відновлюємо поля повідомлень
              last_message_body: c.last_message_body,
              last_message_at: c.last_message_at,
              last_message_status: c.last_message_status,
              last_message_direction: c.last_message_direction,
              unread_count: c.unread_count,
            };
          }
          return c;
        }),
      );
    } catch (error) {
      console.error("Помилка оновлення тегів контакту:", error);
      alert("Не вдалося оновити теги");
    }
  };

  const handleEditTag = async (tagId: string, data: TagUpdate) => {
    try {
      const updatedTag = await apiClient.updateTag(tagId, data);

      // 1. Оновлюємо список доступних тегів
      setAvailableTags((prev) =>
        prev.map((t) => (t.id === tagId ? updatedTag : t)),
      );

      // 2. Оновлюємо поточний контакт
      if (selectedContact) {
        const hasTag = selectedContact.tags.some((t) => t.id === tagId);
        if (hasTag) {
          setSelectedContact((prev) => {
            if (!prev) return null;
            return {
              ...prev,
              tags: prev.tags.map((t) => (t.id === tagId ? updatedTag : t)),
            };
          });
        }
      }

      // 3. Оновлюємо список контактів (плашки)
      setContacts((prevContacts) =>
        prevContacts.map((contact) => {
          if (!contact.tags || contact.tags.length === 0) return contact;

          const tagIndex = contact.tags.findIndex((t) => t.id === tagId);
          if (tagIndex === -1) return contact;

          const newTags = [...contact.tags];
          newTags[tagIndex] = updatedTag;

          return { ...contact, tags: newTags };
        }),
      );
    } catch (error) {
      console.error("Помилка редагування тегу:", error);
      alert("Не вдалося оновити тег");
    }
  };

  return (
    <div className="h-[calc(100vh-8rem)] flex flex-col">
      <div className="mb-4">
        <div className="flex gap-2 items-center">
          {/* Фільтр тегів */}
          <TagFilter
            availableTags={availableTags}
            selectedTagIds={selectedFilterTags}
            onChange={setSelectedFilterTags}
          />

          <input
            type="text"
            placeholder="Пошук контактів..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyPress={(e) => e.key === "Enter" && handleSearch()}
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
          />
          <button
            onClick={handleSearch}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
          >
            Пошук
          </button>
        </div>
      </div>

      <div className="flex-1 flex gap-4 overflow-hidden">
        {/* Contact List Column */}
        <div className="w-1/3 border border-gray-200 rounded-lg bg-white overflow-hidden flex flex-col">
          <div className="p-4 border-b border-gray-200 flex justify-between items-center">
            <h2 className="text-lg font-semibold text-gray-800">Контакти</h2>
            {contacts.length > 0 && !loading && (
              <span className="text-xs text-gray-400">
                Всього: {contacts.length}
              </span>
            )}
          </div>
          {loading ? (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-gray-500">Завантаження...</div>
            </div>
          ) : (
            <ContactList
              contacts={contacts}
              selectedContact={selectedContact}
              onSelectContact={handleSelectContact}
            />
          )}
        </div>

        {/* Chat Window Column */}
        <div className="flex-1 border border-gray-200 rounded-lg bg-white overflow-hidden flex flex-col">
          {selectedContact ? (
            <ChatWindow
              contact={selectedContact}
              messages={messages}
              loading={messagesLoading}
              onSendMessage={handleSendMessage}
              onSendMedia={handleSendMedia}
              // Tag Props
              availableTags={availableTags}
              onUpdateTags={handleUpdateContactTags}
              onCreateTag={handleCreateTag}
              onDeleteTag={handleDeleteTag}
              onEditTag={handleEditTag}
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
