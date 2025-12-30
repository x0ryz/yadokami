import React, { useState, useEffect, useCallback } from 'react';
import { apiClient } from '../api';
import { Template } from '../types';

const TemplatesPage: React.FC = () => {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('all');

  const loadTemplates = useCallback(async () => {
    try {
      setLoading(true);
      let data: Template[];
      if (statusFilter === 'all') {
        data = await apiClient.listTemplates();
      } else {
        data = await apiClient.getTemplatesByStatus(statusFilter);
      }
      setTemplates(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error('Помилка завантаження шаблонів:', error);
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    loadTemplates();
  }, [loadTemplates]);

  const getStatusColor = (status: string) => {
    const statusLower = status.toLowerCase();
    if (statusLower.includes('approved')) {
      return 'bg-green-100 text-green-800';
    } else if (statusLower.includes('pending')) {
      return 'bg-yellow-100 text-yellow-800';
    } else if (statusLower.includes('rejected')) {
      return 'bg-red-100 text-red-800';
    }
    return 'bg-gray-100 text-gray-800';
  };

  return (
    <div className="h-[calc(100vh-8rem)] flex gap-4">
      {/* Templates List */}
      <div className="w-1/3 border border-gray-200 rounded-lg bg-white overflow-hidden flex flex-col">
        <div className="p-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">Шаблони повідомлень</h2>
          <div className="flex gap-2">
            <button
              onClick={() => setStatusFilter('all')}
              className={`px-3 py-1 text-sm rounded-md transition-colors ${
                statusFilter === 'all'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Всі
            </button>
            <button
              onClick={() => setStatusFilter('APPROVED')}
              className={`px-3 py-1 text-sm rounded-md transition-colors ${
                statusFilter === 'APPROVED'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Затверджені
            </button>
            <button
              onClick={() => setStatusFilter('PENDING')}
              className={`px-3 py-1 text-sm rounded-md transition-colors ${
                statusFilter === 'PENDING'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Очікують
            </button>
            <button
              onClick={() => setStatusFilter('REJECTED')}
              className={`px-3 py-1 text-sm rounded-md transition-colors ${
                statusFilter === 'REJECTED'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Відхилені
            </button>
          </div>
        </div>

        {loading ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-gray-500">Завантаження...</div>
          </div>
        ) : templates.length === 0 ? (
          <div className="flex-1 flex items-center justify-center text-gray-500 p-4">
            Шаблони не знайдено
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto">
            {templates.map((template) => (
              <div
                key={template.id}
                onClick={() => setSelectedTemplate(template)}
                className={`p-4 border-b border-gray-100 cursor-pointer hover:bg-gray-50 transition-colors ${
                  selectedTemplate?.id === template.id ? 'bg-blue-50 border-blue-200' : ''
                }`}
              >
                <div className="flex items-start justify-between mb-2">
                  <h3 className="font-semibold text-gray-900">{template.name}</h3>
                  <span
                    className={`text-xs px-2 py-1 rounded-full ${getStatusColor(template.status)}`}
                  >
                    {template.status}
                  </span>
                </div>
                <p className="text-sm text-gray-600 mb-2">
                  <span className="font-medium">Мова:</span> {template.language}
                </p>
                <p className="text-sm text-gray-600">
                  <span className="font-medium">Категорія:</span> {template.category}
                </p>
                <p className="text-xs text-gray-500 mt-2">
                  ID: {template.meta_template_id}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Template Details */}
      <div className="flex-1 border border-gray-200 rounded-lg bg-white overflow-hidden flex flex-col">
        {selectedTemplate ? (
          <>
            <div className="p-6 border-b border-gray-200">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h2 className="text-2xl font-bold text-gray-900 mb-2">
                    {selectedTemplate.name}
                  </h2>
                  <div className="flex items-center gap-4 text-sm text-gray-600">
                    <span>
                      <span className="font-medium">Мова:</span> {selectedTemplate.language}
                    </span>
                    <span>
                      <span className="font-medium">Категорія:</span> {selectedTemplate.category}
                    </span>
                  </div>
                </div>
                <span
                  className={`text-sm px-3 py-1 rounded-full ${getStatusColor(
                    selectedTemplate.status
                  )}`}
                >
                  {selectedTemplate.status}
                </span>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-6">
              <div className="space-y-6">
                <div>
                  <h3 className="text-lg font-semibold text-gray-800 mb-3">Інформація</h3>
                  <div className="bg-gray-50 rounded-lg p-4 space-y-2">
                    <div>
                      <span className="font-medium text-gray-700">Meta Template ID:</span>
                      <p className="text-gray-900 font-mono text-sm">{selectedTemplate.meta_template_id}</p>
                    </div>
                    <div>
                      <span className="font-medium text-gray-700">WABA ID:</span>
                      <p className="text-gray-900 font-mono text-sm">{selectedTemplate.waba_id}</p>
                    </div>
                    <div>
                      <span className="font-medium text-gray-700">Створено:</span>
                      <p className="text-gray-900 text-sm">
                        {new Date(selectedTemplate.created_at).toLocaleString('uk-UA')}
                      </p>
                    </div>
                    <div>
                      <span className="font-medium text-gray-700">Оновлено:</span>
                      <p className="text-gray-900 text-sm">
                        {new Date(selectedTemplate.updated_at).toLocaleString('uk-UA')}
                      </p>
                    </div>
                  </div>
                </div>

                {selectedTemplate.components && selectedTemplate.components.length > 0 && (
                  <div>
                    <h3 className="text-lg font-semibold text-gray-800 mb-3">Компоненти</h3>
                    <div className="bg-gray-50 rounded-lg p-4">
                      <pre className="text-sm text-gray-700 whitespace-pre-wrap">
                        {JSON.stringify(selectedTemplate.components, null, 2)}
                      </pre>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-gray-500">
            Оберіть шаблон для перегляду деталей
          </div>
        )}
      </div>
    </div>
  );
};

export default TemplatesPage;

