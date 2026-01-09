import axios, { AxiosInstance, AxiosRequestConfig } from "axios";
import { config } from "../config/env";
import {
  Contact,
  ContactListResponse,
  ContactCreate,
  ContactUpdate,
  ContactImport,
  ContactImportResult,
  CampaignResponse,
  CampaignCreate,
  CampaignUpdate,
  CampaignStats,
  CampaignSchedule,
  CampaignContactResponse,
  MessageResponse,
  MessageSendResponse,
  Template,
  DashboardStats,
  RecentActivity,
  MessagesTimeline,
  PaginationParams,
  SearchContactsParams,
  SendMessageParams,
  WebhookVerifyParams,
  TagCreate,
  TagUpdate,
  WabaStatusResponse,
  Tag,
} from "../types";

export class ApiClient {
  private client: AxiosInstance;

  constructor(
    // Використовуємо config.apiUrl з імпорту.
    // Якщо config.apiUrl не задано, використовуємо фолбек.
    baseURL: string = config.apiUrl || "https://dev.x0ryz.cc",
    // ЗМІНА: перейменували аргумент на axiosConfig, щоб не конфліктував з імпортом config
    axiosConfig?: AxiosRequestConfig,
  ) {
    this.client = axios.create({
      baseURL,
      headers: {
        "Content-Type": "application/json",
      },
      ...axiosConfig, // Використовуємо перейменований аргумент

      // Кастомна серіалізація параметрів для підтримки масивів (tags=1&tags=2)
      paramsSerializer: (params) => {
        const searchParams = new URLSearchParams();
        for (const key in params) {
          const value = params[key];
          if (Array.isArray(value)) {
            value.forEach((v) => searchParams.append(key, v));
          } else if (value !== undefined && value !== null) {
            searchParams.append(key, value);
          }
        }
        return searchParams.toString();
      },
    });

    this.client.interceptors.response.use(
      (response) => response,
      (error) => Promise.reject(error),
    );
  }

  // ... (решта методів залишаються без змін) ...

  // Webhooks
  async verifyWebhook(params: WebhookVerifyParams): Promise<any> {
    const response = await this.client.get("/webhook", { params });
    return response.data;
  }

  async receiveWebhook(data?: any): Promise<any> {
    const response = await this.client.post("/webhook", data);
    return response.data;
  }

  // Contacts
  async getContacts(
    limit = 50,
    offset = 0,
    tags?: string[],
  ): Promise<ContactListResponse[]> {
    const response = await this.client.get<ContactListResponse[]>("/contacts", {
      params: {
        limit,
        offset,
        tags,
      },
    });
    return response.data;
  }

  async createContact(data: ContactCreate): Promise<Contact> {
    const response = await this.client.post<Contact>("/contacts", data);
    return response.data;
  }

  async searchContacts(
    params: SearchContactsParams,
  ): Promise<ContactListResponse[]> {
    const response = await this.client.get<ContactListResponse[]>(
      "/contacts/search",
      { params },
    );
    return response.data;
  }

  async getContact(contactId: string): Promise<Contact> {
    const response = await this.client.get<Contact>(`/contacts/${contactId}`);
    return response.data;
  }

  async updateContact(
    contactId: string,
    data: ContactUpdate,
  ): Promise<Contact> {
    const response = await this.client.patch<Contact>(
      `/contacts/${contactId}`,
      data,
    );
    return response.data;
  }

  async deleteContact(contactId: string): Promise<void> {
    await this.client.delete(`/contacts/${contactId}`);
  }

  async markContactAsRead(contactId: string): Promise<void> {
    await this.client.post(`/contacts/${contactId}/read`);
  }

  async getChatHistory(
    contactId: string,
    params?: PaginationParams,
  ): Promise<MessageResponse[]> {
    const response = await this.client.get<MessageResponse[]>(
      `/contacts/${contactId}/messages`,
      { params },
    );
    return response.data;
  }

  // Messages
  async sendMessage(params: SendMessageParams): Promise<MessageSendResponse> {
    const payload = {
      phone_number: params.phone,
      body: params.text || params.body,
      type: params.type || "text",
      template_id: params.template_id,
      reply_to_message_id: params.reply_to_message_id,
    };
    const response = await this.client.post<MessageSendResponse>(
      "/messages",
      payload,
    );
    return response.data;
  }

  async sendMediaMessage(
    phone: string,
    file: File,
    caption?: string,
  ): Promise<MessageSendResponse> {
    const formData = new FormData();
    formData.append("phone_number", phone);
    formData.append("file", file);
    if (caption) {
      formData.append("caption", caption);
    }

    const response = await this.client.post<MessageSendResponse>(
      "/messages/media",
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      },
    );
    return response.data;
  }

  // Tags
  async getTags(): Promise<Tag[]> {
    const response = await this.client.get<Tag[]>("/tags");
    return response.data;
  }

  async createTag(data: TagCreate): Promise<Tag> {
    const response = await this.client.post<Tag>("/tags", data);
    return response.data;
  }

  async deleteTag(tagId: string): Promise<void> {
    await this.client.delete(`/tags/${tagId}`);
  }

  async updateTag(tagId: string, data: TagUpdate): Promise<Tag> {
    const response = await this.client.patch<Tag>(`/tags/${tagId}`, data);
    return response.data;
  }

  // WABA
  async triggerWabaSync(): Promise<any> {
    const response = await this.client.post("/waba/sync");
    return response.data;
  }

  async getWabaStatus(): Promise<WabaStatusResponse> {
    const response = await this.client.get<WabaStatusResponse>(
      "/dashboard/waba-status",
    );
    return response.data;
  }

  // Campaigns
  async listCampaigns(): Promise<CampaignResponse[]> {
    const response = await this.client.get<CampaignResponse[]>("/campaigns");
    return response.data;
  }

  async createCampaign(data: CampaignCreate): Promise<CampaignResponse> {
    const response = await this.client.post<CampaignResponse>(
      "/campaigns",
      data,
    );
    return response.data;
  }

  async getCampaign(campaignId: string): Promise<CampaignResponse> {
    const response = await this.client.get<CampaignResponse>(
      `/campaigns/${campaignId}`,
    );
    return response.data;
  }

  async updateCampaign(
    campaignId: string,
    data: CampaignUpdate,
  ): Promise<CampaignResponse> {
    const response = await this.client.patch<CampaignResponse>(
      `/campaigns/${campaignId}`,
      data,
    );
    return response.data;
  }

  async deleteCampaign(campaignId: string): Promise<void> {
    await this.client.delete(`/campaigns/${campaignId}`);
  }

  async scheduleCampaign(
    campaignId: string,
    data: CampaignSchedule,
  ): Promise<CampaignResponse> {
    const response = await this.client.post<CampaignResponse>(
      `/campaigns/${campaignId}/schedule`,
      data,
    );
    return response.data;
  }

  async startCampaign(campaignId: string): Promise<CampaignResponse> {
    const response = await this.client.post<CampaignResponse>(
      `/campaigns/${campaignId}/start`,
    );
    return response.data;
  }

  async pauseCampaign(campaignId: string): Promise<CampaignResponse> {
    const response = await this.client.post<CampaignResponse>(
      `/campaigns/${campaignId}/pause`,
    );
    return response.data;
  }

  async resumeCampaign(campaignId: string): Promise<CampaignResponse> {
    const response = await this.client.post<CampaignResponse>(
      `/campaigns/${campaignId}/resume`,
    );
    return response.data;
  }

  async getCampaignStats(campaignId: string): Promise<CampaignStats> {
    const response = await this.client.get<CampaignStats>(
      `/campaigns/${campaignId}/stats`,
    );
    return response.data;
  }

  async getCampaignContacts(
    campaignId: string,
    params?: PaginationParams,
  ): Promise<CampaignContactResponse[]> {
    const response = await this.client.get<CampaignContactResponse[]>(
      `/campaigns/${campaignId}/contacts`,
      { params },
    );
    return response.data;
  }

  async addContactsManually(
    campaignId: string,
    contacts: ContactImport[],
  ): Promise<ContactImportResult> {
    const response = await this.client.post<ContactImportResult>(
      `/campaigns/${campaignId}/contacts`,
      contacts,
    );
    return response.data;
  }

  async importContactsFromFile(
    campaignId: string,
    file: File,
  ): Promise<ContactImportResult> {
    const formData = new FormData();
    formData.append("file", file);
    const response = await this.client.post<ContactImportResult>(
      `/campaigns/${campaignId}/contacts/import`,
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      },
    );
    return response.data;
  }

  // Templates
  async listTemplates(): Promise<Template[]> {
    const response = await this.client.get<Template[]>("/templates");
    return response.data;
  }

  async getTemplate(templateId: string): Promise<Template> {
    const response = await this.client.get<Template>(
      `/templates/${templateId}`,
    );
    return response.data;
  }

  async getTemplatesByStatus(statusFilter: string): Promise<any> {
    const response = await this.client.get(
      `/templates/by-status/${statusFilter}`,
    );
    return response.data;
  }

  // Dashboard
  async getDashboardStats(): Promise<DashboardStats> {
    const response = await this.client.get<DashboardStats>("/dashboard/stats");
    return response.data;
  }

  async getRecentActivity(limit?: number): Promise<RecentActivity> {
    const response = await this.client.get<RecentActivity>(
      "/dashboard/recent-activity",
      {
        params: { limit },
      },
    );
    return response.data;
  }

  async getMessagesTimeline(days?: number): Promise<MessagesTimeline> {
    const response = await this.client.get<MessagesTimeline>(
      "/dashboard/charts/messages-timeline",
      {
        params: { days },
      },
    );
    return response.data;
  }

  setAuthToken(token: string): void {
    this.client.defaults.headers.common["Authorization"] = `Bearer ${token}`;
    import("../services/websocket").then(({ wsService }) => {
      wsService.setAuthToken(token);
    });
  }

  removeAuthToken(): void {
    delete this.client.defaults.headers.common["Authorization"];
  }

  getAxiosInstance(): AxiosInstance {
    return this.client;
  }
}

export const apiClient = new ApiClient(config.apiUrl);
export default apiClient;
