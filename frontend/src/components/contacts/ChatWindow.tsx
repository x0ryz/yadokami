import React, { useState, useEffect, useRef } from 'react';
import { Contact, MessageResponse, MessageDirection, MessageStatus } from '../../types';

interface ChatWindowProps {
  contact: Contact;
  messages: MessageResponse[];
  loading: boolean;
  onSendMessage: (phone: string, text: string) => void;
}

const ChatWindow: React.FC<ChatWindowProps> = ({
  contact,
  messages = [],
  loading,
  onSendMessage,
}) => {
  const [messageText, setMessageText] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleSend = () => {
    if (messageText.trim()) {
      onSendMessage(contact.phone_number, messageText);
      setMessageText('');
    }
  };

  const formatMessageTime = (dateString: string | null) => {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit' });
  };

  const getStatusIcon = (status: MessageStatus) => {
    switch (status) {
      case MessageStatus.SENT:
        return '✓';
      case MessageStatus.DELIVERED:
        return '✓✓';
      case MessageStatus.READ:
        return '✓✓';
      default:
        return '';
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 bg-white">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">
              {contact.name || contact.phone_number}
            </h2>
            <p className="text-sm text-gray-600">{contact.phone_number}</p>
          </div>
          <div className="flex items-center gap-2">
            {contact.tags && contact.tags.length > 0 && (
              <div className="flex gap-1">
                {contact.tags.map((tag, idx) => (
                  <span
                    key={idx}
                    className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 bg-gray-50">
        {loading ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-gray-500">Завантаження повідомлень...</div>
          </div>
        ) : !messages || messages.length === 0 ? (
          <div className="flex items-center justify-center h-full text-gray-500">
            Немає повідомлень
          </div>
        ) : (
          <div className="space-y-4">
            {messages.map((message, index) => {
              const isOutbound = message.direction === MessageDirection.OUTBOUND;
              return (
                <div
                  key={message.id || `message-${index}`}
                  className={`flex ${isOutbound ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
                      isOutbound
                        ? 'bg-blue-600 text-white'
                        : 'bg-white text-gray-900 border border-gray-200'
                    }`}
                  >
                    {message.body && <p className="text-sm">{message.body}</p>}
                    {message.media_files && message.media_files.length > 0 && (
                      <div className="mt-2 space-y-2">
                        {message.media_files.map((media) => (
                          <div key={media.id} className="rounded overflow-hidden">
                            {media.file_mime_type.startsWith('image/') ? (
                              <img
                                src={media.url}
                                alt={media.caption || media.file_name}
                                className="max-w-full h-auto"
                              />
                            ) : media.file_mime_type.startsWith('video/') ? (
                              <video
                                src={media.url}
                                controls
                                className="max-w-full h-auto"
                              />
                            ) : (
                              <a
                                href={media.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="flex items-center gap-2 p-2 bg-gray-100 rounded text-gray-800 hover:bg-gray-200 transition-colors"
                              >
                                <span className="text-2xl">📄</span>
                                <span className="text-sm underline truncate">
                                  {media.file_name}
                                </span>
                              </a>
                            )}
                            {media.caption && (
                              <p className="text-xs mt-1 opacity-90">{media.caption}</p>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                    <div
                      className={`flex items-center justify-end gap-2 mt-1 text-xs ${
                        isOutbound ? 'text-blue-100' : 'text-gray-500'
                      }`}
                    >
                      <span>{formatMessageTime(message.created_at)}</span>
                      {isOutbound && (
                        <span className="text-xs">{getStatusIcon(message.status)}</span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input */}
      <div className="p-4 border-t border-gray-200 bg-white">
        <div className="flex gap-2">
          <input
            type="text"
            value={messageText}
            onChange={(e) => setMessageText(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSend()}
            placeholder="Введіть повідомлення..."
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={handleSend}
            disabled={!messageText.trim()}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
          >
            Відправити
          </button>
        </div>
      </div>
    </div>
  );
};

export default ChatWindow;

