import React, { useState, useEffect, useCallback, useMemo } from "react";
import { apiClient } from "../api";
import {
  CampaignResponse,
  CampaignCreate,
  CampaignUpdate,
  CampaignStats,
  CampaignSchedule,
  CampaignContactResponse,
  ContactImport,
  CampaignStatus,
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
  const [campaigns, setCampaigns] = useState<CampaignResponse[]>([]);
  const [selectedCampaign, setSelectedCampaign] =
    useState<CampaignResponse | null>(null);
  const [campaignStats, setCampaignStats] = useState<CampaignStats | null>(
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
  const [activeTab, setActiveTab] = useState<CampaignTabKey>("drafts");

  const statusFilter = useMemo(
    () => CAMPAIGN_TABS.find((tab) => tab.key === activeTab)?.status,
    [activeTab],
  );

  const sortCampaigns = useCallback((items: CampaignResponse[]) => {
    const getTimestamp = (campaign: CampaignResponse) => {
      const date = campaign.scheduled_at || campaign.created_at;
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

  useEffect(() => {
    if (selectedCampaign) {
      loadCampaignDetails(selectedCampaign.id);
    }
  }, [selectedCampaign]);

  useEffect(() => {
    if (
      selectedCampaign &&
      !campaigns.some((c) => c.id === selectedCampaign.id)
    ) {
      setSelectedCampaign(null);
      setCampaignStats(null);
      setCampaignContacts([]);
    }
  }, [campaigns, selectedCampaign]);

  // WebSocket event handlers for real-time campaign updates
  const handleCampaignUpdate = useCallback(
    (data: any) => {
      console.log("Campaign update received:", data);

      setCampaigns((prev) => {
        const updated = prev.map((campaign) =>
          campaign.id === data.campaign_id
            ? { ...campaign, status: data.status }
            : campaign,
        );

        const filtered = statusFilter
          ? updated.filter((campaign) => campaign.status === statusFilter)
          : updated;

        return sortCampaigns(filtered);
      });

      // Update selected campaign if it's the one that changed
      if (selectedCampaign?.id === data.campaign_id) {
        setSelectedCampaign((prev) =>
          prev ? { ...prev, status: data.status } : null,
        );
        // Reload stats for the selected campaign
        loadCampaignDetails(data.campaign_id);
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
            }
            : null,
        );
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

  const loadCampaignDetails = async (campaignId: string) => {
    try {
      const stats = await apiClient.getCampaignStats(campaignId);
      setCampaignStats(stats);

      // Load initial contacts
      setContactsPage(1);
      setLoadingContacts(true);
      const contacts = await apiClient.getCampaignContacts(campaignId, {
        limit: CONTACTS_PER_PAGE,
        offset: 0
      });
      setCampaignContacts(contacts);
    } catch (error) {
      console.error("Помилка завантаження деталей кампанії:", error);
    } finally {
      setLoadingContacts(false);
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
      if (selectedCampaign?.id === campaignId) {
        const updated = await apiClient.getCampaign(campaignId);
        setSelectedCampaign(updated);
      }
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
      if (selectedCampaign?.id === campaignId) {
        const updated = await apiClient.getCampaign(campaignId);
        setSelectedCampaign(updated);
      }
    } catch (error) {
      console.error("Помилка планування кампанії:", error);
      throw error;
    }
  };

  const handleStartCampaign = async (campaignId: string) => {
    try {
      await apiClient.startCampaign(campaignId);
      // Don't reload - WebSocket will handle updates
      // await loadCampaigns();
      // if (selectedCampaign?.id === campaignId) {
      //   const updated = await apiClient.getCampaign(campaignId);
      //   setSelectedCampaign(updated);
      // }
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
  ) => {
    try {
      await apiClient.addContactsManually(campaignId, contacts);
      await loadCampaignDetails(campaignId);
      await loadCampaigns();
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

  return (
    <div className="h-[calc(100vh-8rem)] flex gap-4">
      {/* Campaigns List */}
      <div className="w-1/3 border border-gray-200 rounded-lg bg-white overflow-hidden flex flex-col">
        <div className="p-4 border-b border-gray-200">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-semibold text-gray-800">Розсилки</h2>
            <button
              onClick={() => setShowCreateForm(true)}
              className="px-3 py-1 text-sm rounded-md bg-blue-600 text-white hover:bg-blue-700 transition-colors"
            >
              + Створити
            </button>
          </div>
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
            selectedCampaign={selectedCampaign}
            onSelectCampaign={setSelectedCampaign}
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
            showScheduleForm={showScheduleForm}
            onShowScheduleForm={setShowScheduleForm}
            currentPage={contactsPage}
            totalPages={Math.ceil((selectedCampaign?.total_contacts || 0) / CONTACTS_PER_PAGE)}
            onPageChange={handlePageChange}
            loadingContacts={loadingContacts}
          />
        ) : (
          <div className="flex-1 flex items-center justify-center text-gray-500">
            Оберіть кампанію для перегляду деталей
          </div>
        )}
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
