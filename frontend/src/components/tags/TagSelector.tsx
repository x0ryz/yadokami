import React, { useState, useRef, useEffect } from "react";
import { Tag, TagCreate, TagUpdate } from "../../types";
import { Plus } from "lucide-react";

interface TagSelectorProps {
  availableTags: Tag[];
  selectedTags: Tag[];
  onAssignTags: (tagIds: string[]) => void;
  onCreateTag: (tag: TagCreate) => Promise<void>;
  onDeleteTag: (tagId: string) => Promise<void>;
  onEditTag: (tagId: string, data: TagUpdate) => Promise<void>;
  isOpen: boolean;
  onClose: () => void;
}

// Фіксовані кольори
const PRESET_COLORS = [
  "#6B7280", // Gray
  "#EF4444", // Red
  "#F97316", // Orange
  "#F59E0B", // Amber
  "#22C55E", // Green
  "#14B8A6", // Teal
  "#3B82F6", // Blue
  "#6366F1", // Indigo
  "#A855F7", // Purple
  "#EC4899", // Pink
];

// --- Компонент палітри (використовується і для створення, і для редагування) ---
const ColorPalette = ({
  selectedColor,
  onSelect,
}: {
  selectedColor: string;
  onSelect: (color: string) => void;
}) => {
  return (
    <div className="flex flex-wrap gap-2">
      {PRESET_COLORS.map((color) => (
        <button
          key={color}
          type="button"
          onClick={() => onSelect(color)}
          className={`w-5 h-5 rounded-full transition-transform hover:scale-110 focus:outline-none ${selectedColor === color
              ? "ring-2 ring-offset-1 ring-gray-400 scale-110"
              : "ring-1 ring-transparent hover:ring-gray-200"
            }`}
          style={{ backgroundColor: color }}
          title={color}
        />
      ))}

      {/* Кнопка власного кольору */}
      <div
        className={`relative w-5 h-5 rounded-full overflow-hidden transition-transform hover:scale-110 ${!PRESET_COLORS.includes(selectedColor)
            ? "ring-2 ring-offset-1 ring-gray-400 scale-110"
            : "ring-1 ring-gray-200"
          }`}
        title="Власний колір"
      >
        <div
          className="absolute inset-0"
          style={{
            background: !PRESET_COLORS.includes(selectedColor)
              ? selectedColor
              : "conic-gradient(from 180deg at 50% 50%, #FF0000 0deg, #00FF00 120deg, #0000FF 240deg, #FF0000 360deg)",
          }}
        />
        <input
          type="color"
          value={selectedColor}
          onChange={(e) => onSelect(e.target.value)}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
        />
      </div>
    </div>
  );
};

const TagSelector: React.FC<TagSelectorProps> = ({
  availableTags,
  selectedTags,
  onAssignTags,
  onCreateTag,
  onDeleteTag,
  onEditTag,
  isOpen,
  onClose,
}) => {
  // --- Стейт створення ---
  const [isAddingNew, setIsAddingNew] = useState(false); // <--- НОВИЙ СТЕЙТ ДЛЯ ВІДОБРАЖЕННЯ ФОРМИ
  const [newTagName, setNewTagName] = useState("");
  const [newTagColor, setNewTagColor] = useState(PRESET_COLORS[0]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // --- Стейт редагування ---
  const [editingTagId, setEditingTagId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editColor, setEditColor] = useState("");

  const containerRef = useRef<HTMLDivElement>(null);

  // Скидання при закритті/відкритті
  useEffect(() => {
    if (!isOpen) {
      setEditingTagId(null);
      setIsAddingNew(false);
      setNewTagName("");
      setNewTagColor(PRESET_COLORS[0]);
    }
  }, [isOpen]);

  // Закриття при кліку зовні
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        onClose();
      }
    };
    if (isOpen) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isOpen, onClose]);

  const toggleTag = (tagId: string) => {
    if (editingTagId || isAddingNew) return; // Блокуємо вибір, якщо щось редагуємо
    const currentIds = selectedTags.map((t) => t.id);
    const newIds = currentIds.includes(tagId)
      ? currentIds.filter((id) => id !== tagId)
      : [...currentIds, tagId];
    onAssignTags(newIds);
  };

  // --- Логіка редагування ---
  const startEditing = (e: React.MouseEvent, tag: Tag) => {
    e.stopPropagation();
    setIsAddingNew(false); // Закриваємо форму створення, якщо відкрита
    setEditingTagId(tag.id);
    setEditName(tag.name);
    setEditColor(tag.color);
  };

  const cancelEditing = () => {
    setEditingTagId(null);
    setEditName("");
    setEditColor("");
  };

  const saveEdit = async () => {
    if (!editingTagId || !editName.trim()) return;
    try {
      await onEditTag(editingTagId, { name: editName, color: editColor });
      setEditingTagId(null);
    } catch (error) {
      console.error("Failed to update tag", error);
    }
  };

  // --- Логіка створення ---
  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTagName.trim()) return;
    try {
      setIsSubmitting(true);
      await onCreateTag({ name: newTagName, color: newTagColor });
      // Успішно створено: скидаємо форму і закриваємо її
      setNewTagName("");
      setNewTagColor(PRESET_COLORS[0]);
      setIsAddingNew(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  const cancelCreating = () => {
    setIsAddingNew(false);
    setNewTagName("");
  };

  if (!isOpen) return null;

  return (
    <div
      ref={containerRef}
      className="absolute top-10 right-0 w-80 bg-white rounded-lg shadow-xl border border-gray-200 z-50 flex flex-col max-h-[600px]"
    >
      <div className="p-3 border-b border-gray-100 bg-gray-50 rounded-t-lg">
        <h4 className="font-semibold text-gray-700 text-sm">Теги</h4>
      </div>

      {/* СПИСОК ТЕГІВ */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1 min-h-[100px] max-h-[300px]">
        {availableTags.length === 0 ? (
          <div className="text-center text-gray-400 text-xs py-4">
            Список порожній
          </div>
        ) : (
          availableTags.map((tag) => {
            const isSelected = selectedTags.some((t) => t.id === tag.id);
            const isEditing = editingTagId === tag.id;

            // --- РЕЖИМ РЕДАГУВАННЯ (inline) ---
            if (isEditing) {
              return (
                <div
                  key={tag.id}
                  className="p-3 bg-blue-50 rounded border border-blue-200 mb-2 shadow-inner"
                >
                  <input
                    type="text"
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    className="w-full px-2 py-1 text-sm border border-gray-300 rounded mb-2 focus:ring-1 focus:ring-blue-500 outline-none"
                    autoFocus
                    placeholder="Назва тегу"
                  />

                  <div className="mb-3">
                    <ColorPalette
                      selectedColor={editColor}
                      onSelect={setEditColor}
                    />
                  </div>

                  <div className="flex gap-2 justify-end">
                    <button
                      onClick={cancelEditing}
                      className="px-2 py-1 text-xs text-gray-600 hover:bg-gray-200 rounded"
                    >
                      Скасувати
                    </button>
                    <button
                      onClick={saveEdit}
                      className="px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 font-medium"
                    >
                      Зберегти
                    </button>
                  </div>
                </div>
              );
            }

            // --- ЗВИЧАЙНИЙ РЕЖИМ ---
            return (
              <div
                key={tag.id}
                className="flex items-center justify-between p-2 hover:bg-gray-50 rounded cursor-pointer group transition-colors"
                onClick={() => toggleTag(tag.id)}
              >
                <div className="flex items-center gap-2 flex-1">
                  <div
                    className={`w-4 h-4 border rounded flex items-center justify-center transition-colors ${isSelected
                        ? "bg-blue-600 border-blue-600"
                        : "border-gray-300 bg-white"
                      }`}
                  >
                    {isSelected && (
                      <svg
                        className="w-3 h-3 text-white"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={3}
                          d="M5 13l4 4L19 7"
                        />
                      </svg>
                    )}
                  </div>

                  <span
                    className="w-3 h-3 rounded-full shadow-sm"
                    style={{ backgroundColor: tag.color }}
                  />
                  <span className="text-sm text-gray-700">{tag.name}</span>
                </div>

                <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={(e) => startEditing(e, tag)}
                    className="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded"
                    title="Редагувати"
                  >
                    ✎
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      if (window.confirm(`Видалити тег "${tag.name}"?`))
                        onDeleteTag(tag.id);
                    }}
                    className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded"
                    title="Видалити"
                  >
                    ×
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* НИЖНЯ ЧАСТИНА: АБО КНОПКА "+", АБО ФОРМА */}
      <div className="p-3 border-t border-gray-100 bg-gray-50 rounded-b-lg">
        {!isAddingNew ? (
          // --- КНОПКА "+" ---
          <button
            onClick={() => {
              cancelEditing(); // Закриваємо редагування якщо воно активне
              setIsAddingNew(true);
            }}
            className="flex items-center gap-2 text-sm text-gray-600 hover:text-blue-600 w-full px-2 py-1.5 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <Plus className="w-4 h-4" />
            <span>Створити новий тег</span>
          </button>
        ) : (
          // --- ФОРМА СТВОРЕННЯ (ідентична до редагування) ---
          <form
            onSubmit={handleCreate}
            className="space-y-3 animate-in fade-in slide-in-from-top-2 duration-200"
          >
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider flex justify-between items-center">
              <span>Новий тег</span>
              <button
                type="button"
                onClick={cancelCreating}
                className="text-gray-400 hover:text-gray-600 text-lg leading-none"
              >
                ×
              </button>
            </div>

            <input
              type="text"
              value={newTagName}
              onChange={(e) => setNewTagName(e.target.value)}
              placeholder="Назва..."
              autoFocus
              className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
            />

            <div>
              <div className="text-[10px] text-gray-400 mb-1.5">
                Оберіть колір:
              </div>
              <ColorPalette
                selectedColor={newTagColor}
                onSelect={setNewTagColor}
              />
            </div>

            <div className="flex gap-2 pt-1">
              <button
                type="button"
                onClick={cancelCreating}
                className="flex-1 px-3 py-2 text-sm text-gray-600 bg-white border border-gray-300 rounded hover:bg-gray-50"
              >
                Скасувати
              </button>
              <button
                type="submit"
                disabled={!newTagName.trim() || isSubmitting}
                className="flex-1 px-3 py-2 bg-blue-600 text-white text-sm font-medium rounded hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors shadow-sm"
              >
                {isSubmitting ? "..." : "Створити"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};

export default TagSelector;
