import React from "react";
import { Check, Lock } from "lucide-react";

const PHASES = [1, 2, 3, 4, 5];

export default function PhaseStepper({
  currentPhaseNumber,
  activePhaseNumber,
  onSelectPhase,
}) {
  return (
    <aside className="phase-sidebar card">
      <h3>LRI Phases</h3>
      <ul className="phase-list">
        {PHASES.map((phase) => {
          const isCurrent = phase === currentPhaseNumber;
          const isActive = phase === activePhaseNumber;
          const isLocked = phase > currentPhaseNumber;
          const isCompleted = phase < currentPhaseNumber;
          // Completed phases can be reopened (read-only) and the current one
          // returned to; future phases stay locked.
          const isSelectable =
            typeof onSelectPhase === "function" && !isLocked && !isActive;
          const className = `phase-item ${isCurrent ? "current" : ""} ${
            isActive ? "active" : ""
          } ${isLocked ? "locked" : ""} ${isSelectable ? "selectable" : ""}`;
          const content = (
            <>
              <span>Phase {phase}</span>
              {isCompleted ? (
                <Check
                  className="phase-icon phase-icon-check"
                  size={14}
                  aria-hidden="true"
                />
              ) : isLocked ? (
                <Lock
                  className="phase-icon phase-icon-lock"
                  size={14}
                  aria-hidden="true"
                />
              ) : (
                <span className="phase-icon-placeholder" aria-hidden="true" />
              )}
            </>
          );

          return (
            <li key={phase}>
              {isSelectable ? (
                <button
                  type="button"
                  className={className}
                  onClick={() => onSelectPhase(phase)}
                  title={
                    isCompleted
                      ? `View Phase ${phase} (read-only)`
                      : `Back to Phase ${phase}`
                  }
                >
                  {content}
                </button>
              ) : (
                <div
                  className={className}
                  aria-current={isActive ? "step" : undefined}
                >
                  {content}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </aside>
  );
}
