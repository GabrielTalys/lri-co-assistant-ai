METRICS = [
    'feasibility',
    'impact',
    'novelty',
    'alignment',
]

LEGACY_CRITERION_TO_METRIC = {
    'valuable': 'impact',
    'feasible': 'feasibility',
    'applicable': 'alignment',
}

METRIC_TO_LEGACY_CRITERION = {v: k for k, v in LEGACY_CRITERION_TO_METRIC.items()}
