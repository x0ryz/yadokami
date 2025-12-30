import React, { useState, useCallback } from "react";
import { EventType } from "../../services/websocket";
import { useWSEvent } from "../../services/useWebSocket";

interface CampaignProgress {
  campaign_id: string;
  total: number;
  sent: number;
  delivered: number;
  failed: number;
  pending: number;
  progress_percent: number;
  current_rate: number;
  estimated_completion?: string;
}

export function CampaignProgressWidget({ campaignId }: { campaignId: string }) {
  const [progress, setProgress] = useState<CampaignProgress | null>(null);
  const [status, setStatus] = useState<string>("DRAFT");

  // Handle progress updates
  const handleProgress = useCallback((data: CampaignProgress) => {
    if (data.campaign_id === campaignId) {
      setProgress(data);
    }
  }, [campaignId]);

  // Handle status changes
  const handleStatusChange = useCallback((data: any) => {
    if (data.campaign_id === campaignId) {
      setStatus(data.status);
    }
  }, [campaignId]);

  // Subscribe to events
  useWSEvent(EventType.CAMPAIGN_PROGRESS, handleProgress);
  useWSEvent(EventType.CAMPAIGN_STARTED, handleStatusChange);
  useWSEvent(EventType.CAMPAIGN_PAUSED, handleStatusChange);
  useWSEvent(EventType.CAMPAIGN_COMPLETED, handleStatusChange);

  if (!progress) {
    return <div>Waiting for campaign to start...</div>;
  }

  const eta = progress.estimated_completion
    ? new Date(progress.estimated_completion).toLocaleTimeString()
    : "Calculating...";

  return (
    <div className="campaign-progress">
      <h3>Campaign Status: {status}</h3>

      <div className="progress-bar">
        <div
          className="progress-fill"
          style={{ width: `${progress.progress_percent}%` }}
        />
      </div>

      <div className="stats">
        <div>Progress: {progress.progress_percent.toFixed(1)}%</div>
        <div>Sent: {progress.sent} / {progress.total}</div>
        <div>Delivered: {progress.delivered}</div>
        <div>Failed: {progress.failed}</div>
        <div>Pending: {progress.pending}</div>
        <div>Rate: {progress.current_rate.toFixed(1)} msg/min</div>
        <div>ETA: {eta}</div>
      </div>
    </div>
  );
}
