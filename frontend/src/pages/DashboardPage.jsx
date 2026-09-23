import React from "react";
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import LoadingState from '../components/LoadingState';
import ProjectList from '../components/ProjectList';

export default function DashboardPage({ token }) {
  const navigate = useNavigate();
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    loadProjects();
  }, []);

  async function loadProjects() {
    setLoading(true);
    setError('');
    try {
      const data = await api('/projects', 'GET', null, token);
      console.log('Projects payload (/projects):', data);
      setProjects(
        (data || []).map((project) => ({
          ...project,
          created_at: project?.created_at ?? project?.createdAt ?? null,
        }))
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleDeleteProject(project) {
    const confirmed = window.confirm(`Delete project "${project.title}"? This cannot be undone.`);
    if (!confirmed) return;
    try {
      await api(`/projects/${project.id}`, 'DELETE', null, token);
      setProjects((prev) => prev.filter((p) => p.id !== project.id));
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <section className="card">
      <div className="section-header">
        <div>
          <h1>Projects</h1>
          <p className="muted">Manage your Lean Research Inception projects</p>
        </div>
        <button className="btn btn-primary" onClick={() => navigate('/projects/new')}>
          New Project
        </button>
      </div>

      {loading && <LoadingState label="Loading projects..." />}
      {error && <div className="alert alert-error">{error}</div>}

      {!loading && !error && projects.length === 0 && (
        <div className="empty-state">
          <h3>No projects yet</h3>
          <p>Create your first project to start the LRI workflow.</p>
          <button className="btn btn-primary" onClick={() => navigate('/projects/new')}>
            New Project
          </button>
        </div>
      )}

      {!loading && !error && projects.length > 0 && (
        <ProjectList projects={projects} onDeleteProject={handleDeleteProject} />
      )}
    </section>
  );
}
