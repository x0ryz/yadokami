import React, { useState, useEffect } from "react";
import {
  CampaignCreate,
  CampaignUpdate,
  MessageType,
  WabaPhoneNumberResponse,
  AvailableFieldsResponse,
} from "../../types";
import { apiClient } from "../../api";
import { Template } from "../../types";
import { TemplateVariableMapper } from "./TemplateVariableMapper";

interface CampaignFormProps {
  initialData?: CampaignCreate | CampaignUpdate;
  onSubmit: (data: CampaignCreate | CampaignUpdate) => Promise<void>;
  onCancel: () => void;
  isEdit?: boolean;
}

const CampaignForm: React.FC<CampaignFormProps> = ({
  initialData,
  onSubmit,
  onCancel,
  isEdit = false,
}) => {
  const [name, setName] = useState(initialData?.name || "");
  const [templateId, setTemplateId] = useState(initialData?.template_id || "");
  const [wabaPhoneId, setWabaPhoneId] = useState(
    (initialData && "waba_phone_id" in initialData && initialData.waba_phone_id) ||
    "",
  );

  const [variableMapping, setVariableMapping] = useState<Record<string, string>>(
    initialData?.variable_mapping || {}
  );
  const [templates, setTemplates] = useState<Template[]>([]);
  const [wabaPhones, setWabaPhones] = useState<WabaPhoneNumberResponse[]>([]);
  const [availableFields, setAvailableFields] = useState<AvailableFieldsResponse | null>(null);
  const [loadingTemplates, setLoadingTemplates] = useState(false);
  const [loadingPhones, setLoadingPhones] = useState(false);
  const [loadingFields, setLoadingFields] = useState(false);

  useEffect(() => {
    loadWabaPhones();
    loadAvailableFields();
    loadTemplates();
  }, []);

  // Auto-fill variable mapping when template is selected
  useEffect(() => {
    if (templateId && templates.length > 0) {
      const selectedTemplate = templates.find((t) => t.id === templateId);
      if (selectedTemplate?.default_variable_mapping && !initialData?.variable_mapping) {
        setVariableMapping(selectedTemplate.default_variable_mapping);
      }
    }
  }, [templateId, templates]);

  const loadTemplates = async () => {
    try {
      setLoadingTemplates(true);
      const data = await apiClient.listTemplates();
      setTemplates(data);
    } catch (error) {
      console.error("Помилка завантаження шаблонів:", error);
    } finally {
      setLoadingTemplates(false);
    }
  };

  const loadWabaPhones = async () => {
    try {
      setLoadingPhones(true);
      const data = await apiClient.getWabaPhoneNumbers();
      setWabaPhones(data.phone_numbers);
    } catch (error) {
      console.error("Помилка завантаження номерів WABA:", error);
    } finally {
      setLoadingPhones(false);
    }
  };

  const loadAvailableFields = async () => {
    try {
      setLoadingFields(true);
      const data = await apiClient.getAvailableFields();
      setAvailableFields(data);
    } catch (error) {
      console.error("Помилка завантаження доступних полів:", error);
    } finally {
      setLoadingFields(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isEdit) {
      const data: CampaignUpdate = {
        name: name || null,
        template_id: templateId || null,
        variable_mapping:
          Object.keys(variableMapping).length > 0
            ? variableMapping
            : null,
      };
      await onSubmit(data);
    } else {
      const data: CampaignCreate = {
        name: name,
        template_id: templateId || null,
        waba_phone_id: wabaPhoneId || null,
        variable_mapping:
          Object.keys(variableMapping).length > 0
            ? variableMapping
            : null,
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
          Номер WABA
        </label>
        {loadingPhones ? (
          <div className="text-sm text-gray-500">Завантаження номерів...</div>
        ) : (
          <select
            value={wabaPhoneId}
            onChange={(e) => setWabaPhoneId(e.target.value)}
            disabled={isEdit}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Оберіть номер</option>
            {wabaPhones.map((phone) => (
              <option key={phone.id} value={phone.id}>
                {phone.display_phone_number} ({phone.quality_rating})
              </option>
            ))}
          </select>
        )}
      </div>

      {/* Removed Message Type selector, simplified to just Template selection */}

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Шаблон
        </label>
        {loadingTemplates ? (
          <div className="text-sm text-gray-500">Завантаження шаблонів...</div>
        ) : (
          <select
            value={templateId}
            onChange={(e) => setTemplateId(e.target.value)}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Оберіть шаблон</option>
            {templates
              .filter((t) => t.status.toLowerCase().includes("approved"))
              .map((template) => (
                <option key={template.id} value={template.id}>
                  {template.name} ({template.language})
                </option>
              ))}
          </select>
        )}
      </div>

      {templateId && (
        <TemplateVariableMapper
          template={templates.find((t) => t.id === templateId) || null}
          variableMapping={variableMapping}
          onChange={setVariableMapping}
          availableFields={availableFields}
        />
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

