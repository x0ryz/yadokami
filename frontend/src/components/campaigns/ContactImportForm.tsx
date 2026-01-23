import React, { useState } from "react";
import { ContactImport, DuplicateCheckResult, DuplicateContact } from "../../types";
import DuplicateContactsModal from "./DuplicateContactsModal";

interface ContactImportFormProps {
  campaignId: string;
  onAddContacts: (contacts: ContactImport[], forceAdd?: boolean) => Promise<void>;
  onCheckDuplicates: (contacts: ContactImport[]) => Promise<DuplicateCheckResult>;
  onImportFile: (file: File) => Promise<void>;
  onCancel: () => void;
}

const ContactImportForm: React.FC<ContactImportFormProps> = ({
  campaignId,
  onAddContacts,
  onCheckDuplicates,
  onImportFile,
  onCancel,
}) => {
  const [importMethod, setImportMethod] = useState<"manual" | "file">("manual");
  const [contacts, setContacts] = useState<ContactImport[]>([
    { phone_number: "", name: "", tags: [], custom_data: {} },
  ]);
  const [file, setFile] = useState<File | null>(null);
  const [showDuplicateModal, setShowDuplicateModal] = useState(false);
  const [duplicates, setDuplicates] = useState<DuplicateContact[]>([]);
  const [pendingContacts, setPendingContacts] = useState<ContactImport[]>([]);

  const addContactRow = () => {
    setContacts([...contacts, { phone_number: "", name: "", tags: [], custom_data: {} }]);
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

  const updateCustomData = (index: number, customData: Record<string, any>) => {
    const updated = [...contacts];
    updated[index] = { ...updated[index], custom_data: customData };
    setContacts(updated);
  };

  const parseCustomDataString = (input: string): Record<string, any> => {
    if (!input.trim()) return {};
    try {
      // Try parsing as JSON first
      return JSON.parse(input);
    } catch {
      // Fall back to key:value format
      const result: Record<string, any> = {};
      const pairs = input.split(",").map((s) => s.trim()).filter(Boolean);
      for (const pair of pairs) {
        const [key, ...valueParts] = pair.split(":");
        if (key && valueParts.length > 0) {
          result[key.trim()] = valueParts.join(":").trim();
        }
      }
      return result;
    }
  };

  const customDataToString = (data: Record<string, any>): string => {
    if (!data || Object.keys(data).length === 0) return "";
    return Object.entries(data)
      .map(([key, value]) => `${key}: ${value}`)
      .join(", ");
  };

  const handleManualSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const validContacts = contacts.filter((c) => c.phone_number.trim());
    if (validContacts.length > 0) {
      // Check for duplicates
      const result = await onCheckDuplicates(validContacts);
      
      if (result.duplicates.length > 0) {
        // Show modal if duplicates found
        setDuplicates(result.duplicates);
        setPendingContacts(validContacts);
        setShowDuplicateModal(true);
      } else {
        // No duplicates, add directly
        await onAddContacts(validContacts, false);
      }
    }
  };

  const handleSkipDuplicates = async () => {
    setShowDuplicateModal(false);
    // Add only contacts that are not duplicates
    const duplicatePhones = new Set(duplicates.map(d => d.phone_number));
    const nonDuplicateContacts = pendingContacts.filter(
      c => !duplicatePhones.has(c.phone_number)
    );
    if (nonDuplicateContacts.length > 0) {
      await onAddContacts(nonDuplicateContacts, false);
    }
  };

  const handleForceAdd = async () => {
    setShowDuplicateModal(false);
    // Add all contacts with force flag
    await onAddContacts(pendingContacts, true);
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
                <textarea
                  placeholder="Додаткові поля (key: value, key2: value2 або JSON)"
                  value={customDataToString(contact.custom_data || {})}
                  onChange={(e) =>
                    updateCustomData(index, parseCustomDataString(e.target.value))
                  }
                  rows={2}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm font-mono"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Приклад: city: Київ, order_id: 12345 або {"{"}"city": "Київ", "order_id": "12345"{"}"}
                </p>
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
            </label> CSV/Excel: phone_number, name, tags (теги через крапку з комою), додаткові колонки будуть збережені як custom_data
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

      <DuplicateContactsModal
        isOpen={showDuplicateModal}
        duplicates={duplicates}
        onClose={() => setShowDuplicateModal(false)}
        onSkipDuplicates={handleSkipDuplicates}
        onForceAdd={handleForceAdd}
      />
    </div>
  );
};

export default ContactImportForm;
