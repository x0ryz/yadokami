import React, { useEffect, useState } from "react";
import apiClient from "../api/client";
import { DashboardStats, RecentActivity, MessagesTimeline } from "../types";
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
  Activity,
  TrendingUp,
  Clock,
  Send,
  Inbox,
} from "lucide-react";

const DashboardPage: React.FC = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [activity, setActivity] = useState<RecentActivity | null>(null);
  const [timeline, setTimeline] = useState<MessagesTimeline | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        setLoading(true);
        const [statsData, activityData, timelineData] = await Promise.all([
          apiClient.getDashboardStats(),
          apiClient.getRecentActivity(10),
          apiClient.getMessagesTimeline(7),
        ]);

        setStats(statsData);
        setActivity(activityData);
        setTimeline(timelineData);
      } catch (err) {
        console.error("Failed to fetch dashboard data:", err);
        setError("Failed to load dashboard data");
      } finally {
        setLoading(false);
      }
    };

    fetchDashboardData();
  }, []);

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

  // ВИПРАВЛЕННЯ: прибрано зайвий клас p-6, залишено тільки space-y-6
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>

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

        {/* Campaigns Card */}
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-gray-500 text-sm font-medium">
              Active Campaigns
            </h3>
            <Activity className="h-5 w-5 text-blue-500" />
          </div>
          <div className="text-3xl font-bold text-gray-900">
            {stats.campaigns.active}
          </div>
          <div className="mt-2 text-sm text-gray-600">
            {stats.campaigns.completed} completed
          </div>
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

        {/* Recent Activity Section */}
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200 flex flex-col h-full max-h-[460px]">
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
            <Clock className="h-5 w-5 mr-2 text-gray-500" />
            Recent Activity
          </h2>

          <div className="flex-1 overflow-y-auto pr-2 space-y-4">
            {/* Recent Campaigns List */}
            {activity?.campaigns && activity.campaigns.length > 0 && (
              <div className="mb-4">
                <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                  Campaigns
                </h3>
                <ul className="space-y-3">
                  {activity.campaigns.map((camp) => (
                    <li
                      key={camp.id}
                      className="text-sm border-l-2 border-blue-500 pl-3 py-1"
                    >
                      <div
                        className="font-medium text-gray-900 truncate"
                        title={camp.name}
                      >
                        {camp.name}
                      </div>
                      <div className="text-xs text-gray-500 flex justify-between mt-1">
                        <span
                          className={`px-1.5 py-0.5 rounded text-[10px] uppercase ${
                            camp.status === "running"
                              ? "bg-green-100 text-green-800"
                              : "bg-gray-100 text-gray-800"
                          }`}
                        >
                          {camp.status}
                        </span>
                        <span>
                          {camp.sent_count}/{camp.total_contacts} sent
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Recent Messages List */}
            {activity?.messages && activity.messages.length > 0 && (
              <div>
                <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                  Latest Messages
                </h3>
                <ul className="space-y-3">
                  {activity.messages.map((msg) => (
                    <li key={msg.id} className="flex items-start text-sm group">
                      <div
                        className={`mt-0.5 mr-3 p-1 rounded-full shrink-0 ${
                          msg.direction === "outbound"
                            ? "bg-indigo-100 text-indigo-600"
                            : "bg-emerald-100 text-emerald-600"
                        }`}
                      >
                        {msg.direction === "outbound" ? (
                          <Send size={12} />
                        ) : (
                          <Inbox size={12} />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex justify-between items-center">
                          <span className="font-medium text-gray-900 capitalize truncate">
                            {msg.type}
                          </span>
                          <span className="text-xs text-gray-400 ml-2 whitespace-nowrap">
                            {new Date(msg.created_at).toLocaleTimeString([], {
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </span>
                        </div>
                        <div className="text-xs text-gray-500 capitalize flex justify-between">
                          <span>
                            Status:{" "}
                            <span
                              className={
                                msg.status === "failed"
                                  ? "text-red-500 font-medium"
                                  : ""
                              }
                            >
                              {msg.status}
                            </span>
                          </span>
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default DashboardPage;
