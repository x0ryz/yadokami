// Enums
export enum ContactStatus {
  ACTIVE = "active",
  NEW = "new",
  SCHEDULED = "scheduled",
  SENT = "sent",
  DELIVERED = "delivered",
  READ = "read",
  FAILED = "failed",
  OPTED_OUT = "opted_out",
  BLOCKED = "blocked",
  ARCHIVED = "archived",
}

export enum CampaignStatus {
  DRAFT = "draft",
  SCHEDULED = "scheduled",
  RUNNING = "running",
  PAUSED = "paused",
  COMPLETED = "completed",
  FAILED = "failed",
}

export enum MessageStatus {
  PENDING = "pending",
  SENT = "sent",
  DELIVERED = "delivered",
  READ = "read",
  FAILED = "failed",
  RECEIVED = "received",
}

export enum MessageDirection {
  INBOUND = "inbound",
  OUTBOUND = "outbound",
}

export enum MessageType {
  TEXT = "text",
  TEMPLATE = "template",
}

// Tag Types
export interface Tag {
  id: string;
  name: string;
  color: string;
}

export interface TagCreate {
  name: string;
  color: string;
}

export interface TagUpdate {
  name?: string;
  color?: string;
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
  tags: Tag[];
  custom_data?: Record<string, any>;
  created_at: string;
  updated_at: string;
  last_message_body?: string | null;
  last_message_status?: MessageStatus | null;
  last_incoming_message_at: string | null;
  last_message_direction?: MessageDirection | null;
}

// Alias for list response if it matches Contact
export type ContactListResponse = Contact;

export interface ContactCreate {
  phone_number: string;
  name?: string | null;
  tag_ids?: string[];
  custom_data?: Record<string, any>;
}

export interface ContactUpdate {
  name?: string | null;
  status?: ContactStatus;
  tag_ids?: string[] | null;
  custom_data?: Record<string, any>;
}

export interface ContactImport {
  phone_number: string;
  name?: string | null;
  tags?: string[];
  custom_data?: Record<string, any>;
}

export interface ContactImportResult {
  total: number;
  imported: number;
  skipped: number;
  errors?: string[];
}

export interface DuplicateContact {
  phone_number: string;
  name: string | null;
}

export interface DuplicateCheckResult {
  duplicates: DuplicateContact[];
  new_contacts: string[];
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
  read_count: number;
  replied_count: number;
  failed_count: number;
  created_at: string;
  updated_at: string;
}

export interface CampaignCreate {
  name: string;
  message_type?: MessageType;
  template_id?: string | null;
  waba_phone_id?: string | null;
  message_body?: string | null;
  variable_mapping?: Record<string, string> | null;
}

export interface CampaignUpdate {
  name?: string | null;
  message_type?: MessageType | null;
  template_id?: string | null;
  message_body?: string | null;
  variable_mapping?: Record<string, string> | null;
}

export interface CampaignStats {
  id: string;
  name: string;
  status: CampaignStatus;
  total_contacts: number;
  sent_count: number;
  delivered_count: number;
  read_count: number;
  replied_count: number;
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
  custom_data: Record<string, any>;
  status: ContactStatus;
  last_sent_at: string | null;
  retry_count: number;
  message_error_code?: number | null;
  message_error_message?: string | null;
}

export interface CampaignContactUpdate {
  name?: string | null;
  custom_data?: Record<string, any>;
  status?: ContactStatus;
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
  scheduled_at?: string | null;
  sent_at?: string | null;
  media_files: MediaFileResponse[];
  reply_to_message_id?: string | null;
  reaction?: string | null;
  error_code?: number | null;
  error_message?: string | null;
}

export interface MediaFileResponse {
  id: string;
  file_name: string;
  file_mime_type: string;
  caption: string | null;
  url: string;
}

export interface MessageSendResponse {
  status: string;
  message_id: string;
  request_id: string;
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
  components: TemplateComponent[];
  default_variable_mapping?: Record<string, string>;
  is_deleted: boolean;
  created_at: string;
  updated_at: string;
}

export interface TemplateUpdate {
  default_variable_mapping?: Record<string, string>;
}

export interface TemplateComponent {
  type: string;
  format?: string;
  text?: string;
  example?: any;
  buttons?: TemplateButton[];
  [key: string]: any;
}

export interface TemplateButton {
  type: string;
  text?: string;
  url?: string;
  phone_number?: string;
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

// Dashboard
export interface DashboardStats {
  contacts: {
    total: number;
    unread: number;
  };
  messages: {
    total: number;
    sent: number;
    received: number;
    last_24h: number;
    delivery_rate: number;
  };
  campaigns: {
    total: number;
    active: number;
    completed: number;
  };
}

export interface RecentMessage {
  id: string;
  direction: "inbound" | "outbound";
  type: string;
  status: string;
  created_at: string;
}

export interface RecentCampaign {
  id: string;
  name: string;
  status: string;
  sent_count: number;
  total_contacts: number;
  updated_at: string;
}

export interface RecentActivity {
  messages: RecentMessage[];
  campaigns: RecentCampaign[];
}

export interface TimelinePoint {
  date: string;
  sent: number;
  received: number;
}

export type MessagesTimeline = TimelinePoint[];

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
  body?: string;
  template_id?: string;
  reply_to_message_id?: string;
  scheduled_at?: string;
}

export interface WebhookVerifyParams {
  "hub.mode": string;
  "hub.verify_token": string;
  "hub.challenge": string;
}

export interface WabaAccountStatus {
  id: string;
  waba_id: string;
  name: string;
  account_review_status: string | null;
  business_verification_status: string | null;
}

export interface WabaPhoneStatus {
  id: string;
  waba_id: string;
  phone_number_id: string;
  display_phone_number: string;
  status: string | null;
  quality_rating: string;
  messaging_limit_tier: string | null;
  updated_at: string | null;
}

export interface WabaStatusResponse {
  accounts: WabaAccountStatus[];
  phone_numbers: WabaPhoneStatus[];
}

export interface WabaPhoneNumberResponse {
  id: string;
  display_phone_number: string;
  quality_rating: string;
}

export interface WabaPhoneNumbersResponse {
  phone_numbers: WabaPhoneNumberResponse[];
}

export interface WabaSettingsResponse {
  id: string;
  waba_id: string;
  name: string;
  account_review_status: string | null;
  business_verification_status: string | null;
  graph_api_version: string | null;
}

// Available Fields Response
export interface AvailableFieldsResponse {
  standard_fields: string[];
  custom_fields: string[];
  total_contacts: number;
}

// Quick Reply Types
export interface QuickReply {
  id: string;
  title: string;
  content: Record<string, string>;
  created_at: string;
  updated_at: string;
}

export interface QuickReplyCreate {
  title: string;
  content: Record<string, string>;
}

export interface QuickReplyUpdate {
  title?: string;
  content?: Record<string, string>;
}

export interface QuickReplyTextResponse {
  text: string;
  language: string;
}
