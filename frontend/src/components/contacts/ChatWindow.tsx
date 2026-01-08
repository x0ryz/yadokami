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

interface ChatWindowProps {
  contact: Contact;
  messages: MessageResponse[];
  loading: boolean;
  onSendMessage: (phone: string, text: string, replyToId?: string) => void;
  onSendMedia: (phone: string, file: File, caption?: string) => void;

  // Нові пропси для роботи з тегами
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

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    scrollToBottom("auto");
    setSelectedFile(null);
    setMessageText("");
    setIsTagSelectorOpen(false); // Закриваємо селектор при зміні контакту
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
        return "✓";
      case MessageStatus.DELIVERED:
        return "✓✓";
      case MessageStatus.READ:
        return "✓✓";
      case MessageStatus.FAILED:
        return "!";
      default:
        return "🕒";
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

  return (
    <div className="flex flex-col h-full bg-[#efeae2]">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 bg-white flex items-center justify-between shadow-sm z-20">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">
            {contact.name || contact.phone_number}
          </h2>
          <p className="text-sm text-gray-600">{contact.phone_number}</p>
        </div>

        {/* Блок тегів */}
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

          <button
            onClick={() => setIsTagSelectorOpen(!isTagSelectorOpen)}
            className={`p-1.5 rounded-full transition-colors ${
              isTagSelectorOpen
                ? "bg-blue-100 text-blue-600"
                : "text-gray-400 hover:text-blue-600 hover:bg-blue-50"
            }`}
            title="Редагувати теги"
          >
            ✏️
          </button>

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
                    ${
                      isOutbound
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
                            {media.file_mime_type.startsWith("image/") ? (
                              <img
                                src={media.url}
                                alt="media"
                                className="max-w-full h-auto rounded-lg"
                                loading="lazy"
                              />
                            ) : (
                              <a
                                href={media.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="flex items-center gap-2 p-3 bg-black/5 rounded-lg hover:bg-black/10 transition border border-black/5"
                              >
                                <span className="text-xl">📎</span>
                                <span className="underline decoration-dotted">
                                  {media.file_name}
                                </span>
                              </a>
                            )}
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
                    ↩️
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
              ✕
            </button>
          </div>
        )}

        {/* File Preview */}
        {selectedFile && (
          <div className="flex justify-between items-center bg-white p-2 mb-2 rounded-lg border-l-4 border-green-500 shadow-sm mx-2">
            <div className="flex items-center gap-3 overflow-hidden">
              <div className="bg-gray-100 p-2 rounded text-xl">📎</div>
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
              ✕
            </button>
          </div>
        )}

        <div className="flex gap-2 items-end bg-white p-2 rounded-2xl border border-gray-200 shadow-sm">
          <input
            type="file"
            ref={fileInputRef}
            className="hidden"
            onChange={handleFileSelect}
          />

          <button
            onClick={() => fileInputRef.current?.click()}
            className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-full transition-colors w-10 h-10 flex items-center justify-center"
            title="Прикріпити файл"
          >
            🔗
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
              selectedFile ? "Додати підпис..." : "Написати повідомлення..."
            }
            className="flex-1 max-h-32 px-2 py-2 bg-transparent outline-none text-gray-800 placeholder-gray-400 overflow-y-auto resize-none"
            rows={1}
            style={{ minHeight: "40px" }}
          />
          <button
            onClick={handleSend}
            disabled={!messageText.trim() && !selectedFile}
            className="p-2 bg-blue-600 text-white rounded-full hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-all flex-shrink-0 w-10 h-10 flex items-center justify-center"
          >
            ➤
          </button>
        </div>
      </div>
    </div>
  );
};

export default ChatWindow;
