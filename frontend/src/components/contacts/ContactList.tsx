import React from "react";
import { Contact, MessageDirection, MessageStatus } from "../../types";

interface ContactListProps {
  contacts: Contact[];
  selectedContact: Contact | null;
  onSelectContact: (contact: Contact) => void;
}

const ContactList: React.FC<ContactListProps> = ({
  contacts,
  selectedContact,
  onSelectContact,
}) => {
  const formatDate = (dateString: string | null) => {
    if (!dateString) return "";
    const date = new Date(dateString);
    const now = new Date();

    // Перевірка на "Сьогодні" (порівнюємо календарні дати)
    const isToday =
      date.getDate() === now.getDate() &&
      date.getMonth() === now.getMonth() &&
      date.getFullYear() === now.getFullYear();

    // Перевірка на "Вчора"
    const yesterday = new Date(now);
    yesterday.setDate(now.getDate() - 1);
    const isYesterday =
      date.getDate() === yesterday.getDate() &&
      date.getMonth() === yesterday.getMonth() &&
      date.getFullYear() === yesterday.getFullYear();

    if (isToday) {
      return date.toLocaleTimeString("uk-UA", {
        hour: "2-digit",
        minute: "2-digit",
      });
    } else if (isYesterday) {
      return "Вчора";
    } else {
      // Якщо більше 7 днів тому - повна дата, інакше - день тижня
      const diffTime = Math.abs(now.getTime() - date.getTime());
      const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

      if (diffDays < 7) {
        return date.toLocaleDateString("uk-UA", { weekday: "short" });
      }
      return date.toLocaleDateString("uk-UA", {
        day: "2-digit",
        month: "2-digit",
      });
    }
  };

  const getStatusIcon = (status?: MessageStatus | null) => {
    if (!status) return null;
    switch (status) {
      case MessageStatus.SENT:
        return <span className="text-gray-400">✓</span>;
      case MessageStatus.DELIVERED:
        return <span className="text-gray-400">✓✓</span>;
      case MessageStatus.READ:
        return <span className="text-blue-500 font-bold">✓✓</span>; // font-bold для кращої видимості
      case MessageStatus.FAILED:
        return <span className="text-red-500">!</span>;
      case MessageStatus.PENDING:
        return <span className="text-gray-300">🕒</span>;
      default:
        return <span className="text-gray-300">🕒</span>;
    }
  };

  if (!contacts || contacts.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-500 p-4">
        Контакти не знайдено
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto">
      {contacts.map((contact) => {
        const isSelected = selectedContact?.id === contact.id;
        const lastMsgBody = contact.last_message_body;
        const isOutbound =
          contact.last_message_direction === MessageDirection.OUTBOUND;

        return (
          <div
            key={contact.id}
            onClick={() => onSelectContact(contact)}
            className={`p-3 border-b border-gray-100 cursor-pointer hover:bg-gray-50 transition-colors ${
              isSelected ? "bg-blue-50 border-blue-200" : ""
            }`}
          >
            <div className="flex justify-between items-baseline mb-1">
              {/* Ім'я або телефон */}
              <h3
                className={`font-semibold text-sm truncate pr-2 ${isSelected ? "text-blue-900" : "text-gray-900"}`}
              >
                {contact.name || contact.phone_number}
              </h3>

              {/* Час останнього повідомлення */}
              {contact.last_message_at && (
                <span
                  className={`text-xs whitespace-nowrap ${contact.unread_count > 0 ? "text-green-600 font-medium" : "text-gray-400"}`}
                >
                  {formatDate(contact.last_message_at)}
                </span>
              )}
            </div>

            <div className="flex justify-between items-center">
              {/* Прев'ю повідомлення */}
              <div className="flex-1 min-w-0 flex items-center text-sm text-gray-600 h-5">
                {isOutbound && (
                  <span className="mr-1 text-xs flex-shrink-0">
                    {getStatusIcon(contact.last_message_status)}
                  </span>
                )}
                <p className="truncate">
                  {lastMsgBody ? (
                    lastMsgBody
                  ) : (
                    <span className="italic text-gray-400">
                      Немає повідомлень
                    </span>
                  )}
                </p>
              </div>

              {/* Лічильник непрочитаних */}
              {contact.unread_count > 0 && (
                <span className="ml-2 bg-green-500 text-white text-xs font-bold rounded-full px-2 py-0.5 min-w-[20px] text-center flex-shrink-0">
                  {contact.unread_count}
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default ContactList;
