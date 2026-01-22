import React, { useState, useEffect } from "react";
import { MessageType, Template } from "../../types";
import { apiClient } from "../../api";

interface MessagePreviewProps {
  messageType: string;
  templateId: string | null;
  messageBody: string | null;
}

const MessagePreview: React.FC<MessagePreviewProps> = ({
  messageType,
  templateId,
  messageBody,
}) => {
  const [template, setTemplate] = useState<Template | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (messageType === MessageType.TEMPLATE && templateId) {
      loadTemplate();
    }
  }, [messageType, templateId]);

  const loadTemplate = async () => {
    if (!templateId) return;
    try {
      setLoading(true);
      const templates = await apiClient.listTemplates();
      const found = templates.find((t) => t.id === templateId);
      setTemplate(found || null);
    } catch (error) {
      console.error("Помилка завантаження шаблону:", error);
    } finally {
      setLoading(false);
    }
  };

  const renderTemplateContent = () => {
    if (!template) return null;

    const headerComponent = template.components.find((c) => c.type === "HEADER");
    const bodyComponent = template.components.find((c) => c.type === "BODY");
    const footerComponent = template.components.find((c) => c.type === "FOOTER");
    const buttonsComponent = template.components.find((c) => c.type === "BUTTONS");

    return (
      <div className="space-y-2">
        {/* Header */}
        {headerComponent && (
          <div>
            {headerComponent.format === "IMAGE" && (
              <div className="w-full h-40 bg-gray-200 rounded-t-lg flex items-center justify-center mb-2">
                <svg
                  className="w-12 h-12 text-gray-400"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                  />
                </svg>
              </div>
            )}
            {headerComponent.format === "VIDEO" && (
              <div className="w-full h-40 bg-gray-200 rounded-t-lg flex items-center justify-center mb-2">
                <svg
                  className="w-12 h-12 text-gray-400"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"
                  />
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
              </div>
            )}
            {headerComponent.format === "DOCUMENT" && (
              <div className="w-full h-16 bg-gray-100 rounded-lg flex items-center px-3 gap-3 mb-2">
                <svg
                  className="w-8 h-8 text-gray-400"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
                <span className="text-sm text-gray-600">Документ</span>
              </div>
            )}
            {headerComponent.format === "TEXT" && headerComponent.text && (
              <div className="font-semibold text-gray-900 text-sm">
                {headerComponent.text}
              </div>
            )}
          </div>
        )}

        {/* Body */}
        {bodyComponent?.text && (
          <div className="text-gray-900 text-sm whitespace-pre-wrap leading-relaxed">
            {bodyComponent.text}
          </div>
        )}

        {/* Footer */}
        {footerComponent?.text && (
          <div className="text-xs text-gray-500 pt-1">
            {footerComponent.text}
          </div>
        )}

        {/* Buttons */}
        {buttonsComponent?.buttons && buttonsComponent.buttons.length > 0 && (
          <div className="pt-2 border-t border-gray-100 mt-2 -mx-3 -mb-3">
            {buttonsComponent.buttons.map((button, idx) => (
              <button
                key={idx}
                className="w-full py-2.5 px-4 text-blue-600 text-sm font-medium hover:bg-gray-50 transition-colors flex items-center justify-center gap-2 border-b border-gray-100 last:border-b-0 last:rounded-b-lg"
                disabled
              >
                {button.type === "URL" && (
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                  </svg>
                )}
                {button.type === "PHONE_NUMBER" && (
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
                  </svg>
                )}
                {button.text}
              </button>
            ))}
          </div>
        )}
      </div>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="text-gray-500 text-sm">Завантаження...</div>
      </div>
    );
  }

  return (
    <div className="bg-[#efeae2] p-4 rounded-lg min-h-[200px] flex items-start">
      <div className="w-full max-w-sm">
        {/* Message bubble - similar to ChatWindow style */}
        <div className="bg-white rounded-lg rounded-tl-none shadow-sm p-3 relative">
          {messageType === MessageType.TEMPLATE ? (
            template ? (
              renderTemplateContent()
            ) : (
              <div className="text-gray-500 text-sm">
                Шаблон не знайдено
              </div>
            )
          ) : messageBody ? (
            <div className="text-gray-900 text-sm whitespace-pre-wrap leading-relaxed">
              {messageBody}
            </div>
          ) : (
            <div className="text-gray-400 text-sm italic">
              Текст повідомлення не вказано
            </div>
          )}
          
          {/* Time stamp */}
          <div className="flex items-center justify-end gap-1 mt-1">
            <span className="text-[11px] text-gray-400">
              {new Date().toLocaleTimeString("uk-UA", {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MessagePreview;
