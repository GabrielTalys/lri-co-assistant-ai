import React, { useEffect, useMemo, useState } from 'react';
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { api } from './services/api';
import AppShell from './components/AppShell';
import DashboardPage from './pages/DashboardPage';
import InvitePage from './pages/InvitePage';
import LoginPage from './pages/LoginPage';
import NewProjectPage from './pages/NewProjectPage';
import ProjectPhasePage from './pages/ProjectPhasePage';

function ResearcherLayout({ me, onLogout, children }) {
  return (
    <AppShell user={me} onLogout={onLogout}>
      {children}
    </AppShell>
  );
}

function ParticipantLayout({ children }) {
  return (
    <AppShell participantMode>
      {children}
    </AppShell>
  );
}

function AppRoutes() {
  const location = useLocation();

  const [token, setToken] = useState(localStorage.getItem('token'));
  const [me, setMe] = useState(null);
  const [checkingAuth, setCheckingAuth] = useState(Boolean(token));

  const participantSession = useMemo(() => {
    const raw = localStorage.getItem('participant');
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch {
      return null;
    }
  }, [location.pathname, location.search]);

  useEffect(() => {
    if (!token) {
      setMe(null);
      setCheckingAuth(false);
      return;
    }

    setCheckingAuth(true);
    api('/auth/me', 'GET', null, token)
      .then((user) => setMe(user))
      .catch(() => {
        localStorage.removeItem('token');
        setToken(null);
      })
      .finally(() => setCheckingAuth(false));
  }, [token]);

  const onLogin = (newToken) => {
    localStorage.setItem('token', newToken);
    setToken(newToken);
  };

  const onLogout = () => {
    localStorage.removeItem('token');
    setToken(null);
    setMe(null);
  };

  if (checkingAuth) return <div className="loading-page">Checking session...</div>;

  const allowParticipantRoute = location.pathname.startsWith('/projects/') && location.search.includes('mode=participant');

  return (
    <Routes>
      <Route path="/invite/:token" element={<InvitePage />} />

      {token && me ? (
        <>
          <Route
            path="/dashboard"
            element={
              <ResearcherLayout me={me} onLogout={onLogout}>
                <DashboardPage token={token} />
              </ResearcherLayout>
            }
          />
          <Route path="/projects" element={<Navigate to="/dashboard" replace />} />
          <Route
            path="/projects/new"
            element={
              <ResearcherLayout me={me} onLogout={onLogout}>
                <NewProjectPage token={token} />
              </ResearcherLayout>
            }
          />
          <Route
            path="/projects/:id/phase/:phaseNumber"
            element={
              <ResearcherLayout me={me} onLogout={onLogout}>
                <ProjectPhasePage token={token} me={me} />
              </ResearcherLayout>
            }
          />
          <Route path="/projects/:id" element={<Navigate to="/dashboard" replace />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </>
      ) : allowParticipantRoute && participantSession ? (
        <>
          <Route
            path="/projects/:id/phase/:phaseNumber"
            element={
              <ParticipantLayout>
                <ProjectPhasePage me={null} token={null} />
              </ParticipantLayout>
            }
          />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </>
      ) : (
        <>
          <Route path="/login" element={<LoginPage onLogin={onLogin} />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </>
      )}
    </Routes>
  );
}

export default function App() {
  return <AppRoutes />;
}
