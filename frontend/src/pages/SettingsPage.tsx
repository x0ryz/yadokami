import React, { useEffect, useState } from "react";
import apiClient from "../api/client";
import { WabaAccountStatus } from "../types";
import { AlertCircle, Loader, Save, Check } from "lucide-react";

const SettingsPage: React.FC = () => {
  const [account, setAccount] = useState<WabaAccountStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Form state
  const [formData, setFormData] = useState({
    waba_id: "",
    name: "",
  });

  const [isSaving, setIsSaving] = useState(false);

  // Завантажуємо дані акаунту при завантаженні сторінки
  useEffect(() => {
    loadAccountData();
  }, []);

  const loadAccountData = async () => {
    try {
      setLoading(true);
      setError(null);
      const wabaStatus = await apiClient.getWabaStatus();

      if (wabaStatus.accounts && wabaStatus.accounts.length > 0) {
        const currentAccount = wabaStatus.accounts[0];
        setAccount(currentAccount);
        setFormData({
          waba_id: currentAccount.waba_id,
          name: currentAccount.name,
        });
      } else {
        setFormData({
          waba_id: "",
          name: "",
        });
      }
    } catch (err) {
      console.error("Failed to load account data:", err);
      setError("Не вдалося завантажити дані акаунту");
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

      const response = await apiClient.updateWabaAccount({
        waba_id: formData.waba_id.trim(),
        name: formData.name.trim(),
      });

      setAccount(response);
      setSuccess(true);

      // Приховуємо повідомлення про успіх через 3 секунди
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      console.error("Failed to update account:", err);
      setError(
        err instanceof Error
          ? err.message
          : "Не вдалося зберегти дані акаунту"
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
            <h3 className="font-medium text-green-900">Збережено</h3>
            <p className="text-sm text-green-700">
              Дані акаунту успішно оновлені
            </p>
          </div>
        </div>
      )}

      {/* Форма */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
        <h2 className="text-lg font-semibold text-gray-900 mb-6">
          Дані WABA акаунту
        </h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* WABA ID */}
          <div>
            <label htmlFor="waba_id" className="block text-sm font-medium text-gray-700 mb-2">
              ID акаунту *
            </label>
            <input
              type="text"
              id="waba_id"
              name="waba_id"
              value={formData.waba_id}
              onChange={handleInputChange}
              placeholder="Введіть ID WABA акаунту"
              required
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            />
            <p className="mt-1 text-xs text-gray-500">
              Унікальний ID вашого WABA акаунту від Meta
            </p>
          </div>

          {/* Account Name */}
          <div>
            <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-2">
              Назва акаунту
            </label>
            <input
              type="text"
              id="name"
              name="name"
              value={formData.name}
              onChange={handleInputChange}
              placeholder="Введіть назву акаунту (опціонально)"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            />
            <p className="mt-1 text-xs text-gray-500">
              Внутрішня назва для вашого акаунту
            </p>
          </div>

          {/* Кнопка збереження */}
          <div className="flex gap-3 pt-4">
            <button
              type="submit"
              disabled={isSaving}
              className="inline-flex items-center gap-2 px-6 py-2 bg-indigo-600 text-white rounded-md font-medium hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
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
      </div>
    </div>
  );
};

export default SettingsPage;
