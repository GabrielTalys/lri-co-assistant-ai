MIN_PHASE = 1
MAX_PHASE = 5
DEFAULT_PHASE = 1

LEGACY_PHASE_ENUM = {
    1: 'F1',
    2: 'F2',
    3: 'F3',
    4: 'F4',
    5: 'F5',
}

LEGACY_PHASE_TO_NUMBER = {v: k for k, v in LEGACY_PHASE_ENUM.items()}


def advance_phase(current_phase: int) -> int:
    return min(current_phase + 1, MAX_PHASE)
