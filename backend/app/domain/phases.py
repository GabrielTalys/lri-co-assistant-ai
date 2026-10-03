MAX_PHASE = 5


def advance_phase(current_phase: int) -> int:
    return min(current_phase + 1, MAX_PHASE)
