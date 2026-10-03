import React, { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import FieldEditor from "../components/FieldEditor";
import LoadingState from "../components/LoadingState";
import PhaseStepper from "../components/PhaseStepper";
import {
  CANVAS_FIELDS,
  FIELD_LABELS,
  FIELD_PLACEHOLDERS,
  PHASE3_FIELD_LABELS,
} from "../config/canvasFields";
import { phaseConfig, phaseLabels } from "../config/phaseConfig";
import { API_URL, api } from "../services/api";
import { readParticipantSession } from "../services/participantSession";

// The canvas is edited in phases 1-3; phases 4 and 5 have no canvas fields.
const phaseFields = { 1: CANVAS_FIELDS, 2: CANVAS_FIELDS, 3: CANVAS_FIELDS };

// The three assessment criteria, in the order the assessment form and the
// results show them.
const assessmentCriteria = [
  {
    key: "valuable",
    metricKey: "impact",
    label: "Valuable",
    resultLabel: "Value",
    anchors: { left: "Not Valuable", right: "Valuable" },
    description:
      "Valuable: To what extent does addressing the formulated problem have the potential to generate meaningful value for industrial practice?",
  },
  {
    key: "applicable",
    metricKey: "alignment",
    label: "Applicable",
    resultLabel: "Applicability",
    anchors: { left: "Not Applicable", right: "Applicable" },
    description:
      "Applicable: To what extent can the expected results of this formulated research problem be realistically applied in real industry scenarios (considering factors such as adoption potential, contextual fit, and stakeholder willingness to use the outcomes)?",
  },
  {
    key: "feasible",
    metricKey: "feasibility",
    label: "Feasible",
    resultLabel: "Feasibility",
    anchors: { left: "Not Feasible", right: "Feasible" },
    description:
      "Feasible: To what extent can this research problem be realistically investigated with the resources typically available?",
  },
];
// Scores are stored in submission order, which is the order phase 5 lists each
// participant's comments in.
const assessmentSubmitOrder = ["valuable", "feasible", "applicable"];
const criterionByKey = Object.fromEntries(
  assessmentCriteria.map((criterion) => [criterion.key, criterion])
);
const criterionLabelByMetric = Object.fromEntries(
  assessmentCriteria.map((criterion) => [criterion.metricKey, criterion.label])
);

function criteriaState(value) {
  return Object.fromEntries(
    assessmentCriteria.map((criterion) => [criterion.key, value])
  );
}

const phase5DecisionMessages = {
  GO: "The formulated problem received a 'Go' because of its high perceived relevance!",
  ABORT:
    "The formulated problem was aborted because of its low perceived relevance!",
  PIVOT:
    "The formulated problem was selected for reformulation before continuing.",
};

const phase5Decisions = ["GO", "PIVOT", "ABORT"];
const decisionAriaLabels = {
  GO: "Proceed with the research problem",
  ABORT: "Stop pursuing this research problem",
  PIVOT: "Refine the research problem before continuing",
};
const canvasAutoSavePollingMs = 5000;

// Mirrors the backend column limits for AI specialist role and context.
const aiSpecialistRoleMaxLength = 120;
const aiSpecialistContextMaxLength = 500;
const emptyAiSpecialistDraft = { role_title: "", role_description: "" };

function aiSpecialistToDraft(specialist) {
  return {
    role_title: specialist?.role_title || "",
    role_description: specialist?.role_description || "",
  };
}

function mapCanvasItems(items) {
  const nextEntries = {};
  const nextSuggestions = {};

  for (const item of items || []) {
    const key = item.question_key;
    if (!CANVAS_FIELDS.includes(key)) continue;

    if (item.response) {
      nextEntries[key] = item.response.content || "";
    }

    const suggestedText = item.suggestion?.output?.text;
    if (suggestedText) {
      nextSuggestions[key] = {
        suggested_text: suggestedText,
        status: item.suggestion?.status,
      };
    }
  }

  return { nextEntries, nextSuggestions };
}

export default function ProjectPhasePage({ token, me }) {
  const { id, phaseNumber } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const projectId = Number(id);
  const routePhase = Number(phaseNumber);
  const isParticipant = searchParams.get("mode") === "participant";

  const participantSession = useMemo(readParticipantSession, []);

  const participantIdFromQuery =
    Number(searchParams.get("participantId")) || null;
  const participantId =
    participantIdFromQuery || participantSession?.participant_id || null;

  const [project, setProject] = useState(null);
  const [actorParticipantId, setActorParticipantId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionMessage, setActionMessage] = useState("");
  const [isExporting, setIsExporting] = useState(false);
  const [isGeneratingRecommendations, setIsGeneratingRecommendations] =
    useState(false);
  const [isGeneratingPhase3Overview, setIsGeneratingPhase3Overview] =
    useState(false);
  // { [field]: [{ id, label, text, perspectives }] } — the overview of each field,
  // plus the individual AI specialist reviews it consolidates (panel mode).
  const [phase3OverviewsByField, setPhase3OverviewsByField] = useState({});
  const [isPhase3OverviewPending, setIsPhase3OverviewPending] = useState(false);

  const [entries, setEntries] = useState({});
  const [suggestions, setSuggestions] = useState({});
  const [recommendationPendingByField, setRecommendationPendingByField] =
    useState({});

  const [inviteeName, setInviteeName] = useState("");
  const [generatedInvites, setGeneratedInvites] = useState([]);
  const [isGeneratingInvite, setIsGeneratingInvite] = useState(false);

  const [aiSpecialists, setAiSpecialists] = useState([]);
  const [maxAiSpecialists, setMaxAiSpecialists] = useState(3);
  // Unsaved edits of each configured specialist, keyed by participant id.
  const [aiSpecialistDrafts, setAiSpecialistDrafts] = useState({});
  const [newAiSpecialist, setNewAiSpecialist] = useState(
    emptyAiSpecialistDraft
  );
  // Participant id being saved, or "new" while adding one.
  const [savingAiSpecialistId, setSavingAiSpecialistId] = useState(null);
  const [removingAiSpecialistId, setRemovingAiSpecialistId] = useState(null);
  const [aiEvaluations, setAiEvaluations] = useState([]);
  const [generatingAiEvaluationIds, setGeneratingAiEvaluationIds] = useState(
    []
  );
  const [resettingAiEvaluationId, setResettingAiEvaluationId] = useState(null);
  const [assessment, setAssessment] = useState(() => criteriaState(1));
  const [assessmentComments, setAssessmentComments] = useState(() =>
    criteriaState("")
  );
  const [assessmentSaved, setAssessmentSaved] = useState(() =>
    criteriaState(false)
  );
  const [completionInfo, setCompletionInfo] = useState({
    all_done: false,
    required_respondents: 0,
    completed_respondents: 0,
    pending_invites: 0,
  });
  const [resultsInfo, setResultsInfo] = useState(null);
  const [commentsInfo, setCommentsInfo] = useState([]);
  const [problemSynthesis, setProblemSynthesis] = useState("");
  const [selectedDecision, setSelectedDecision] = useState(null);

  const saveTimersRef = useRef({});
  const problemSynthesisSaveTimerRef = useRef(null);
  const actionMessageTimerRef = useRef(null);
  const phase1RecommendationGenerationRef = useRef(0);
  const phase3OverviewGenerationRef = useRef(0);
  const entriesRef = useRef({});
  const lastSyncedCanvasRef = useRef({});
  const problemSynthesisRef = useRef("");
  const lastSavedProblemSynthesisRef = useRef("");

  const config = phaseConfig[routePhase] || phaseConfig[1];
  const fields = phaseFields[routePhase] || [];
  const suggestionsEnabled = routePhase === 1;
  const isFieldFilled = (field) =>
    String(entries[field] || "").trim().length > 0;
  const filledBoardFields = fields.filter(isFieldFilled);
  const emptyBoardFields = fields.filter((field) => !isFieldFilled(field));

  const participantQuery = isParticipant
    ? `?participant_id=${participantId}`
    : "";
  // The facilitator can reopen completed phases read-only; guests always follow
  // the project's current phase.
  const serverPhaseNumber = Number(project?.current_phase || 0);
  const isReviewMode =
    !isParticipant && serverPhaseNumber > 0 && routePhase < serverPhaseNumber;

  function shouldFollowServerPhase(serverPhase) {
    if (!Number.isInteger(routePhase) || routePhase < 1) return true;
    return isParticipant ? serverPhase !== routePhase : routePhase > serverPhase;
  }

  function participantRoute(phase) {
    const suffix = isParticipant
      ? `?mode=participant&participantId=${participantId}`
      : "";
    return `/projects/${projectId}/phase/${phase}${suffix}`;
  }

  async function fetchProjectState() {
    if (isParticipant) {
      if (!participantId) {
        throw new Error("Missing participant session.");
      }
      return api(
        `/projects/${projectId}?participant_id=${participantId}`,
        "GET"
      );
    }
    return api(`/projects/${projectId}`, "GET", null, token);
  }

  async function fetchInvites() {
    if (isParticipant) return [];
    const data = await api(
      `/projects/${projectId}/invites`,
      "GET",
      null,
      token
    );
    if (!Array.isArray(data)) return [];
    return data.map((item) => ({
      id: item.id,
      name: item.name || "Participant",
      invite_url: item.invite_url || "",
      status: item.status || "pending",
    }));
  }

  function currentServerPhase(data) {
    return Number(data?.current_phase || 1);
  }

  async function fetchAiSpecialists() {
    try {
      const data = isParticipant
        ? await api(
            `/projects/${projectId}/ai-specialists?participant_id=${participantId}`,
            "GET"
          )
        : await api(`/projects/${projectId}/ai-specialists`, "GET", null, token);
      const items = Array.isArray(data?.items) ? data.items : [];
      setAiSpecialists(items);
      setMaxAiSpecialists(Number(data?.max_specialists) || 3);
      setAiSpecialistDrafts(
        Object.fromEntries(
          items.map((item) => [item.participant_id, aiSpecialistToDraft(item)])
        )
      );
    } catch {
      setAiSpecialists([]);
      setAiSpecialistDrafts({});
    }
  }

  async function fetchCanvas() {
    const data = await api(
      `/projects/${projectId}/canvas${participantQuery}`,
      "GET",
      null,
      token
    );
    const { nextEntries, nextSuggestions } = mapCanvasItems(data.items);
    setEntries((prev) =>
      routePhase === 3 ? nextEntries : { ...prev, ...nextEntries }
    );
    setSuggestions(suggestionsEnabled ? nextSuggestions : {});
    lastSyncedCanvasRef.current =
      routePhase === 3
        ? { ...nextEntries }
        : {
            ...lastSyncedCanvasRef.current,
            ...nextEntries,
          };
    return data;
  }

  async function loadProjectContext() {
    setLoading(true);
    setError("");

    try {
      const projectData = await fetchProjectState();
      const serverPhase = currentServerPhase(projectData);
      if (shouldFollowServerPhase(serverPhase)) {
        navigate(participantRoute(serverPhase), { replace: true });
        return;
      }
      setProject(projectData);

      if (isParticipant) {
        setActorParticipantId(participantId);
      } else {
        const participants = await api(
          `/projects/${projectId}/participants`,
          "GET",
          null,
          token
        );
        const facilitator = participants.find((p) => p.user_id === me?.id);
        if (!facilitator) {
          throw new Error("Facilitator participant not found for project.");
        }
        setActorParticipantId(facilitator.id);
      }

      await fetchCanvas();
      await fetchAiSpecialists();

      if (isParticipant && routePhase === 4 && participantId) {
        await hydrateParticipantAssessment();
      }
      if (!isParticipant && routePhase === 4) {
        await refreshCompletion();
      }
      if (routePhase === 5) {
        await loadResults();
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!Number.isFinite(projectId) || projectId <= 0) {
      setError("Invalid project id.");
      setLoading(false);
      return;
    }
    loadProjectContext();
  }, [projectId, routePhase, isParticipant]);

  useEffect(() => {
    if (!project) return;
    const serverPhase = currentServerPhase(project);
    if (shouldFollowServerPhase(serverPhase)) {
      navigate(participantRoute(serverPhase), { replace: true });
    }
    if (
      routePhase === 5 &&
      serverPhase === 5 &&
      (project.decision || "").toUpperCase() === "PIVOT"
    ) {
      setSelectedDecision(null);
      navigate(participantRoute(2), { replace: true });
    }
  }, [project?.current_phase, project?.decision, routePhase]);

  useEffect(() => {
    setInviteeName("");
    if (isParticipant) {
      setGeneratedInvites([]);
      return;
    }
    if (routePhase !== 2) return;
    fetchInvites()
      .then((invites) => setGeneratedInvites(invites))
      .catch(() => setGeneratedInvites([]));
  }, [projectId, isParticipant, routePhase]);

  useEffect(() => {
    if (!projectId) return;
    const interval = setInterval(async () => {
      try {
        const latest = await fetchProjectState();
        setProject((prev) => ({ ...prev, ...latest }));
        const latestPhase = currentServerPhase(latest);
        if (shouldFollowServerPhase(latestPhase)) {
          navigate(participantRoute(latestPhase), { replace: true });
        }
      } catch {
        // Keep silent during polling to avoid noisy UX.
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [projectId, isParticipant, participantId, token, routePhase]);

  useEffect(() => {
    if (isParticipant || routePhase !== 4) return;
    const interval = setInterval(() => {
      void refreshCompletion();
    }, 3000);
    return () => clearInterval(interval);
  }, [isParticipant, routePhase, projectId, token]);

  useEffect(() => {
    entriesRef.current = entries;
  }, [entries]);

  useEffect(() => {
    problemSynthesisRef.current = problemSynthesis;
  }, [problemSynthesis]);

  // A new project, cycle or phase drops the previous one's sync state and any
  // AI generation still in flight.
  useEffect(() => {
    lastSyncedCanvasRef.current = {};
    phase1RecommendationGenerationRef.current += 1;
    setRecommendationPendingByField({});
    setIsGeneratingRecommendations(false);
    phase3OverviewGenerationRef.current += 1;
    setPhase3OverviewsByField({});
    setIsPhase3OverviewPending(false);
    setIsGeneratingPhase3Overview(false);
  }, [projectId, project?.current_cycle, routePhase]);

  useEffect(() => {
    return () => {
      clearActionMessageTimer();
      clearProblemSynthesisSaveTimer();
      clearPendingFieldSaveTimers();
    };
  }, []);

  useEffect(() => {
    clearPendingFieldSaveTimers();
    clearProblemSynthesisSaveTimer();
  }, [projectId, routePhase]);

  useEffect(() => {
    clearActionMessageTimer();
    setActionMessage("");
  }, [routePhase]);

  useEffect(() => {
    if (!project) {
      setSelectedDecision(null);
      return;
    }
    setSelectedDecision(project.decision || null);
  }, [project?.id, project?.decision]);

  useEffect(() => {
    const nextSynthesis = project?.problem_synthesis || "";
    setProblemSynthesis(nextSynthesis);
    problemSynthesisRef.current = nextSynthesis;
    lastSavedProblemSynthesisRef.current = nextSynthesis;
  }, [project?.id, project?.current_cycle, project?.problem_synthesis]);

  function clearActionMessageTimer() {
    if (actionMessageTimerRef.current) {
      clearTimeout(actionMessageTimerRef.current);
      actionMessageTimerRef.current = null;
    }
  }

  function clearProblemSynthesisSaveTimer() {
    if (problemSynthesisSaveTimerRef.current) {
      clearTimeout(problemSynthesisSaveTimerRef.current);
      problemSynthesisSaveTimerRef.current = null;
    }
  }

  function setTimedActionMessage(message, durationMs = 0) {
    setActionMessage(message);
    clearActionMessageTimer();

    if (durationMs > 0) {
      actionMessageTimerRef.current = setTimeout(() => {
        setActionMessage((current) => (current === message ? "" : current));
        actionMessageTimerRef.current = null;
      }, durationMs);
    }
  }

  function clearPendingFieldSaveTimers() {
    for (const timer of Object.values(saveTimersRef.current || {})) {
      clearTimeout(timer);
    }
    saveTimersRef.current = {};
  }

  function fieldChange(field, content) {
    setEntries((prev) => ({ ...prev, [field]: content }));
    if (routePhase === 3) {
      phase3OverviewGenerationRef.current += 1;
      setPhase3OverviewsByField({});
      setIsPhase3OverviewPending(false);
    }

    if (!config.collaborativeAutoSave || !actorParticipantId) return;

    clearTimeout(saveTimersRef.current[field]);
    saveTimersRef.current[field] = setTimeout(
      () => saveEntry(field, content),
      700
    );
  }

  async function putCanvasResponse(field, content) {
    await api(
      `/projects/${projectId}/canvas/${encodeURIComponent(field)}/response`,
      "PUT",
      { participant_id: actorParticipantId, content },
      token
    );
    lastSyncedCanvasRef.current[field] = content ?? "";
  }

  async function saveEntry(field, content, explicit = false) {
    if (!project || !actorParticipantId) return;

    try {
      await putCanvasResponse(field, content);
      if (explicit) setTimedActionMessage("Saved.", 4000);
    } catch (err) {
      setActionMessage(err.message);
    }
  }

  async function saveAllDraft() {
    for (const field of fields) {
      await saveEntry(field, entries[field] || "", true);
    }
  }

  async function persistProblemSynthesis(explicit = false) {
    if (!project || isParticipant || !token) return true;

    const nextValue = String(problemSynthesisRef.current || "");
    if (nextValue === lastSavedProblemSynthesisRef.current) return true;

    try {
      const updated = await api(
        `/projects/${projectId}`,
        "PATCH",
        { problem_synthesis: nextValue },
        token
      );
      lastSavedProblemSynthesisRef.current = updated.problem_synthesis || "";
      setProject((prev) =>
        prev
          ? { ...prev, problem_synthesis: updated.problem_synthesis || "" }
          : prev
      );
      if (explicit) setTimedActionMessage("Problem synthesis saved.", 2500);
      return true;
    } catch (err) {
      setActionMessage(`Failed to save problem synthesis: ${err.message}`);
      return false;
    }
  }

  function handleProblemSynthesisChange(event) {
    setProblemSynthesis(event.target.value);
    clearProblemSynthesisSaveTimer();
    problemSynthesisSaveTimerRef.current = setTimeout(() => {
      void persistProblemSynthesis(false);
      problemSynthesisSaveTimerRef.current = null;
    }, 700);
  }

  async function handleProblemSynthesisBlur() {
    clearProblemSynthesisSaveTimer();
    await persistProblemSynthesis(true);
  }

  async function persistPhaseEntriesBeforeAdvance() {
    if (!project || !actorParticipantId || routePhase > 3) return true;

    const editedFields = fields.filter((field) =>
      Object.prototype.hasOwnProperty.call(entries, field)
    );
    if (editedFields.length === 0) return true;

    try {
      for (const field of editedFields) {
        await putCanvasResponse(field, entries[field] ?? "");
      }
      return true;
    } catch (err) {
      setActionMessage(
        `Failed to save phase content before advancing: ${err.message}`
      );
      return false;
    }
  }

  async function generateRecommendations() {
    if (
      isParticipant ||
      routePhase !== 1 ||
      !project?.ai_mode_enabled ||
      isGeneratingRecommendations
    ) {
      return;
    }

    if (filledBoardFields.length === 0) {
      setActionMessage(
        "Fill at least one board field before requesting recommendations."
      );
      return;
    }

    if (emptyBoardFields.length === 0) {
      setTimedActionMessage("All board fields are already filled.", 2500);
      return;
    }

    clearPendingFieldSaveTimers();
    const persisted = await persistPhaseEntriesBeforeAdvance();
    if (!persisted) return;

    setIsGeneratingRecommendations(true);
    const generationId = phase1RecommendationGenerationRef.current + 1;
    phase1RecommendationGenerationRef.current = generationId;
    setRecommendationPendingByField(
      Object.fromEntries(emptyBoardFields.map((field) => [field, true]))
    );

    try {
      const failures = [];
      const tasks = emptyBoardFields.map((field) =>
        api(
          `/projects/${projectId}/canvas/${encodeURIComponent(
            field
          )}/recommendation`,
          "POST",
          {},
          token
        )
          .then((data) => {
            if (phase1RecommendationGenerationRef.current !== generationId) {
              return;
            }
            const suggestedText = String(data?.suggested_text || "").trim();
            if (!suggestedText) return;
            setSuggestions((prev) => ({
              ...prev,
              [field]: {
                suggested_text: suggestedText,
                status: data?.status || "succeeded",
              },
            }));
          })
          .catch((err) => {
            failures.push({ field, message: err.message });
          })
          .finally(() => {
            if (phase1RecommendationGenerationRef.current !== generationId) {
              return;
            }
            setRecommendationPendingByField((prev) => ({
              ...prev,
              [field]: false,
            }));
          })
      );

      await Promise.allSettled(tasks);
      if (phase1RecommendationGenerationRef.current !== generationId) return;

      const generatedCount = emptyBoardFields.length - failures.length;
      if (generatedCount > 0 && failures.length === 0) {
        setTimedActionMessage(
          `${generatedCount} recommendation${
            generatedCount === 1 ? "" : "s"
          } ready.`,
          3000
        );
      } else if (generatedCount > 0) {
        setActionMessage(
          `${generatedCount} recommendation${
            generatedCount === 1 ? "" : "s"
          } ready. ${failures.length} failed.`
        );
      } else {
        setTimedActionMessage("No recommendations were generated.", 2500);
      }
    } catch (err) {
      setActionMessage(err.message);
    } finally {
      setIsGeneratingRecommendations(false);
    }
  }

  async function generatePhase3Overview() {
    if (
      isParticipant ||
      routePhase !== 3 ||
      !project?.ai_mode_enabled ||
      isGeneratingPhase3Overview
    ) {
      return;
    }

    if (emptyBoardFields.length > 0) {
      setActionMessage(
        "Fill every canvas field before requesting the overview."
      );
      return;
    }

    clearPendingFieldSaveTimers();
    const persisted = await persistPhaseEntriesBeforeAdvance();
    if (!persisted) return;

    // A single request: with 2+ AI specialists the backend has each one review
    // the canvas independently and a moderator consolidates them into one
    // overview per field (their individual reviews come back as `perspectives`).
    setIsGeneratingPhase3Overview(true);
    const generationId = phase3OverviewGenerationRef.current + 1;
    phase3OverviewGenerationRef.current = generationId;
    setPhase3OverviewsByField({});
    setIsPhase3OverviewPending(true);

    try {
      const data = await api(
        `/projects/${projectId}/canvas/overview`,
        "POST",
        {},
        token
      );
      if (phase3OverviewGenerationRef.current !== generationId) return;

      const overviews = data?.overviews || {};
      const perspectives = Array.isArray(data?.perspectives)
        ? data.perspectives
        : [];
      const label =
        data?.mode === "panel"
          ? `AI specialist panel: ${perspectives
              .map((perspective) => perspective.role_title)
              .join(", ")}`
          : data?.role_title || "";
      setPhase3OverviewsByField(
        Object.fromEntries(
          fields
            .filter((field) => String(overviews[field] || "").trim())
            .map((field) => [
              field,
              [
                {
                  id: data?.mode || "overview",
                  label,
                  text: overviews[field],
                  perspectives: perspectives
                    .filter((perspective) => perspective.overviews?.[field])
                    .map((perspective) => ({
                      id: perspective.specialist_id,
                      label: perspective.role_title,
                      text: perspective.overviews[field],
                    })),
                },
              ],
            ])
        )
      );

      const failed = Array.isArray(data?.failed_specialists)
        ? data.failed_specialists
        : [];
      if (failed.length > 0) {
        setActionMessage(
          `Overview ready, but these AI specialists could not respond: ${failed.join(
            ", "
          )}.`
        );
      } else {
        setTimedActionMessage("Overview ready.", 3000);
      }
    } catch (err) {
      if (phase3OverviewGenerationRef.current !== generationId) return;
      setActionMessage(err.message);
    } finally {
      if (phase3OverviewGenerationRef.current === generationId) {
        setIsPhase3OverviewPending(false);
      }
      setIsGeneratingPhase3Overview(false);
    }
  }

  function acceptSuggestion(field, text) {
    setSuggestions((prev) => ({ ...prev, [field]: null }));
    fieldChange(field, `${entries[field] || ""}\n${text}`.trim());
  }

  function dismissSuggestion(field) {
    setSuggestions((prev) => ({ ...prev, [field]: null }));
  }

  function dismissPhase3Overview(field, overviewId) {
    setPhase3OverviewsByField((prev) => {
      const remaining = (prev[field] || []).filter(
        (overview) => overview.id !== overviewId
      );
      const next = { ...prev };
      if (remaining.length > 0) {
        next[field] = remaining;
      } else {
        delete next[field];
      }
      return next;
    });
  }

  async function persistCanvasSnapshotByPolling() {
    if (isParticipant || !project || !actorParticipantId) return;

    const currentEntries = entriesRef.current || {};
    for (const field of fields) {
      if (!Object.prototype.hasOwnProperty.call(currentEntries, field)) {
        continue;
      }
      const content = currentEntries[field] ?? "";
      if (lastSyncedCanvasRef.current[field] === content) continue;

      try {
        await putCanvasResponse(field, content);
      } catch {
        // Silent by design: polling autosave should not interrupt UX.
      }
    }
  }

  useEffect(() => {
    // Read-only review of a past phase must never write the shared canvas.
    if (!project || isParticipant || isReviewMode || !actorParticipantId) return;

    const interval = setInterval(() => {
      void persistCanvasSnapshotByPolling();
    }, canvasAutoSavePollingMs);

    return () => clearInterval(interval);
  }, [
    project?.id,
    project?.current_cycle,
    isParticipant,
    isReviewMode,
    actorParticipantId,
    routePhase,
    token,
  ]);

  async function advancePhase() {
    if (isParticipant) return;
    const isFollowUpCycle = Number(project?.current_cycle || 1) > 1;
    if (routePhase <= 3 && emptyBoardFields.length > 0) {
      setActionMessage(
        "Fill every canvas field before advancing to the next phase."
      );
      return;
    }

    if (
      routePhase === 2 &&
      !isFollowUpCycle &&
      !project?.invite_links_generated
    ) {
      setActionMessage(
        "Generate at least one invite link before advancing to Phase 3."
      );
      return;
    }

    if (
      routePhase === 4 &&
      config.requiresAllParticipantsDone &&
      !completionInfo.all_done
    ) {
      setActionMessage(
        `Waiting for participants to complete evaluation (${completionInfo.required_respondents}).`
      );
      return;
    }

    clearPendingFieldSaveTimers();
    const persisted = await persistPhaseEntriesBeforeAdvance();
    if (!persisted) return;

    try {
      const updated = await api(
        `/projects/${projectId}/advance-phase`,
        "POST",
        {},
        token
      );
      setProject(updated);
      const nextPhase = Number(updated.current_phase || routePhase);
      navigate(participantRoute(nextPhase));
    } catch (err) {
      setActionMessage(err.message);
    }
  }

  async function generateInvite() {
    if (isParticipant || routePhase !== 2) return;
    const normalizedName = String(inviteeName || "").trim();
    if (!normalizedName) {
      setActionMessage(
        "Enter the participant name before generating the link."
      );
      return;
    }
    if (Number(project?.current_cycle || 1) > 1) {
      setActionMessage("Invites are locked after pivot.");
      return;
    }
    try {
      setIsGeneratingInvite(true);
      await api(
        `/projects/${projectId}/invites`,
        "POST",
        { name: normalizedName },
        token
      );
      const refreshedInvites = await fetchInvites();
      setGeneratedInvites(refreshedInvites);
      setInviteeName("");
      setProject((prev) =>
        prev ? { ...prev, invite_links_generated: true } : prev
      );
      setTimedActionMessage("Invite link generated.", 2500);
    } catch (err) {
      setActionMessage(err.message);
    } finally {
      setIsGeneratingInvite(false);
    }
  }

  async function copyInviteUrl(url) {
    try {
      await navigator.clipboard.writeText(url);
      setTimedActionMessage("Invite link copied.", 2500);
    } catch {
      setActionMessage("Failed to copy invite link.");
    }
  }

  async function fetchScores() {
    if (isParticipant) {
      return api(
        `/projects/${projectId}/scores?participant_id=${participantId}`,
        "GET"
      );
    }
    return api(`/projects/${projectId}/scores`, "GET", null, token);
  }

  function applyScoreSummary(data) {
    setResultsInfo(data.criteria || null);
    setCommentsInfo(Array.isArray(data.comments) ? data.comments : []);
    setAiEvaluations(
      Array.isArray(data.ai_evaluations) ? data.ai_evaluations : []
    );
  }

  async function hydrateParticipantAssessment() {
    try {
      const data = await fetchScores();
      const participantScores = data.participant_scores || {};
      const participantComments = data.participant_comments || {};
      const byCriterion = (valueOf) =>
        Object.fromEntries(
          assessmentCriteria.map(({ key, metricKey }) => [
            key,
            valueOf(metricKey),
          ])
        );
      setAssessment(byCriterion((metric) => participantScores[metric] || 1));
      setAssessmentComments(
        byCriterion((metric) => participantComments[metric] || "")
      );
      setAssessmentSaved(
        byCriterion((metric) => participantScores[metric] != null)
      );
    } catch {
      // Non-blocking: participant can still fill and submit.
    }
  }

  async function loadResults() {
    try {
      applyScoreSummary(await fetchScores());
    } catch {
      setResultsInfo(null);
      setCommentsInfo([]);
      setAiEvaluations([]);
    }
  }

  async function refreshCompletion() {
    if (isParticipant) return;

    try {
      const scoresData = await fetchScores();
      setCompletionInfo({
        all_done: Boolean(scoresData.all_done),
        required_respondents: Number(scoresData.required_respondents || 0),
        completed_respondents: Number(scoresData.completed_respondents || 0),
        pending_invites: Number(scoresData.pending_invites || 0),
      });
      applyScoreSummary(scoresData);
    } catch (err) {
      setCompletionInfo({
        all_done: false,
        required_respondents: 0,
        completed_respondents: 0,
        pending_invites: 0,
      });
      setCommentsInfo([]);
      setActionMessage(`Completion status unavailable: ${err.message}`);
    }
  }

  function changeAiSpecialistDraft(specialistId, key, value) {
    setAiSpecialistDrafts((prev) => ({
      ...prev,
      [specialistId]: { ...(prev[specialistId] || {}), [key]: value },
    }));
  }

  function isAiSpecialistDraftDirty(specialist) {
    const draft = aiSpecialistDrafts[specialist.participant_id];
    if (!draft) return false;
    const saved = aiSpecialistToDraft(specialist);
    return (
      draft.role_title.trim() !== saved.role_title.trim() ||
      draft.role_description.trim() !== saved.role_description.trim()
    );
  }

  async function addAiSpecialist() {
    const roleTitle = String(newAiSpecialist.role_title || "").trim();
    if (!roleTitle) {
      setActionMessage("AI specialist role is required.");
      return;
    }
    try {
      setSavingAiSpecialistId("new");
      const created = await api(
        `/projects/${projectId}/ai-specialists`,
        "POST",
        {
          role_title: roleTitle,
          role_description: newAiSpecialist.role_description || null,
        },
        token
      );
      setAiSpecialists((prev) => [...prev, created]);
      setAiSpecialistDrafts((prev) => ({
        ...prev,
        [created.participant_id]: aiSpecialistToDraft(created),
      }));
      setNewAiSpecialist(emptyAiSpecialistDraft);
      setTimedActionMessage("AI specialist added.", 2500);
    } catch (err) {
      setActionMessage(err.message);
    } finally {
      setSavingAiSpecialistId(null);
    }
  }

  async function updateAiSpecialist(specialistId) {
    const draft = aiSpecialistDrafts[specialistId] || emptyAiSpecialistDraft;
    const roleTitle = String(draft.role_title || "").trim();
    if (!roleTitle) {
      setActionMessage("AI specialist role is required.");
      return;
    }
    try {
      setSavingAiSpecialistId(specialistId);
      const updated = await api(
        `/projects/${projectId}/ai-specialists/${specialistId}`,
        "PUT",
        {
          role_title: roleTitle,
          role_description: draft.role_description || null,
        },
        token
      );
      setAiSpecialists((prev) =>
        prev.map((item) =>
          item.participant_id === specialistId ? updated : item
        )
      );
      setAiSpecialistDrafts((prev) => ({
        ...prev,
        [specialistId]: aiSpecialistToDraft(updated),
      }));
      setTimedActionMessage("AI specialist updated.", 2500);
    } catch (err) {
      setActionMessage(err.message);
    } finally {
      setSavingAiSpecialistId(null);
    }
  }

  async function removeAiSpecialist(specialistId) {
    try {
      setRemovingAiSpecialistId(specialistId);
      await api(
        `/projects/${projectId}/ai-specialists/${specialistId}`,
        "DELETE",
        null,
        token
      );
      setAiSpecialists((prev) =>
        prev.filter((item) => item.participant_id !== specialistId)
      );
      setAiSpecialistDrafts((prev) => {
        const next = { ...prev };
        delete next[specialistId];
        return next;
      });
      setTimedActionMessage("AI specialist removed.", 2500);
    } catch (err) {
      setActionMessage(err.message);
    } finally {
      setRemovingAiSpecialistId(null);
    }
  }

  async function requestAiEvaluation(specialistId) {
    setGeneratingAiEvaluationIds((prev) => [...prev, specialistId]);
    try {
      await api(
        `/projects/${projectId}/ai-specialists/${specialistId}/evaluate`,
        "POST",
        {},
        token
      );
    } finally {
      setGeneratingAiEvaluationIds((prev) =>
        prev.filter((id) => id !== specialistId)
      );
    }
  }

  async function generateAiEvaluations(specialistIds) {
    if (specialistIds.length === 0) return;
    // Each specialist evaluates independently, so the requests run in parallel.
    const results = await Promise.allSettled(
      specialistIds.map((specialistId) => requestAiEvaluation(specialistId))
    );
    await refreshCompletion();

    const failures = results
      .map((result, index) => ({ result, specialistId: specialistIds[index] }))
      .filter(({ result }) => result.status === "rejected")
      .map(({ result, specialistId }) => {
        const specialist = aiSpecialists.find(
          (item) => item.participant_id === specialistId
        );
        return `${specialist?.role_title || "AI specialist"}: ${
          result.reason?.message || "failed"
        }`;
      });
    if (failures.length === 0) {
      setTimedActionMessage(
        specialistIds.length === 1
          ? "AI evaluation generated."
          : `${specialistIds.length} AI evaluations generated.`,
        2500
      );
    } else {
      setActionMessage(`AI evaluation failed - ${failures.join(" | ")}`);
    }
  }

  async function resetAiEvaluation(specialistId) {
    try {
      setResettingAiEvaluationId(specialistId);
      await api(
        `/projects/${projectId}/scores/${specialistId}`,
        "DELETE",
        null,
        token
      );
      await refreshCompletion();
      setTimedActionMessage("AI evaluation reset.", 2500);
    } catch (err) {
      setActionMessage(err.message);
    } finally {
      setResettingAiEvaluationId(null);
    }
  }

  async function saveAssessmentCriterion(criterion, value, comment) {
    if (!actorParticipantId || !value) return false;

    const metricKey = criterionByKey[criterion]?.metricKey;
    if (!metricKey) return;

    try {
      await api(
        `/projects/${projectId}/scores`,
        "POST",
        {
          participant_id: actorParticipantId,
          metric_key: metricKey,
          value,
          comment: comment || "",
        },
        token
      );
      setAssessmentSaved((prev) => ({ ...prev, [criterion]: true }));
      return true;
    } catch (err) {
      if (String(err.message).toLowerCase().includes("already submitted")) {
        setAssessmentSaved((prev) => ({ ...prev, [criterion]: true }));
        return true;
      } else {
        setActionMessage(err.message);
        return false;
      }
    }
  }

  async function submitAssessment() {
    if (!actorParticipantId) return;

    for (const criterion of assessmentSubmitOrder) {
      if (assessmentSaved[criterion]) continue;
      await saveAssessmentCriterion(
        criterion,
        assessment[criterion],
        assessmentComments[criterion]
      );
    }
  }

  async function editAssessment() {
    if (!actorParticipantId) return;
    try {
      await api(
        `/projects/${projectId}/scores/${actorParticipantId}`,
        "DELETE",
        null,
        token
      );
      setAssessmentSaved(criteriaState(false));
      setActionMessage(
        "Assessment unlocked for editing. Please submit again when finished."
      );
    } catch (err) {
      setActionMessage(err.message);
    }
  }

  function renderLikertScale(avg, count) {
    const hasResponses = Number(count || 0) > 0;
    const normalized = hasResponses
      ? Math.max(1, Math.min(7, Math.round(Number(avg || 0))))
      : null;

    return (
      <div className="result-scale" aria-label="Assessment scale from 1 to 7">
        {[1, 2, 3, 4, 5, 6, 7].map((value) => {
          const isSelected = normalized === value;
          return (
            <span
              key={value}
              className={`result-scale-point ${isSelected ? "selected" : ""}`}
            >
              {value}
            </span>
          );
        })}
      </div>
    );
  }

  async function submitDecision(decision) {
    if (!token || isParticipant) return;

    const synthesisSaved = await persistProblemSynthesis(false);
    if (!synthesisSaved) return;

    try {
      const updated = await api(
        `/projects/${projectId}/decision`,
        "POST",
        { decision, justification: phase5DecisionMessages[decision] || "" },
        token
      );
      let nextState = updated;
      if (decision === "PIVOT") {
        try {
          nextState = await fetchProjectState();
        } catch (refreshErr) {
          console.warn(
            "Failed to refresh project after pivot decision.",
            refreshErr
          );
        }
      }

      setSelectedDecision(nextState.decision || null);
      setProject((prev) => (prev ? { ...prev, ...nextState } : prev));
      if (decision === "GO" || decision === "ABORT") {
        setActionMessage("Decision saved. You can export the PDF now.");
      } else {
        const targetPhase = Number(nextState?.current_phase || 2);
        setActionMessage(
          "Decision saved. Returning to phase 2 to reformulate."
        );
        navigate(participantRoute(targetPhase), { replace: true });
      }
    } catch (err) {
      setActionMessage(err?.message || "Failed to submit decision.");
    }
  }

  async function exportPdf() {
    if (!token || isParticipant || isExporting || !project) return;
    try {
      const synthesisSaved = await persistProblemSynthesis(false);
      if (!synthesisSaved) return;

      setIsExporting(true);
      setActionMessage("Preparing PDF export...");
      const data = await api(
        `/projects/${projectId}/export/pdf`,
        "POST",
        {},
        token
      );
      const res = await fetch(
        `${API_URL}/projects/${projectId}/export/${data.export_id}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );
      if (!res.ok) {
        throw new Error(
          `Export download failed: ${res.status} ${res.statusText}`
        );
      }
      const blob = await res.blob();
      const filename =
        data.file_path && typeof data.file_path === "string"
          ? data.file_path.split("/").pop() || `project_${projectId}_report.pdf`
          : `project_${projectId}_report.pdf`;
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      setActionMessage("PDF exported.");
    } catch (err) {
      setActionMessage(err.message);
    } finally {
      setIsExporting(false);
    }
  }

  if (loading) return <LoadingState label="Loading phase..." />;
  if (error) return <div className="alert alert-error">{error}</div>;
  if (!project) return null;

  const phaseTitle = phaseLabels[routePhase] || "Phase";
  // Facilitator actions that change the project: hidden while reviewing a past phase.
  const canActOnPhase = !isParticipant && !isReviewMode;
  const canAdvance = canActOnPhase && config.canAdvance;
  const isFollowUpCycle = Number(project?.current_cycle || 1) > 1;
  const canGenerateInvite =
    config.showInviteLink && canActOnPhase && !isFollowUpCycle;
  const missingInviteForPhase3 =
    routePhase === 2 &&
    canActOnPhase &&
    !isFollowUpCycle &&
    !project?.invite_links_generated;
  const phase4Blocked =
    routePhase === 4 && canActOnPhase && config.requiresAllParticipantsDone
      ? !completionInfo.all_done
      : false;
  const canvasAdvanceBlocked =
    canActOnPhase && routePhase <= 3 && emptyBoardFields.length > 0;
  const advanceDisabled =
    missingInviteForPhase3 || phase4Blocked || canvasAdvanceBlocked;
  const assessmentSubmitted = assessmentCriteria.every(
    (criterion) => assessmentSaved[criterion.key]
  );
  const finalDecisionKey = (
    selectedDecision ||
    project?.decision ||
    ""
  ).toUpperCase();
  const hasFinalDecision =
    finalDecisionKey === "GO" || finalDecisionKey === "ABORT";
  const showRecommendationButton =
    routePhase === 1 && canActOnPhase && Boolean(project?.ai_mode_enabled);
  const showPhase3OverviewButton =
    routePhase === 3 && canActOnPhase && Boolean(project?.ai_mode_enabled);
  const completedAiEvaluations = aiEvaluations.filter(
    (evaluation) => evaluation.is_complete
  );
  const pendingAiEvaluationIds = aiSpecialists
    .map((specialist) => specialist.participant_id)
    .filter(
      (specialistId) =>
        !generatingAiEvaluationIds.includes(specialistId) &&
        !completedAiEvaluations.some(
          (evaluation) => evaluation.participant_id === specialistId
        )
    );

  return (
    <div className="project-layout">
      <PhaseStepper
        currentPhaseNumber={currentServerPhase(project)}
        activePhaseNumber={routePhase}
        onSelectPhase={
          isParticipant ? undefined : (phase) => navigate(participantRoute(phase))
        }
      />

      <section className="project-main">
        <div className="card">
          <div className="section-header">
            <div>
              <h1>{phaseTitle}</h1>
              <p className="muted">Project: {project.title}</p>
            </div>
            <div className="phase-chip">Phase {routePhase}</div>
          </div>
          {isReviewMode && (
            <div className="review-banner" role="status">
              <span>
                Viewing Phase {routePhase} (read-only). The project is in Phase{" "}
                {serverPhaseNumber}.
                {routePhase <= 3 &&
                  " The canvas shows its current content: edits made in later phases replace earlier text."}
              </span>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => navigate(participantRoute(serverPhaseNumber))}
              >
                Back to current phase
              </button>
            </div>
          )}
        </div>

        <div className="card">
          {routePhase <= 3 && (
            <>
              <div className="section-header board-section-header">
                <h2>
                  {isParticipant
                    ? "Workshop Contribution"
                    : "Problem Vision board"}
                </h2>
                {(showRecommendationButton || showPhase3OverviewButton) && (
                  <div className="board-actions">
                    {showRecommendationButton && (
                      <button
                        className="btn btn-success"
                        type="button"
                        onClick={generateRecommendations}
                        disabled={
                          isGeneratingRecommendations ||
                          filledBoardFields.length === 0 ||
                          emptyBoardFields.length === 0
                        }
                      >
                        {isGeneratingRecommendations
                          ? "Generating..."
                          : "Get recommendation"}
                      </button>
                    )}
                    {showPhase3OverviewButton && (
                      <button
                        className="btn btn-success"
                        type="button"
                        onClick={generatePhase3Overview}
                        disabled={
                          isGeneratingPhase3Overview ||
                          emptyBoardFields.length > 0
                        }
                      >
                        {isGeneratingPhase3Overview
                          ? "Generating..."
                          : "Get overview"}
                      </button>
                    )}
                    {showPhase3OverviewButton && (
                      <p className="hint">
                        {aiSpecialists.length > 1
                          ? `Each AI specialist reviews the canvas independently, then their views are consolidated into one overview per field: ${aiSpecialists
                              .map((specialist) => specialist.role_title)
                              .join(", ")}.`
                          : aiSpecialists.length === 1
                          ? `Overview will reflect the perspective of: ${aiSpecialists[0].role_title}`
                          : "No AI specialist configured: the overview uses a research methodology perspective."}
                      </p>
                    )}
                  </div>
                )}
              </div>
              {fields.map((f) => (
                <div key={f}>
                  <FieldEditor
                    field={f}
                    label={
                      (routePhase === 3 ? PHASE3_FIELD_LABELS : FIELD_LABELS)[f]
                    }
                    placeholder={routePhase === 3 ? "" : FIELD_PLACEHOLDERS[f]}
                    value={entries[f]}
                    suggestion={suggestionsEnabled ? suggestions[f] : null}
                    aiOverviews={
                      routePhase === 3 ? phase3OverviewsByField[f] : null
                    }
                    aiOverviewPending={
                      routePhase === 3 && isPhase3OverviewPending
                    }
                    pending={
                      suggestionsEnabled
                        ? recommendationPendingByField[f]
                        : false
                    }
                    readOnly={!canActOnPhase}
                    onChange={fieldChange}
                    onAccept={acceptSuggestion}
                    onDismiss={dismissSuggestion}
                    onDismissOverview={dismissPhase3Overview}
                  />
                </div>
              ))}
            </>
          )}

          {routePhase === 2 && !isParticipant && (
            <div className="field-card invite-card">
              <div className="invite-card-header">
                <h3>Invite Participants</h3>
                <p className="muted">
                  Add each participant name and generate one unique invite link.
                </p>
              </div>
              <div className="invite-create-row">
                <input
                  type="text"
                  value={inviteeName}
                  onChange={(event) => setInviteeName(event.target.value)}
                  placeholder="Participant name"
                  disabled={!canGenerateInvite || isGeneratingInvite}
                />
                <button
                  className="btn btn-secondary"
                  onClick={generateInvite}
                  disabled={
                    !canGenerateInvite ||
                    isGeneratingInvite ||
                    !String(inviteeName || "").trim()
                  }
                >
                  {isGeneratingInvite
                    ? "Generating..."
                    : "Generate Invite Link"}
                </button>
              </div>
              {generatedInvites.length > 0 ? (
                <div className="invite-list">
                  {generatedInvites.map((entry, index) => (
                    <div
                      className="invite-item"
                      key={entry.id || `${entry.name}-${index}`}
                    >
                      <strong>{entry.name}</strong>
                      {entry.invite_url ? (
                        <a href={entry.invite_url}>{entry.invite_url}</a>
                      ) : (
                        <span className="muted">
                          Legacy invite (link unavailable)
                        </span>
                      )}
                      <button
                        type="button"
                        className="btn btn-tertiary btn-sm"
                        disabled={!entry.invite_url}
                        onClick={() => copyInviteUrl(entry.invite_url)}
                      >
                        Copy
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="hint">No invite links generated yet.</p>
              )}
              {isFollowUpCycle && (
                <p className="hint">
                  Invites are locked after pivot. Continue with the same
                  participant group.
                </p>
              )}
            </div>
          )}

          {routePhase === 2 && isReviewMode && (
            <div className="field-card card-stack">
              <div className="invite-card-header">
                <h3>AI Specialists</h3>
              </div>
              {aiSpecialists.length > 0 ? (
                <div className="ai-specialist-list">
                  {aiSpecialists.map((specialist, index) => (
                    <div
                      className="ai-specialist-item"
                      key={specialist.participant_id}
                    >
                      <span className="phase-badge">
                        Specialist {index + 1}
                      </span>
                      <strong>{specialist.role_title}</strong>
                      {specialist.role_description && (
                        <p className="muted">{specialist.role_description}</p>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="hint">No AI specialist was configured.</p>
              )}
            </div>
          )}

          {routePhase === 2 && canActOnPhase && (
            <div className="field-card card-stack">
              <div className="invite-card-header">
                <h3>AI Specialists (optional)</h3>
                <p className="muted">
                  If no one in this workshop covers a needed expertise, have
                  the AI join as that specialist (up to {maxAiSpecialists}).
                  Each one reviews the reformulated problem and evaluates it
                  from its own perspective, alongside the human participants.
                </p>
              </div>
              {!project?.ai_mode_enabled && (
                <p className="hint">
                  AI mode is disabled for this project, so AI specialists
                  cannot be added.
                </p>
              )}
              {aiSpecialists.length > 0 && (
                <div className="ai-specialist-list">
                  {aiSpecialists.map((specialist, index) => {
                    const specialistId = specialist.participant_id;
                    const draft =
                      aiSpecialistDrafts[specialistId] ||
                      aiSpecialistToDraft(specialist);
                    const isSaving = savingAiSpecialistId === specialistId;
                    const isRemoving = removingAiSpecialistId === specialistId;
                    return (
                      <div className="ai-specialist-item" key={specialistId}>
                        <span className="phase-badge">
                          Specialist {index + 1}
                        </span>
                        <div className="form-grid">
                          <label htmlFor={`ai-specialist-role-${specialistId}`}>
                            Specialist role
                          </label>
                          <input
                            id={`ai-specialist-role-${specialistId}`}
                            type="text"
                            value={draft.role_title}
                            maxLength={aiSpecialistRoleMaxLength}
                            onChange={(event) =>
                              changeAiSpecialistDraft(
                                specialistId,
                                "role_title",
                                event.target.value
                              )
                            }
                            disabled={isSaving || isRemoving}
                          />
                          <label
                            htmlFor={`ai-specialist-context-${specialistId}`}
                          >
                            Context
                          </label>
                          <textarea
                            id={`ai-specialist-context-${specialistId}`}
                            value={draft.role_description}
                            maxLength={aiSpecialistContextMaxLength}
                            onChange={(event) =>
                              changeAiSpecialistDraft(
                                specialistId,
                                "role_description",
                                event.target.value
                              )
                            }
                            placeholder="Experience, focus and what this specialist should pay attention to."
                            disabled={isSaving || isRemoving}
                          />
                          <p className="hint">
                            {draft.role_description.length}/
                            {aiSpecialistContextMaxLength} characters
                          </p>
                        </div>
                        <div className="row gap-8">
                          <button
                            className="btn btn-secondary"
                            type="button"
                            onClick={() => updateAiSpecialist(specialistId)}
                            disabled={
                              isSaving ||
                              isRemoving ||
                              !draft.role_title.trim() ||
                              !isAiSpecialistDraftDirty(specialist)
                            }
                          >
                            {isSaving ? "Saving..." : "Save changes"}
                          </button>
                          <button
                            className="btn btn-tertiary"
                            type="button"
                            onClick={() => removeAiSpecialist(specialistId)}
                            disabled={isSaving || isRemoving}
                          >
                            {isRemoving ? "Removing..." : "Remove"}
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
              {aiSpecialists.length < maxAiSpecialists ? (
                <div className="ai-specialist-item ai-specialist-new">
                  <div className="form-grid">
                    <label htmlFor="ai-specialist-role-new">
                      {aiSpecialists.length > 0
                        ? "Add another specialist role"
                        : "Specialist role"}
                    </label>
                    <input
                      id="ai-specialist-role-new"
                      type="text"
                      value={newAiSpecialist.role_title}
                      maxLength={aiSpecialistRoleMaxLength}
                      onChange={(event) =>
                        setNewAiSpecialist((prev) => ({
                          ...prev,
                          role_title: event.target.value,
                        }))
                      }
                      placeholder="e.g. Sales specialist"
                      disabled={
                        savingAiSpecialistId === "new" ||
                        !project?.ai_mode_enabled
                      }
                    />
                    <label htmlFor="ai-specialist-context-new">
                      Context (recommended)
                    </label>
                    <textarea
                      id="ai-specialist-context-new"
                      value={newAiSpecialist.role_description}
                      maxLength={aiSpecialistContextMaxLength}
                      onChange={(event) =>
                        setNewAiSpecialist((prev) => ({
                          ...prev,
                          role_description: event.target.value,
                        }))
                      }
                      placeholder="Experience, focus and what this specialist should pay attention to. The more specific the context, the more specific its answers."
                      disabled={
                        savingAiSpecialistId === "new" ||
                        !project?.ai_mode_enabled
                      }
                    />
                    <p className="hint">
                      {newAiSpecialist.role_description.length}/
                      {aiSpecialistContextMaxLength} characters
                    </p>
                  </div>
                  <div className="row gap-8">
                    <button
                      className="btn btn-secondary"
                      type="button"
                      onClick={addAiSpecialist}
                      disabled={
                        savingAiSpecialistId === "new" ||
                        !project?.ai_mode_enabled ||
                        !newAiSpecialist.role_title.trim()
                      }
                    >
                      {savingAiSpecialistId === "new"
                        ? "Adding..."
                        : "Add AI specialist"}
                    </button>
                  </div>
                </div>
              ) : (
                <p className="hint">
                  Maximum of {maxAiSpecialists} AI specialists reached. Remove
                  one to add another.
                </p>
              )}
              <p className="hint">
                {aiSpecialists.length} of {maxAiSpecialists} AI specialists
                configured.
              </p>
            </div>
          )}

          {routePhase === 4 && (
            <>
              <h2>Semantic Differential Scale</h2>
              {isParticipant ? (
                <div className="assessment-grid">
                  {assessmentCriteria.map(({ key: criterion, anchors, description }) => (
                    <div className="field-card" key={criterion}>
                      <label>{description}</label>
                      <div className="semantic-scale-row">
                        <span className="semantic-anchor">{anchors.left}</span>
                        <div
                          className="semantic-scale"
                          role="radiogroup"
                          aria-label={`${criterion} scale from 1 to 7`}
                        >
                          {[1, 2, 3, 4, 5, 6, 7].map((value) => {
                            const isSelected =
                              Number(assessment[criterion] || 1) === value;
                            return (
                              <button
                                key={value}
                                type="button"
                                role="radio"
                                aria-checked={isSelected}
                                className={`semantic-scale-option ${
                                  isSelected ? "selected" : ""
                                }`}
                                disabled={assessmentSaved[criterion]}
                                onClick={() =>
                                  setAssessment((prev) => ({
                                    ...prev,
                                    [criterion]: value,
                                  }))
                                }
                              >
                                {value}
                              </button>
                            );
                          })}
                        </div>
                        <span className="semantic-anchor">{anchors.right}</span>
                      </div>
                      {assessmentSaved[criterion] && (
                        <span className="phase-badge">Completed</span>
                      )}
                      <div className="form-grid">
                        <label htmlFor={`comment-${criterion}`}>
                          Comment (optional)
                        </label>
                        <textarea
                          id={`comment-${criterion}`}
                          value={assessmentComments[criterion] || ""}
                          onChange={(event) =>
                            setAssessmentComments((prev) => ({
                              ...prev,
                              [criterion]: event.target.value,
                            }))
                          }
                          placeholder="Add your comment about this aspect"
                          disabled={assessmentSaved[criterion]}
                        />
                      </div>
                    </div>
                  ))}
                  <div className="field-card">
                    <div className="row gap-8">
                      <button
                        className="btn btn-primary"
                        onClick={submitAssessment}
                        disabled={assessmentSubmitted}
                      >
                        Submit assessment
                      </button>
                      {assessmentSubmitted && (
                        <button
                          className="btn btn-secondary"
                          onClick={editAssessment}
                        >
                          Edit assessment
                        </button>
                      )}
                    </div>
                    {assessmentSubmitted && (
                      <p className="hint">Assessment submitted.</p>
                    )}
                  </div>
                </div>
              ) : (
                <div>
                  <p className="muted">
                    Advance is enabled only when all respondents complete their
                    assessments.
                  </p>
                  <p className="hint">
                    Status:{" "}
                    {completionInfo.all_done
                      ? `All participants completed (${completionInfo.completed_respondents}/${completionInfo.required_respondents})`
                      : `Waiting for participants (${completionInfo.completed_respondents}/${completionInfo.required_respondents})`}
                    {completionInfo.pending_invites > 0 &&
                      ` - ${completionInfo.pending_invites} invite(s) pending acceptance`}
                  </p>
                </div>
              )}
              {!isParticipant && aiSpecialists.length > 0 && (
                <div className="field-card card-stack">
                  <h3>AI Specialists</h3>
                  <p className="muted">
                    Each AI specialist evaluates the problem independently,
                    without seeing anyone else's scores. Their evaluations are
                    shown separately in phase 5 and never count toward the
                    consolidated results.
                  </p>
                  <div className="ai-specialist-list">
                    {aiSpecialists.map((specialist) => {
                      const specialistId = specialist.participant_id;
                      const evaluation = aiEvaluations.find(
                        (item) => item.participant_id === specialistId
                      );
                      const isGenerating =
                        generatingAiEvaluationIds.includes(specialistId);
                      const isResetting =
                        resettingAiEvaluationId === specialistId;
                      return (
                        <div className="ai-specialist-item" key={specialistId}>
                          <strong>{specialist.role_title}</strong>
                          {evaluation?.is_complete ? (
                            <div className="row gap-8">
                              <span className="phase-badge">Evaluated</span>
                              {canActOnPhase && (
                                <button
                                  className="btn btn-secondary btn-sm"
                                  type="button"
                                  onClick={() => resetAiEvaluation(specialistId)}
                                  disabled={isResetting}
                                >
                                  {isResetting
                                    ? "Resetting..."
                                    : "Reset AI evaluation"}
                                </button>
                              )}
                            </div>
                          ) : canActOnPhase ? (
                            <div className="row gap-8">
                              <button
                                className="btn btn-primary btn-sm"
                                type="button"
                                onClick={() =>
                                  generateAiEvaluations([specialistId])
                                }
                                disabled={isGenerating}
                              >
                                {isGenerating
                                  ? "Generating..."
                                  : "Generate AI evaluation"}
                              </button>
                            </div>
                          ) : (
                            <p className="hint">Not evaluated.</p>
                          )}
                        </div>
                      );
                    })}
                  </div>
                  {canActOnPhase && pendingAiEvaluationIds.length > 1 && (
                    <div className="row gap-8">
                      <button
                        className="btn btn-primary"
                        type="button"
                        onClick={() =>
                          generateAiEvaluations(pendingAiEvaluationIds)
                        }
                      >
                        Generate all pending AI evaluations
                      </button>
                    </div>
                  )}
                </div>
              )}
            </>
          )}

          {routePhase === 5 && (
            <>
              <h2>Results</h2>
              {resultsInfo ? (
                <div className="results-grid">
                  {assessmentCriteria.map(({ metricKey, resultLabel }) => {
                    const info = resultsInfo[metricKey] || {
                      avg: 0,
                      median: 0,
                      count: 0,
                    };
                    const responseCount = Number(info.count || 0);
                    const displayValue = Number(
                      info.median != null ? info.median : info.avg || 0
                    );
                    return (
                      <div
                        className="field-card result-metric-card"
                        key={metricKey}
                      >
                        <div className="result-metric-row">
                          <div className="result-metric-text">
                            <h3>{resultLabel}</h3>
                            <p className="result-summary">
                              Median {displayValue.toFixed(1)} • {responseCount}{" "}
                              {responseCount === 1 ? "response" : "responses"}
                            </p>
                          </div>
                          {renderLikertScale(displayValue, info.count)}
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="muted">No score aggregates available yet.</p>
              )}

              {!isParticipant && (
                <div className="decision-section">
                  <div className="decision-divider" />
                  <h2>Decision</h2>
                  {hasFinalDecision ? (
                    <>
                      <p className="muted">
                        {phase5DecisionMessages[finalDecisionKey]}
                      </p>
                      <div className="action-group decision-primary-action">
                        <button
                          className="btn btn-primary"
                          onClick={exportPdf}
                          disabled={isExporting}
                        >
                          {isExporting ? "Exporting PDF..." : "Export PDF"}
                        </button>
                      </div>
                    </>
                  ) : (
                    <>
                      <p className="muted">
                        Based on the assessment results, choose the next step
                        for this research problem.
                      </p>
                      <div className="decision-actions">
                        {phase5Decisions.map((decision) => (
                          <button
                            key={decision}
                            type="button"
                            aria-pressed={selectedDecision === decision}
                            aria-label={decisionAriaLabels[decision]}
                            className={`btn decision-btn decision-${decision.toLowerCase()} ${
                              selectedDecision === decision ? "selected" : ""
                            }`}
                            onClick={() => submitDecision(decision)}
                          >
                            {decision}
                          </button>
                        ))}
                      </div>
                    </>
                  )}
                </div>
              )}
              <div className="decision-section">
                <div className="decision-divider" />
                <h2>Comments</h2>
                {commentsInfo.length > 0 ? (
                  <div className="comments-grid">
                    {commentsInfo.map((entry, index) => {
                      const commentsByMetric = entry.comments || {};
                      const commentPairs = Object.entries(commentsByMetric);
                      return (
                        <div
                          className="field-card comment-card"
                          key={entry.participant_id || index}
                        >
                          <h3>{entry.participant_label || "Participant"}</h3>
                          {commentPairs.length > 0 ? (
                            <div className="comment-list">
                              {commentPairs.map(([metricKey, text]) => (
                                <p
                                  key={`${
                                    entry.participant_id || index
                                  }-${metricKey}`}
                                >
                                  <strong>
                                    {criterionLabelByMetric[metricKey] ||
                                      metricKey}
                                    :
                                  </strong>{" "}
                                  {text}
                                </p>
                              ))}
                            </div>
                          ) : (
                            <p className="muted">No comments submitted.</p>
                          )}
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="muted">No comments submitted yet.</p>
                )}
              </div>
              {completedAiEvaluations.length > 0 && (
                <div className="decision-section">
                  <div className="decision-divider" />
                  <h2>
                    AI Specialist Perspective
                    {completedAiEvaluations.length === 1 ? "" : "s"}
                  </h2>
                  <div className="comments-grid">
                    {completedAiEvaluations.map((evaluation) => (
                      <div
                        className="field-card comment-card"
                        key={evaluation.participant_id}
                      >
                        <h3>{evaluation.role_title}</h3>
                        <div className="comment-list">
                          {assessmentCriteria.map(({ metricKey, resultLabel }) => {
                            const entry = evaluation.scores?.[metricKey];
                            if (!entry) return null;
                            return (
                              <p key={metricKey}>
                                <strong>
                                  {resultLabel}: {entry.value}/7
                                </strong>{" "}
                                {entry.comment}
                              </p>
                            );
                          })}
                        </div>
                      </div>
                    ))}
                  </div>
                  <p className="hint">
                    Shown for comparison only — not included in the
                    consolidated results above or in the final decision.
                  </p>
                </div>
              )}
              {!isParticipant && (
                <div className="decision-section">
                  <div className="decision-divider" />
                  <h2>Problem Synthesis</h2>
                  <div className="field-card">
                    <div className="form-grid">
                      <label htmlFor="problem-synthesis">
                        Researcher synthesis of the problem
                      </label>
                      <textarea
                        id="problem-synthesis"
                        value={problemSynthesis}
                        onChange={handleProblemSynthesisChange}
                        onBlur={handleProblemSynthesisBlur}
                        placeholder="Write the problem synthesis that should appear in the PDF."
                      />
                      <p className="hint">
                        Saved automatically and used in the PDF decision text.
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}

          <div className="action-divider" />
          <div className="action-group primary-group">
            {config.canSaveDraft && canActOnPhase && (
              <button className="btn btn-secondary" onClick={saveAllDraft}>
                Save draft
              </button>
            )}
            {canAdvance && (
              <button
                className="btn btn-primary"
                onClick={advancePhase}
                disabled={advanceDisabled}
              >
                {`Advance to Phase ${Math.min(routePhase + 1, 5)}`}
              </button>
            )}
          </div>

          {missingInviteForPhase3 && (
            <p className="hint">
              Generate at least one invite link in Phase 2 before advancing to
              Phase 3.
            </p>
          )}

          {phase4Blocked && (
            <p className="hint">
              Waiting for all participants to complete evaluation before
              advancing to Phase 5.
            </p>
          )}

          {canvasAdvanceBlocked && (
            <p className="hint">
              Fill every canvas field before advancing to the next phase.
            </p>
          )}

          {actionMessage && <p className="hint">{actionMessage}</p>}
        </div>
      </section>
    </div>
  );
}
