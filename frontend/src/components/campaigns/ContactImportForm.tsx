import React, { useState } from "react";
import { ContactImport } from "../../types";

interface ContactImportFormProps {
  onAddContacts: (contacts: ContactImport[]) => Promise<void>;
  onImportFile: (file: File) => Promise<void>;
  onCancel: () => void;
}

const ContactImportForm: React.FC<ContactImportFormProps> = ({
  onAddContacts,
  onImportFile,
  onCancel,
}) => {
  const [importMethod, setImportMethod] = useState<"manual" | "file">("manual");
  const [contacts, setContacts] = useState<ContactImport[]>([
    { phone_number: "", name: "", tags: [] },
  ]);
  const [file, setFile] = useState<File | null>(null);

  const addContactRow = () => {
    setContacts([...contacts, { phone_number: "", name: "", tags: [] }]);
  };

  const removeContactRow = (index: number) => {
    setContacts(contacts.filter((_, i) => i !== index));
  };

  const updateContact = (
    index: number,
    field: keyof ContactImport,
    value: any,
  ) => {
    const updated = [...contacts];
    updated[index] = { ...updated[index], [field]: value };
    setContacts(updated);
  };

  const handleManualSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const validContacts = contacts.filter((c) => c.phone_number.trim());
    if (validContacts.length > 0) {
      await onAddContacts(validContacts);
    }
  };

  const handleFileSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (file) {
      await onImportFile(file);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex gap-2 border-b border-gray-200">
        <button
          onClick={() => setImportMethod("manual")}
          className={`px-4 py-2 font-medium text-sm transition-colors ${
            importMethod === "manual"
              ? "border-b-2 border-blue-600 text-blue-600"
              : "text-gray-600 hover:text-gray-900"
          }`}
        >
          Вручну
        </button>
        <button
          onClick={() => setImportMethod("file")}
          className={`px-4 py-2 font-medium text-sm transition-colors ${
            importMethod === "file"
              ? "border-b-2 border-blue-600 text-blue-600"
              : "text-gray-600 hover:text-gray-900"
          }`}
        >
          З файлу
        </button>
      </div>

      {importMethod === "manual" ? (
        <form onSubmit={handleManualSubmit} className="space-y-4">
          <div className="max-h-64 overflow-y-auto space-y-2">
            {contacts.map((contact, index) => (
              <div
                key={index}
                className="p-3 border border-gray-200 rounded-lg space-y-2"
              >
                <div className="flex gap-2">
                  <input
                    type="text"
                    placeholder="Номер телефону *"
                    value={contact.phone_number}
                    onChange={(e) =>
                      updateContact(index, "phone_number", e.target.value)
                    }
                    required
                    className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                  />
                  {contacts.length > 1 && (
                    <button
                      type="button"
                      onClick={() => removeContactRow(index)}
                      className="px-3 py-2 bg-red-100 text-red-700 rounded-lg hover:bg-red-200 transition-colors text-sm"
                    >
                      ×
                    </button>
                  )}
                </div>
                <input
                  type="text"
                  placeholder="Ім'я (необов'язково)"
                  value={contact.name || ""}
                  onChange={(e) =>
                    updateContact(index, "name", e.target.value || null)
                  }
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                />
                <input
                  type="text"
                  placeholder="Теги через кому (необов'язково)"
                  value={contact.tags?.join(", ") || ""}
                  onChange={(e) =>
                    updateContact(
                      index,
                      "tags",
                      e.target.value
                        .split(",")
                        .map((t: string) => t.trim())
                        .filter(Boolean),
                    )
                  }
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                />
              </div>
            ))}
          </div>
          <button
            type="button"
            onClick={addContactRow}
            className="w-full px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors text-sm"
          >
            + Додати контакт
          </button>
          <div className="flex gap-2 justify-end">
            <button
              type="button"
              onClick={onCancel}
              className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors"
            >
              Скасувати
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              Додати
            </button>
          </div>
        </form>
      ) : (
        <form onSubmit={handleFileSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Файл (CSV або Excel)
            </label>
            <input
              type="file"
              accept=".csv,.xlsx,.xls"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              required
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <p className="mt-2 text-xs text-gray-500">
              Формат: phone_number, name, tags (теги через крапку з комою)
            </p>
          </div>
          <div className="flex gap-2 justify-end">
            <button
              type="button"
              onClick={onCancel}
              className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors"
            >
              Скасувати
            </button>
            <button
              type="submit"
              disabled={!file}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
            >
              Імпортувати
            </button>
          </div>
        </form>
      )}
    </div>
  );
};

export default ContactImportForm;
