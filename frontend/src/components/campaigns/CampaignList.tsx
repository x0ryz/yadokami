import React from "react";
import { CampaignListResponse, CampaignStatus } from "../../types";

interface CampaignListProps {
  campaigns: CampaignListResponse[];
  selectedCampaign: CampaignListResponse | null;
  onSelectCampaign: (campaign: CampaignListResponse) => void;
  onDeleteCampaign: (campaignId: string) => void;
}

const CampaignList: React.FC<CampaignListProps> = ({
  campaigns,
  selectedCampaign,
  onSelectCampaign,
  onDeleteCampaign,
}) => {
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

  const formatDate = (dateString: string | null) => {
    if (!dateString) return "";
    return new Date(dateString).toLocaleDateString("uk-UA");
  };

  return (
    <div className="flex-1 overflow-y-auto">
      {campaigns.map((campaign) => (
        <div
          key={campaign.id}
          onClick={() => onSelectCampaign(campaign)}
          className={`p-4 border-b border-gray-100 cursor-pointer hover:bg-gray-50 transition-colors ${selectedCampaign?.id === campaign.id
            ? "bg-blue-50 border-blue-200"
            : ""
            }`}
        >
          <div className="flex items-start justify-between mb-2">
            <h3 className="font-semibold text-gray-900 flex-1">
              {campaign.name}
            </h3>
            <span
              className={`text-xs px-2 py-1 rounded-full ml-2 ${getStatusColor(campaign.status)}`}
            >
              {campaign.status}
            </span>
          </div>
          <div className="text-sm text-gray-600 space-y-1">
            <div className="flex items-center gap-4">
              {/* Type display removed as per request */}
            </div>
            {campaign.scheduled_at && (
              <p className="text-xs text-gray-500">
                Заплановано: {formatDate(campaign.scheduled_at)}
              </p>
            )}
          </div>
          {campaign.status === CampaignStatus.DRAFT && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onDeleteCampaign(campaign.id);
              }}
              className="mt-2 text-xs text-red-600 hover:text-red-800"
            >
              Видалити
            </button>
          )}
        </div>
      ))}
    </div>
  );
};

export default CampaignList;
