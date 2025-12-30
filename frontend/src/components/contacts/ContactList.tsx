import React from 'react';
import { Contact, ContactStatus } from '../../types';

interface ContactListProps {
  contacts: Contact[];
  selectedContact: Contact | null;
  onSelectContact: (contact: Contact) => void;
  onMarkAsRead: (contactId: string) => void;
}

const ContactList: React.FC<ContactListProps> = ({
  contacts,
  selectedContact,
  onSelectContact,
  onMarkAsRead,
}) => {
  const getStatusColor = (status: ContactStatus) => {
    const colors = {
      [ContactStatus.NEW]: 'bg-blue-100 text-blue-800',
      [ContactStatus.SENT]: 'bg-yellow-100 text-yellow-800',
      [ContactStatus.DELIVERED]: 'bg-green-100 text-green-800',
      [ContactStatus.READ]: 'bg-gray-100 text-gray-800',
      [ContactStatus.FAILED]: 'bg-red-100 text-red-800',
      [ContactStatus.OPTED_OUT]: 'bg-orange-100 text-orange-800',
      [ContactStatus.BLOCKED]: 'bg-red-100 text-red-800',
      [ContactStatus.SCHEDULED]: 'bg-purple-100 text-purple-800',
    };
    return colors[status] || 'bg-gray-100 text-gray-800';
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return '';
    const date = new Date(dateString);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));

    if (days === 0) {
      return date.toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit' });
    } else if (days === 1) {
      return 'Вчора';
    } else if (days < 7) {
      return `${days} дн. тому`;
    } else {
      return date.toLocaleDateString('uk-UA');
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
        const tags = contact.tags || [];
        return (
        <div
          key={contact.id}
          onClick={() => onSelectContact(contact)}
          className={`p-4 border-b border-gray-100 cursor-pointer hover:bg-gray-50 transition-colors ${
            selectedContact?.id === contact.id ? 'bg-blue-50 border-blue-200' : ''
          }`}
        >
          <div className="flex items-start justify-between">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <h3 className="font-semibold text-gray-900 truncate">
                  {contact.name || contact.phone_number}
                </h3>
                {contact.unread_count > 0 && (
                  <span className="bg-red-500 text-white text-xs font-bold rounded-full px-2 py-0.5 min-w-[20px] text-center">
                    {contact.unread_count}
                  </span>
                )}
              </div>
              <p className="text-sm text-gray-600 truncate">{contact.phone_number}</p>
              {contact.last_message_at && (
                <p className="text-xs text-gray-500 mt-1">
                  {formatDate(contact.last_message_at)}
                </p>
              )}
            </div>
            <div className="ml-2 flex flex-col items-end gap-1">
              <span
                className={`text-xs px-2 py-1 rounded-full ${getStatusColor(contact.status)}`}
              >
                {contact.status}
              </span>
              {tags.length > 0 && (
                <div className="flex gap-1 flex-wrap justify-end">
                  {tags.slice(0, 2).map((tag, idx) => (
                    <span
                      key={idx}
                      className="text-xs bg-gray-200 text-gray-700 px-1.5 py-0.5 rounded"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
        );
      })}
    </div>
  );
};

export default ContactList;

