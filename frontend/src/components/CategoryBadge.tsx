import type { CategoryType, ScopeType } from "../types";

const CATEGORY_STYLES: Record<CategoryType, { label: string; bg: string; text: string }> = {
  WATER: { label: "Water", bg: "bg-blue-100", text: "text-blue-800" },
  AIR:   { label: "Air",   bg: "bg-slate-100", text: "text-slate-700" },
  WASTE: { label: "Waste", bg: "bg-green-100", text: "text-green-800" },
};

const SCOPE_STYLES: Record<ScopeType, { label: string; bg: string; text: string }> = {
  CAMPUS: { label: "Campus", bg: "bg-purple-100", text: "text-purple-800" },
  CITY:   { label: "City",   bg: "bg-orange-100", text: "text-orange-800" },
};

interface CategoryBadgeProps {
  category?: CategoryType | null;
  scope?: ScopeType | null;
}

export function CategoryBadge({ category, scope }: CategoryBadgeProps) {
  if (!category && !scope) return null;

  return (
    <div className="flex gap-1.5 mt-1.5 flex-wrap">
      {category && (
        <span
          className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${CATEGORY_STYLES[category].bg} ${CATEGORY_STYLES[category].text}`}
        >
          {CATEGORY_STYLES[category].label}
        </span>
      )}
      {scope && (
        <span
          className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${SCOPE_STYLES[scope].bg} ${SCOPE_STYLES[scope].text}`}
        >
          {SCOPE_STYLES[scope].label}
        </span>
      )}
    </div>
  );
}
