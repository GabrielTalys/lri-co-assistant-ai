// The Problem Vision canvas fields, in board order. The keys are legacy backend
// names (e.g. "risks" holds the research questions); the labels say what each
// field holds.
export const CANVAS_FIELDS = [
  "problem",
  "stakeholders",
  "research_questions",
  "hypotheses",
  "method",
  "evaluation",
  "risks",
];

// Field labels in phases 1 and 2. " " (no-break space) keeps the words around
// it on the same line when a label wraps.
export const FIELD_LABELS = {
  problem: "For the practical problem (what/how/why)",
  stakeholders: "Involved in the context (where/when)",
  research_questions:
    "Which bring the following implications/impacts (why) ",
  hypotheses: "For the stakeholders (who)",
  method: "We have the following evidence (how)",
  evaluation: "And we want to investigate (what/how)",
  risks: "Answering the following research question (what)",
};

// Field labels in phase 3, worded as the formulated research problem.
export const PHASE3_FIELD_LABELS = {
  problem: "For the practical problem (what/how/why)",
  stakeholders: "Involved in the context (where/when)",
  research_questions:
    "Which bring the following implications/impacts (why) ",
  hypotheses: "For the stakeholders (who)",
  method: "We have the following evidence (how)",
  evaluation: "And we want to investigate - objective (what/how)",
  risks: "Answering the following research questions (what)",
};

// Guidance shown in empty fields in phases 1 and 2.
export const FIELD_PLACEHOLDERS = {
  problem:
    "Describe the pain point or opportunity to be addressed. Clarify its origin, current relevance, and potential future persistence, from the perspective of those affected.",
  stakeholders:
    "Characterize the environment in which the problem occurs. Provide relevant contextual details (e.g., organization type, project stage, tools, team structure) to situate the problem clearly.",
  research_questions:
    "Explain the consequences of not solving the problem and the potential benefits of addressing it. Consider perspectives such as business impact, Return of Investiment, innovation, and broader relevance.",
  hypotheses:
    "Identify the people directly and indirectly involved, affected, or interested in solving the problem. Consider roles, responsibilities, and motivations.",
  method:
    "Present the initial scoping of scientific evidence related to the problem and related solution options.",
  evaluation:
    "Define the objectives of your research problem (e.g., analyze different interventions).",
  risks:
    'Define the research questions for your "research problem" keeping in mind the actual, ideal and proposed situation.',
};
