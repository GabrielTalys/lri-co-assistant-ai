import React from "react";
import { useEffect, useState } from "react";
import { getFieldLabel, getFieldPlaceholder } from "../utils/placeholder";

function formatSuggestionText(field, text) {
  const normalized = String(text || "").trim();
  if (!normalized) return "";

  if (field === "risks") {
    return normalized
      .replace(/\s*(\d+\s*-\s*)/g, "\n$1")
      .trim();
  }

  if (field === "method") {
    return normalized
      .replace(/\s*([A-Z][^.]+?\bet al\.[^.]+?\.\s*[A-Z][A-Za-z0-9&/\- ]+,\s*\d{4}\.)/g, "\n$1")
      .trim();
  }

  return normalized;
}

export default function FieldEditor({
  field,
  value,
  onChange,
  onConfirm,
  suggestion,
  aiOverview,
  aiOverviewPending,
  onAccept,
  onDismiss,
  onDismissOverview,
  pending,
  readOnly,
  labelOverride,
  placeholderOverride,
}) {
  const [draft, setDraft] = useState(value || "");
  const [hasInteracted, setHasInteracted] = useState(Boolean((value || "").trim().length));

  useEffect(() => {
    setDraft(value || "");
    if ((value || "").trim().length > 0) {
      setHasInteracted(true);
    }
  }, [value]);

  const label = labelOverride || getFieldLabel(field);
  const placeholder =
    hasInteracted ? "" : (placeholderOverride ?? getFieldPlaceholder(field));
  const formattedSuggestionText = formatSuggestionText(
    field,
    suggestion?.suggested_text
  );
  const formattedOverviewText = formatSuggestionText(field, aiOverview);

  return (
    <div className="field-card">
      <label htmlFor={field}>{label}</label>
      <textarea
        id={field}
        value={draft}
        readOnly={readOnly}
        onChange={(e) => {
          if (readOnly) return;
          if (typeof onChange !== "function") return;
          setHasInteracted(true);
          setDraft(e.target.value);
          onChange(field, e.target.value);
        }}
        onBlur={() => {
          if (readOnly) return;
          if (typeof onChange !== "function") return;
          onChange(field, draft, true);
        }}
        placeholder={placeholder}
      />
      {onConfirm && (
        <div className="confirm-row">
          <button className="btn btn-secondary btn-sm" onClick={() => onConfirm(field, draft)}>
            Confirm response
          </button>
        </div>
      )}
      {pending && <p className="hint">Suggestion pending...</p>}
      {!readOnly && suggestion && (
        <div className="suggestion-inline suggestion-inline-ai">
          <p>{formattedSuggestionText}</p>
          <div className="row gap-8">
            <button
              className="btn btn-sm btn-success"
              onClick={() => onAccept(field, suggestion.suggested_text)}
            >
              ✓
            </button>
            <button
              className="btn btn-sm btn-secondary"
              onClick={() => onDismiss(field)}
            >
              ✕
            </button>
          </div>
        </div>
      )}
      {!readOnly && aiOverviewPending && <p className="hint">Overview pending...</p>}
      {!readOnly && formattedOverviewText && (
        <div className="suggestion-inline suggestion-inline-ai">
          <p>{formattedOverviewText}</p>
          <div className="row gap-8">
            <button
              className="btn btn-sm btn-secondary"
              onClick={() => onDismissOverview?.(field)}
            >
              ✕
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
