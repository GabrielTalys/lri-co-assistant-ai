const phaseCanvasKeysInOrder = [
  'problem',
  'stakeholders',
  'research_questions',
  'hypotheses',
  'method',
  'evaluation',
  'risks',
];

const phase1PlaceholdersInOrder = [
  'Describe the pain point or opportunity to be addressed. Clarify its origin, current relevance, and potential future persistence, from the perspective of those affected.',
  'Characterize the environment in which the problem occurs. Provide relevant contextual details (e.g., organization type, project stage, tools, team structure) to situate the problem clearly.',
  'Explain the consequences of not solving the problem and the potential benefits of addressing it. Consider perspectives such as business impact, Return of Investiment, innovation, and broader relevance.',
  'Identify the people directly and indirectly involved, affected, or interested in solving the problem. Consider roles, responsibilities, and motivations.',
  'Present the initial scoping of scientific evidence related to the problem and related solution options.',
  'Define the objectives of your research problem (e.g., analyze different interventions).',
  'Define the research questions for your "research problem" keeping in mind the actual, ideal and proposed situation.',
];

const phase1FieldOrder = [
  'For the practical problem (what/how/why)',
  'Involved in the context (where/when)',
  'Which bring the following implications/impacts (why) ',
  'For the stakeholders (who)',
  'We have the following evidence (how)',
  'And we want to investigate (what/how)',
  'Answering the following research question (what)',
];

const fieldPlaceholderMap = Object.fromEntries(
  phaseCanvasKeysInOrder.map((field, idx) => [field, phase1PlaceholdersInOrder[idx]])
);

const fieldLabelMap = Object.fromEntries(
  phaseCanvasKeysInOrder.map((field, idx) => [field, phase1FieldOrder[idx]])
);

export function getFieldPlaceholder(field) {
  if (fieldPlaceholderMap[field]) return fieldPlaceholderMap[field];
  return `Write ${String(field || '').replaceAll('_', ' ')}...`;
}

export function getFieldLabel(field) {
  if (fieldLabelMap[field]) return fieldLabelMap[field];
  return String(field || '')
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (m) => m.toUpperCase());
}
