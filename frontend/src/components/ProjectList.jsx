import React from "react";
import { useNavigate } from "react-router-dom";
import { Trash2 } from "lucide-react";
import { enumToPhaseNumber, phaseLabels } from "../config/phaseConfig";

const TOTAL_PHASES = 5;

function resolvePhaseNumber(project) {
  const phaseFromCurrent = Number(enumToPhaseNumber(project?.current_phase));
  if (Number.isFinite(phaseFromCurrent) && phaseFromCurrent > 0) {
    return Math.max(1, Math.min(TOTAL_PHASES, Math.trunc(phaseFromCurrent)));
  }

  const phaseFromLegacyStatus = Number(project?.status);
  if (Number.isFinite(phaseFromLegacyStatus) && phaseFromLegacyStatus > 0) {
    return Math.max(1, Math.min(TOTAL_PHASES, Math.trunc(phaseFromLegacyStatus)));
  }

  return 1;
}

function phaseLabel(phaseNumber) {
  return phaseLabels[phaseNumber] || "Unknown Phase";
}

function finalOutcomeLabel(project) {
  const decision = String(project?.decision || "").trim().toUpperCase();
  if (decision === "ABORT") return "Project Aborted";
  if (decision === "GO") return "Project Succeeded";
  return null;
}

function progressPercent(phaseNumber) {
  const completedPhases = Math.max(
    0,
    Math.min(TOTAL_PHASES, Number(phaseNumber) - 1)
  );
  return Math.round((completedPhases / TOTAL_PHASES) * 100);
}

const ABSOLUTE_DATE_FORMATTER = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
});

function normalizeTimestamp(input) {
  if (typeof input !== "string") return input;
  const withIsoSeparator =
    input.includes(" ") && !input.includes("T")
      ? input.replace(" ", "T")
      : input;
  // Trim fractional seconds to milliseconds (3 digits) so Date parsing stays consistent.
  return withIsoSeparator.replace(
    /\.(\d{3})\d+(?=(Z|[+-]\d{2}:\d{2})?$)/,
    ".$1"
  );
}

function timeAgo(inputDate) {
  const date = inputDate instanceof Date ? inputDate : new Date(inputDate);
  const timestamp = date.getTime();
  if (Number.isNaN(timestamp)) return "just now";

  const diffMs = Math.max(0, Date.now() - timestamp);
  const seconds = Math.floor(diffMs / 1000);
  if (seconds < 10) return "just now";
  if (seconds < 60) return "less than a minute ago";

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) {
    return `${minutes} minute${minutes === 1 ? "" : "s"} ago`;
  }

  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  }

  const days = Math.floor(hours / 24);
  if (days < 30) {
    return `${days} day${days === 1 ? "" : "s"} ago`;
  }

  return ABSOLUTE_DATE_FORMATTER.format(date);
}

function formatCreatedAt(project) {
  const raw = project?.created_at ?? project?.createdAt;
  if (!raw) return "Created —";
  const normalized = normalizeTimestamp(raw);
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return "Created —";
  return `Created ${timeAgo(date)}`;
}

export default function ProjectList({ projects, onDeleteProject }) {
  const navigate = useNavigate();

  return (
    <div className="project-list">
      {projects.map((project) => {
        const phaseNumber = resolvePhaseNumber(project);
        const outcome = finalOutcomeLabel(project);
        const progress = outcome ? 100 : progressPercent(phaseNumber);
        const label = phaseLabel(phaseNumber);
        const progressLabel = outcome || `Phase ${phaseNumber} — ${label}`;
        const ctaLabel = outcome ? "View Result" : "Continue Project";

        return (
          <article key={project.id} className="project-card">
            <div className="project-card-header">
              <h3 className="project-title">{project.title}</h3>
              <button
                type="button"
                className="btn btn-ghost btn-sm project-delete-btn"
                onClick={() => onDeleteProject?.(project)}
                aria-label={`Delete project ${project.title}`}
                title="Delete project"
              >
                <Trash2 size={16} aria-hidden="true" />
              </button>
            </div>

            <div className="project-phase-progress-row">
              <p className="project-phase-label">{progressLabel}</p>
              <p className="project-progress-value">{`${progress}%`}</p>
            </div>

            <div
              className="project-progress mt-1.5"
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={progress}
            >
              <div
                className="project-progress-fill"
                style={{ width: `${progress}%` }}
              />
            </div>

            <p className="muted project-created-at">
              {formatCreatedAt(project)}
            </p>

            <div className="project-card-actions">
              <button
                type="button"
                className="btn btn-primary"
                onClick={() =>
                  navigate(`/projects/${project.id}/phase/${phaseNumber}`)
                }
              >
                {ctaLabel}
              </button>
            </div>
          </article>
        );
      })}
    </div>
  );
}
