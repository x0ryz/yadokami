import React, { useEffect, useState } from "react";
import { Activity, Database, Server, AlertCircle, CheckCircle, Clock } from "lucide-react";
import { HealthResponse } from "../../types";
import { apiClient } from "../../api";

const SystemHealthWidget: React.FC = () => {
    const [health, setHealth] = useState<HealthResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchHealth = async () => {
        try {
            const data = await apiClient.getSystemHealth();
            setHealth(data);
            setError(null);
        } catch (err: any) {
            // Якщо API вернуло 503 (Unhealthy), ми все одно хочемо показати дані
            if (err.response && err.response.status === 503 && err.response.data) {
                setHealth(err.response.data);
                setError(null);
            } else {
                console.error("Failed to fetch health status:", err);
                setError("System unreachable");
                setHealth(null); // Reset health data on connection error
            }
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchHealth();
        // Auto-refresh every 30 seconds
        const interval = setInterval(fetchHealth, 30000);
        return () => clearInterval(interval);
    }, []);

    if (loading && !health) {
        return (
            <div className="bg-white p-6 rounded-lg border border-gray-200 animate-pulse h-[200px]">
                <div className="h-6 bg-gray-200 rounded w-1/3 mb-4"></div>
                <div className="space-y-3">
                    <div className="h-10 bg-gray-200 rounded"></div>
                    <div className="h-10 bg-gray-200 rounded"></div>
                </div>
            </div>
        );
    }

    const getStatusColor = (status: string) => {
        switch (status) {
            case "up":
            case "healthy":
                return "text-green-500";
            case "down":
            case "unhealthy":
                return "text-red-500";
            case "degraded":
                return "text-yellow-500";
            default:
                return "text-gray-400";
        }
    };

    const getStatusIcon = (status: string) => {
        switch (status) {
            case "up":
            case "healthy":
                return <CheckCircle className={`w-5 h-5 ${getStatusColor(status)}`} />;
            case "down":
            case "unhealthy":
                return <AlertCircle className={`w-5 h-5 ${getStatusColor(status)}`} />;
            default:
                return <AlertCircle className="w-5 h-5 text-gray-400" />;
        }
    };

    const formatUptime = (seconds: number) => {
        const d = Math.floor(seconds / (3600 * 24));
        const h = Math.floor((seconds % (3600 * 24)) / 3600);
        const m = Math.floor((seconds % 3600) / 60);

        const parts = [];
        if (d > 0) parts.push(`${d}d`);
        if (h > 0) parts.push(`${h}h`);
        if (m > 0 || parts.length === 0) parts.push(`${m}m`);

        return parts.join(" ");
    };

    return (
        <div className="bg-white p-6 rounded-lg border border-gray-200">
            <div className="flex items-center justify-between mb-4">
                <h3 className="text-gray-500 text-sm font-medium flex items-center gap-2">
                    <Activity className="w-4 h-4" />
                    System Status
                </h3>
                {health && (
                    <span className={`text-xs font-bold uppercase px-2 py-0.5 rounded-full border ${health.status === 'healthy' ? 'bg-green-50 border-green-200 text-green-700' :
                        health.status === 'degraded' ? 'bg-yellow-50 border-yellow-200 text-yellow-700' :
                            'bg-red-50 border-red-200 text-red-700'
                        }`}>
                        {health.status}
                    </span>
                )}
            </div>

            {error ? (
                <div className="text-red-500 text-sm flex items-center gap-2 bg-red-50 p-3 rounded-lg border border-red-100">
                    <AlertCircle className="w-4 h-4" />
                    {error}
                </div>
            ) : health ? (
                <div className="space-y-4">
                    {/* Components Grid */}
                    <div className="grid grid-cols-1 gap-3">
                        {/* API / Backend */}
                        <div className="flex items-center justify-between p-2 bg-gray-50 rounded-lg border border-gray-100">
                            <div className="flex items-center gap-3">
                                <div className="p-2 bg-white rounded-md border border-gray-100">
                                    <Server className="w-4 h-4 text-indigo-500" />
                                </div>
                                <div>
                                    <div className="text-sm font-medium text-gray-900">Backend API</div>
                                    <div className="text-xs text-gray-500 flex items-center gap-1">
                                        <Clock className="w-3 h-3" />
                                        {formatUptime(health.uptime_seconds)}
                                    </div>
                                </div>
                            </div>
                            {getStatusIcon("up")}
                        </div>

                        {/* Database */}
                        <div className="flex items-center justify-between p-2 bg-gray-50 rounded-lg border border-gray-100">
                            <div className="flex items-center gap-3">
                                <div className="p-2 bg-white rounded-md border border-gray-100">
                                    <Database className="w-4 h-4 text-blue-500" />
                                </div>
                                <div>
                                    <div className="text-sm font-medium text-gray-900">Database</div>
                                    <div className="text-xs text-gray-500">
                                        Latency: {health.components.database?.latency_ms}ms
                                    </div>
                                </div>
                            </div>
                            {getStatusIcon(health.components.database?.status || "down")}
                        </div>

                        {/* Broker */}
                        <div className="flex items-center justify-between p-2 bg-gray-50 rounded-lg border border-gray-100">
                            <div className="flex items-center gap-3">
                                <div className="p-2 bg-white rounded-md border border-gray-100">
                                    <Activity className="w-4 h-4 text-orange-500" />
                                </div>
                                <div>
                                    <div className="text-sm font-medium text-gray-900">Message Broker</div>
                                    <div className="text-xs text-gray-500">
                                        {health.components.broker?.details ? (
                                            <span className="text-red-500">{health.components.broker.details}</span>
                                        ) : (
                                            `Latency: ${health.components.broker?.latency_ms}ms`
                                        )}
                                    </div>
                                </div>
                            </div>
                            {getStatusIcon(health.components.broker?.status || "down")}
                        </div>
                    </div>

                    <div className="text-[10px] text-gray-400 text-right">
                        Last updated: {new Date().toLocaleTimeString()}
                    </div>
                </div>
            ) : null}
        </div>
    );
};

export default SystemHealthWidget;
