import React, { useEffect, useState } from "react";
import { apiClient } from "../api";
import { WabaSettingsResponse } from "../types";
import { AlertCircle, Loader, Save, Check, RefreshCw } from "lucide-react";

interface WabaSettings {
  waba_id: string;
  name: string;
  access_token?: string;
  app_secret?: string;
  verify_token?: string;
  graph_api_version?: string;
}

const SettingsPage: React.FC = () => {
  const [account, setAccount] = useState<WabaSettingsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Form state
  const [formData, setFormData] = useState<WabaSettings>({
    waba_id: "",
    name: "My Business",
    access_token: "",
    app_secret: "",
    verify_token: "",
    graph_api_version: "v21.0",
  });

  const [isSaving, setIsSaving] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);

  // Завантажуємо дані акаунту при завантаженні сторінки
  useEffect(() => {
    loadAccountData();
  }, []);

  const loadAccountData = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const settings = await apiClient.getWabaSettings();
      
      if (settings) {
        setAccount(settings);
        setFormData({
          waba_id: settings.waba_id || "",
          name: settings.name || "My Business",
          access_token: "",
          app_secret: "",
          verify_token: "",
          graph_api_version: settings.graph_api_version || "v21.0",
        });
      }
    } catch (err: any) {
      console.error("Failed to load account data:", err);
      if (err.response?.status !== 404) {
        setError("Не вдалося завантажити дані акаунту");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));
    setSuccess(false);
  };

  const handleSync = async () => {
    try {
      setIsSyncing(true);
      setError(null);
      setSuccess(false);

      await apiClient.triggerWabaSync();
      
      setSuccess(true);
      setError(null);
      
      // Reload data after sync
      setTimeout(() => {
        loadAccountData();
      }, 2000);
      
      // Hide success message after 3 seconds
      setTimeout(() => setSuccess(false), 3000);
    } catch (err: any) {
      console.error("Failed to trigger sync:", err);
      setError(
        err.response?.data?.detail || "Не вдалося розпочати синхронізацію"
      );
    } finally {
      setIsSyncing(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    if (!formData.waba_id.trim()) {
      setError("ID акаунту не може бути пустим");
      return;
    }

    try {
      setIsSaving(true);
      setError(null);
      setSuccess(false);

      const payload: any = {
        waba_id: formData.waba_id.trim(),
        name: formData.name.trim(),
        graph_api_version: formData.graph_api_version,
      };

      // Only include tokens if they are provided
      if (formData.access_token?.trim()) {
        payload.access_token = formData.access_token.trim();
      }
      if (formData.app_secret?.trim()) {
        payload.app_secret = formData.app_secret.trim();
      }
      if (formData.verify_token?.trim()) {
        payload.verify_token = formData.verify_token.trim();
      }

      const response = await apiClient.updateWabaSettings(payload);

      setAccount(response);
      setSuccess(true);
      
      // Clear sensitive fields after saving
      setFormData(prev => ({
        ...prev,
        access_token: "",
        app_secret: "",
        verify_token: "",
      }));

      // Приховуємо повідомлення про успіх через 3 секунди
      setTimeout(() => setSuccess(false), 3000);
    } catch (err: any) {
      console.error("Failed to update account:", err);
      setError(
        err.response?.data?.detail || "Не вдалося зберегти дані акаунту"
      );
    } finally {
      setIsSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="flex flex-col items-center gap-2">
          <Loader className="w-8 h-8 text-blue-600 animate-spin" />
          <p className="text-gray-600">Завантаження...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">Налаштування WABA</h1>
        <button
          onClick={handleSync}
          disabled={isSyncing}
          className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md font-medium hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <RefreshCw className={`w-4 h-4 ${isSyncing ? "animate-spin" : ""}`} />
          {isSyncing ? "Синхронізація..." : "Синхронізувати"}
        </button>
      </div>

      {/* Повідомлення про помилку */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
          <div>
            <h3 className="font-medium text-red-900">Помилка</h3>
            <p className="text-sm text-red-700">{error}</p>
          </div>
        </div>
      )}

      {/* Повідомлення про успіх */}
      {success && (
        <div className="p-4 bg-green-50 border border-green-200 rounded-lg flex items-start gap-3">
          <Check className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
          <div>
            <h3 className="font-medium text-green-900">Успішно</h3>
            <p className="text-sm text-green-700">
              {isSyncing ? "Синхронізацію розпочато" : "Дані акаунту успішно оновлені"}
            </p>
          </div>
        </div>
      )}

      {/* Форма */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-6">
          Дані WABA акаунту
        </h2>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* WABA ID */}
          <div>
            <label htmlFor="waba_id" className="block text-sm font-medium text-gray-700 mb-2">
              WABA ID <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              id="waba_id"
              name="waba_id"
              value={formData.waba_id}
              onChange={handleInputChange}
              placeholder="1234567890"
              required
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            />
            <p className="mt-1 text-xs text-gray-500">
              WhatsApp Business Account ID з Meta Business Manager
            </p>
          </div>

          {/* Account Name */}
          <div>
            <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-2">
              Назва бізнесу <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              id="name"
              name="name"
              value={formData.name}
              onChange={handleInputChange}
              placeholder="My Business"
              required
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            />
            <p className="mt-1 text-xs text-gray-500">
              Назва вашого бізнесу
            </p>
          </div>

          {/* Access Token */}
          <div>
            <label htmlFor="access_token" className="block text-sm font-medium text-gray-700 mb-2">
              Access Token
            </label>
            <input
              type="password"
              id="access_token"
              name="access_token"
              value={formData.access_token}
              onChange={handleInputChange}
              placeholder="Залиште порожнім, якщо не змінюєте"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            />
            <p className="mt-1 text-xs text-gray-500">
              System User Access Token з Meta Business Manager
            </p>
          </div>

          {/* App Secret */}
          <div>
            <label htmlFor="app_secret" className="block text-sm font-medium text-gray-700 mb-2">
              App Secret
            </label>
            <input
              type="password"
              id="app_secret"
              name="app_secret"
              value={formData.app_secret}
              onChange={handleInputChange}
              placeholder="Залиште порожнім, якщо не змінюєте"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            />
            <p className="mt-1 text-xs text-gray-500">
              App Secret з Meta App Dashboard
            </p>
          </div>

          {/* Verify Token */}
          <div>
            <label htmlFor="verify_token" className="block text-sm font-medium text-gray-700 mb-2">
              Verify Token
            </label>
            <input
              type="password"
              id="verify_token"
              name="verify_token"
              value={formData.verify_token}
              onChange={handleInputChange}
              placeholder="Залиште порожнім, якщо не змінюєте"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            />
            <p className="mt-1 text-xs text-gray-500">
              Verify Token для webhook верифікації
            </p>
          </div>

          {/* Graph API Version */}
          <div>
            <label htmlFor="graph_api_version" className="block text-sm font-medium text-gray-700 mb-2">
              Graph API Version
            </label>
            <input
              type="text"
              id="graph_api_version"
              name="graph_api_version"
              value={formData.graph_api_version}
              onChange={handleInputChange}
              placeholder="v21.0"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            />
            <p className="mt-1 text-xs text-gray-500">
              Версія Meta Graph API (наприклад, v21.0)
            </p>
          </div>

          {/* Кнопка збереження */}
          <div className="flex gap-3 pt-4">
            <button
              type="submit"
              disabled={isSaving}
              className="inline-flex items-center gap-2 px-6 py-2 bg-green-600 text-white rounded-md font-medium hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSaving ? (
                <>
                  <Loader className="w-4 h-4 animate-spin" />
                  Збереження...
                </>
              ) : (
                <>
                  <Save className="w-4 h-4" />
                  Зберегти
                </>
              )}
            </button>
          </div>
        </form>

        {/* Info Section */}
        <div className="mt-8 pt-8 border-t border-gray-200">
          <h3 className="text-sm font-semibold text-gray-900 mb-3">
            Інформація
          </h3>
          <div className="space-y-2 text-sm text-gray-600">
            <p>• Токени та секрети автоматично шифруються при збереженні</p>
            <p>• Після збереження поля з токенами очищаються з міркувань безпеки</p>
            <p>• Синхронізація оновлює інформацію про акаунт та телефонні номери</p>
            <p>
              • Для отримання токенів відвідайте{" "}
              <a
                href="https://developers.facebook.com"
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline"
              >
                Meta for Developers
              </a>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SettingsPage;
