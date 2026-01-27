import React, { useState, useEffect, useCallback, useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Plus } from "lucide-react";
import { apiClient } from "../api";
import {
  CampaignResponse,
  CampaignListResponse,
  CampaignCreate,
  CampaignUpdate,
  CampaignStatsResponse,
  CampaignSchedule,
  CampaignContactResponse,
  ContactImport,
  CampaignStatus,
  ContactStatus,
  MessageType,
  CampaignStats,
} from "../types";
import CampaignList from "../components/campaigns/CampaignList";
import CampaignDetails from "../components/campaigns/CampaignDetails";
import CampaignForm from "../components/campaigns/CampaignForm";
import { useWSEvent } from "../services/useWebSocket";
import { EventType } from "../services/websocket";

type CampaignTabKey = "all" | "drafts" | "scheduled" | "completed";

const CAMPAIGN_TABS: {
  key: CampaignTabKey;
  label: string;
  status?: CampaignStatus;
}[] = [
    { key: "all", label: "Усі", status: undefined },
    { key: "drafts", label: "Чернетки", status: CampaignStatus.DRAFT },
    { key: "scheduled", label: "Заплановані", status: CampaignStatus.SCHEDULED },
    { key: "completed", label: "Завершені", status: CampaignStatus.COMPLETED },
  ];

const CampaignsPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [campaigns, setCampaigns] = useState<CampaignListResponse[]>([]);
  const [selectedCampaign, setSelectedCampaign] =
    useState<CampaignResponse | null>(null);
  const [campaignStats, setCampaignStats] = useState<CampaignStatsResponse | null>(
    null,
  );
  const [campaignContacts, setCampaignContacts] = useState<
    CampaignContactResponse[]
  >([]);
  const [loading, setLoading] = useState(true);
  const [loadingContacts, setLoadingContacts] = useState(false);
  const [contactsPage, setContactsPage] = useState(1);
  const CONTACTS_PER_PAGE = 50;
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [showScheduleForm, setShowScheduleForm] = useState(false);
  const [activeTab, setActiveTab] = useState<CampaignTabKey>("all");

  const statusFilter = useMemo(
    () => CAMPAIGN_TABS.find((tab) => tab.key === activeTab)?.status,
    [activeTab],
  );

  const sortCampaigns = useCallback((items: CampaignListResponse[]) => {
    const getTimestamp = (campaign: CampaignListResponse) => {
      const date = campaign.updated_at || campaign.created_at;
      return date ? new Date(date).getTime() : 0;
    };

    return [...items].sort((a, b) => getTimestamp(b) - getTimestamp(a));
  }, []);

  const loadCampaigns = useCallback(async () => {
    try {
      setLoading(true);
      const data = await apiClient.listCampaigns(statusFilter);
      setCampaigns(sortCampaigns(data));
    } catch (error) {
      console.error("Помилка завантаження кампаній:", error);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, sortCampaigns]);

  useEffect(() => {
    loadCampaigns();
  }, [loadCampaigns]);

  // WebSocket event handlers for real-time campaign updates
  const handleCampaignUpdate = useCallback(
    (data: any) => {
      console.log("Campaign update received:", data);

      setCampaigns((prev) => {
        const updated = prev.map((campaign) =>
          campaign.id === data.campaign_id
            ? {
              ...campaign,
              status: data.status,
              // Note: List view no longer has stats, so we only update status
            }
            : campaign,
        );

        const filtered = statusFilter
          ? updated.filter((campaign) => campaign.status === statusFilter)
          : updated;

        // Update selected campaign status if needed
        if (selectedCampaign?.id === data.campaign_id) {
          // We might want to reload full details here, but for now just optional state update if simple field
          // Ideally we re-fetch to be safe
        }

        return sortCampaigns(filtered);
      });

      // If selected campaign is updated, reload details
      if (selectedCampaign && selectedCampaign.id === data.campaign_id) {
        loadCampaignDetails(selectedCampaign.id);
      }
    },
    [selectedCampaign, sortCampaigns, statusFilter],
  );

  const handleTabChange = useCallback((tabKey: CampaignTabKey) => {
    setActiveTab(tabKey);
    setSelectedCampaign(null);
    setCampaignStats(null);
    setCampaignContacts([]);
  }, []);

  const handleCampaignProgress = useCallback(
    (data: any) => {
      console.log("Campaign progress received:", data);

      // Update campaign stats if this campaign is selected
      if (selectedCampaign?.id === data.campaign_id) {
        setCampaignStats((prev) =>
          prev
            ? {
              ...prev,
              sent_count: data.sent,
              delivered_count: data.delivered,
              failed_count: data.failed,
              progress_percent: data.progress_percent,
              total_contacts: prev.total_contacts, // Ensure we keep other fields
            }
            : null,
        );
      }
    },
    [selectedCampaign],
  );

  // Handle individual message status updates
  const handleMessageStatusUpdate = useCallback(
    (data: any) => {
      console.log("Message status update received:", data);

      // Update campaign stats if this is for the selected campaign
      if (selectedCampaign?.id === data.campaign_id) {
        // Reload campaign stats to get accurate counts
        apiClient.getCampaignStats(data.campaign_id).then((stats) => {
          setCampaignStats(stats);
        });

        // Update contact in the list if present
        if (data.contact_id) {
          setCampaignContacts((prev) =>
            prev.map((contact) =>
              contact.contact_id === data.contact_id
                ? {
                  ...contact,
                  // Map backend status to UI status if needed, or just use string
                  status: data.status,
                  retry_count: data.retry_count !== undefined ? data.retry_count : contact.retry_count,
                }
                : contact,
            ),
          );
        }
      }
    },
    [selectedCampaign],
  );

  // Subscribe to WebSocket events
  useWSEvent(EventType.CAMPAIGN_STARTED, handleCampaignUpdate);
  useWSEvent(EventType.CAMPAIGN_PAUSED, handleCampaignUpdate);
  useWSEvent(EventType.CAMPAIGN_RESUMED, handleCampaignUpdate);
  useWSEvent(EventType.CAMPAIGN_COMPLETED, handleCampaignUpdate);
  useWSEvent(EventType.CAMPAIGN_FAILED, handleCampaignUpdate);
  useWSEvent(EventType.CAMPAIGN_PROGRESS, handleCampaignProgress);
  useWSEvent(EventType.MESSAGE_SENT, handleMessageStatusUpdate);
  useWSEvent(EventType.MESSAGE_DELIVERED, handleMessageStatusUpdate);
  useWSEvent(EventType.MESSAGE_FAILED, handleMessageStatusUpdate);

  const loadCampaignDetails = useCallback(async (campaignId: string) => {
    try {
      // Parallel fetch
      const [fullCampaign, stats, contacts] = await Promise.all([
        apiClient.getCampaign(campaignId),
        apiClient.getCampaignStats(campaignId),
        apiClient.getCampaignContacts(campaignId, {
          limit: CONTACTS_PER_PAGE,
          offset: 0
        })
      ]);

      setSelectedCampaign(fullCampaign);
      setCampaignStats(stats);
      setCampaignContacts(contacts);
      setContactsPage(1);
    } catch (error) {
      console.error("Помилка завантаження деталей кампанії:", error);
      // Optional: navigate back if not found?
    }
  }, []);

  useEffect(() => {
    if (id) {
      loadCampaignDetails(id);
    } else {
      setSelectedCampaign(null);
      setCampaignStats(null);
      setCampaignContacts([]);
    }
  }, [id, loadCampaignDetails]);

  const handleSelectCampaign = (listCampaign: CampaignListResponse) => {
    if (id !== listCampaign.id) {
      navigate(`/campaigns/${listCampaign.id}`);
    }
  };

  const handlePageChange = async (newPage: number) => {
    if (!selectedCampaign || loadingContacts) return;

    try {
      setLoadingContacts(true);
      setContactsPage(newPage);
      const offset = (newPage - 1) * CONTACTS_PER_PAGE;

      const newContacts = await apiClient.getCampaignContacts(selectedCampaign.id, {
        limit: CONTACTS_PER_PAGE,
        offset: offset,
      });

      setCampaignContacts(newContacts);
    } catch (error) {
      console.error("Помилка завантаження сторінки контактів:", error);
    } finally {
      setLoadingContacts(false);
    }
  };

  const handleCreateCampaign = async (
    data: CampaignCreate | CampaignUpdate,
  ) => {
    try {
      await apiClient.createCampaign(data as CampaignCreate);
      setShowCreateForm(false);
      await loadCampaigns();
    } catch (error) {
      console.error("Помилка створення кампанії:", error);
      throw error;
    }
  };

  const handleUpdateCampaign = async (
    campaignId: string,
    data: CampaignUpdate,
  ) => {
    try {
      await apiClient.updateCampaign(campaignId, data);
      await loadCampaigns();
      // Reload details to get updated fields
      await loadCampaignDetails(campaignId);
    } catch (error) {
      console.error("Помилка оновлення кампанії:", error);
      throw error;
    }
  };

  const handleDeleteCampaign = async (campaignId: string) => {
    if (!window.confirm("Ви впевнені, що хочете видалити цю кампанію?")) {
      return;
    }
    try {
      await apiClient.deleteCampaign(campaignId);
      if (selectedCampaign?.id === campaignId) {
        setSelectedCampaign(null);
        setCampaignStats(null);
        setCampaignContacts([]);
      }
      await loadCampaigns();
    } catch (error) {
      console.error("Помилка видалення кампанії:", error);
    }
  };

  const handleScheduleCampaign = async (
    campaignId: string,
    data: CampaignSchedule,
  ) => {
    try {
      await apiClient.scheduleCampaign(campaignId, data);
      setShowScheduleForm(false);
      await loadCampaigns();
      await loadCampaignDetails(campaignId);
    } catch (error) {
      console.error("Помилка планування кампанії:", error);
      throw error;
    }
  };

  const handleStartCampaign = async (campaignId: string) => {
    try {
      await apiClient.startCampaign(campaignId);
      // Don't reload - WebSocket will handle updates
    } catch (error) {
      console.error("Помилка запуску кампанії:", error);
    }
  };

  const handlePauseCampaign = async (campaignId: string) => {
    try {
      await apiClient.pauseCampaign(campaignId);
      // Don't reload - WebSocket will handle updates
    } catch (error) {
      console.error("Помилка паузи кампанії:", error);
    }
  };

  const handleResumeCampaign = async (campaignId: string) => {
    try {
      await apiClient.resumeCampaign(campaignId);
      // Don't reload - WebSocket will handle updates
    } catch (error) {
      console.error("Помилка відновлення кампанії:", error);
    }
  };

  const handleAddContacts = async (
    campaignId: string,
    contacts: ContactImport[],
    forceAdd: boolean = false,
  ) => {
    try {
      await apiClient.addContactsManually(campaignId, contacts, forceAdd);
      await loadCampaignDetails(campaignId);
      await loadCampaigns(); // To update list if status changes (unlikely for add contacts but good to sync)
    } catch (error) {
      console.error("Помилка додавання контактів:", error);
      throw error;
    }
  };

  const handleImportContacts = async (campaignId: string, file: File) => {
    try {
      await apiClient.importContactsFromFile(campaignId, file);
      await loadCampaignDetails(campaignId);
      await loadCampaigns();
    } catch (error) {
      console.error("Помилка імпорту контактів:", error);
      throw error;
    }
  };

  const handleUpdateCampaignContact = async (
    campaignId: string,
    contactId: string,
    data: { name?: string | null; custom_data?: Record<string, any>; status?: string },
  ) => {
    try {
      await apiClient.updateCampaignContact(campaignId, contactId, data);
      await loadCampaignDetails(campaignId);
    } catch (error) {
      console.error("Помилка оновлення контакту кампанії:", error);
      throw error;
    }
  };

  const handleDeleteCampaignContact = async (
    campaignId: string,
    contactId: string,
  ) => {
    if (!window.confirm("Ви впевнені, що хочете видалити цей контакт з кампанії?")) {
      return;
    }
    try {
      await apiClient.deleteCampaignContact(campaignId, contactId);
      await loadCampaignDetails(campaignId);
      // List might not change
    } catch (error) {
      console.error("Помилка видалення контакту кампанії:", error);
      throw error;
    }
  };

  return (
    <div className="h-[calc(100vh-4rem)] flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-shrink-0">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Campaigns</h1>
          <p className="text-sm text-gray-500 mt-1">
            Manage and track your messaging campaigns
          </p>
        </div>
        <button
          onClick={() => setShowCreateForm(true)}
          className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors shadow-sm"
        >
          <Plus className="w-4 h-4" />
          Create Campaign
        </button>
      </div>

      <div className="flex-1 flex gap-4 overflow-hidden min-h-0">
        {/* Campaigns List */}
        <div className="w-1/3 border border-gray-200 rounded-lg bg-white overflow-hidden flex flex-col">
          <div className="p-4 border-b border-gray-200">
            <div className="flex gap-2 overflow-x-auto">
              {CAMPAIGN_TABS.map((tab) => {
                const isActive = tab.key === activeTab;
                return (
                  <button
                    key={tab.key}
                    onClick={() => handleTabChange(tab.key)}
                    className={`px-3 py-1 text-sm rounded-md transition-colors whitespace-nowrap ${isActive ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-700 hover:bg-gray-200"}`}
                  >
                    {tab.label}
                  </button>
                );
              })}
            </div>
          </div>

          {loading ? (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-gray-500">Завантаження...</div>
            </div>
          ) : campaigns.length === 0 ? (
            <div className="flex-1 flex items-center justify-center text-gray-500 p-4">
              Кампанії не знайдено
            </div>
          ) : (
            <CampaignList
              campaigns={campaigns}
              selectedCampaign={selectedCampaign as unknown as CampaignListResponse}
              onSelectCampaign={handleSelectCampaign}
              onDeleteCampaign={handleDeleteCampaign}
            />
          )}
        </div>

        {/* Campaign Details */}
        <div className="flex-1 border border-gray-200 rounded-lg bg-white overflow-hidden flex flex-col">
          {selectedCampaign ? (
            <CampaignDetails
              campaign={selectedCampaign}
              stats={campaignStats}
              contacts={campaignContacts}
              onUpdate={handleUpdateCampaign}
              onSchedule={handleScheduleCampaign}
              onStart={handleStartCampaign}
              onPause={handlePauseCampaign}
              onResume={handleResumeCampaign}
              onAddContacts={handleAddContacts}
              onImportContacts={handleImportContacts}
              onUpdateContact={handleUpdateCampaignContact}
              onDeleteContact={handleDeleteCampaignContact}
              showScheduleForm={showScheduleForm}
              onShowScheduleForm={setShowScheduleForm}
              currentPage={contactsPage}
              totalPages={Math.ceil((campaignStats?.total_contacts || 0) / CONTACTS_PER_PAGE)}
              onPageChange={handlePageChange}
              loadingContacts={loadingContacts}
            />
          ) : (
            <div className="flex-1 flex items-center justify-center text-gray-500">
              Оберіть кампанію для перегляду деталей
            </div>
          )}
        </div>

      </div>

      {/* Create Campaign Modal */}
      {showCreateForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <h3 className="text-xl font-bold mb-4">Створити кампанію</h3>
            <CampaignForm
              onSubmit={handleCreateCampaign}
              onCancel={() => setShowCreateForm(false)}
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default CampaignsPage;
