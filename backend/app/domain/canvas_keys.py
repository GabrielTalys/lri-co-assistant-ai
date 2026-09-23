CANVAS_KEYS = [
    'problem',
    'stakeholders',
    'research_questions',
    'hypotheses',
    'method',
    'evaluation',
    'risks',
]

CANVAS_TITLES = {
    'problem': 'Describe the pain point',
    'stakeholders': 'Characterize the environment',
    'research_questions': 'Consequences/Benefits',
    'hypotheses': 'Identify People Involved',
    'method': 'What scientific evidence?',
    'evaluation': 'Define the objectives',
    'risks': 'What research questions?',
}

CANVAS_PROMPT_TEMPLATES = {
    'problem': (
        'Describe the pain point or opportunity to be addressed. Clarify its origin, '
        'current relevance, and potential future persistence, from the perspective of '
        'those affected.'
    ),
    'stakeholders': (
        'Characterize the environment in which the problem occurs. Provide relevant '
        'contextual details such as organization type, project stage, tools, and team '
        'structure.'
    ),
    'research_questions': (
        'Explain the consequences of not solving the problem and the potential benefits '
        'of addressing it. Consider business impact, return on investment, innovation, '
        'and broader relevance.'
    ),
    'hypotheses': (
        'Identify the people directly and indirectly involved, affected, or interested '
        'in solving the problem. Consider roles, responsibilities, and motivations.'
    ),
    'method': (
        'Present the initial scoping of scientific evidence related to the problem and '
        'related solution options. Include 1 to 3 academic references in a concise '
        'citation format such as "Kim et al. The emerging role of data scientists on '
        'software development teams. ICSE, 2016."'
    ),
    'evaluation': (
        'Define the objectives of your research problem, such as analyzing different '
        'interventions.'
    ),
    'risks': (
        'Define the research questions for your research problem, keeping in mind the '
        'actual, ideal, and proposed situation.'
    ),
}
