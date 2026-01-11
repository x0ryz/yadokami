import React, { useState, useRef, useEffect } from "react";
import { MoreVertical, Tag, Ban, Archive, Trash2, Undo } from "lucide-react";
import { Contact, ContactStatus } from "../../types";
import { apiClient } from "../../api";

interface ContactActionsMenuProps {
  contact: Contact;
  onUpdate: (contact: Contact) => void;
  onDelete: (contactId: string) => void;
  onEditTags: () => void;
}

const ContactActionsMenu: React.FC<ContactActionsMenuProps> = ({
  contact,
  onUpdate,
  onDelete,
  onEditTags,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  const handleUpdateStatus = async (status: ContactStatus) => {
    try {
      setLoading(true);
      const updatedContact = await apiClient.updateContact(contact.id, { status });
      onUpdate(updatedContact);
      setIsOpen(false);
    } catch (error) {
      console.error("Failed to update contact status:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (window.confirm("Ви дійсно хочете видалити цей контакт?")) {
      try {
        setLoading(true);
        await apiClient.deleteContact(contact.id);
        onDelete(contact.id);
      } catch (error) {
        console.error("Failed to delete contact:", error);
      } finally {
        setLoading(false);
      }
    }
  };

  const isBlocked = contact.status === ContactStatus.BLOCKED;
  const isArchived = contact.status === ContactStatus.ARCHIVED;

  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="p-1.5 rounded-full text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
        title="More options"
      >
        <MoreVertical size={20} />
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-56 bg-white rounded-md shadow-lg z-50 border border-gray-100 py-1">
          {/* Edit Tags */}
          <button
            onClick={() => {
              onEditTags();
              setIsOpen(false);
            }}
            className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-2"
          >
            <Tag size={16} />
            Редагувати теги
          </button>

          {/* Block/Unblock */}
          <button
            onClick={() => handleUpdateStatus(isBlocked ? ContactStatus.ACTIVE : ContactStatus.BLOCKED)}
            className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-2"
            disabled={loading}
          >
            {isBlocked ? <Undo size={16} /> : <Ban size={16} />}
            {isBlocked ? "Розблокувати" : "Заблокувати"}
          </button>

           {/* Archive/Unarchive */}
           <button
            onClick={() => handleUpdateStatus(isArchived ? ContactStatus.ACTIVE : ContactStatus.ARCHIVED)}
            className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-2"
            disabled={loading}
          >
            {isArchived ? <Undo size={16} /> : <Archive size={16} />}
            {isArchived ? "Розархівувати" : "Архівувати"}
          </button>

          <div className="border-t border-gray-100 my-1"></div>

          {/* Delete */}
          <button
            onClick={handleDelete}
            className="w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50 flex items-center gap-2"
            disabled={loading}
          >
            <Trash2 size={16} />
            Видалити
          </button>
        </div>
      )}
    </div>
  );
};

export default ContactActionsMenu;
