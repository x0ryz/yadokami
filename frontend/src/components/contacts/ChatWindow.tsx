import React, { useState, useEffect, useRef } from "react";
import {
  Contact,
  MessageResponse,
  MessageDirection,
  MessageStatus,
  Tag,
  TagCreate,
  TagUpdate,
} from "../../types";
import TagSelector from "../tags/TagSelector";
import ContactActionsMenu from "./ContactActionsMenu";
import QuickReplyPicker from "../quickReplies/QuickReplyPicker";
import { apiClient } from "../../api";
import {
  detectLanguageFromPhone,
  AVAILABLE_LANGUAGES,
  getLanguageName,
} from "../../utils/languageDetector";
import {
  Check,
  X,
  CheckCheck,
  Clock,
  Paperclip,
  CornerUpLeft,
  Link,
  Send,
  Lock,
  Zap,
  Languages,
  Calendar,
} from "lucide-react";

// --- КОМПОНЕНТ ТАЙМЕРА З КІЛЬЦЕМ ТА HOVER-ЕФЕКТОМ ---
const SessionTimer: React.FC<{ lastIncomingAt: string | null | undefined }> = ({
  lastIncomingAt,
}) => {
  const [timeLeft, setTimeLeft] = useState<{
    totalMs: number;
    hours: number;
    minutes: number;
    expired: boolean;
  } | null>(null);

  const [isHovered, setIsHovered] = useState(false);

  useEffect(() => {
    const calculateTime = () => {
      if (!lastIncomingAt) {
        setTimeLeft({ totalMs: 0, hours: 0, minutes: 0, expired: true });
        return;
      }

      const lastMsgTime = new Date(lastIncomingAt).getTime();
      const expirationTime = lastMsgTime + 24 * 60 * 60 * 1000; // +24 години
      const now = Date.now();
      const diff = expirationTime - now;

      if (diff <= 0) {
        setTimeLeft({ totalMs: 0, hours: 0, minutes: 0, expired: true });
      } else {
        const hours = Math.floor(diff / (1000 * 60 * 60));
        const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
        setTimeLeft({ totalMs: diff, hours, minutes, expired: false });
      }
    };

    calculateTime();
    const interval = setInterval(calculateTime, 1000);

    return () => clearInterval(interval);
  }, [lastIncomingAt]);

  if (!timeLeft) return null;

  // Налаштування SVG кільця
  const size = 42;
  const strokeWidth = 3;
  const center = size / 2;
  const radius = center - strokeWidth;
  const circumference = 2 * Math.PI * radius;

  // Прогрес
  const maxTime = 24 * 60 * 60 * 1000;
  const progress = Math.max(0, Math.min(1, timeLeft.totalMs / maxTime));
  const strokeDashoffset = circumference * (1 - progress);

  // Кольори
  let strokeColor = "text-green-500";
  if (timeLeft.hours < 4) strokeColor = "text-amber-500";
  if (timeLeft.hours < 1) strokeColor = "text-red-500";

  if (timeLeft.expired) {
    return (
      <div
        className="flex items-center justify-center bg-gray-100 rounded-full border border-gray-300 text-gray-400 cursor-help"
        style={{ width: size, height: size }}
        title="Сесія закрита (24г). Потрібен шаблон."
      >
        <Lock size={16} />
      </div>
    );
  }

  return (
    <div
      className="relative flex items-center justify-center cursor-help"
      style={{ width: size, height: size }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      title={`Залишилось: ${timeLeft.hours}г ${timeLeft.minutes}хв`}
    >
      {/* Фонове кільце */}
      <svg
        className="absolute inset-0 transform -rotate-90"
        width={size}
        height={size}
      >
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="transparent"
          stroke="#e5e7eb"
          strokeWidth={strokeWidth}
        />
        {/* Активне кільце */}
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="transparent"
          stroke="currentColor"
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          strokeLinecap="round"
          className={`transition-all duration-1000 ease-linear ${strokeColor}`}
        />
      </svg>

      {/* Текст по центру */}
      <div className="z-10 flex flex-col items-center justify-center leading-none select-none">
        <span
          className={`font-bold transition-all duration-200 ${strokeColor} ${isHovered ? "text-[10px]" : "text-[11px]"}`}
        >
          {isHovered ? (
            // При наведенні: показуємо HH:MM (напр. 23:15)
            `${timeLeft.hours}:${timeLeft.minutes.toString().padStart(2, "0")}`
          ) : // Звичайний стан: показуємо години або хвилини
            timeLeft.hours > 0 ? (
              <>
                {timeLeft.hours}
                <span className="text-[9px] font-normal">г</span>
              </>
            ) : (
              <>
                {timeLeft.minutes}
                <span className="text-[9px] font-normal">хв</span>
              </>
            )}
        </span>
      </div>
    </div>
  );
};

// --- DATE HELPERS ---
const getDateIdentifier = (dateString: string | null | undefined): string => {
  if (!dateString) return "";
  return new Date(dateString).toLocaleDateString("uk-UA");
};

const getDateLabel = (dateString: string) => {
  const date = new Date(dateString);
  const now = new Date();
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);

  const isToday =
    date.getDate() === now.getDate() &&
    date.getMonth() === now.getMonth() &&
    date.getFullYear() === now.getFullYear();

  const isYesterday =
    date.getDate() === yesterday.getDate() &&
    date.getMonth() === yesterday.getMonth() &&
    date.getFullYear() === yesterday.getFullYear();

  if (isToday) return "Сьогодні";
  if (isYesterday) return "Вчора";
  return date.toLocaleDateString("uk-UA", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
};

const DateSeparator: React.FC<{ date: string }> = ({ date }) => (
  <div className="flex justify-center my-4">
    <span className="bg-gray-200 text-gray-600 text-xs px-3 py-1 rounded-full shadow-sm border border-gray-300">
      {getDateLabel(date)}
    </span>
  </div>
);

// --- ОСНОВНИЙ КОМПОНЕНТ ---

interface ChatWindowProps {
  contact: Contact;
  messages: MessageResponse[];
  loading: boolean;
  onSendMessage: (phone: string, text: string, replyToId?: string, scheduledAt?: string) => void;
  onSendMedia: (phone: string, file: File, caption?: string) => void;

  onContactUpdate?: (contact: Contact) => void;
  onContactDelete?: (contactId: string) => void;

  availableTags: Tag[];
  onUpdateTags: (tagIds: string[]) => void;
  onCreateTag: (tag: TagCreate) => Promise<void>;
  onDeleteTag: (tagId: string) => Promise<void>;
  onEditTag: (tagId: string, data: TagUpdate) => Promise<void>;

  // Пагінація
  hasMoreMessages?: boolean;
  loadingOlderMessages?: boolean;
  onLoadOlderMessages?: () => void;
}

const ChatWindow: React.FC<ChatWindowProps> = ({
  contact,
  messages = [],
  loading,
  onSendMessage,
  onSendMedia,
  onContactUpdate,
  onContactDelete,
  availableTags,
  onUpdateTags,
  onCreateTag,
  onDeleteTag,
  onEditTag,
  hasMoreMessages = false,
  loadingOlderMessages = false,
  onLoadOlderMessages,
}) => {
  const [messageText, setMessageText] = useState("");
  const [replyTo, setReplyTo] = useState<MessageResponse | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isTagSelectorOpen, setIsTagSelectorOpen] = useState(false);
  const [isQuickReplyPickerOpen, setIsQuickReplyPickerOpen] = useState(false);
  const [scheduledAt, setScheduledAt] = useState<string | null>(null);
  const [showSchedulePicker, setShowSchedulePicker] = useState(false);
  const [scheduledMessageMenu, setScheduledMessageMenu] = useState<{
    messageId: string;
    x: number;
    y: number;
  } | null>(null);

  // Визначаємо мову: спочатку з custom_data, потім автовизначення, потім дефолт
  const [selectedLanguage, setSelectedLanguage] = useState<string>(() => {
    if (contact.custom_data?.language) {
      return contact.custom_data.language as string;
    }
    return detectLanguageFromPhone(contact.phone_number);
  });

  // Editing Name State
  const [isEditingName, setIsEditingName] = useState(false);
  const [editedName, setEditedName] = useState("");

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const quickReplyButtonRef = useRef<HTMLButtonElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const shouldScrollRef = useRef(false);
  const prevContactIdRef = useRef<string | null>(null);
  const prevMessagesLengthRef = useRef(0);
  const prevScrollHeightRef = useRef(0);

  // Перевірка чи сесія активна
  const isSessionExpired = React.useMemo(() => {
    if (!contact.last_incoming_message_at) return true;
    const end =
      new Date(contact.last_incoming_message_at).getTime() +
      24 * 60 * 60 * 1000;
    return Date.now() > end;
  }, [contact.last_incoming_message_at]);

  // При зміні контакта - скролимо вниз
  useEffect(() => {
    if (prevContactIdRef.current !== contact.id) {
      shouldScrollRef.current = true;
      scrollToBottom("auto");
      setSelectedFile(null);
      setMessageText("");
      setIsTagSelectorOpen(false);
      setIsEditingName(false);
      prevContactIdRef.current = contact.id;
      prevMessagesLengthRef.current = 0;

      // Оновлюємо мову при зміні контакта
      if (contact.custom_data?.language) {
        setSelectedLanguage(contact.custom_data.language as string);
      } else {
        setSelectedLanguage(detectLanguageFromPhone(contact.phone_number));
      }
    }
  }, [contact.id, contact.phone_number, contact.custom_data]);

  // Скролимо тільки якщо встановлений прапорець або користувач вже внизу
  useEffect(() => {
    const container = messagesContainerRef.current;
    if (!container || messages.length === 0) return;

    // Якщо завантажили старіші повідомлення (додались на початок)
    const loadedOlder = messages.length > prevMessagesLengthRef.current &&
      !shouldScrollRef.current &&
      loadingOlderMessages === false;

    if (loadedOlder && prevScrollHeightRef.current > 0) {
      // Зберігаємо позицію скролу після додавання старіших повідомлень
      const newScrollHeight = container.scrollHeight;
      const scrollDiff = newScrollHeight - prevScrollHeightRef.current;
      container.scrollTop = scrollDiff;
      prevScrollHeightRef.current = 0;
    } else {
      // Перевіряємо чи користувач вже внизу (з невеликою похибкою 100px)
      const isNearBottom =
        container.scrollHeight - container.scrollTop - container.clientHeight < 100;

      // Скролимо якщо:
      // 1. Встановлений прапорець (зміна контакту або відправка)
      // 2. Користувач вже знаходиться внизу чату
      if (shouldScrollRef.current || isNearBottom) {
        scrollToBottom("smooth");
        shouldScrollRef.current = false;
      }
    }

    prevMessagesLengthRef.current = messages.length;
  }, [messages, loadingOlderMessages]);

  const scrollToBottom = (behavior: ScrollBehavior = "smooth") => {
    setTimeout(() => {
      messagesEndRef.current?.scrollIntoView({ behavior });
    }, 100);
  };

  const handleLoadOlder = () => {
    const container = messagesContainerRef.current;
    if (container) {
      prevScrollHeightRef.current = container.scrollHeight;
    }
    onLoadOlderMessages?.();
  };

  const handleSend = () => {
    if (selectedFile) {
      onSendMedia(contact.phone_number, selectedFile, messageText);
      setSelectedFile(null);
      setMessageText("");
      setReplyTo(null);
      setScheduledAt(null);
      setShowSchedulePicker(false);
      // Скролимо вниз після відправки
      shouldScrollRef.current = true;
      // Скидаємо висоту textarea
      if (textareaRef.current) {
        textareaRef.current.style.height = "40px";
      }
    } else if (messageText.trim()) {
      onSendMessage(contact.phone_number, messageText, replyTo?.id, scheduledAt || undefined);
      setMessageText("");
      setReplyTo(null);
      setScheduledAt(null);
      setShowSchedulePicker(false);
      // Скролимо вниз після відправки
      shouldScrollRef.current = true;
      // Скидаємо висоту textarea
      if (textareaRef.current) {
        textareaRef.current.style.height = "40px";
      }
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const formatMessageTime = (dateString: string | null) => {
    if (!dateString) return "";
    const date = new Date(dateString);
    return date.toLocaleTimeString("uk-UA", {
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const getStatusIcon = (status: MessageStatus) => {
    switch (status) {
      case MessageStatus.SENT:
        return <Check className="w-3 h-3" />;
      case MessageStatus.DELIVERED:
        return <CheckCheck className="w-3 h-3" />;
      case MessageStatus.READ:
        return <CheckCheck className="w-3 h-3" />;
      case MessageStatus.FAILED:
        return "!";
      default:
        return <Clock className="w-3 h-3" />;
    }
  };

  const getStatusClass = (status: MessageStatus) => {
    if (status === MessageStatus.READ) return "text-blue-400 font-bold";
    if (status === MessageStatus.FAILED) return "text-red-500 font-bold";
    return "text-blue-200";
  };

  const getReplyingToMessage = (replyId: string | null | undefined) => {
    if (!replyId) return null;
    return messages.find((m) => m.id === replyId);
  };

  const handleSaveName = async () => {
    if (editedName !== contact.name) {
      try {
        const updated = await apiClient.updateContact(contact.id, {
          name: editedName,
        });
        if (onContactUpdate) {
          onContactUpdate(updated);
        }
      } catch (error) {
        console.error("Failed to update name:", error);
        alert("Не вдалося оновити ім'я");
      }
    }
    setIsEditingName(false);
  };

  const handleQuickReplySelect = (text: string) => {
    setMessageText((prev) => (prev ? `${prev}\n${text}` : text));
    // Оновлюємо висоту textarea після вставки
    setTimeout(() => {
      if (textareaRef.current) {
        textareaRef.current.style.height = "40px";
        textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
      }
    }, 0);
  };

  const handleSendScheduledNow = async (messageId: string) => {
    try {
      await apiClient.sendScheduledMessageNow(messageId);
      setScheduledMessageMenu(null);
    } catch (error) {
      console.error("Failed to send scheduled message:", error);
      alert("Не вдалося відправити повідомлення");
    }
  };

  const handleDeleteScheduledMessage = async (messageId: string) => {
    try {
      await apiClient.deleteScheduledMessage(messageId);
      setScheduledMessageMenu(null);
      // Message will be removed via WebSocket update
    } catch (error) {
      console.error("Failed to delete scheduled message:", error);
      alert("Не вдалося видалити повідомлення");
    }
  };

  return (
    <div className="flex flex-col h-full bg-[#efeae2]">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 bg-white flex items-center justify-between shadow-sm z-20">
        {/* ЛІВА ЧАСТИНА: Таймер + Інфо про контакт */}
        <div className="flex items-center gap-3">
          {/* ТАЙМЕР СЕСІЇ */}
          <SessionTimer lastIncomingAt={contact.last_incoming_message_at} />

          {/* ІМ'Я ТА ТЕЛЕФОН */}
          <div>
            {isEditingName ? (
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={editedName}
                  onChange={(e) => setEditedName(e.target.value)}
                  className="border border-gray-300 rounded px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                  autoFocus
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleSaveName();
                    if (e.key === "Escape") setIsEditingName(false);
                  }}
                />
                <button
                  onClick={handleSaveName}
                  className="text-green-600 hover:text-green-800 p-1"
                  title="Save"
                >
                  <Check size={18} />
                </button>
                <button
                  onClick={() => setIsEditingName(false)}
                  className="text-gray-400 hover:text-gray-600 p-1"
                  title="Cancel"
                >
                  <X size={18} />
                </button>
              </div>
            ) : (
              <h2 className="text-lg font-semibold text-gray-900 leading-tight">
                {contact.name || contact.phone_number}
              </h2>
            )}
            {!isEditingName && (
              <p className="text-sm text-gray-600">{contact.phone_number}</p>
            )}
          </div>
        </div>

        {/* ПРАВА ЧАСТИНА: Теги та Дії */}
        <div className="flex items-center gap-2 relative">
          <div className="flex gap-1 flex-wrap justify-end max-w-[300px]">
            {contact.tags?.map((tag) => (
              <span
                key={tag.id}
                className="text-xs px-2 py-1 rounded-full text-white whitespace-nowrap"
                style={{ backgroundColor: tag.color }}
              >
                {tag.name}
              </span>
            ))}
          </div>

          <ContactActionsMenu
            contact={contact}
            onUpdate={(c) => onContactUpdate && onContactUpdate(c)}
            onDelete={(id) => onContactDelete && onContactDelete(id)}
            onEditTags={() => setIsTagSelectorOpen(true)}
            onEditNameClick={() => {
              setEditedName(contact.name || "");
              setIsEditingName(true);
            }}
          />

          <TagSelector
            isOpen={isTagSelectorOpen}
            onClose={() => setIsTagSelectorOpen(false)}
            availableTags={availableTags}
            selectedTags={contact.tags || []}
            onAssignTags={onUpdateTags}
            onCreateTag={onCreateTag}
            onDeleteTag={onDeleteTag}
            onEditTag={onEditTag}
          />
        </div>
      </div>

      {/* Messages Area */}
      <div
        ref={messagesContainerRef}
        className="flex-1 overflow-y-auto p-4 space-y-2 relative"
      >
        {loading ? (
          <div className="flex items-center justify-center h-full text-gray-500">
            Завантаження...
          </div>
        ) : !messages.length ? (
          <div className="flex items-center justify-center h-full text-gray-400 text-sm">
            Немає повідомлень. Почніть спілкування.
          </div>
        ) : (
          <>
            {/* Кнопка завантаження старіших повідомлень */}
            {hasMoreMessages && onLoadOlderMessages && (
              <div className="flex justify-center mb-4">
                <button
                  onClick={handleLoadOlder}
                  disabled={loadingOlderMessages}
                  className="px-4 py-2 text-sm text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loadingOlderMessages ? (
                    <span className="flex items-center gap-2">
                      <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
                      Завантаження...
                    </span>
                  ) : (
                    "Завантажити старіші повідомлення"
                  )}
                </button>
              </div>
            )}
            {messages.map((message, index) => {
              const isOutbound = message.direction === MessageDirection.OUTBOUND;
              const repliedMessage = getReplyingToMessage(
                message.reply_to_message_id,
              );
              const hasReaction = !!message.reaction;
              const paddingClass = hasReaction ? "pt-2 pb-5 px-3" : "py-2 px-3";

              // Date Separation Logic
              const currentDate = message.sent_at || message.scheduled_at || message.created_at || "";
              const previousDate = index > 0
                ? (messages[index - 1].sent_at || messages[index - 1].scheduled_at || messages[index - 1].created_at || "")
                : "";

              const currentDayId = getDateIdentifier(currentDate);
              const previousDayId = getDateIdentifier(previousDate);
              const showDateSeparator = index === 0 || currentDayId !== previousDayId;

              // Debug logging for failed messages
              if (message.status === MessageStatus.FAILED) {
                console.log('Failed message:', {
                  id: message.id,
                  status: message.status,
                  error_code: message.error_code,
                  error_message: message.error_message
                });
              }

              return (
                <React.Fragment key={message.id}>
                  {showDateSeparator && currentDayId && (
                    <DateSeparator date={currentDate} />
                  )}
                  <div
                    className={`flex ${isOutbound ? "justify-end" : "justify-start"} group ${hasReaction ? "mb-4" : "mb-1"}`}
                  >
                    <div
                      className={`relative max-w-[85%] lg:max-w-[70%] ${paddingClass} rounded-lg shadow-sm text-sm leading-relaxed
                    ${isOutbound
                          ? "bg-[#d9fdd3] text-gray-900 rounded-tr-none"
                          : "bg-white text-gray-900 rounded-tl-none"
                        }`}
                    >
                      {repliedMessage && (
                        <div
                          className={`mb-2 p-2 rounded border-l-4 text-xs cursor-pointer opacity-80
                      ${isOutbound ? "bg-[#cfe9c6] border-green-600" : "bg-gray-100 border-gray-400"}`}
                          onClick={() => {
                            const el = document.getElementById(
                              `msg-${repliedMessage.id}`,
                            );
                            el?.scrollIntoView({
                              behavior: "smooth",
                              block: "center",
                            });
                          }}
                        >
                          <div className="font-bold text-gray-700 mb-1">
                            {repliedMessage.direction === MessageDirection.OUTBOUND
                              ? "Ви"
                              : contact.name || contact.phone_number}
                          </div>
                          <div className="truncate line-clamp-1">
                            {repliedMessage.body || "Медіа файл"}
                          </div>
                        </div>
                      )}

                      <div id={`msg-${message.id}`}>
                        {/* Media Files */}
                        {message.media_files?.length > 0 && (
                          <div className="mb-2 grid gap-1">
                            {message.media_files?.map((media) => (
                              <div
                                key={media.id}
                                className="rounded overflow-hidden"
                              >
                                <a
                                  href={media.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="flex items-center gap-2 p-3 bg-black/5 rounded-lg hover:bg-black/10 transition border border-black/5"
                                >
                                  <Paperclip className="w-5 h-5 text-gray-600" />
                                  <span className="underline decoration-dotted">
                                    {media.file_name}
                                  </span>
                                </a>
                              </div>
                            ))}
                          </div>
                        )}

                        {message.body && (
                          <div className="whitespace-pre-wrap">{message.body}</div>
                        )}
                      </div>

                      <div className="flex items-center justify-end gap-1 mt-1 select-none">
                        <span className="text-[10px] text-gray-500">
                          {formatMessageTime(message.sent_at || message.scheduled_at || message.created_at)}
                        </span>
                        {isOutbound && (
                          <span
                            onClick={(e) => {
                              if (message.scheduled_at) {
                                e.stopPropagation();
                                const rect = e.currentTarget.getBoundingClientRect();
                                setScheduledMessageMenu({
                                  messageId: message.id,
                                  x: rect.left,
                                  y: rect.bottom + 5,
                                });
                              }
                            }}
                            className={`text-[10px] ${getStatusClass(message.status)} ${message.scheduled_at ? "cursor-pointer" : "cursor-help"} flex items-center justify-center`}
                            title={
                              message.status === MessageStatus.FAILED
                                ? `Помилка: ${message.error_message || "Невідома помилка"}`
                                : message.scheduled_at
                                  ? `Статус: ${message.status}\nЗаплановано на: ${new Date(
                                    message.scheduled_at,
                                  ).toLocaleString("uk-UA")}`
                                  : `Статус: ${message.status}`
                            }
                          >
                            {getStatusIcon(message.status)}
                          </span>
                        )}
                      </div>

                      {message.reaction && (
                        <div
                          className={`absolute -bottom-3 ${isOutbound ? "right-0" : "left-0"}
                      bg-white rounded-full px-1.5 py-0.5 shadow-sm text-base border border-gray-100 z-10`}
                        >
                          {message.reaction}
                        </div>
                      )}

                      <button
                        onClick={() => setReplyTo(message)}
                        className={`absolute top-0 ${isOutbound ? "-left-8" : "-right-8"}
                      opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-gray-600 transition-opacity`}
                        title="Відповісти"
                      >
                        <CornerUpLeft className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </React.Fragment>
              );
            })}
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="bg-gray-100 p-2">
        {/* Reply Preview */}
        {replyTo && !selectedFile && (
          <div className="flex justify-between items-center bg-white p-2 mb-2 rounded-lg border-l-4 border-blue-500 shadow-sm mx-2">
            <div className="text-sm overflow-hidden">
              <span className="text-blue-600 font-semibold text-xs block mb-0.5">
                Відповідь для:{" "}
                {replyTo.direction === MessageDirection.OUTBOUND
                  ? "Ви"
                  : contact.name || contact.phone_number}
              </span>
              <div className="text-gray-500 truncate">
                {replyTo.body || "Медіа файл"}
              </div>
            </div>
            <button
              onClick={() => setReplyTo(null)}
              className="text-gray-400 hover:text-gray-600 p-1"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* File Preview */}
        {selectedFile && (
          <div className="flex justify-between items-center bg-white p-2 mb-2 rounded-lg border-l-4 border-green-500 shadow-sm mx-2">
            <div className="flex items-center gap-3 overflow-hidden">
              <div className="bg-gray-100 p-2 rounded">
                <Paperclip className="w-5 h-5 text-gray-600" />
              </div>
              <div className="text-sm">
                <span className="font-semibold text-gray-700 block">
                  Відправка файлу:
                </span>
                <span className="text-gray-500 truncate block max-w-[200px]">
                  {selectedFile.name}
                </span>
              </div>
            </div>
            <button
              onClick={() => {
                setSelectedFile(null);
                if (fileInputRef.current) fileInputRef.current.value = "";
              }}
              className="text-gray-400 hover:text-gray-600 p-1"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        <div
          className={`flex gap-2 items-end bg-white p-2 rounded-2xl border border-gray-200 shadow-sm ${isSessionExpired ? "bg-gray-50" : ""}`}
        >
          <input
            type="file"
            ref={fileInputRef}
            className="hidden"
            onChange={handleFileSelect}
            disabled={isSessionExpired} // Блокування файлів
          />

          <button
            onClick={() => setIsQuickReplyPickerOpen(true)}
            ref={quickReplyButtonRef}
            className={`p-2 text-yellow-500 hover:text-yellow-600 hover:bg-yellow-50 rounded-full transition-colors w-10 h-10 flex items-center justify-center ${isSessionExpired ? "opacity-50 cursor-not-allowed" : ""}`}
            title="Швидкі відповіді"
            disabled={isSessionExpired}
          >
            <Zap className="w-5 h-5" />
          </button>

          <button
            onClick={() => fileInputRef.current?.click()}
            className={`p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-full transition-colors w-10 h-10 flex items-center justify-center ${isSessionExpired ? "opacity-50 cursor-not-allowed" : ""}`}
            title="Прикріпити файл"
            disabled={isSessionExpired}
          >
            <Link className="w-5 h-5" />
          </button>

          <textarea
            ref={textareaRef}
            value={messageText}
            onChange={(e) => {
              setMessageText(e.target.value);
              // Auto-resize
              if (textareaRef.current) {
                textareaRef.current.style.height = "40px";
                textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
              }
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder={
              isSessionExpired
                ? "Сесія закрита (24г). Використайте шаблон."
                : selectedFile
                  ? "Додати підпис..."
                  : "Написати повідомлення..."
            }
            className="flex-1 px-2 py-2 bg-transparent outline-none text-gray-800 placeholder-gray-400 overflow-y-auto resize-none disabled:text-gray-400"
            rows={1}
            style={{ minHeight: "40px" }}
            disabled={isSessionExpired} // Блокування тексту
          />

          {/* Schedule Button */}
          <button
            onClick={() => setShowSchedulePicker(!showSchedulePicker)}
            className={`p-2 hover:bg-gray-100 rounded-full transition-colors w-10 h-10 flex items-center justify-center ${isSessionExpired ? "opacity-50 cursor-not-allowed" : ""} ${scheduledAt ? "text-orange-500" : "text-gray-500 hover:text-gray-700"}`}
            title={scheduledAt ? `Заплановано на ${new Date(scheduledAt).toLocaleString('uk-UA')}` : "Запланувати відправку"}
            disabled={isSessionExpired}
          >
            <Calendar className="w-5 h-5" />
          </button>

          <button
            onClick={handleSend}
            disabled={
              (!messageText.trim() && !selectedFile) || isSessionExpired
            }
            className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-full transition-colors w-10 h-10 flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSessionExpired ? (
              <Lock className="w-5 h-5" />
            ) : (
              <Send className="w-5 h-5" />
            )}
          </button>
        </div>

        {/* Schedule Picker Modal */}
        {showSchedulePicker && (
          <div className="absolute bottom-16 right-4 bg-white rounded-lg shadow-2xl border border-gray-200 p-4 z-50 min-w-[300px]">
            <div className="flex justify-between items-center mb-3">
              <h3 className="font-semibold text-gray-800">Запланувати відправку</h3>
              <button
                onClick={() => setShowSchedulePicker(false)}
                className="text-gray-400 hover:text-gray-600 p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3">
              {/* Session Based Scheduling */}
              {contact.last_incoming_message_at && (() => {
                const lastMsgTime = new Date(contact.last_incoming_message_at).getTime();
                const sessionEnd = lastMsgTime + 24 * 60 * 60 * 1000;
                const now = Date.now();

                if (sessionEnd <= now) return null; // Session expired

                const timeLeftMs = sessionEnd - now;
                const timeLeftHours = timeLeftMs / (1000 * 60 * 60);

                const setRelativeTime = (minutesBeforeEnd: number) => {
                  const targetTime = new Date(sessionEnd - minutesBeforeEnd * 60 * 1000);
                  if (targetTime.getTime() > now) {
                    setScheduledAt(targetTime.toISOString());
                  }
                };

                return (
                  <div className="mb-3 p-2 bg-blue-50 rounded-lg border border-blue-100">
                    <div className="text-xs font-medium text-blue-800 mb-2 flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      До кінця сесії: {Math.floor(timeLeftHours)}г {Math.floor((timeLeftMs % (3600000)) / 60000)}хв
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      {timeLeftMs > 15 * 60000 && (
                        <button
                          onClick={() => setRelativeTime(15)}
                          className="text-xs bg-white border border-blue-200 text-blue-700 px-2 py-1.5 rounded hover:bg-blue-100 transition-colors"
                        >
                          За 15 хв до кінця
                        </button>
                      )}
                      {timeLeftMs > 60 * 60000 && (
                        <button
                          onClick={() => setRelativeTime(60)}
                          className="text-xs bg-white border border-blue-200 text-blue-700 px-2 py-1.5 rounded hover:bg-blue-100 transition-colors"
                        >
                          За 1 год до кінця
                        </button>
                      )}
                      {timeLeftMs > 120 * 60000 && (
                        <button
                          onClick={() => setRelativeTime(120)}
                          className="text-xs bg-white border border-blue-200 text-blue-700 px-2 py-1.5 rounded hover:bg-blue-100 transition-colors"
                        >
                          За 2 год до кінця
                        </button>
                      )}
                      {timeLeftMs > 180 * 60000 && (
                        <button
                          onClick={() => setRelativeTime(180)}
                          className="text-xs bg-white border border-blue-200 text-blue-700 px-2 py-1.5 rounded hover:bg-blue-100 transition-colors"
                        >
                          За 3 год до кінця
                        </button>
                      )}
                    </div>
                  </div>
                );
              })()}

              <div>
                <label className="block text-sm text-gray-600 mb-1">Дата і час</label>
                <input
                  type="datetime-local"
                  value={(() => {
                    if (!scheduledAt) return '';
                    const date = new Date(scheduledAt);
                    const offsetMs = date.getTimezoneOffset() * 60000;
                    const localDate = new Date(date.getTime() - offsetMs);
                    return localDate.toISOString().slice(0, 16);
                  })()}
                  onChange={(e) => {
                    if (e.target.value) {
                      setScheduledAt(new Date(e.target.value).toISOString());
                    } else {
                      setScheduledAt(null);
                    }
                  }}
                  min={(() => {
                    const date = new Date();
                    const offsetMs = date.getTimezoneOffset() * 60000;
                    const localDate = new Date(date.getTime() - offsetMs);
                    return localDate.toISOString().slice(0, 16);
                  })()}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              {scheduledAt && (
                <div className="text-xs text-gray-500 bg-orange-50 border border-orange-200 rounded p-2">
                  📅 Буде відправлено: {new Date(scheduledAt).toLocaleString('uk-UA')}
                </div>
              )}

              <div className="flex gap-2">
                {scheduledAt && (
                  <button
                    onClick={() => {
                      setScheduledAt(null);
                    }}
                    className="flex-1 px-3 py-2 text-sm text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg transition-colors"
                  >
                    Скасувати
                  </button>
                )}
                <button
                  onClick={() => {
                    setShowSchedulePicker(false);
                  }}
                  disabled={!scheduledAt}
                  className="flex-1 px-3 py-2 text-sm bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Готово
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Scheduled Message Context Menu */}
      {
        scheduledMessageMenu &&
        (() => {
          const msg = messages.find(
            (m) => m.id === scheduledMessageMenu.messageId
          );
          if (!msg) return null;

          return (
            <>
              <div
                className="fixed inset-0 z-[100]"
                onClick={() => setScheduledMessageMenu(null)}
              />
              <div
                className="fixed z-[101] bg-white rounded-lg shadow-2xl border border-gray-200 py-1 min-w-[180px]"
                style={{
                  left: `${scheduledMessageMenu.x}px`,
                  top: `${scheduledMessageMenu.y}px`,
                }}
              >
                {msg.status === MessageStatus.PENDING ? (
                  <>
                    <button
                      onClick={() =>
                        handleSendScheduledNow(scheduledMessageMenu.messageId)
                      }
                      className="w-full px-4 py-2 text-left text-sm hover:bg-blue-50 text-blue-600 font-medium flex items-center gap-2"
                    >
                      <Send className="w-4 h-4" />
                      Відправити зараз
                    </button>
                    <button
                      onClick={() =>
                        handleDeleteScheduledMessage(
                          scheduledMessageMenu.messageId
                        )
                      }
                      className="w-full px-4 py-2 text-left text-sm hover:bg-red-50 text-red-600 font-medium flex items-center gap-2"
                    >
                      <X className="w-4 h-4" />
                      Видалити
                    </button>
                  </>
                ) : (
                  <div className="px-4 py-2 text-sm text-gray-500 text-center">
                    Status: {msg.status}
                  </div>
                )}
              </div>
            </>
          );
        })()
      }

      {/* Quick Reply Picker */}
      <QuickReplyPicker
        isOpen={isQuickReplyPickerOpen}
        onClose={() => setIsQuickReplyPickerOpen(false)}
        onSelect={handleQuickReplySelect}
        language={selectedLanguage}
        buttonRef={quickReplyButtonRef}
      />
    </div >
  );
};

export default ChatWindow;
