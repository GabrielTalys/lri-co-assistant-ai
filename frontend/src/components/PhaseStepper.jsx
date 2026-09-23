import React from "react";
import { Check, Lock } from "lucide-react";

const PHASES = [1, 2, 3, 4, 5];

export default function PhaseStepper({
  currentPhaseNumber,
  activePhaseNumber,
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

          return (
            <li
              key={phase}
              className={`phase-item ${isCurrent ? "current" : ""} ${
                isActive ? "active" : ""
              } ${isLocked ? "locked" : ""}`}
            >
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
            </li>
          );
        })}
      </ul>
    </aside>
  );
}
