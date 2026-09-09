import type { CategoryType, ScopeType } from "../types";

interface ComplaintConfirmModalProps {
  draft: Record<string, string>;
  category?: CategoryType | null;
  scope?: ScopeType | null;
  onConfirm: () => void;
  onCancel: () => void;
  isSubmitting?: boolean;
}

export function ComplaintConfirmModal({
  draft,
  category,
  scope,
  onConfirm,
  onCancel,
  isSubmitting = false,
}: ComplaintConfirmModalProps) {
  const routedTo =
    scope === "CAMPUS"
      ? "Campus Management / Maintenance"
      : "Municipal / Civic Authority";

  const fields: { label: string; key: string }[] = [
    { label: "Category",        key: "category" },
    { label: "Scope",           key: "scope" },
    { label: "Issue Summary",   key: "issue_summary" },
    { label: "Location",        key: "location" },
    { label: "Duration",        key: "duration" },
    { label: "Description",     key: "description" },
    { label: "Previous Action", key: "previous_action" },
  ];

  return (
    /* Backdrop */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="complaint-modal-title"
    >
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="px-6 pt-5 pb-4 border-b border-gray-100">
          <h2
            id="complaint-modal-title"
            className="text-base font-semibold text-gray-900"
          >
            Review Your Complaint
          </h2>
          <p className="text-xs text-gray-500 mt-0.5">
            Please review the details below before submitting.
          </p>
        </div>

        {/* Details table */}
        <div className="px-6 py-4">
          <table className="w-full text-sm">
            <tbody>
              {fields.map(({ label, key }) => {
                const value = draft[key] || (key === "previous_action" ? "None taken" : "—");
                return (
                  <tr key={key} className="border-b border-gray-50 last:border-0">
                    <td className="py-2 pr-3 font-medium text-gray-600 whitespace-nowrap align-top w-36">
                      {label}
                    </td>
                    <td className="py-2 text-gray-800 break-words">{value}</td>
                  </tr>
                );
              })}
              <tr className="border-b border-gray-50">
                <td className="py-2 pr-3 font-medium text-gray-600 whitespace-nowrap align-top w-36">
                  Routed To
                </td>
                <td className="py-2 text-gray-800">{routedTo}</td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* Disclaimer — prominent */}
        <div className="mx-6 mb-4 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-xs text-red-800 leading-snug">
          <span className="font-bold">Important:</span> This complaint is{" "}
          <span className="font-bold">simulated</span>. It will be logged in
          CivicAI for demonstration purposes only.{" "}
          <span className="font-bold">
            No real authority will be notified and no real action will be taken.
          </span>
        </div>

        {/* Actions */}
        <div className="px-6 pb-5 flex gap-3 justify-end">
          <button
            onClick={onCancel}
            disabled={isSubmitting}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={isSubmitting}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-60 transition-colors"
          >
            {isSubmitting ? "Submitting…" : "Submit Complaint"}
          </button>
        </div>
      </div>
    </div>
  );
}
