import React, { useState, useRef, useEffect } from "react";
import { Tag } from "../../types";

interface TagFilterProps {
  availableTags: Tag[];
  selectedTagIds: string[];
  onChange: (tagIds: string[]) => void;
}

const TagFilter: React.FC<TagFilterProps> = ({
  availableTags,
  selectedTagIds,
  onChange,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    };
    if (isOpen) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isOpen]);

  const toggleTag = (tagId: string) => {
    const newIds = selectedTagIds.includes(tagId)
      ? selectedTagIds.filter((id) => id !== tagId)
      : [...selectedTagIds, tagId];
    onChange(newIds);
  };

  const activeCount = selectedTagIds.length;

  return (
    <div className="relative" ref={containerRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`flex items-center gap-2 px-3 py-2 border rounded-lg transition-colors ${activeCount > 0
            ? "bg-blue-50 border-blue-200 text-blue-700"
            : "bg-white border-gray-300 text-gray-700 hover:bg-gray-50"
          }`}
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="h-5 w-5"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"
          />
        </svg>
        <span className="text-sm font-medium">Фільтр</span>
        {activeCount > 0 && (
          <span className="bg-blue-600 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center">
            {activeCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 mt-2 w-64 bg-white rounded-lg shadow-xl border border-gray-200 z-50">
          <div className="p-3 border-b border-gray-100 flex justify-between items-center">
            <span className="text-xs font-semibold text-gray-500 uppercase">
              Фільтрувати за тегом
            </span>
            {activeCount > 0 && (
              <button
                onClick={() => onChange([])}
                className="text-xs text-red-500 hover:text-red-700"
              >
                Скинути
              </button>
            )}
          </div>

          <div className="max-h-60 overflow-y-auto p-2 space-y-1">
            {availableTags.length === 0 ? (
              <div className="text-center text-gray-400 text-xs py-2">
                Тегів немає
              </div>
            ) : (
              availableTags.map((tag) => {
                const isSelected = selectedTagIds.includes(tag.id);
                return (
                  <div
                    key={tag.id}
                    onClick={() => toggleTag(tag.id)}
                    className={`flex items-center gap-2 p-2 rounded cursor-pointer text-sm ${isSelected ? "bg-blue-50" : "hover:bg-gray-50"
                      }`}
                  >
                    <div
                      className={`w-4 h-4 border rounded flex items-center justify-center ${isSelected
                          ? "bg-blue-600 border-blue-600"
                          : "border-gray-300"
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
                      className="w-2.5 h-2.5 rounded-full"
                      style={{ backgroundColor: tag.color }}
                    />
                    <span className="text-gray-700 truncate">{tag.name}</span>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default TagFilter;
