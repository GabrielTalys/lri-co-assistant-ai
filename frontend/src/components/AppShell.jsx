import React from "react";
import { Link, useLocation } from "react-router-dom";
import logoPUC from "../img/logoPUC.png";

export default function AppShell({
  user,
  onLogout,
  children,
  participantMode = false,
}) {
  const location = useLocation();
  const participantView =
    participantMode || location.search.includes("mode=participant");

  return (
    <div className="app-root">
      <header className="topbar">
        <div className="topbar-inner">
          {participantView ? (
            <span className="brand">LRI Tool</span>
          ) : (
            <div>
              {}
              <Link className="brand" to="/dashboard">
                LRI Co-Assistant
              </Link>
            </div>
          )}
          <div className="topbar-right">
            {!participantView && (
              <>
                {user && <span className="user-email">{user.email}</span>}
                {user && (
                  <button className="btn btn-ghost" onClick={onLogout}>
                    Logout
                  </button>
                )}
              </>
            )}
          </div>
        </div>
      </header>
      <main className="page-shell">
        <div className="page-container">{children}</div>
      </main>
    </div>
  );
}
