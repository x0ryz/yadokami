import React from "react";
import { DuplicateContact } from "../../types";

interface DuplicateContactsModalProps {
  isOpen: boolean;
  duplicates: DuplicateContact[];
  onClose: () => void;
  onSkipDuplicates: () => void;
  onForceAdd: () => void;
}

const DuplicateContactsModal: React.FC<DuplicateContactsModalProps> = ({
  isOpen,
  duplicates,
  onClose,
  onSkipDuplicates,
  onForceAdd,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[80vh] flex flex-col">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">
            Знайдено дублікати
          </h3>
          <p className="text-sm text-gray-600 mt-1">
            Наступні контакти вже отримували цей шаблон раніше
          </p>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4">
          <div className="space-y-2">
            {duplicates.map((contact, index) => (
              <div
                key={index}
                className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg"
              >
                <div className="flex items-start">
                  <svg
                    className="w-5 h-5 text-yellow-600 mr-2 mt-0.5"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      fillRule="evenodd"
                      d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                      clipRule="evenodd"
                    />
                  </svg>
                  <div>
                    <div className="font-medium text-gray-900">
                      {contact.phone_number}
                    </div>
                    {contact.name && (
                      <div className="text-sm text-gray-600">{contact.name}</div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <div className="flex">
              <svg
                className="w-5 h-5 text-blue-600 mr-2 mt-0.5"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path
                  fillRule="evenodd"
                  d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
                  clipRule="evenodd"
                />
              </svg>
              <div className="text-sm text-blue-800">
                <p className="font-medium">Що це означає?</p>
                <p className="mt-1">
                  Відправка одного й того ж шаблону контакту протягом 24 годин може
                  порушити політику WhatsApp. Рекомендуємо пропустити ці контакти або
                  змінити шаблон.
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="px-6 py-4 border-t border-gray-200 bg-gray-50 flex gap-2 justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
          >
            Скасувати
          </button>
          <button
            onClick={onSkipDuplicates}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Пропустити дублікати
          </button>
          <button
            onClick={onForceAdd}
            className="px-4 py-2 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 transition-colors"
          >
            Додати всіх
          </button>
        </div>
      </div>
    </div>
  );
};

export default DuplicateContactsModal;
