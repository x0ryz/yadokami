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
import { apiClient } from "../../api";
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

// --- ОСНОВНИЙ КОМПОНЕНТ ---

interface ChatWindowProps {
  contact: Contact;
  messages: MessageResponse[];
  loading: boolean;
  onSendMessage: (phone: string, text: string, replyToId?: string) => void;
  onSendMedia: (phone: string, file: File, caption?: string) => void;

  onContactUpdate?: (contact: Contact) => void;
  onContactDelete?: (contactId: string) => void;

  availableTags: Tag[];
  onUpdateTags: (tagIds: string[]) => void;
  onCreateTag: (tag: TagCreate) => Promise<void>;
  onDeleteTag: (tagId: string) => Promise<void>;
  onEditTag: (tagId: string, data: TagUpdate) => Promise<void>;
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
}) => {
  const [messageText, setMessageText] = useState("");
  const [replyTo, setReplyTo] = useState<MessageResponse | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isTagSelectorOpen, setIsTagSelectorOpen] = useState(false);

  // Editing Name State
  const [isEditingName, setIsEditingName] = useState(false);
  const [editedName, setEditedName] = useState("");

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Перевірка чи сесія активна
  const isSessionExpired = React.useMemo(() => {
    if (!contact.last_incoming_message_at) return true;
    const end =
      new Date(contact.last_incoming_message_at).getTime() +
      24 * 60 * 60 * 1000;
    return Date.now() > end;
  }, [contact.last_incoming_message_at]);

  useEffect(() => {
    scrollToBottom("auto");
    setSelectedFile(null);
    setMessageText("");
    setIsTagSelectorOpen(false);
    setIsEditingName(false);
  }, [contact.id]);

  useEffect(() => {
    scrollToBottom("smooth");
  }, [messages, replyTo, selectedFile]);

  const scrollToBottom = (behavior: ScrollBehavior = "smooth") => {
    setTimeout(() => {
      messagesEndRef.current?.scrollIntoView({ behavior });
    }, 100);
  };

  const handleSend = () => {
    if (selectedFile) {
      onSendMedia(contact.phone_number, selectedFile, messageText);
      setSelectedFile(null);
      setMessageText("");
      setReplyTo(null);
    } else if (messageText.trim()) {
      onSendMessage(contact.phone_number, messageText, replyTo?.id);
      setMessageText("");
      setReplyTo(null);
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
      <div className="flex-1 overflow-y-auto p-4 space-y-2 relative">
        {loading ? (
          <div className="flex items-center justify-center h-full text-gray-500">
            Завантаження...
          </div>
        ) : !messages.length ? (
          <div className="flex items-center justify-center h-full text-gray-400 text-sm">
            Немає повідомлень. Почніть спілкування.
          </div>
        ) : (
          messages.map((message) => {
            const isOutbound = message.direction === MessageDirection.OUTBOUND;
            const repliedMessage = getReplyingToMessage(
              message.reply_to_message_id,
            );
            const hasReaction = !!message.reaction;
            const paddingClass = hasReaction ? "pt-2 pb-5 px-3" : "py-2 px-3";

            return (
              <div
                key={message.id}
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
                        {message.media_files.map((media) => (
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
                      {formatMessageTime(message.created_at)}
                    </span>
                    {isOutbound && (
                      <span
                        className={`text-[10px] ${getStatusClass(message.status)}`}
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
            );
          })
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
            onClick={() => fileInputRef.current?.click()}
            className={`p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-full transition-colors w-10 h-10 flex items-center justify-center ${isSessionExpired ? "opacity-50 cursor-not-allowed" : ""}`}
            title="Прикріпити файл"
            disabled={isSessionExpired}
          >
            <Link className="w-5 h-5" />
          </button>

          <textarea
            value={messageText}
            onChange={(e) => setMessageText(e.target.value)}
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
            className="flex-1 max-h-32 px-2 py-2 bg-transparent outline-none text-gray-800 placeholder-gray-400 overflow-y-auto resize-none disabled:text-gray-400"
            rows={1}
            style={{ minHeight: "40px" }}
            disabled={isSessionExpired} // Блокування тексту
          />
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
      </div>
    </div>
  );
};

export default ChatWindow;
