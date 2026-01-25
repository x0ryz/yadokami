import React, { useEffect, useState } from "react";
import apiClient from "../api/client";
import { DashboardStats, MessagesTimeline, WabaStatusResponse } from "../types";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import {
  Users,
  MessageSquare,
  TrendingUp,
  Smartphone,
  RefreshCw,
} from "lucide-react";
import SystemHealthWidget from "../components/widgets/SystemHealthWidget";

const DashboardPage: React.FC = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [timeline, setTimeline] = useState<MessagesTimeline | null>(null);
  const [wabaStatus, setWabaStatus] = useState<WabaStatusResponse | null>(null);

  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Функція для завантаження всіх даних
  const fetchDashboardData = async () => {
    try {
      if (!wabaStatus) setLoading(true);

      const [statsData, timelineData, wabaData] = await Promise.all([
        apiClient.getDashboardStats(),
        apiClient.getMessagesTimeline(7),
        apiClient.getWabaStatus(),
      ]);

      setStats(statsData);
      setTimeline(timelineData);
      setWabaStatus(wabaData);
    } catch (err) {
      console.error("Failed to fetch dashboard data:", err);
      setError("Failed to load dashboard data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, []);

  // Обробник синхронізації WABA
  const handleSync = async () => {
    try {
      setSyncing(true);
      await apiClient.triggerWabaSync();
      setTimeout(async () => {
        await apiClient.getWabaStatus().then(setWabaStatus);
        setSyncing(false);
      }, 3000);
    } catch (error) {
      console.error("Failed to trigger sync:", error);
      setSyncing(false);
    }
  };

  const getStatusColor = (status: string | null) => {
    if (!status) return "bg-gray-100 text-gray-800";
    const lower = status.toLowerCase();
    if (
      lower.includes("connected") ||
      lower.includes("verified") ||
      lower.includes("approved")
    ) {
      return "bg-green-100 text-green-800";
    }
    if (lower.includes("pending")) return "bg-yellow-100 text-yellow-800";
    if (lower.includes("rejected") || lower.includes("failed")) {
      return "bg-red-100 text-red-800";
    }
    return "bg-gray-100 text-gray-800";
  };

  const getQualityColor = (rating: string) => {
    const lower = rating.toLowerCase();
    if (lower === "green") return "bg-green-100 text-green-800";
    if (lower === "yellow") return "bg-yellow-100 text-yellow-800";
    if (lower === "red") return "bg-red-100 text-red-800";
    return "bg-gray-100 text-gray-800";
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-8rem)]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  if (error || !stats) {
    return <div className="text-red-500 p-4">{error}</div>;
  }

  const mainAccount = wabaStatus?.accounts[0];

  return (
    <div className="space-y-6">
      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Contacts Card */}
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-gray-500 text-sm font-medium">Contacts</h3>
            <Users className="h-5 w-5 text-indigo-500" />
          </div>
          <div className="text-3xl font-bold text-gray-900">
            {stats.contacts.total}
          </div>
          <div className="mt-2 text-sm text-gray-600">
            <span className="text-orange-500 font-medium">
              {stats.contacts.unread}
            </span>{" "}
            unread chats
          </div>
        </div>

        {/* Messages Card */}
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-gray-500 text-sm font-medium">
              Messages (24h)
            </h3>
            <MessageSquare className="h-5 w-5 text-green-500" />
          </div>
          <div className="text-3xl font-bold text-gray-900">
            {stats.messages.last_24h}
          </div>
          <div className="mt-2 text-sm text-gray-600 flex justify-between">
            <span>Deliv. Rate: {stats.messages.delivery_rate}%</span>
            <span>Total: {stats.messages.total}</span>
          </div>
        </div>

        {/* WABA Account Card */}
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-gray-500 text-sm font-medium">WABA Account</h3>
            {/* Кнопка синхронізації замість іконки Shield */}
            <button
              onClick={handleSync}
              disabled={syncing}
              title="Оновити статус WABA"
              className={`p-1.5 rounded-md transition-all duration-200 ${syncing
                ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                : "text-indigo-600 hover:bg-indigo-50 hover:text-indigo-800 active:scale-95"
                }`}
            >
              <RefreshCw
                className={`w-5 h-5 ${syncing ? "animate-spin" : ""}`}
              />
            </button>
          </div>

          {mainAccount ? (
            <>
              <div
                className="text-lg font-bold text-gray-900 truncate"
                title={mainAccount.name}
              >
                {mainAccount.name}
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <span
                  className={`px-2 py-1 rounded text-xs font-medium ${getStatusColor(mainAccount.account_review_status)}`}
                >
                  {mainAccount.account_review_status || "Review: N/A"}
                </span>
                <span
                  className={`px-2 py-1 rounded text-xs font-medium ${getStatusColor(mainAccount.business_verification_status)}`}
                >
                  {mainAccount.business_verification_status || "Verify: N/A"}
                </span>
              </div>
            </>
          ) : (
            <div className="text-sm text-gray-500 py-2">
              No account connected
            </div>
          )}
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Chart Section */}
        <div className="lg:col-span-2 bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
            <TrendingUp className="h-5 w-5 mr-2 text-gray-500" />
            Message Traffic (Last 7 Days)
          </h2>
          <div className="h-80 w-full">
            {timeline && (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={timeline}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis
                    dataKey="date"
                    tickFormatter={(val) =>
                      new Date(val).toLocaleDateString(undefined, {
                        weekday: "short",
                      })
                    }
                  />
                  <YAxis />
                  <Tooltip
                    labelFormatter={(val) => new Date(val).toLocaleDateString()}
                  />
                  <Legend />
                  <Bar
                    dataKey="sent"
                    name="Sent"
                    fill="#4f46e5"
                    radius={[4, 4, 0, 0]}
                  />
                  <Bar
                    dataKey="received"
                    name="Received"
                    fill="#10b981"
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Right Column */}
        <div className="space-y-6">
          {/* Phone Numbers Section */}
          <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200 flex flex-col h-full">
            <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center justify-between">
              <div className="flex items-center">
                <Smartphone className="h-5 w-5 mr-2 text-gray-500" />
                Phone Numbers
              </div>
              {wabaStatus?.phone_numbers && (
                <span className="text-xs font-normal text-gray-400 bg-gray-100 px-2 py-1 rounded-full">
                  {wabaStatus.phone_numbers.length}
                </span>
              )}
            </h2>

            <div className="flex-1 overflow-y-auto pr-1 space-y-4 custom-scrollbar">
              {wabaStatus?.phone_numbers &&
                wabaStatus.phone_numbers.length > 0 ? (
                <ul className="space-y-3">
                  {wabaStatus.phone_numbers.map((phone) => (
                    <li
                      key={phone.id}
                      className="p-3 bg-gray-50 rounded-lg border border-gray-100 hover:border-indigo-100 transition-colors"
                    >
                      <div className="flex justify-between items-start mb-2">
                        <div className="font-semibold text-gray-900">
                          {phone.display_phone_number}
                        </div>
                        <span
                          className={`px-1.5 py-0.5 rounded text-[10px] uppercase font-bold ${getStatusColor(phone.status)}`}
                        >
                          {phone.status || "UNK"}
                        </span>
                      </div>

                      <div className="grid grid-cols-2 gap-2 text-xs text-gray-500">
                        <div>
                          <span className="block text-[10px] uppercase tracking-wider text-gray-400">
                            Quality
                          </span>
                          <span
                            className={`inline-block mt-0.5 px-1.5 py-0.5 rounded font-medium ${getQualityColor(phone.quality_rating)}`}
                          >
                            {phone.quality_rating}
                          </span>
                        </div>
                        <div className="text-right">
                          <span className="block text-[10px] uppercase tracking-wider text-gray-400">
                            Limit
                          </span>
                          <span className="font-medium text-gray-700 mt-0.5 block">
                            {phone.messaging_limit_tier?.replace("_", " ") ||
                              "N/A"}
                          </span>
                        </div>
                      </div>

                      {phone.updated_at && (
                        <div className="mt-2 pt-2 border-t border-gray-200 text-[10px] text-gray-400 text-right">
                          Upd: {new Date(phone.updated_at).toLocaleDateString()}
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="text-center text-gray-500 py-8">
                  No phone numbers found
                </div>
              )}
            </div>
          </div>

          {/* System Health Section */}
          <SystemHealthWidget />
        </div>
      </div>
    </div>
  );
};

export default DashboardPage;
