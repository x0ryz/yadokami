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

  const handleSync = async () => {
    try {
      setSyncing(true);
      await apiClient.triggerWabaSync();
      // Wait a bit for backend to process, then refresh
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
    if (!status) return "bg-gray-100 text-gray-600";
    const lower = status.toLowerCase();
    if (lower.includes("connected") || lower.includes("verified") || lower.includes("approved")) return "bg-green-100 text-green-700 border-green-200";
    if (lower.includes("pending")) return "bg-yellow-100 text-yellow-700 border-yellow-200";
    if (lower.includes("rejected") || lower.includes("failed")) return "bg-red-100 text-red-700 border-red-200";
    return "bg-gray-100 text-gray-600 border-gray-200";
  };

  const getQualityColor = (rating: string) => {
    const lower = rating.toLowerCase();
    if (lower === "green") return "text-green-600 bg-green-50 border-green-100";
    if (lower === "yellow") return "text-yellow-600 bg-yellow-50 border-yellow-100";
    if (lower === "red") return "text-red-600 bg-red-50 border-red-100";
    return "text-gray-600 bg-gray-50 border-gray-100";
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-8rem)]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  if (error || !stats) {
    return <div className="text-red-500 p-4 bg-red-50 rounded-lg border border-red-100 flex items-center gap-2"><div className="w-2 h-2 rounded-full bg-red-500"></div>{error}</div>;
  }

  const mainAccount = wabaStatus?.accounts[0];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-sm text-gray-500 mt-1">
            Overview of your business messaging
          </p>
        </div>
      </div>

      {/* KPI Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Contacts */}
        <div className="bg-white p-6 rounded-xl border border-gray-200 relative overflow-hidden">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-gray-500 text-sm font-medium">Contacts</h3>
            <div className="p-2 bg-indigo-50 rounded-lg">
              <Users className="h-5 w-5 text-indigo-600" />
            </div>
          </div>
          <div className="flex items-baseline gap-2">
            <div className="text-3xl font-bold text-gray-900">{stats.contacts.total.toLocaleString()}</div>
            {stats.contacts.unread > 0 && (
              <span className="text-xs font-medium text-orange-600 bg-orange-50 px-2 py-0.5 rounded-full border border-orange-100">
                {stats.contacts.unread} unread
              </span>
            )}
          </div>
          <div className="mt-4 text-xs text-gray-400">Total reach</div>
        </div>

        {/* Messages */}
        <div className="bg-white p-6 rounded-xl border border-gray-200 relative overflow-hidden">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-gray-500 text-sm font-medium">Messages (24h)</h3>
            <div className="p-2 bg-green-50 rounded-lg">
              <MessageSquare className="h-5 w-5 text-green-600" />
            </div>
          </div>
          <div className="flex items-baseline gap-2">
            <div className="text-3xl font-bold text-gray-900">{stats.messages.last_24h.toLocaleString()}</div>
            <span className={`text-xs font-medium px-2 py-0.5 rounded-full border ${stats.messages.delivery_rate > 90 ? 'text-green-600 bg-green-50 border-green-100' :
              stats.messages.delivery_rate > 70 ? 'text-yellow-600 bg-yellow-50 border-yellow-100' :
                'text-red-600 bg-red-50 border-red-100'
              }`}>
              {stats.messages.delivery_rate}% deliv.
            </span>
          </div>
          <div className="mt-4 text-xs text-gray-400">
            <span className="font-medium text-gray-600">{stats.messages.sent}</span> sent / <span className="font-medium text-gray-600">{stats.messages.received}</span> received
          </div>
        </div>

        {/* Campaigns */}
        <div className="bg-white p-6 rounded-xl border border-gray-200 relative overflow-hidden">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-gray-500 text-sm font-medium">Active Campaigns</h3>
            <div className="p-2 bg-purple-50 rounded-lg">
              <TrendingUp className="h-5 w-5 text-purple-600" />
            </div>
          </div>
          <div className="flex items-baseline gap-2">
            <div className="text-3xl font-bold text-gray-900">{stats.campaigns.active}</div>
            {stats.campaigns.active > 0 && (
              <span className="flex h-2 w-2 relative">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-purple-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-purple-500"></span>
              </span>
            )}
          </div>
          <div className="mt-4 text-xs text-gray-400">
            {stats.campaigns.completed} completed historically
          </div>
        </div>
      </div>

      {/* Main Content Split */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Left Column: Analytics */}
        <div className="lg:col-span-2 space-y-6">
          {/* Chart Card */}
          <div className="bg-white p-6 rounded-xl border border-gray-200 h-[400px]">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-semibold text-gray-900">Message Traffic</h2>
              <select className="text-sm border-gray-300 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500">
                <option>Last 7 Days</option>
              </select>
            </div>
            <div className="h-[300px] w-full">
              {timeline && (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={timeline} barGap={4}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f3f4f6" />
                    <XAxis
                      dataKey="date"
                      axisLine={false}
                      tickLine={false}
                      tick={{ fill: '#9ca3af', fontSize: 12 }}
                      dy={10}
                      tickFormatter={(val) => new Date(val).toLocaleDateString(undefined, { weekday: 'short' })}
                    />
                    <YAxis
                      axisLine={false}
                      tickLine={false}
                      tick={{ fill: '#9ca3af', fontSize: 12 }}
                    />
                    <Tooltip
                      contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                      cursor={{ fill: '#f9fafb' }}
                    />
                    <Legend wrapperStyle={{ paddingTop: '20px' }} />
                    <Bar dataKey="sent" name="Sent" fill="#4f46e5" radius={[4, 4, 0, 0]} maxBarSize={40} />
                    <Bar dataKey="received" name="Received" fill="#10b981" radius={[4, 4, 0, 0]} maxBarSize={40} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Infrastructure */}
        <div className="space-y-6">

          {/* WhatsApp Connection Card */}
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="p-4 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
              <h2 className="font-semibold text-gray-900 flex items-center gap-2">
                <Smartphone className="w-4 h-4 text-green-600" />
                WhatsApp Connection
              </h2>
              <button
                onClick={handleSync}
                disabled={syncing}
                className={`p-1.5 rounded-md transition-all ${syncing ? 'bg-gray-200 cursor-not-allowed' : 'hover:bg-white border border-transparent hover:border-gray-200 text-gray-500 hover:text-indigo-600'}`}
                title="Sync Account Info"
              >
                <RefreshCw className={`w-4 h-4 ${syncing ? 'animate-spin' : ''}`} />
              </button>
            </div>

            <div className="p-4 space-y-6">
              {/* Account Status */}
              {mainAccount ? (
                <div className="mb-4 pb-4 border-b border-gray-100">
                  <div className="text-sm text-gray-500 mb-1">Business Account</div>
                  <div className="font-medium text-gray-900 truncate mb-2">{mainAccount.name}</div>
                  <div className="flex gap-2">
                    <span className={`text-[10px] px-2 py-0.5 rounded border font-medium ${getStatusColor(mainAccount.account_review_status)}`}>
                      {mainAccount.account_review_status || 'REVIEW: N/A'}
                    </span>
                    <span className={`text-[10px] px-2 py-0.5 rounded border font-medium ${getStatusColor(mainAccount.business_verification_status)}`}>
                      {mainAccount.business_verification_status || 'VERIFY: N/A'}
                    </span>
                  </div>
                </div>
              ) : (
                <div className="text-sm text-gray-400 italic mb-4">No account connected</div>
              )}

              {/* Phone Lists */}
              <div>
                <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Phone Numbers</div>
                <div className="space-y-3 max-h-[300px] overflow-y-auto pr-1">
                  {wabaStatus?.phone_numbers && wabaStatus.phone_numbers.length > 0 ? (
                    wabaStatus.phone_numbers.map((phone) => (
                      <div key={phone.id} className="group p-3 rounded-lg border border-gray-100 bg-gray-50/50 hover:bg-white hover:border-indigo-100 transition-all">
                        <div className="flex justify-between items-start mb-2">
                          <div className="font-medium text-gray-900 text-sm font-mono">{phone.display_phone_number}</div>
                          <span className={`text-[10px] px-1.5 py-0.5 rounded border font-bold ${getStatusColor(phone.status)}`}>
                            {phone.status}
                          </span>
                        </div>
                        <div className="flex items-center justify-between text-xs">
                          <span className={`px-1.5 py-0.5 rounded border ${getQualityColor(phone.quality_rating)}`}>
                            Quality: {phone.quality_rating}
                          </span>
                          <span className="text-gray-400" title="Messaging Limit">
                            {phone.messaging_limit_tier?.split('_')[0] || 'N/A'}
                          </span>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="text-center text-gray-400 text-sm py-2">No numbers</div>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* System Health */}
          <SystemHealthWidget />

        </div>
      </div>
    </div>
  );
};

export default DashboardPage;
