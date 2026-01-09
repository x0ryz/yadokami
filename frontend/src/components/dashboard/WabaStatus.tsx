import React, { useState, useEffect } from "react";
import { apiClient } from "../../api";
import { WabaStatusResponse } from "../../types";
import { RefreshCw, Smartphone, ShieldCheck, AlertCircle } from "lucide-react";

const WabaStatus: React.FC = () => {
  const [status, setStatus] = useState<WabaStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [lastSyncTime, setLastSyncTime] = useState<Date | null>(null);

  useEffect(() => {
    loadStatus();
  }, []);

  const loadStatus = async () => {
    try {
      setLoading(true);
      const data = await apiClient.getWabaStatus();
      setStatus(data);
    } catch (error) {
      console.error("Failed to load WABA status:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleSync = async () => {
    try {
      setSyncing(true);
      await apiClient.triggerWabaSync();
      setTimeout(async () => {
        await loadStatus();
        setLastSyncTime(new Date());
        setSyncing(false);
      }, 3000);
    } catch (error) {
      console.error("Failed to trigger sync:", error);
      setSyncing(false);
    }
  };

  const getStatusBadge = (status: string | null) => {
    if (!status)
      return (
        <span className="px-2 py-1 rounded text-xs font-medium bg-gray-100 text-gray-800">
          Unknown
        </span>
      );

    const lower = status.toLowerCase();
    let colorClass = "bg-gray-100 text-gray-800";

    if (
      lower.includes("connected") ||
      lower.includes("verified") ||
      lower.includes("approved")
    ) {
      colorClass = "bg-green-100 text-green-800";
    } else if (lower.includes("pending")) {
      colorClass = "bg-yellow-100 text-yellow-800";
    } else if (lower.includes("rejected") || lower.includes("failed")) {
      colorClass = "bg-red-100 text-red-800";
    }

    return (
      <span
        className={`px-2 py-1 rounded text-xs font-medium ${colorClass} capitalize`}
      >
        {status.replace(/_/g, " ").toLowerCase()}
      </span>
    );
  };

  const getQualityBadge = (rating: string) => {
    const lower = rating.toLowerCase();
    let colorClass = "bg-gray-100 text-gray-800";

    if (lower === "green") colorClass = "bg-green-100 text-green-800";
    else if (lower === "yellow") colorClass = "bg-yellow-100 text-yellow-800";
    else if (lower === "red") colorClass = "bg-red-100 text-red-800";

    return (
      <span
        className={`px-2 py-1 rounded text-xs font-medium ${colorClass} capitalize`}
      >
        {rating}
      </span>
    );
  };

  if (loading) {
    return (
      <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200 flex justify-center py-8">
        <div className="text-gray-500 flex items-center">
          <RefreshCw className="w-4 h-4 animate-spin mr-2" />
          Loading WABA Status...
        </div>
      </div>
    );
  }

  if (!status) return null;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Header & Sync for the whole section (Visual Only) */}
      <div className="lg:col-span-2 flex items-center justify-between pb-2">
        <h2 className="text-lg font-semibold text-gray-900 flex items-center">
          <Smartphone className="h-5 w-5 mr-2 text-gray-500" />
          WhatsApp Business Integration
        </h2>
        <div className="flex items-center gap-3">
          {lastSyncTime && (
            <span className="text-xs text-gray-400 hidden sm:inline">
              Updated: {lastSyncTime.toLocaleTimeString()}
            </span>
          )}
          <button
            onClick={handleSync}
            disabled={syncing}
            className={`p-2 rounded-md transition-colors ${
              syncing
                ? "bg-gray-100 text-gray-400"
                : "bg-white text-gray-500 hover:text-indigo-600 hover:bg-indigo-50 border border-gray-200"
            }`}
            title="Sync WABA Data"
          >
            <RefreshCw className={`w-4 h-4 ${syncing ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* WABA Accounts Card */}
      <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
        <h3 className="text-base font-medium text-gray-900 mb-4 flex items-center">
          <ShieldCheck className="h-4 w-4 mr-2 text-indigo-500" />
          WABA Accounts
        </h3>
        {status.accounts.length === 0 ? (
          <div className="text-center text-gray-400 text-sm py-4">
            No accounts found
          </div>
        ) : (
          <div className="space-y-4">
            {status.accounts.map((account) => (
              <div
                key={account.id}
                className="pb-4 border-b border-gray-100 last:border-0 last:pb-0"
              >
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <div className="font-medium text-gray-900 text-sm">
                      {account.name}
                    </div>
                    <div className="text-xs text-gray-500 font-mono mt-0.5">
                      ID: {account.waba_id}
                    </div>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="flex flex-col">
                    <span className="text-gray-500 mb-1">Review Status</span>
                    <div>{getStatusBadge(account.account_review_status)}</div>
                  </div>
                  <div className="flex flex-col">
                    <span className="text-gray-500 mb-1">Business Verify</span>
                    <div>
                      {getStatusBadge(account.business_verification_status)}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Phone Numbers Card */}
      <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
        <h3 className="text-base font-medium text-gray-900 mb-4 flex items-center">
          <Smartphone className="h-4 w-4 mr-2 text-green-500" />
          Phone Numbers
        </h3>
        {status.phone_numbers.length === 0 ? (
          <div className="text-center text-gray-400 text-sm py-4">
            No phone numbers found
          </div>
        ) : (
          <div className="space-y-4">
            {status.phone_numbers.map((phone) => (
              <div
                key={phone.id}
                className="pb-4 border-b border-gray-100 last:border-0 last:pb-0"
              >
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <div className="font-medium text-gray-900 text-sm">
                      {phone.display_phone_number}
                    </div>
                    <div className="text-xs text-gray-500 font-mono mt-0.5">
                      ID: {phone.phone_number_id}
                    </div>
                  </div>
                  {getStatusBadge(phone.status)}
                </div>

                <div className="grid grid-cols-3 gap-2 text-xs mt-3">
                  <div className="flex flex-col">
                    <span className="text-gray-500 mb-1">Quality</span>
                    <div>{getQualityBadge(phone.quality_rating)}</div>
                  </div>
                  <div className="flex flex-col">
                    <span className="text-gray-500 mb-1">Limit</span>
                    <span className="font-medium text-gray-700">
                      {phone.messaging_limit_tier || "-"}
                    </span>
                  </div>
                  <div className="flex flex-col text-right">
                    <span className="text-gray-500 mb-1">Updated</span>
                    <span className="text-gray-700">
                      {phone.updated_at
                        ? new Date(phone.updated_at).toLocaleDateString()
                        : "-"}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default WabaStatus;
