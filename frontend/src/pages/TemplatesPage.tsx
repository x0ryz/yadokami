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
          <div className="flex gap-2 mb-3">
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
            {templates.map((template) => {
              // Get first BODY component for preview
              const bodyComponent = template.components?.find((c: any) => c.type === 'BODY');
              const previewText = bodyComponent?.text || '';
              
              return (
                <div
                  key={template.id}
                  onClick={() => setSelectedTemplate(template)}
                  className={`p-4 border-b border-gray-100 cursor-pointer hover:bg-gray-50 transition-colors ${
                    selectedTemplate?.id === template.id ? 'bg-blue-50 border-blue-200' : ''
                  } ${template.is_deleted ? 'opacity-50' : ''}`}
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <h3 className="font-semibold text-gray-900">{template.name}</h3>
                      {template.is_deleted && (
                        <span className="text-xs px-2 py-0.5 bg-red-100 text-red-700 rounded">
                          Видалено
                        </span>
                      )}
                    </div>
                    <span
                      className={`text-xs px-2 py-1 rounded-full ${getStatusColor(template.status)}`}
                    >
                      {template.status}
                    </span>
                  </div>
                  <p className="text-sm text-gray-600 mb-2">
                    <span className="font-medium">Мова:</span> {template.language}
                  </p>
                  <p className="text-sm text-gray-600 mb-2">
                    <span className="font-medium">Категорія:</span> {template.category}
                  </p>
                  {previewText && (
                    <p className="text-xs text-gray-500 line-clamp-2 mb-2 bg-gray-50 p-2 rounded">
                      {previewText.substring(0, 100)}{previewText.length > 100 ? '...' : ''}
                    </p>
                  )}
                  <div className="flex items-center justify-between">
                    <p className="text-xs text-gray-400">
                      {template.components?.length || 0} компонент{template.components?.length === 1 ? '' : 'ів'}
                    </p>
                    <p className="text-xs text-gray-400">
                      ID: {template.meta_template_id}
                    </p>
                  </div>
                </div>
              );
            })}
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
                  <div className="flex items-center gap-3 mb-2">
                    <h2 className="text-2xl font-bold text-gray-900">
                      {selectedTemplate.name}
                    </h2>
                    {selectedTemplate.is_deleted && (
                      <span className="px-3 py-1 text-sm bg-red-100 text-red-700 rounded-md font-medium">
                        Видалено з Meta
                      </span>
                    )}
                  </div>
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
                  <div className="bg-gray-50 rounded-lg p-4 space-y-3">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <span className="text-xs font-medium text-gray-500 uppercase">Meta Template ID</span>
                        <p className="text-sm text-gray-900 font-mono mt-1">{selectedTemplate.meta_template_id}</p>
                      </div>
                      <div>
                        <span className="text-xs font-medium text-gray-500 uppercase">WABA ID</span>
                        <p className="text-sm text-gray-900 font-mono mt-1">{selectedTemplate.waba_id}</p>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-4 pt-2 border-t border-gray-200">
                      <div>
                        <span className="text-xs font-medium text-gray-500 uppercase">Створено</span>
                        <p className="text-sm text-gray-900 mt-1">
                          {new Date(selectedTemplate.created_at).toLocaleString('uk-UA', {
                            day: '2-digit',
                            month: '2-digit',
                            year: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit'
                          })}
                        </p>
                      </div>
                      <div>
                        <span className="text-xs font-medium text-gray-500 uppercase">Оновлено</span>
                        <p className="text-sm text-gray-900 mt-1">
                          {new Date(selectedTemplate.updated_at).toLocaleString('uk-UA', {
                            day: '2-digit',
                            month: '2-digit',
                            year: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit'
                          })}
                        </p>
                      </div>
                    </div>
                    <div className="pt-2 border-t border-gray-200">
                      <span className="text-xs font-medium text-gray-500 uppercase">Статус синхронізації</span>
                      <p className="text-sm mt-1">
                        {selectedTemplate.is_deleted ? (
                          <span className="text-red-600 font-medium">Видалено з Meta (залишається в історії)</span>
                        ) : (
                          <span className="text-green-600 font-medium">Активний в Meta</span>
                        )}
                      </p>
                    </div>
                  </div>
                </div>

                {selectedTemplate.components && selectedTemplate.components.length > 0 && (
                  <div>
                    <h3 className="text-lg font-semibold text-gray-800 mb-3">Компоненти шаблону</h3>
                    <div className="space-y-3">
                      {selectedTemplate.components.map((component: any, index: number) => (
                        <div key={index} className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                          <div className="flex items-center gap-2 mb-2">
                            <span className="inline-block px-2 py-1 text-xs font-semibold bg-blue-100 text-blue-800 rounded">
                              {component.type}
                            </span>
                            {component.format && (
                              <span className="inline-block px-2 py-1 text-xs bg-gray-200 text-gray-700 rounded">
                                {component.format}
                              </span>
                            )}
                          </div>
                          
                          {component.text && (
                            <div className="mt-2">
                              <p className="text-sm font-medium text-gray-700 mb-1">Текст:</p>
                              <p className="text-sm text-gray-900 whitespace-pre-wrap bg-white p-3 rounded border border-gray-200">
                                {component.text}
                              </p>
                            </div>
                          )}
                          
                          {component.example && (
                            <div className="mt-2">
                              <p className="text-sm font-medium text-gray-700 mb-1">Приклад:</p>
                              <div className="text-sm text-gray-600 bg-white p-3 rounded border border-gray-200">
                                <pre className="whitespace-pre-wrap">{JSON.stringify(component.example, null, 2)}</pre>
                              </div>
                            </div>
                          )}
                          
                          {component.buttons && component.buttons.length > 0 && (
                            <div className="mt-2">
                              <p className="text-sm font-medium text-gray-700 mb-1">Кнопки:</p>
                              <div className="space-y-2">
                                {component.buttons.map((button: any, btnIndex: number) => (
                                  <div key={btnIndex} className="bg-white p-2 rounded border border-gray-200 text-sm">
                                    <span className="font-medium">{button.type}:</span> {button.text || button.url || button.phone_number}
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                          
                          {/* Show full JSON for debugging */}
                          <details className="mt-3">
                            <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-700">
                              Показати повний JSON
                            </summary>
                            <pre className="text-xs text-gray-600 mt-2 p-2 bg-white rounded border border-gray-200 overflow-x-auto">
                              {JSON.stringify(component, null, 2)}
                            </pre>
                          </details>
                        </div>
                      ))}
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

