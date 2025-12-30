import React, { useState, useEffect } from 'react';
import { CampaignCreate, CampaignUpdate, MessageType } from '../../types';
import { apiClient } from '../../api';
import { Template } from '../../types';

interface CampaignFormProps {
  initialData?: CampaignCreate | CampaignUpdate;
  onSubmit: (data: CampaignCreate | CampaignUpdate) => Promise<void>;
  onCancel: () => void;
  isEdit?: boolean;
}

const CampaignForm: React.FC<CampaignFormProps> = ({ initialData, onSubmit, onCancel, isEdit = false }) => {
  const [name, setName] = useState(initialData?.name || '');
  const [messageType, setMessageType] = useState<MessageType>(
    (initialData?.message_type as MessageType) || MessageType.TEMPLATE
  );
  const [templateId, setTemplateId] = useState(initialData?.template_id || '');
  const [messageBody, setMessageBody] = useState(initialData?.message_body || '');
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState(false);

  useEffect(() => {
    if (messageType === MessageType.TEMPLATE) {
      loadTemplates();
    }
  }, [messageType]);

  const loadTemplates = async () => {
    try {
      setLoadingTemplates(true);
      const data = await apiClient.listTemplates();
      setTemplates(data);
    } catch (error) {
      console.error('Помилка завантаження шаблонів:', error);
    } finally {
      setLoadingTemplates(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isEdit) {
      const data: CampaignUpdate = {
        name: name || null,
        message_type: messageType,
        template_id: messageType === MessageType.TEMPLATE ? templateId || null : null,
        message_body: messageType === MessageType.TEXT ? messageBody || null : null,
      };
      await onSubmit(data);
    } else {
      const data: CampaignCreate = {
        name: name,
        message_type: messageType,
        template_id: messageType === MessageType.TEMPLATE ? templateId || null : null,
        message_body: messageType === MessageType.TEXT ? messageBody || null : null,
      };
      await onSubmit(data);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Назва кампанії <span className="text-red-500">*</span>
        </label>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Тип повідомлення
        </label>
        <select
          value={messageType}
          onChange={(e) => setMessageType(e.target.value as MessageType)}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value={MessageType.TEMPLATE}>Шаблон</option>
          <option value={MessageType.TEXT}>Текст</option>
        </select>
      </div>

      {messageType === MessageType.TEMPLATE && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Шаблон <span className="text-red-500">*</span>
          </label>
          {loadingTemplates ? (
            <div className="text-sm text-gray-500">Завантаження шаблонів...</div>
          ) : (
            <select
              value={templateId}
              onChange={(e) => setTemplateId(e.target.value)}
              required
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Оберіть шаблон</option>
              {templates
                .filter((t) => t.status.toLowerCase().includes('approved'))
                .map((template) => (
                  <option key={template.id} value={template.id}>
                    {template.name} ({template.language})
                  </option>
                ))}
            </select>
          )}
        </div>
      )}

      {messageType === MessageType.TEXT && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Текст повідомлення <span className="text-red-500">*</span>
          </label>
          <textarea
            value={messageBody}
            onChange={(e) => setMessageBody(e.target.value)}
            required
            rows={5}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      )}

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
          Зберегти
        </button>
      </div>
    </form>
  );
};

export default CampaignForm;

