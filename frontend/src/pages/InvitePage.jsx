import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api } from '../services/api';

export default function InvitePage() {
  const { token } = useParams();
  const navigate = useNavigate();

  const [name, setName] = useState('');
  const [company, setCompany] = useState('');
  const [consent, setConsent] = useState(true);
  const [checkingInvite, setCheckingInvite] = useState(true);
  const [inviteValid, setInviteValid] = useState(false);
  const [message, setMessage] = useState('');
  const [redirectTarget, setRedirectTarget] = useState('');

  useEffect(() => {
    let cancelled = false;
    setCheckingInvite(true);
    setInviteValid(false);
    setMessage('');

    api(`/invites/${token}`, 'GET')
      .then(() => {
        if (!cancelled) {
          setInviteValid(true);
          setMessage('');
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setInviteValid(false);
          setMessage(err.message);
        }
      })
      .finally(() => {
        if (!cancelled) setCheckingInvite(false);
      });

    return () => {
      cancelled = true;
    };
  }, [token]);

  async function join(e) {
    e.preventDefault();
    if (!inviteValid) {
      setMessage(message || 'Invite is not available.');
      return;
    }
    if (!consent) {
      setMessage('Consent is required.');
      return;
    }

    try {
      const safeName = String(name || 'guest').toLowerCase().replace(/[^a-z0-9]+/g, '.');
      const safeCompany = String(company || 'invite').toLowerCase().replace(/[^a-z0-9]+/g, '.');
      const guestEmail = `${safeName}.${safeCompany}@invite.local`;
      const data = await api(`/invites/${token}/accept`, 'POST', { email: guestEmail });
      localStorage.setItem('participant', JSON.stringify(data));

      const project = await api(`/projects/${data.project_id}?participant_id=${data.participant_id}`, 'GET', null, null);
      const phase = Number(project.current_phase || 1);
      const target = `/projects/${data.project_id}/phase/${phase}?mode=participant&participantId=${data.participant_id}`;
      setRedirectTarget(target);
      setMessage('Joined successfully. Redirecting to workshop...');

      setTimeout(() => navigate(target), 900);
    } catch (err) {
      setMessage(err.message);
    }
  }

  return (
    <main className="login-wrap">
      <section className="card login-card">
        <h1>Participant Access</h1>
        <p className="muted">Enter your workshop details</p>
        <form onSubmit={join} className="form-grid">
          <label htmlFor="name">Name</label>
          <input id="name" value={name} onChange={(e) => setName(e.target.value)} required />

          <label htmlFor="company">Company</label>
          <input id="company" value={company} onChange={(e) => setCompany(e.target.value)} required />

          <label className="checkbox-row">
            <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
            I accept consent terms
          </label>

          <button type="submit" className="btn btn-primary" disabled={checkingInvite || !inviteValid}>
            {checkingInvite ? 'Checking invite...' : 'Join Workshop'}
          </button>
          {message && <div className="alert">{message}</div>}
          {redirectTarget && (
            <button type="button" className="btn btn-secondary" onClick={() => navigate(redirectTarget)}>
              Go to Workshop
            </button>
          )}
        </form>
      </section>
    </main>
  );
}
