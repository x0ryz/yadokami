import React from "react";
import { Contact, MessageDirection, MessageStatus } from "../../types";
import { Check, CheckCheck, AlertCircle, Clock } from "lucide-react";

interface ContactListProps {
  contacts: Contact[];
  selectedContact: Contact | null;
  onSelectContact: (contact: Contact) => void;
  onLoadMore?: () => void;
  hasMore?: boolean;
  loading?: boolean;
}

const ContactList: React.FC<ContactListProps> = ({
  contacts,
  selectedContact,
  onSelectContact,
  onLoadMore,
  hasMore = false,
  loading = false,
}) => {
  const observerTarget = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore && !loading && onLoadMore) {
          onLoadMore();
        }
      },
      { threshold: 1.0 }
    );

    if (observerTarget.current) {
      observer.observe(observerTarget.current);
    }

    return () => observer.disconnect();
  }, [hasMore, loading, onLoadMore]);
  const formatDate = (dateString: string | null) => {
    if (!dateString) return "";
    const date = new Date(dateString);
    const now = new Date();

    const isToday =
      date.getDate() === now.getDate() &&
      date.getMonth() === now.getMonth() &&
      date.getFullYear() === now.getFullYear();

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
        return <Check className="w-4 h-4 text-gray-400" />;
      case MessageStatus.DELIVERED:
        return <CheckCheck className="w-4 h-4 text-gray-400" />;
      case MessageStatus.READ:
        return <CheckCheck className="w-4 h-4 text-blue-500" />;
      case MessageStatus.FAILED:
        return <AlertCircle className="w-4 h-4 text-red-500" />;
      case MessageStatus.PENDING:
        return <Clock className="w-4 h-4 text-gray-300" />;
      default:
        return <Clock className="w-4 h-4 text-gray-300" />;
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
            className={`p-4 border-b border-gray-100 cursor-pointer hover:bg-gray-50 transition-all ${isSelected ? "bg-blue-50 border-l-4 border-l-blue-500" : "border-l-4 border-l-transparent"
              }`}
          >
            <div className="flex justify-between items-baseline mb-1">
              <h3
                className={`font-semibold text-sm truncate pr-2 ${isSelected ? "text-blue-900" : "text-gray-900"}`}
              >
                {contact.name || contact.phone_number}
              </h3>

              {contact.last_message_at && (
                <span
                  className={`text-xs whitespace-nowrap ${contact.unread_count > 0 ? "text-green-600 font-medium" : "text-gray-400"}`}
                >
                  {formatDate(contact.last_message_at)}
                </span>
              )}
            </div>

            {/* ВІДОБРАЖЕННЯ ТЕГІВ */}
            {contact.tags && contact.tags.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mb-2">
                {contact.tags.map((tag) => (
                  <span
                    key={tag.id}
                    className="text-[10px] px-2 py-0.5 rounded-lg text-white shadow-sm"
                    style={{ backgroundColor: tag.color }}
                  >
                    {tag.name}
                  </span>
                ))}
              </div>
            )}

            <div className="flex justify-between items-center">
              <div className="flex-1 min-w-0 flex items-center text-sm text-gray-600 gap-2">
                {isOutbound && (
                  <span className="flex-shrink-0">
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

              {contact.unread_count > 0 && (
                <span className="ml-2 bg-green-500 text-white text-xs font-bold rounded-lg px-2.5 py-1 min-w-[24px] text-center flex-shrink-0 shadow-sm">
                  {contact.unread_count}
                </span>
              )}
            </div>
          </div>
        );
      })}


      {/* Loading indicator for infinite scroll */}
      {(hasMore || loading) && (
        <div
          ref={observerTarget}
          className="p-4 text-center text-gray-500 text-sm flex items-center justify-center gap-2"
        >
          {loading ? (
            <>
              <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin"></div>
              <span>Завантаження...</span>
            </>
          ) : (
            <span className="opacity-0">Load more</span>
          )}
        </div>
      )}
    </div>
  );
};

export default ContactList;
