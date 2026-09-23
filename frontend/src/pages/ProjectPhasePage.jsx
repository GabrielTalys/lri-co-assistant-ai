import React, { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import FieldEditor from "../components/FieldEditor";
import LoadingState from "../components/LoadingState";
import PhaseStepper from "../components/PhaseStepper";
import {
  enumToPhaseNumber,
  phaseConfig,
  phaseLabels,
} from "../config/phaseConfig";
import { API_URL, api } from "../services/api";

const phaseFields = {
  1: [
    "problem",
    "stakeholders",
    "research_questions",
    "hypotheses",
    "method",
    "evaluation",
    "risks",
  ],
  2: [
    "problem",
    "stakeholders",
    "research_questions",
    "hypotheses",
    "method",
    "evaluation",
    "risks",
  ],
  3: [
    "problem",
    "stakeholders",
    "research_questions",
    "hypotheses",
    "method",
    "evaluation",
    "risks",
  ],
  4: [],
  5: ["observations"],
};

const scoreCriterionToMetric = {
  valuable: "impact",
  feasible: "feasibility",
  applicable: "alignment",
};

const phase5ResultOrder = [
  { metricKey: "impact", label: "Value" },
  { metricKey: "alignment", label: "Applicability" },
  { metricKey: "feasibility", label: "Feasibility" },
];

const metricKeyToCriterionLabel = {
  impact: "Valuable",
  alignment: "Applicable",
  feasibility: "Feasible",
};

const phase5DecisionMessages = {
  GO: "The formulated problem received a 'Go' because of its high perceived relevance!",
  ABORT:
    "The formulated problem was aborted because of its low perceived relevance!",
  PIVOT:
    "The formulated problem was selected for reformulation before continuing.",
};

const phase5FinalDecisionMessages = {
  GO: "The formulated problem received a 'Go' because of its high perceived relevance!",
  ABORT:
    "The formulated problem was aborted because of its low perceived relevance!",
};

const semanticAnchors = {
  valuable: { left: "Not Valuable", right: "Valuable" },
  applicable: { left: "Not Applicable", right: "Applicable" },
  feasible: { left: "Not Feasible", right: "Feasible" },
};

const assessmentCriterionDescriptions = {
  valuable:
    "Valuable: To what extent does addressing the formulated problem have the potential to generate meaningful value for industrial practice?",
  applicable:
    "Applicable: To what extent can the expected results of this formulated research problem be realistically applied in real industry scenarios (considering factors such as adoption potential, contextual fit, and stakeholder willingness to use the outcomes)?",
  feasible:
    "Feasible: To what extent can this research problem be realistically investigated with the resources typically available?",
};

const phase5Decisions = ["GO", "PIVOT", "ABORT"];
const decisionAriaLabels = {
  GO: "Proceed with the research problem",
  ABORT: "Stop pursuing this research problem",
  PIVOT: "Refine the research problem before continuing",
};
const canvasAutoSavePollingMs = 5000;

const phase3CanvasTitles = {
  problem: "For the practical problem (what/how/why)",
  stakeholders: "Involved in the context (where/when)",
  research_questions: "Which bring the following implications/impacts (why) ",
  hypotheses: "For the stakeholders (who)",
  method: "We have the following evidence (how)",
  evaluation: "And we want to investigate - objective (what/how)",
  risks: "Answering the following research questions (what)",
};

const canonicalCanvasKeys = new Set([
  "problem",
  "stakeholders",
  "research_questions",
  "hypotheses",
  "method",
  "evaluation",
  "risks",
]);

const legacyCanvasKeyAliases = {
  describe_the_pain_point: "problem",
  characterize_the_environment: "stakeholders",
  consequences_benefits: "research_questions",
  identify_people_involved: "hypotheses",
  what_scientific_evidence: "method",
  define_the_objectives: "evaluation",
  what_research_questions: "risks",
};

function normalizeCanvasKey(rawKey) {
  if (!rawKey) return null;
  const normalized = String(rawKey)
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");

  if (!normalized) return null;
  if (canonicalCanvasKeys.has(normalized)) return normalized;
  return legacyCanvasKeyAliases[normalized] || null;
}

function mapCanvasItems(items) {
  const nextEntries = {};
  const nextSuggestions = {};

  for (const item of items || []) {
    const key = normalizeCanvasKey(item.question_key);
    if (!key) continue;

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

  const participantSession = useMemo(() => {
    const raw = localStorage.getItem("participant");
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch {
      return null;
    }
  }, []);

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
  const [phase3OverviewsByField, setPhase3OverviewsByField] = useState({});
  const [phase3OverviewPendingByField, setPhase3OverviewPendingByField] =
    useState({});

  const [entries, setEntries] = useState({});
  const [suggestions, setSuggestions] = useState({});
  const [recommendationPendingByField, setRecommendationPendingByField] =
    useState({});

  const [inviteeName, setInviteeName] = useState("");
  const [generatedInvites, setGeneratedInvites] = useState([]);
  const [isGeneratingInvite, setIsGeneratingInvite] = useState(false);
  const [assessment, setAssessment] = useState({
    valuable: 1,
    feasible: 1,
    applicable: 1,
  });
  const [assessmentComments, setAssessmentComments] = useState({
    valuable: "",
    feasible: "",
    applicable: "",
  });
  const [assessmentSaved, setAssessmentSaved] = useState({
    valuable: false,
    feasible: false,
    applicable: false,
  });
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

  const participantQuery = isParticipant
    ? `?participant_id=${participantId}`
    : "";
  const currentPhaseNumber = enumToPhaseNumber(project?.current_phase);

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
      if (serverPhase !== routePhase) {
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

      if (isParticipant && routePhase === 4 && participantId) {
        await hydrateParticipantAssessment(participantId);
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
    const serverPhase = Number(project.current_phase || 1);
    if (serverPhase !== routePhase) {
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
    if (isParticipant) {
      setInviteeName("");
      setGeneratedInvites([]);
      return;
    }
    setInviteeName("");
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
        const latestPhase = currentServerPhase(latest);
        if (latestPhase !== routePhase) {
          setProject((prev) => ({ ...prev, ...latest }));
          navigate(participantRoute(latestPhase), { replace: true });
        } else {
          setProject((prev) => ({ ...prev, ...latest }));
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

  useEffect(() => {
    lastSyncedCanvasRef.current = {};
  }, [projectId, project?.current_cycle, routePhase]);

  useEffect(() => {
    phase1RecommendationGenerationRef.current += 1;
    setRecommendationPendingByField({});
    setIsGeneratingRecommendations(false);
  }, [projectId, project?.current_cycle, routePhase]);

  useEffect(() => {
    phase3OverviewGenerationRef.current += 1;
    setPhase3OverviewsByField({});
    setPhase3OverviewPendingByField({});
    setIsGeneratingPhase3Overview(false);
  }, [projectId, project?.current_cycle, routePhase]);

  useEffect(() => {
    return () => {
      if (actionMessageTimerRef.current) {
        clearTimeout(actionMessageTimerRef.current);
      }
      if (problemSynthesisSaveTimerRef.current) {
        clearTimeout(problemSynthesisSaveTimerRef.current);
      }
      for (const timer of Object.values(saveTimersRef.current || {})) {
        clearTimeout(timer);
      }
      saveTimersRef.current = {};
    };
  }, []);

  useEffect(() => {
    for (const timer of Object.values(saveTimersRef.current || {})) {
      clearTimeout(timer);
    }
    saveTimersRef.current = {};
    if (problemSynthesisSaveTimerRef.current) {
      clearTimeout(problemSynthesisSaveTimerRef.current);
      problemSynthesisSaveTimerRef.current = null;
    }
  }, [projectId, routePhase]);

  useEffect(() => {
    if (actionMessageTimerRef.current) {
      clearTimeout(actionMessageTimerRef.current);
      actionMessageTimerRef.current = null;
    }
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

  function setTimedActionMessage(message, durationMs = 0) {
    setActionMessage(message);

    if (actionMessageTimerRef.current) {
      clearTimeout(actionMessageTimerRef.current);
      actionMessageTimerRef.current = null;
    }

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
      setPhase3OverviewPendingByField({});
    }

    if (!config.collaborativeAutoSave || !actorParticipantId) return;

    clearTimeout(saveTimersRef.current[field]);
    saveTimersRef.current[field] = setTimeout(
      () => saveEntry(field, content),
      700
    );
  }

  async function saveEntry(field, content, explicit = false) {
    if (!project || !actorParticipantId) return;

    try {
      await api(
        `/projects/${projectId}/canvas/${encodeURIComponent(field)}/response`,
        "PUT",
        {
          participant_id: actorParticipantId,
          content,
        },
        token
      );
      lastSyncedCanvasRef.current[field] = content ?? "";
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
    const nextValue = event.target.value;
    setProblemSynthesis(nextValue);

    if (problemSynthesisSaveTimerRef.current) {
      clearTimeout(problemSynthesisSaveTimerRef.current);
    }

    problemSynthesisSaveTimerRef.current = setTimeout(() => {
      void persistProblemSynthesis(false);
      problemSynthesisSaveTimerRef.current = null;
    }, 700);
  }

  async function handleProblemSynthesisBlur() {
    if (problemSynthesisSaveTimerRef.current) {
      clearTimeout(problemSynthesisSaveTimerRef.current);
      problemSynthesisSaveTimerRef.current = null;
    }
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
        await api(
          `/projects/${projectId}/canvas/${encodeURIComponent(field)}/response`,
          "PUT",
          {
            participant_id: actorParticipantId,
            content: entries[field] ?? "",
          },
          token
        );
        lastSyncedCanvasRef.current[field] = entries[field] ?? "";
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

    const filledFields = fields.filter(
      (field) => String(entries[field] || "").trim().length > 0
    );
    const emptyFields = fields.filter(
      (field) => String(entries[field] || "").trim().length === 0
    );

    if (filledFields.length === 0) {
      setActionMessage(
        "Fill at least one board field before requesting recommendations."
      );
      return;
    }

    if (emptyFields.length === 0) {
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
      Object.fromEntries(emptyFields.map((field) => [field, true]))
    );

    try {
      const failures = [];
      const tasks = emptyFields.map((field) =>
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

      const generatedCount = emptyFields.length - failures.length;
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

    setIsGeneratingPhase3Overview(true);
    const generationId = phase3OverviewGenerationRef.current + 1;
    phase3OverviewGenerationRef.current = generationId;
    setPhase3OverviewsByField({});
    setPhase3OverviewPendingByField(
      Object.fromEntries(fields.map((field) => [field, true]))
    );

    try {
      const failures = [];
      const tasks = fields.map((field) =>
        api(
          `/projects/${projectId}/canvas/${encodeURIComponent(field)}/overview`,
          "POST",
          {},
          token
        )
          .then((data) => {
            if (phase3OverviewGenerationRef.current !== generationId) return;
            const overviewText = String(data?.overview_text || "").trim();
            if (overviewText) {
              setPhase3OverviewsByField((prev) => ({
                ...prev,
                [field]: overviewText,
              }));
            }
          })
          .catch((err) => {
            failures.push({ field, message: err.message });
          })
          .finally(() => {
            if (phase3OverviewGenerationRef.current !== generationId) return;
            setPhase3OverviewPendingByField((prev) => ({
              ...prev,
              [field]: false,
            }));
          })
      );

      await Promise.allSettled(tasks);
      if (phase3OverviewGenerationRef.current !== generationId) return;

      const generatedCount = fields.length - failures.length;
      if (generatedCount > 0 && failures.length === 0) {
        setTimedActionMessage(
          `${generatedCount} overview${generatedCount === 1 ? "" : "s"} ready.`,
          3000
        );
      } else if (generatedCount > 0) {
        setActionMessage(
          `${generatedCount} overview${
            generatedCount === 1 ? "" : "s"
          } ready. ${failures.length} failed.`
        );
      } else {
        setTimedActionMessage("No overviews were generated.", 2500);
      }
    } catch (err) {
      setActionMessage(err.message);
    } finally {
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

  function dismissPhase3Overview(field) {
    setPhase3OverviewsByField((prev) => {
      const next = { ...prev };
      delete next[field];
      return next;
    });
    setPhase3OverviewPendingByField((prev) => ({
      ...prev,
      [field]: false,
    }));
  }

  async function persistCanvasSnapshotByPolling() {
    if (isParticipant || !project || !actorParticipantId) return;

    const currentEntries = entriesRef.current || {};
    const syncFields = fields.filter(
      (field) =>
        canonicalCanvasKeys.has(field) &&
        Object.prototype.hasOwnProperty.call(currentEntries, field)
    );
    if (syncFields.length === 0) return;

    for (const field of syncFields) {
      const content = currentEntries[field] ?? "";
      if (lastSyncedCanvasRef.current[field] === content) continue;

      try {
        await api(
          `/projects/${projectId}/canvas/${encodeURIComponent(field)}/response`,
          "PUT",
          {
            participant_id: actorParticipantId,
            content,
          },
          token
        );
        lastSyncedCanvasRef.current[field] = content;
      } catch {
        // Silent by design: polling autosave should not interrupt UX.
      }
    }
  }

  useEffect(() => {
    if (!project || isParticipant || !actorParticipantId) return;

    const interval = setInterval(() => {
      void persistCanvasSnapshotByPolling();
    }, canvasAutoSavePollingMs);

    return () => clearInterval(interval);
  }, [
    project?.id,
    project?.current_cycle,
    isParticipant,
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

  async function loadScores() {
    if (isParticipant) {
      return api(
        `/projects/${projectId}/scores?participant_id=${participantId}`,
        "GET"
      );
    }
    return api(`/projects/${projectId}/scores`, "GET", null, token);
  }

  async function hydrateParticipantAssessment(currentParticipantId) {
    try {
      const data = await api(
        `/projects/${projectId}/scores?participant_id=${currentParticipantId}`,
        "GET",
        null,
        token
      );
      const participantScores = data.participant_scores || {};
      const nextAssessment = {
        valuable: participantScores.impact || 1,
        feasible: participantScores.feasibility || 1,
        applicable: participantScores.alignment || 1,
      };
      const participantComments = data.participant_comments || {};
      const nextComments = {
        valuable: participantComments.impact || "",
        feasible: participantComments.feasibility || "",
        applicable: participantComments.alignment || "",
      };
      setAssessment(nextAssessment);
      setAssessmentComments(nextComments);
      setAssessmentSaved({
        valuable: Boolean(participantScores.impact != null),
        feasible: Boolean(participantScores.feasibility != null),
        applicable: Boolean(participantScores.alignment != null),
      });
    } catch {
      // Non-blocking: participant can still fill and submit.
    }
  }

  async function loadResults() {
    try {
      const data = await loadScores();
      setResultsInfo(data.criteria || null);
      setCommentsInfo(Array.isArray(data.comments) ? data.comments : []);
    } catch {
      setResultsInfo(null);
      setCommentsInfo([]);
    }
  }

  async function refreshCompletion() {
    if (isParticipant) return;

    try {
      const scoresData = await api(
        `/projects/${projectId}/scores`,
        "GET",
        null,
        token
      );
      const criteria = scoresData.criteria || {};
      setCompletionInfo({
        all_done: Boolean(scoresData.all_done),
        required_respondents: Number(scoresData.required_respondents || 0),
        completed_respondents: Number(scoresData.completed_respondents || 0),
        pending_invites: Number(scoresData.pending_invites || 0),
      });
      setResultsInfo(criteria || null);
      setCommentsInfo(
        Array.isArray(scoresData.comments) ? scoresData.comments : []
      );
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

  async function saveAssessmentCriterion(criterion, value, comment) {
    if (!actorParticipantId || !value) return false;

    const metricKey = scoreCriterionToMetric[criterion];
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

    const criteria = ["valuable", "feasible", "applicable"];
    let hadError = false;

    for (const criterion of criteria) {
      if (assessmentSaved[criterion]) continue;
      const ok = await saveAssessmentCriterion(
        criterion,
        assessment[criterion],
        assessmentComments[criterion]
      );
      if (!ok) {
        hadError = true;
      }
    }

    if (!hadError) return;
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
      setAssessmentSaved({
        valuable: false,
        feasible: false,
        applicable: false,
      });
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

  function handleDecisionSelect(decision) {
    submitDecision(decision);
  }

  async function submitDecision(decision) {
    if (!token || isParticipant) return;
    const resolvedRunId = Number(project?.id || projectId);
    if (!Number.isFinite(resolvedRunId) || resolvedRunId <= 0) {
      setActionMessage("Invalid project id.");
      return;
    }

    const synthesisSaved = await persistProblemSynthesis(false);
    if (!synthesisSaved) return;

    const payload = {
      decision,
      justification: phase5DecisionMessages[decision] || "",
    };

    const decisionEndpoints = [
      `/projects/${resolvedRunId}/decision`,
      `/projects/${resolvedRunId}/decisions`,
      `/runs/${resolvedRunId}/decision`,
      `/runs/${resolvedRunId}/decisions`,
      `/project/${resolvedRunId}/decision`,
      `/project/${resolvedRunId}/decisions`,
      `/run/${resolvedRunId}/decision`,
      `/run/${resolvedRunId}/decisions`,
    ];

    let lastError = null;

    for (const path of decisionEndpoints) {
      try {
        const updated = await api(path, "POST", payload, token);
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
        return;
      } catch (err) {
        lastError = err;
        if (Number(err?.status) !== 404) {
          break;
        }
      }
    }

    setActionMessage(lastError?.message || "Failed to submit decision.");
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
  const canAdvance = !isParticipant && config.canAdvance;
  const isFollowUpCycle = Number(project?.current_cycle || 1) > 1;
  const canGenerateInvite =
    config.showInviteLink && !isParticipant && !isFollowUpCycle;
  const missingInviteForPhase3 =
    routePhase === 2 &&
    !isParticipant &&
    !isFollowUpCycle &&
    !project?.invite_links_generated;
  const phase4Blocked =
    routePhase === 4 && config.requiresAllParticipantsDone
      ? !completionInfo.all_done
      : false;
  const filledBoardFields = fields.filter(
    (field) => String(entries[field] || "").trim().length > 0
  );
  const emptyBoardFields = fields.filter(
    (field) => String(entries[field] || "").trim().length === 0
  );
  const canvasAdvanceBlocked =
    !isParticipant && routePhase <= 3 && emptyBoardFields.length > 0;
  const advanceDisabled =
    missingInviteForPhase3 || phase4Blocked || canvasAdvanceBlocked;
  const assessmentSubmitted =
    assessmentSaved.valuable &&
    assessmentSaved.feasible &&
    assessmentSaved.applicable;
  const finalDecisionKey = (
    selectedDecision ||
    project?.decision ||
    ""
  ).toUpperCase();
  const hasFinalDecision =
    finalDecisionKey === "GO" || finalDecisionKey === "ABORT";
  const canEditCanvas = !isParticipant;
  const showRecommendationButton =
    routePhase === 1 && !isParticipant && Boolean(project?.ai_mode_enabled);
  const showPhase3OverviewButton =
    routePhase === 3 && !isParticipant && Boolean(project?.ai_mode_enabled);

  return (
    <div className="project-layout">
      <PhaseStepper
        currentPhaseNumber={Number(currentPhaseNumber || 1)}
        activePhaseNumber={routePhase}
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
                  </div>
                )}
              </div>
              {fields.map((f) => (
                <div key={f}>
                  <FieldEditor
                    field={f}
                    value={entries[f]}
                    suggestion={suggestionsEnabled ? suggestions[f] : null}
                    aiOverview={
                      routePhase === 3 ? phase3OverviewsByField[f] : null
                    }
                    aiOverviewPending={
                      routePhase === 3 ? phase3OverviewPendingByField[f] : false
                    }
                    pending={
                      suggestionsEnabled
                        ? recommendationPendingByField[f]
                        : false
                    }
                    readOnly={!canEditCanvas}
                    labelOverride={
                      routePhase === 3 ? phase3CanvasTitles[f] : undefined
                    }
                    placeholderOverride={routePhase === 3 ? "" : undefined}
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

          {routePhase === 4 && (
            <>
              <h2>Semantic Differential Scale</h2>
              {isParticipant ? (
                <div className="assessment-grid">
                  {["valuable", "applicable", "feasible"].map((criterion) => (
                    <div className="field-card" key={criterion}>
                      <label>{assessmentCriterionDescriptions[criterion]}</label>
                      <div className="semantic-scale-row">
                        <span className="semantic-anchor">
                          {semanticAnchors[criterion].left}
                        </span>
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
                        <span className="semantic-anchor">
                          {semanticAnchors[criterion].right}
                        </span>
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
            </>
          )}

          {routePhase === 5 && (
            <>
              <h2>Results</h2>
              {resultsInfo ? (
                <div className="results-grid">
                  {phase5ResultOrder.map(({ metricKey, label }) => {
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
                            <h3>{label}</h3>
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
                        {phase5FinalDecisionMessages[finalDecisionKey] ||
                          `Final decision: ${finalDecisionKey}.`}
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
                            onClick={() => handleDecisionSelect(decision)}
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
                                    {metricKeyToCriterionLabel[metricKey] ||
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
            {config.canSaveDraft && !isParticipant && (
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
                {routePhase === 1
                  ? "Advance to Phase 2"
                  : routePhase === 2
                  ? "Advance to Phase 3"
                  : routePhase === 3
                  ? "Advance to Phase 4"
                  : "Advance to Phase 5"}
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
