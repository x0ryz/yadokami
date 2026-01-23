import { config } from "../config/env";
import { WEBSOCKET } from "../constants";

export enum EventType {
  CAMPAIGN_CREATED = "campaign_created",
  CAMPAIGN_UPDATED = "campaign_updated",
  CAMPAIGN_SCHEDULED = "campaign_scheduled",
  CAMPAIGN_STARTED = "campaign_started",
  CAMPAIGN_PAUSED = "campaign_paused",
  CAMPAIGN_RESUMED = "campaign_resumed",
  CAMPAIGN_COMPLETED = "campaign_completed",
  CAMPAIGN_FAILED = "campaign_failed",
  CAMPAIGN_PROGRESS = "campaign_progress",
  NEW_MESSAGE = "new_message",
  MESSAGE_SENT = "message_sent",
  MESSAGE_DELIVERED = "message_delivered",
  MESSAGE_READ = "message_read",
  MESSAGE_FAILED = "message_failed",
  MESSAGE_RECEIVED = "message_received",
  CONTACT_UNREAD_CHANGED = "contact_unread_changed",
  CONTACT_SESSION_UPDATE = "contact_session_update",
  BATCH_PROGRESS = "batch_progress",
  SYNC_COMPLETED = "sync_completed",
  STATUS_UPDATE = "status_update",
  MESSAGE_REACTION = "message_reaction",
  TEMPLATE_STATUS_UPDATE = "template_status_update",
  WABA_STATUS_UPDATE = "waba_status_update",
  PHONE_STATUS_UPDATE = "phone_status_update",
}

export interface WSEvent {
  event: EventType;
  data: Record<string, any>;
  timestamp: string;
}

export type EventHandler = (data: any) => void;

class WebSocketService {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private reconnectTimer: number | null = null;
  private handlers: Map<EventType, EventHandler[]> = new Map();
  private url: string;
  private authToken?: string;
  private connectionCallbacks: ((connected: boolean) => void)[] = [];

  constructor(url?: string, authToken?: string) {
    this.url = url || config.wsUrl;
    this.authToken = authToken || config.wsToken;

    if (this.authToken) {
      const urlObj = new URL(this.url);
      urlObj.searchParams.set("token", this.authToken);
      this.url = urlObj.toString();
    }
  }

  connect() {
    if (
      this.ws?.readyState === WebSocket.OPEN ||
      this.ws?.readyState === WebSocket.CONNECTING
    ) {
      return;
    }

    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
        if (this.reconnectTimer) {
          clearTimeout(this.reconnectTimer);
          this.reconnectTimer = null;
        }
        this.notifyConnectionStatus(true);
      };

      this.ws.onmessage = (event) => {
        try {
          const message: WSEvent = JSON.parse(event.data);
          this.handleEvent(message);
        } catch (error) {
          try {
            const rawData = JSON.parse(event.data);

            if (rawData.event && rawData.data) {
              this.handleEvent(rawData);
            } else if (rawData.type && rawData.payload) {
              this.handleEvent({
                event: rawData.type,
                data: rawData.payload,
                timestamp: new Date().toISOString(),
              });
            } else {
              this.handleRawMessage(rawData);
            }
          } catch {
            // Ignore malformed messages
          }
        }
      };

      this.ws.onerror = () => {
        // Error handling is done in onclose
      };

      this.ws.onclose = () => {
        this.notifyConnectionStatus(false);
        this.scheduleReconnect();
      };
    } catch {
      this.scheduleReconnect();
    }
  }

  private handleEvent(message: WSEvent) {
    const handlers = this.handlers.get(message.event);
    if (handlers) {
      handlers.forEach((handler) => handler(message.data));
    }
  }

  private handleRawMessage(data: any) {
    if (data.message_type || data.direction) {
      this.handleEvent({
        event: EventType.NEW_MESSAGE,
        data: data,
        timestamp: new Date().toISOString(),
      });
    } else if (data.campaign_id || data.progress_percent) {
      this.handleEvent({
        event: EventType.CAMPAIGN_PROGRESS,
        data: data,
        timestamp: new Date().toISOString(),
      });
    } else if (data.contact_id || data.unread_count !== undefined) {
      this.handleEvent({
        event: EventType.CONTACT_UNREAD_CHANGED,
        data: data,
        timestamp: new Date().toISOString(),
      });
    }
  }

  on(eventType: EventType, handler: EventHandler) {
    if (!this.handlers.has(eventType)) {
      this.handlers.set(eventType, []);
    }
    this.handlers.get(eventType)!.push(handler);
  }

  off(eventType: EventType, handler: EventHandler) {
    const handlers = this.handlers.get(eventType);
    if (handlers) {
      const index = handlers.indexOf(handler);
      if (index > -1) {
        handlers.splice(index, 1);
      }
    }
  }

  private scheduleReconnect() {
    if (
      this.reconnectTimer ||
      this.reconnectAttempts >= WEBSOCKET.MAX_RECONNECT_ATTEMPTS
    ) {
      return;
    }

    this.reconnectAttempts++;
    const delay = Math.min(
      WEBSOCKET.RECONNECT_INTERVAL * Math.pow(2, this.reconnectAttempts - 1),
      30000,
    );

    this.reconnectTimer = window.setTimeout(() => {
      this.connect();
    }, delay);
  }

  private notifyConnectionStatus(connected: boolean) {
    this.connectionCallbacks.forEach((callback) => callback(connected));
  }

  onConnectionChange(callback: (connected: boolean) => void) {
    this.connectionCallbacks.push(callback);
    return () => {
      this.connectionCallbacks = this.connectionCallbacks.filter(
        (cb) => cb !== callback,
      );
    };
  }

  disconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  getUrl(): string {
    return this.url;
  }

  setUrl(url: string) {
    this.url = url;
    if (this.isConnected()) {
      this.disconnect();
      setTimeout(() => this.connect(), WEBSOCKET.RECONNECT_TIMEOUT);
    }
  }

  setAuthToken(token: string) {
    this.authToken = token;
    const urlObj = new URL(this.url.replace(/\?.*$/, ""));
    urlObj.searchParams.set("token", token);
    this.url = urlObj.toString();

    if (this.isConnected()) {
      this.disconnect();
      setTimeout(() => this.connect(), WEBSOCKET.RECONNECT_TIMEOUT);
    }
  }
}

export const wsService = new WebSocketService();

if (config.wsUrl) {
  wsService.setUrl(config.wsUrl);
}
