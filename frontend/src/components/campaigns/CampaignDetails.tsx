import React, { useState } from "react";
import {
  CampaignResponse,
  CampaignCreate,
  CampaignUpdate,
  CampaignStats,
  CampaignSchedule,
  CampaignContactResponse,
  ContactImport,
  CampaignStatus, // <--- Переконайтеся, що це тут є
  MessageType,
} from "../../types";
import CampaignForm from "./CampaignForm";
import ContactImportForm from "./ContactImportForm";

interface CampaignDetailsProps {
  campaign: CampaignResponse;
  stats: CampaignStats | null;
  contacts: CampaignContactResponse[];
  onUpdate: (campaignId: string, data: CampaignUpdate) => Promise<void>;
  onSchedule: (campaignId: string, data: CampaignSchedule) => Promise<void>;
  onStart: (campaignId: string) => Promise<void>;
  onPause: (campaignId: string) => Promise<void>;
  onResume: (campaignId: string) => Promise<void>;
  onAddContacts: (
    campaignId: string,
    contacts: ContactImport[],
  ) => Promise<void>;
  onImportContacts: (campaignId: string, file: File) => Promise<void>;
  showScheduleForm: boolean;
  onShowScheduleForm: (show: boolean) => void;
}

const CampaignDetails: React.FC<CampaignDetailsProps> = ({
  campaign,
  stats,
  contacts,
  onUpdate,
  onSchedule,
  onStart,
  onPause,
  onResume,
  onAddContacts,
  onImportContacts,
  showScheduleForm,
  onShowScheduleForm,
}) => {
  const [showEditForm, setShowEditForm] = useState(false);
  const [showAddContacts, setShowAddContacts] = useState(false);
  const [activeTab, setActiveTab] = useState<"overview" | "contacts">(
    "overview",
  );

  const canEdit = campaign.status === CampaignStatus.DRAFT;
  const canSchedule = campaign.status === CampaignStatus.DRAFT;
  const canStart =
    (campaign.status === CampaignStatus.DRAFT ||
      campaign.status === CampaignStatus.SCHEDULED) &&
    campaign.total_contacts > 0;
  const canPause = campaign.status === CampaignStatus.RUNNING;
  const canResume = campaign.status === CampaignStatus.PAUSED;

  const handleUpdate = async (data: CampaignCreate | CampaignUpdate) => {
    await onUpdate(campaign.id, data as CampaignUpdate);
    setShowEditForm(false);
  };

  const handleSchedule = async (data: CampaignSchedule) => {
    await onSchedule(campaign.id, data);
    onShowScheduleForm(false);
  };

  const progressPercent = stats?.progress_percent || 0;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-6 border-b border-gray-200">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">
              {campaign.name}
            </h2>
            <div className="flex items-center gap-4 text-sm text-gray-600">
              <span
                className={`px-3 py-1 rounded-full ${getStatusColor(campaign.status)}`}
              >
                {campaign.status}
              </span>
              <span>
                <span className="font-medium">Тип:</span>{" "}
                {campaign.message_type}
              </span>
            </div>
          </div>
          <div className="flex gap-2">
            {canEdit && (
              <button
                onClick={() => setShowEditForm(true)}
                className="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors text-sm"
              >
                Редагувати
              </button>
            )}
            {canSchedule && (
              <button
                onClick={() => onShowScheduleForm(true)}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm"
              >
                Запланувати
              </button>
            )}
            {canStart && (
              <button
                onClick={() => onStart(campaign.id)}
                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors text-sm"
              >
                Запустити
              </button>
            )}
            {canPause && (
              <button
                onClick={() => onPause(campaign.id)}
                className="px-4 py-2 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 transition-colors text-sm"
              >
                Пауза
              </button>
            )}
            {canResume && (
              <button
                onClick={() => onResume(campaign.id)}
                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors text-sm"
              >
                Відновити
              </button>
            )}
          </div>
        </div>

        {/* Progress Bar */}
        {stats && (
          <div className="mt-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-gray-700">Прогрес</span>
              <span className="text-sm text-gray-600">
                {progressPercent.toFixed(1)}%
              </span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-blue-600 h-2 rounded-full transition-all"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 px-6">
        <div className="flex gap-4">
          <button
            onClick={() => setActiveTab("overview")}
            className={`py-3 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === "overview"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-600 hover:text-gray-900"
            }`}
          >
            Огляд
          </button>
          <button
            onClick={() => setActiveTab("contacts")}
            className={`py-3 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === "contacts"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-600 hover:text-gray-900"
            }`}
          >
            Контакти ({contacts.length})
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {activeTab === "overview" ? (
          <div className="space-y-6">
            {/* Stats */}
            {stats && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-gray-50 rounded-lg p-4">
                  <div className="text-2xl font-bold text-gray-900">
                    {stats.total_contacts}
                  </div>
                  <div className="text-sm text-gray-600">Всього контактів</div>
                </div>
                <div className="bg-blue-50 rounded-lg p-4">
                  <div className="text-2xl font-bold text-blue-600">
                    {stats.sent_count}
                  </div>
                  <div className="text-sm text-gray-600">Відправлено</div>
                </div>
                <div className="bg-green-50 rounded-lg p-4">
                  <div className="text-2xl font-bold text-green-600">
                    {stats.delivered_count}
                  </div>
                  <div className="text-sm text-gray-600">Доставлено</div>
                </div>
                <div className="bg-red-50 rounded-lg p-4">
                  <div className="text-2xl font-bold text-red-600">
                    {stats.failed_count}
                  </div>
                  <div className="text-sm text-gray-600">Помилок</div>
                </div>
              </div>
            )}

            {/* Details */}
            <div className="bg-gray-50 rounded-lg p-4 space-y-3">
              <h3 className="font-semibold text-gray-800 mb-3">
                Деталі кампанії
              </h3>
              <div>
                <span className="font-medium text-gray-700">
                  Тип повідомлення:
                </span>
                <span className="ml-2 text-gray-900">
                  {campaign.message_type}
                </span>
              </div>
              {campaign.template_id && (
                <div>
                  <span className="font-medium text-gray-700">ID шаблону:</span>
                  <span className="ml-2 text-gray-900 font-mono text-sm">
                    {campaign.template_id}
                  </span>
                </div>
              )}
              {campaign.message_body && (
                <div>
                  <span className="font-medium text-gray-700">
                    Текст повідомлення:
                  </span>
                  <p className="mt-1 text-gray-900 bg-white p-3 rounded border">
                    {campaign.message_body}
                  </p>
                </div>
              )}
              {campaign.scheduled_at && (
                <div>
                  <span className="font-medium text-gray-700">
                    Заплановано:
                  </span>
                  <span className="ml-2 text-gray-900">
                    {new Date(campaign.scheduled_at).toLocaleString("uk-UA")}
                  </span>
                </div>
              )}
              {campaign.started_at && (
                <div>
                  <span className="font-medium text-gray-700">Запущено:</span>
                  <span className="ml-2 text-gray-900">
                    {new Date(campaign.started_at).toLocaleString("uk-UA")}
                  </span>
                </div>
              )}
              {campaign.completed_at && (
                <div>
                  <span className="font-medium text-gray-700">Завершено:</span>
                  <span className="ml-2 text-gray-900">
                    {new Date(campaign.completed_at).toLocaleString("uk-UA")}
                  </span>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <h3 className="text-lg font-semibold text-gray-800">
                Контакти кампанії
              </h3>
              {canEdit && (
                <button
                  onClick={() => setShowAddContacts(true)}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm"
                >
                  + Додати контакти
                </button>
              )}
            </div>

            {contacts.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                Немає контактів у кампанії
              </div>
            ) : (
              <div className="border border-gray-200 rounded-lg overflow-hidden">
                <table className="w-full">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">
                        Телефон
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">
                        Ім'я
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">
                        Статус
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">
                        Спроби
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {contacts.map((contact) => (
                      <tr key={contact.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 text-sm text-gray-900">
                          {contact.phone_number}
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-600">
                          {contact.name || "-"}
                        </td>
                        <td className="px-4 py-3 text-sm">
                          <span
                            className={`px-2 py-1 rounded-full text-xs ${getContactStatusColor(contact.status)}`}
                          >
                            {contact.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-600">
                          {contact.retry_count}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Edit Modal */}
      {showEditForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <h3 className="text-xl font-bold mb-4">Редагувати кампанію</h3>
            <CampaignForm
              initialData={{
                name: campaign.name,
                message_type: campaign.message_type as MessageType,
                template_id: campaign.template_id,
                message_body: campaign.message_body,
              }}
              onSubmit={handleUpdate}
              onCancel={() => setShowEditForm(false)}
              isEdit={true}
            />
          </div>
        </div>
      )}

      {/* Schedule Modal */}
      {showScheduleForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <h3 className="text-xl font-bold mb-4">Запланувати кампанію</h3>
            <ScheduleForm
              onSubmit={handleSchedule}
              onCancel={() => onShowScheduleForm(false)}
            />
          </div>
        </div>
      )}

      {/* Add Contacts Modal */}
      {showAddContacts && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-lg">
            <h3 className="text-xl font-bold mb-4">Додати контакти</h3>
            <ContactImportForm
              onAddContacts={(contacts) => onAddContacts(campaign.id, contacts)}
              onImportFile={(file) => onImportContacts(campaign.id, file)}
              onCancel={() => setShowAddContacts(false)}
            />
          </div>
        </div>
      )}
    </div>
  );
};

// Helper components outside
const getStatusColor = (status: CampaignStatus) => {
  const colors = {
    [CampaignStatus.DRAFT]: "bg-gray-100 text-gray-800",
    [CampaignStatus.SCHEDULED]: "bg-blue-100 text-blue-800",
    [CampaignStatus.RUNNING]: "bg-green-100 text-green-800",
    [CampaignStatus.PAUSED]: "bg-yellow-100 text-yellow-800",
    [CampaignStatus.COMPLETED]: "bg-purple-100 text-purple-800",
    [CampaignStatus.FAILED]: "bg-red-100 text-red-800",
  };
  return colors[status] || "bg-gray-100 text-gray-800";
};

const getContactStatusColor = (status: string) => {
  const statusLower = status.toLowerCase();
  if (statusLower === "sent") return "bg-blue-100 text-blue-800";
  if (statusLower === "delivered") return "bg-green-100 text-green-800";
  if (statusLower === "failed") return "bg-red-100 text-red-800";
  return "bg-gray-100 text-gray-800";
};

const ScheduleForm: React.FC<{
  onSubmit: (data: CampaignSchedule) => Promise<void>;
  onCancel: () => void;
}> = ({ onSubmit, onCancel }) => {
  const [scheduledAt, setScheduledAt] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (scheduledAt) {
      await onSubmit({ scheduled_at: new Date(scheduledAt).toISOString() });
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Дата та час запуску
        </label>
        <input
          type="datetime-local"
          value={scheduledAt}
          onChange={(e) => setScheduledAt(e.target.value)}
          required
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
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
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          Запланувати
        </button>
      </div>
    </form>
  );
};

export default CampaignDetails;
