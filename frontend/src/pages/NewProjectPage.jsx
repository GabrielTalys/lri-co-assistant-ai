import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';

export default function NewProjectPage({ token }) {
  const navigate = useNavigate();
  const [title, setTitle] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function createProject(e) {
    e.preventDefault();
    if (!title.trim()) {
      setError('Project title is required.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const project = await api('/projects', 'POST', { title: title.trim(), ai_mode_enabled: true }, token);
      navigate(`/projects/${project.id}/phase/1`);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="card form-card">
      <h1>Create Project</h1>
      <p className="muted">Title is required.</p>
      <form onSubmit={createProject} className="form-grid">
        <label htmlFor="project-title">Title</label>
        <input
          id="project-title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="e.g. Insect Monitoring"
          required
        />
        {error && <div className="alert alert-error">{error}</div>}
        <div className="row gap-8">
          <button className="btn btn-primary" type="submit" disabled={loading}>
            {loading ? 'Creating...' : 'Create'}
          </button>
          <button className="btn btn-secondary" type="button" onClick={() => navigate('/dashboard')}>
            Cancel
          </button>
        </div>
      </form>
    </section>
  );
}
