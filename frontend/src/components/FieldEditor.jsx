import React, { useEffect, useState } from "react";

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
  label,
  placeholder,
  value,
  onChange,
  suggestion,
  aiOverviews,
  aiOverviewPending,
  onAccept,
  onDismiss,
  onDismissOverview,
  pending,
  readOnly,
}) {
  const [draft, setDraft] = useState(value || "");
  const [hasInteracted, setHasInteracted] = useState(Boolean((value || "").trim().length));

  useEffect(() => {
    setDraft(value || "");
    if ((value || "").trim().length > 0) {
      setHasInteracted(true);
    }
  }, [value]);

  const formattedSuggestionText = formatSuggestionText(
    field,
    suggestion?.suggested_text
  );
  // Overviews arrive already line-structured ("Overview: ... / Suggestions: • ..."),
  // so they skip formatSuggestionText, whose numbering split would break "RQ1 - ...".
  const overviews = (aiOverviews || []).filter((overview) =>
    String(overview?.text || "").trim()
  );

  return (
    <div className="field-card">
      <label htmlFor={field}>{label}</label>
      <textarea
        id={field}
        value={draft}
        readOnly={readOnly}
        onChange={(e) => {
          if (readOnly) return;
          setHasInteracted(true);
          setDraft(e.target.value);
          onChange(field, e.target.value);
        }}
        onBlur={() => {
          if (readOnly) return;
          onChange(field, draft);
        }}
        placeholder={hasInteracted ? "" : placeholder}
      />
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
      {!readOnly && aiOverviewPending && (
        <p className="hint">Overview pending... (30s - 90s)</p>
      )}
      {!readOnly &&
        overviews.map((overview) => (
          <div
            className="suggestion-inline suggestion-inline-ai"
            key={overview.id}
          >
            {overview.label && (
              <p className="suggestion-inline-label">{overview.label}</p>
            )}
            <p>{String(overview.text).trim()}</p>
            {overview.perspectives?.length > 0 && (
              <details className="overview-perspectives">
                <summary>See each specialist's analysis</summary>
                {overview.perspectives.map((perspective) => (
                  <div className="overview-perspective" key={perspective.id}>
                    <p className="suggestion-inline-label">
                      {perspective.label}
                    </p>
                    <p>{String(perspective.text || "").trim()}</p>
                  </div>
                ))}
              </details>
            )}
            <div className="row gap-8">
              <button
                className="btn btn-sm btn-secondary"
                onClick={() => onDismissOverview?.(field, overview.id)}
              >
                ✕
              </button>
            </div>
          </div>
        ))}
    </div>
  );
}
