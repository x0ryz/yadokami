import React, { useState, useEffect, useCallback } from 'react';
import { apiClient } from '../api';
import { Contact, MessageResponse, MessageDirection, MessageStatus } from '../types';
import ContactList from '../components/contacts/ContactList';
import ChatWindow from '../components/contacts/ChatWindow';
import { useWSEvent } from '../services/useWebSocket';
import { EventType } from '../services/websocket';

const ContactsPage: React.FC = () => {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
  const [messages, setMessages] = useState<MessageResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    loadContacts();
  }, []);

  useEffect(() => {
    if (selectedContact) {
      loadMessages(selectedContact.id);
    }
  }, [selectedContact]);

  // --- WebSocket Handlers ---

  const handleNewMessage = useCallback((data: any) => {
    console.log('WS: New message received:', data);
    
    // 1. Визначаємо номер телефону повідомлення (вхідні мають 'from', вихідні 'phone')
    const msgPhone = data.phone || data.from || data.phone_number;
    const msgContactId = data.contact_id;

    // 2. Перевіряємо, чи це повідомлення для поточного чату
    const isForCurrentChat = selectedContact && (
      (msgContactId && msgContactId === selectedContact.id) ||
      (msgPhone && msgPhone === selectedContact.phone_number)
    );
    
    if (isForCurrentChat) {
      setMessages(prev => {
        if (!Array.isArray(prev)) return [data];
        // Запобігаємо дублікатам
        if (prev.some(m => m.id === data.id)) return prev;

        // Нормалізуємо об'єкт повідомлення (щоб точно відповідав інтерфейсу)
        const newMessage: MessageResponse = {
            id: data.id,
            wamid: data.wamid,
            direction: data.direction || (data.from ? MessageDirection.INBOUND : MessageDirection.OUTBOUND),
            status: data.status || MessageStatus.RECEIVED,
            message_type: data.type || 'text',
            body: data.body,
            created_at: data.created_at || new Date().toISOString(),
            media_files: data.media_files || []
        };

        return [...prev, newMessage].sort((a, b) => 
            new Date(a.created_at || 0).getTime() - new Date(b.created_at || 0).getTime()
        );
      });
    }
    
    // 3. Оновлюємо список контактів (піднімаємо активний контакт вгору, оновлюємо текст)
    setContacts(prev => {
        const updated = prev.map(contact => {
            const isMatch = (msgContactId && contact.id === msgContactId) || 
                            (msgPhone && contact.phone_number === msgPhone);
            
            if (isMatch) {
                return {
                    ...contact,
                    last_message_at: data.created_at || new Date().toISOString(),
                    // Якщо чат відкритий - не збільшуємо лічильник непрочитаних
                    unread_count: isForCurrentChat ? 0 : (contact.unread_count || 0) + 1
                };
            }
            return contact;
        });
        // Сортуємо: контакти з найновішими повідомленнями зверху
        return updated.sort((a, b) => {
            const dateA = new Date(a.last_message_at || 0).getTime();
            const dateB = new Date(b.last_message_at || 0).getTime();
            return dateB - dateA;
        });
    });

    // Якщо прийшло повідомлення від нового контакту, якого немає в списку - перезавантажуємо список
    // (опціонально, можна додати логіку додавання в список без перезавантаження)
  }, [selectedContact]);

  const handleMessageStatusUpdate = useCallback((data: any) => {
    console.log('WS: Status update:', data);
    
    // Отримуємо новий статус (підтримуємо різні формати API)
    const newStatus = data.new_status || data.status;
    if (!newStatus) return;

    setMessages(prev => {
      if (!Array.isArray(prev)) return [];
      return prev.map(msg => {
        // Шукаємо повідомлення за ID або WAMID
        const isMatch = (data.id && msg.id === data.id) || 
                        (data.message_id && msg.id === data.message_id) ||
                        (data.wamid && msg.wamid === data.wamid);

        if (isMatch) {
          return { 
              ...msg, 
              status: newStatus,
              // Оновлюємо WAMID, якщо він прийшов (важливо для наступних апдейтів)
              wamid: data.wamid || msg.wamid 
          };
        }
        return msg;
      });
    });
  }, []);

  const handleContactUnreadChanged = useCallback((data: any) => {
    setContacts(prev => prev.map(contact => {
      if (contact.id === data.contact_id) {
        return { ...contact, unread_count: data.unread_count };
      }
      return contact;
    }));
  }, []);

  // Підписки на події
  useWSEvent(EventType.NEW_MESSAGE, handleNewMessage);
  // Додаємо STATUS_UPDATE, бо саме його часто шле бекенд
  useWSEvent(EventType.STATUS_UPDATE, handleMessageStatusUpdate);
  // Залишаємо специфічні події про всяк випадок
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
      console.error('Помилка завантаження контактів:', error);
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
      console.error('Помилка завантаження повідомлень:', error);
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
      console.error('Помилка пошуку:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleMarkAsRead = async (contactId: string) => {
    try {
      await apiClient.markContactAsRead(contactId);
      setContacts(prev => prev.map(contact => 
        contact.id === contactId ? { ...contact, unread_count: 0 } : contact
      ));
    } catch (error) {
      console.error('Помилка позначення як прочитане:', error);
    }
  };

  const handleSendMessage = async (phone: string, text: string) => {
    try {
      await apiClient.sendMessage({ phone, text, type: 'text' });
      // Не додаємо вручну, чекаємо WebSocket події (outbound message)
    } catch (error) {
      console.error('Помилка відправки повідомлення:', error);
      alert('Не вдалося відправити повідомлення');
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
            onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
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
              onMarkAsRead={handleMarkAsRead}
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