// Enums
export enum ContactStatus {
  NEW = 'new',
  SCHEDULED = 'scheduled',
  SENT = 'sent',
  DELIVERED = 'delivered',
  READ = 'read',
  FAILED = 'failed',
  OPTED_OUT = 'opted_out',
  BLOCKED = 'blocked',
}

export enum CampaignStatus {
  DRAFT = 'draft',
  SCHEDULED = 'scheduled',
  RUNNING = 'running',
  PAUSED = 'paused',
  COMPLETED = 'completed',
  FAILED = 'failed',
}

export enum MessageStatus {
  PENDING = 'pending',
  SENT = 'sent',
  DELIVERED = 'delivered',
  READ = 'read',
  FAILED = 'failed',
  RECEIVED = 'received',
}

export enum MessageDirection {
  INBOUND = 'inbound',
  OUTBOUND = 'outbound',
}

export enum MessageType {
  TEXT = 'text',
  TEMPLATE = 'template',
}

// Contact Types
export interface Contact {
  id: string;
  phone_number: string;
  name: string | null;
  unread_count: number;
  status: ContactStatus;
  last_message_at: string | null;
  source: string | null;
  tags: string[] | null;
  created_at: string;
  updated_at: string;
}

export interface ContactCreate {
  phone_number: string;
  name?: string | null;
  tags?: string[];
}

export interface ContactUpdate {
  name?: string | null;
  tags?: string[] | null;
}

export interface ContactImport {
  phone_number: string;
  name?: string | null;
  tags?: string[];
}

export interface ContactImportResult {
  total: number;
  imported: number;
  skipped: number;
  errors?: string[];
}

// Campaign Types
export interface CampaignResponse {
  id: string;
  name: string;
  status: CampaignStatus;
  message_type: string;
  template_id: string | null;
  message_body: string | null;
  scheduled_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  total_contacts: number;
  sent_count: number;
  delivered_count: number;
  failed_count: number;
  created_at: string;
  updated_at: string;
}

export interface CampaignCreate {
  name: string;
  message_type?: MessageType;
  template_id?: string | null;
  message_body?: string | null;
}

export interface CampaignUpdate {
  name?: string | null;
  message_type?: MessageType | null;
  template_id?: string | null;
  message_body?: string | null;
}

export interface CampaignStats {
  id: string;
  name: string;
  status: CampaignStatus;
  total_contacts: number;
  sent_count: number;
  delivered_count: number;
  failed_count: number;
  progress_percent: number;
  scheduled_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CampaignSchedule {
  scheduled_at: string; // ISO 8601 datetime
}

export interface CampaignContactResponse {
  id: string;
  contact_id: string;
  phone_number: string;
  name: string | null;
  status: ContactStatus;
  last_sent_at: string | null;
  error_message: string | null;
  retry_count: number;
}

// Message Types
export interface MessageResponse {
  id: string;
  wamid: string | null;
  direction: MessageDirection;
  status: MessageStatus;
  message_type: string;
  body: string | null;
  created_at: string | null;
  media_files: MediaFileResponse[];
}

export interface MediaFileResponse {
  id: string;
  file_name: string;
  file_mime_type: string;
  caption: string | null;
  url: string;
}

// Template Types
export interface Template {
  id: string;
  waba_id: string;
  meta_template_id: string;
  name: string;
  language: string;
  status: string;
  category: string;
  components: Record<string, any>[];
  created_at: string;
  updated_at: string;
}

// Error Types
export interface ValidationError {
  loc: (string | number)[];
  msg: string;
  type: string;
}

export interface HTTPValidationError {
  detail: ValidationError[];
}

// Dashboard Types (schemas are empty in OpenAPI, but we can infer structure)
export interface DashboardStats {
  total_contacts?: number;
  total_messages?: number;
  sent_messages?: number;
  received_messages?: number;
  active_campaigns?: number;
  [key: string]: any;
}

export interface RecentActivity {
  messages?: MessageResponse[];
  campaigns?: CampaignResponse[];
  [key: string]: any;
}

export interface MessagesTimeline {
  date: string;
  count: number;
  [key: string]: any;
}

// Query Parameters Types
export interface PaginationParams {
  limit?: number;
  offset?: number;
}

export interface SearchContactsParams {
  q: string;
  limit?: number;
}

export interface SendMessageParams {
  phone: string;
  type?: string;
  text?: string;
}

export interface WebhookVerifyParams {
  'hub.mode': string;
  'hub.verify_token': string;
  'hub.challenge': string;
}

