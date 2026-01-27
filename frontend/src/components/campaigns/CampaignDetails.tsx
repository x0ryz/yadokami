import React, { useState } from "react";
import {
  CampaignResponse,
  CampaignCreate,
  CampaignUpdate,
  CampaignStats,
  CampaignSchedule,
  CampaignContactResponse,
  ContactImport,
  CampaignStatus,
  MessageType,
} from "../../types";
import CampaignForm from "./CampaignForm";
import ContactImportForm from "./ContactImportForm";
import MessagePreview from "./MessagePreview";
import apiClient from "../../api/client";

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
    forceAdd?: boolean,
  ) => Promise<void>;
  onImportContacts: (campaignId: string, file: File) => Promise<void>;
  onUpdateContact: (
    campaignId: string,
    contactId: string,
    data: { name?: string | null; custom_data?: Record<string, any>; status?: string },
  ) => Promise<void>;
  onDeleteContact: (campaignId: string, contactId: string) => Promise<void>;
  showScheduleForm: boolean;
  onShowScheduleForm: (show: boolean) => void;
  currentPage?: number;
  totalPages?: number;
  onPageChange?: (page: number) => void;
  loadingContacts?: boolean;
}

// КОНФІГУРАЦІЯ СТИЛІВ ДЛЯ СТАТИСТИКИ
// Використовуємо насичені кольори (500) для графіки, щоб було яскраво
const STATUS_STYLES = {
  replied: {
    bg: "bg-orange-500",     // Яскравий помаранчевий
    text: "text-orange-700", // Темний текст для контрасту
    label: "Відповіли",
  },
  read: {
    bg: "bg-purple-500",     // Яскравий фіолетовий
    text: "text-purple-700",
    label: "Прочитано",
  },
  delivered: {
    bg: "bg-green-500",      // Яскравий зелений
    text: "text-green-700",
    label: "Доставлено",
  },
  sent: {
    bg: "bg-blue-500",       // Яскравий синій
    text: "text-blue-700",
    label: "Відправлено",
  },
  failed: {
    bg: "bg-red-500",        // Яскравий червоний
    text: "text-red-700",
    label: "Помилка",
  },
};

const CampaignStatsBar: React.FC<{ stats: CampaignStats }> = ({ stats }) => {
  const {
    total_contacts,
    sent_count = 0,
    delivered_count = 0,
    read_count = 0,
    replied_count = 0,
    failed_count = 0,
  } = stats;

  if (total_contacts === 0) return null;

  // subtract replied from read/delivered/sent in the visual bar? 
  // The user asked "track replied, and then subtract replied from viewed count".
  // Let's implement that subtraction logic for the VISUAL segments, 
  // but keep the raw data in the tooltip/legend.

  // If we just stack them:
  // Replied is subset of Read. Read is subset of Delivered. Delivered is subset of Sent.
  // We want to show distinct segments.
  // Replied (orange)
  // Read (purple) - minus Replied
  // Delivered (green) - minus Read (which includes Replied)
  // Sent (blue) - minus Delivered (which includes Read)

  // However, the backend counts provided in `stats` are usually cumulative (Total Sent, Total Delivered, Total Read).
  // Assuming the backend returns cumulative counts:
  const sent = sent_count;
  const delivered = delivered_count;
  const read = read_count;
  const replied = replied_count;
  const failed = failed_count;

  // Visual segments (exclusive)
  const visualReplied = replied;
  const visualRead = Math.max(0, read - replied);
  const visualDelivered = Math.max(0, delivered - read);
  const visualSent = Math.max(0, sent - delivered - failed);
  // * Note: Failed is usually separate from Delivered. 

  const segments = [
    {
      key: "replied",
      value: visualReplied,
      totalValue: replied, // for display text
      ...STATUS_STYLES.replied,
    },
    {
      key: "read",
      value: visualRead,
      totalValue: read,
      ...STATUS_STYLES.read,
    },
    {
      key: "delivered",
      value: visualDelivered,
      totalValue: delivered,
      ...STATUS_STYLES.delivered,
    },
    {
      key: "sent",
      value: visualSent,
      totalValue: sent,
      ...STATUS_STYLES.sent,
    },
    {
      key: "failed",
      value: failed,
      totalValue: failed,
      ...STATUS_STYLES.failed,
    },
  ];

  const sumStats = segments.reduce((acc, curr) => acc + curr.value, 0);
  const pending = Math.max(0, total_contacts - sumStats);

  const getPercent = (val: number) => {
    if (total_contacts === 0) return 0;
    return (val / total_contacts) * 100;
  };

  const activeSegments = segments.filter((s) => s.value > 0);

  return (
    <div className="w-full mt-6 pt-6 border-t border-gray-100">
      {/* 1. Progress Bar */}
      <div className="h-2 w-full bg-gray-100 rounded-full overflow-hidden flex mb-3 border border-gray-100">
        {segments.map((seg) => {
          if (seg.value <= 0) return null;
          return (
            <div
              key={seg.key}
              className={`h-full flex-none transition-all duration-500 ${seg.bg}`}
              style={{
                width: `${getPercent(seg.value)}%`,
              }}
            />
          );
        })}
      </div>

      {/* 2. Legend Row with Split Layout */}
      <div className="flex flex-wrap items-center justify-between gap-y-2 text-sm">

        {/* Left Side: Specific Stats */}
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
          {activeSegments.map((seg) => (
            <div key={seg.key} className="flex items-center gap-2">
              {/* Яскрава крапка */}
              <span className={`w-3 h-3 rounded-full ${seg.bg}`} />

              <span className="text-gray-600">{seg.label}:</span>

              {/* Кольоровий текст цифр */}
              <span className={`font-bold ${seg.text}`}>
                {seg.totalValue}{" "}
                <span className="text-xs font-normal text-gray-400">
                  ({getPercent(seg.totalValue).toFixed(0)}%)
                </span>
              </span>
            </div>
          ))}

          {/* Pending Status (Neutral) */}
          {pending > 0 && (
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-gray-300" />
              <span className="text-gray-500">В черзі:</span>
              <span className="font-bold text-gray-600">{pending}</span>
            </div>
          )}
        </div>

        {/* Right Side: Total with Vertical Separator */}
        <div className="flex items-center gap-2 pl-6 border-l border-gray-200 ml-auto">
          <span className="font-medium text-gray-500">Всього:</span>
          <span className="font-bold text-gray-900">{total_contacts}</span>
        </div>

      </div>
    </div>
  );
};

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
  onUpdateContact,
  onDeleteContact,
  showScheduleForm,
  onShowScheduleForm,
  currentPage = 1,
  totalPages = 1,
  onPageChange,
  loadingContacts = false,
}) => {
  const [showEditForm, setShowEditForm] = useState(false);
  const [showAddContacts, setShowAddContacts] = useState(false);
  const [editingContact, setEditingContact] = useState<CampaignContactResponse | null>(null);
  const [expandedContactId, setExpandedContactId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"overview" | "contacts">(
    "overview",
  );

  // ... inside component ...
  const messageType = campaign.template_id ? "template" : "text"; // Inferred
  const totalContacts = stats?.total_contacts || 0;

  const canEdit = campaign.status === CampaignStatus.DRAFT;
  const canSchedule = campaign.status === CampaignStatus.DRAFT;
  const canStart =
    (campaign.status === CampaignStatus.DRAFT ||
      campaign.status === CampaignStatus.SCHEDULED) &&
    totalContacts > 0;
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

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-6 border-b border-gray-200">
        <div className="flex items-start justify-between">
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
                {messageType === "template" ? "Шаблон" : "Текст"}
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

        {/* Stats Section inserted here */}
        {stats && <CampaignStatsBar stats={stats} />}
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 px-6">
        <div className="flex gap-4">
          <button
            onClick={() => setActiveTab("overview")}
            className={`py-3 px-1 border-b-2 font-medium text-sm transition-colors ${activeTab === "overview"
              ? "border-blue-600 text-blue-600"
              : "border-transparent text-gray-600 hover:text-gray-900"
              }`}
          >
            Огляд
          </button>
          <button
            onClick={() => setActiveTab("contacts")}
            className={`py-3 px-1 border-b-2 font-medium text-sm transition-colors ${activeTab === "contacts"
              ? "border-blue-600 text-blue-600"
              : "border-transparent text-gray-600 hover:text-gray-900"
              }`}
          >
            Контакти ({totalContacts})
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {activeTab === "overview" ? (
          <div className="space-y-6">
            {/* Message Preview Section */}
            <MessagePreview
              messageType={messageType}
              templateId={campaign.template_id}
              messageBody={null}
            />

            <div className="bg-gray-50 rounded-lg p-4 space-y-3">
              <h3 className="font-semibold text-gray-800 mb-3">
                Деталі налаштувань
              </h3>
              <div>
                <span className="font-medium text-gray-700">
                  Тип повідомлення:
                </span>
                <span className="ml-2 text-gray-900">
                  {messageType === "template" ? "Шаблон" : "Текст"}
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
              {/* Message Body is no longer available directly on campaign */}
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
                      {canEdit && (
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">
                          Дії
                        </th>
                      )}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {contacts.map((contact) => {
                      const isExpanded = expandedContactId === contact.id;
                      const hasCustomData = contact.custom_data && Object.keys(contact.custom_data).length > 0;
                      const hasError = contact.error_message;
                      const hasExpandableContent = hasCustomData || hasError;

                      return (
                        <React.Fragment key={contact.id}>
                          <tr
                            className={`hover:bg-gray-50 ${hasExpandableContent ? 'cursor-pointer' : ''}`}
                            onClick={() => hasExpandableContent && setExpandedContactId(isExpanded ? null : contact.id)}
                          >
                            <td className="px-4 py-3 text-sm text-gray-900">
                              {contact.phone_number}
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-600">
                              {contact.name || "-"}
                            </td>
                            <td className="px-4 py-3 text-sm">
                              <div className="flex items-center gap-2">
                                <span
                                  className={`px-2 py-1 rounded-full text-xs ${getContactStatusColor(contact.status)}`}
                                >
                                  {contact.status}
                                </span>
                                {hasError && (
                                  <span
                                    className="text-red-500 text-xs cursor-help"
                                    title="Натисніть, щоб побачити деталі помилки"
                                  >
                                    ⚠️
                                  </span>
                                )}
                              </div>
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-600">
                              {contact.retry_count}
                            </td>
                            {canEdit && (
                              <td className="px-4 py-3 text-sm" onClick={(e) => e.stopPropagation()}>
                                <div className="flex gap-2">
                                  <button
                                    onClick={() => setEditingContact(contact)}
                                    className="text-blue-600 hover:text-blue-800 text-xs"
                                  >
                                    Редагувати
                                  </button>
                                  <button
                                    onClick={() => onDeleteContact(campaign.id, contact.id)}
                                    className="text-red-600 hover:text-red-800 text-xs"
                                  >
                                    Видалити
                                  </button>
                                </div>
                              </td>
                            )}
                          </tr>
                          {isExpanded && hasExpandableContent && (
                            <tr className="bg-gray-50">
                              <td colSpan={canEdit ? 5 : 4} className="px-4 py-3">
                                <div className="bg-white rounded-lg p-4 border border-gray-200">
                                  {/* Error Message */}
                                  {hasError && (
                                    <div className={hasCustomData ? "mb-4" : ""}>
                                      <h4 className="text-sm font-semibold text-red-700 mb-2">Помилка відправки:</h4>
                                      <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                                        <p className="text-sm text-red-800">{contact.error_message}</p>
                                        {contact.error_code && (
                                          <p className="text-xs text-red-600 mt-1">Код помилки: {contact.error_code}</p>
                                        )}
                                      </div>
                                    </div>
                                  )}

                                  {/* Custom Data */}
                                  {hasCustomData && (
                                    <div>
                                      <h4 className="text-sm font-semibold text-gray-700 mb-2">Додаткові дані:</h4>
                                      <div className="grid grid-cols-2 gap-3">
                                        {Object.entries(contact.custom_data).map(([key, value]) => (
                                          <div key={key} className="flex flex-col">
                                            <span className="text-xs font-medium text-gray-500 uppercase">{key}</span>
                                            <span className="text-sm text-gray-900 mt-1">{String(value)}</span>
                                          </div>
                                        ))}
                                      </div>
                                    </div>
                                  )}
                                </div>
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {/* Pagination Controls */}
            {totalPages > 1 && (
              <div className="flex justify-center items-center gap-2 mt-4">
                <button
                  onClick={() => onPageChange?.(currentPage - 1)}
                  disabled={currentPage === 1 || loadingContacts}
                  className="px-3 py-1 text-sm border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Назад
                </button>

                {Array.from({ length: totalPages }, (_, i) => i + 1)
                  .filter(page =>
                    page === 1 ||
                    page === totalPages ||
                    (page >= currentPage - 1 && page <= currentPage + 1)
                  )
                  .map((page, index, array) => (
                    <React.Fragment key={page}>
                      {index > 0 && array[index - 1] !== page - 1 && (
                        <span className="text-gray-400">...</span>
                      )}
                      <button
                        onClick={() => onPageChange?.(page)}
                        disabled={loadingContacts}
                        className={`px-3 py-1 text-sm rounded ${currentPage === page
                          ? "bg-blue-600 text-white"
                          : "border border-gray-300 hover:bg-gray-50"
                          }`}
                      >
                        {page}
                      </button>
                    </React.Fragment>
                  ))}

                <button
                  onClick={() => onPageChange?.(currentPage + 1)}
                  disabled={currentPage === totalPages || loadingContacts}
                  className="px-3 py-1 text-sm border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Далі
                </button>
              </div>
            )}

            {/* Loading indicator overlay or small text */}
            {loadingContacts && (
              <div className="text-center text-xs text-gray-500 mt-2">
                Завантаження...
              </div>
            )}

          </div>
        )}
      </div>

      {/* Modals */}
      {showEditForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <h3 className="text-xl font-bold mb-4">Редагувати кампанію</h3>
            <CampaignForm
              initialData={{
                name: campaign.name,
                template_id: campaign.template_id,
              }}
              onSubmit={handleUpdate}
              onCancel={() => setShowEditForm(false)}
              isEdit={true}
            />
          </div>
        </div>
      )}

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

      {showAddContacts && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-lg">
            <h3 className="text-xl font-bold mb-4">Додати контакти</h3>
            <ContactImportForm
              campaignId={campaign.id}
              onAddContacts={async (contacts, forceAdd) => {
                await onAddContacts(campaign.id, contacts, forceAdd);
                setShowAddContacts(false);
              }}
              onCheckDuplicates={async (contacts) => {
                return await apiClient.checkDuplicateContacts(campaign.id, contacts);
              }}
              onImportFile={async (file) => {
                await onImportContacts(campaign.id, file);
                setShowAddContacts(false);
              }}
              onCancel={() => setShowAddContacts(false)}
            />
          </div>
        </div>
      )}

      {editingContact && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <h3 className="text-xl font-bold mb-4">Редагувати контакт</h3>
            <ContactEditForm
              contact={editingContact}
              onSubmit={async (data) => {
                await onUpdateContact(campaign.id, editingContact.id, data);
                setEditingContact(null);
              }}
              onCancel={() => setEditingContact(null)}
            />
          </div>
        </div>
      )}
    </div>
  );
};

// Helper functions
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

// Для ТАБЛИЦІ залишаємо пастельні кольори (фон + темний текст), бо так читабельніше
const getContactStatusColor = (status: string) => {
  const statusLower = status.toLowerCase();
  if (statusLower === "sent") return "bg-blue-100 text-blue-800";
  if (statusLower === "delivered") return "bg-green-100 text-green-800";
  if (statusLower === "read") return "bg-purple-100 text-purple-800";
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

const ContactEditForm: React.FC<{
  contact: CampaignContactResponse;
  onSubmit: (data: { name?: string | null; custom_data?: Record<string, any> }) => Promise<void>;
  onCancel: () => void;
}> = ({ contact, onSubmit, onCancel }) => {
  const [name, setName] = useState(contact.name || "");
  const [customDataJson, setCustomDataJson] = useState(
    JSON.stringify(contact.custom_data || {}, null, 2)
  );
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    try {
      const parsedData = JSON.parse(customDataJson);
      await onSubmit({
        name: name.trim() || null,
        custom_data: parsedData
      });
    } catch (err) {
      setError("Невірний JSON формат");
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Телефон
        </label>
        <input
          type="text"
          value={contact.phone_number}
          disabled
          className="w-full px-4 py-2 border border-gray-300 rounded-lg bg-gray-50 text-gray-500"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Ім'я
        </label>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Введіть ім'я контакту"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Додаткові дані (JSON)
        </label>
        <textarea
          value={customDataJson}
          onChange={(e) => setCustomDataJson(e.target.value)}
          rows={8}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
          placeholder='{"key": "value"}'
        />
        {error && <p className="mt-1 text-sm text-red-600">{error}</p>}
        <p className="mt-1 text-xs text-gray-500">
          Введіть дані у форматі JSON. Приклад: {`{"firstName": "Іван", "city": "Київ"}`}
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
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          Зберегти
        </button>
      </div>
    </form>
  );
};

export default CampaignDetails;