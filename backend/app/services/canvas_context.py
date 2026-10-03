from __future__ import annotations

from app.repositories import CanvasRepository


def response_cycle_for_run(canvas_repo: CanvasRepository, run) -> int:
    """Cycle whose canvas answers the run currently shows and edits.

    Right after a pivot (phase 2 of a follow-up cycle) the canvas starts from the
    previous cycle's answers; some legacy runs skipped cycles, so it falls back to the
    latest earlier cycle that actually has answers.
    """
    if run.current_phase != 2 or run.current_cycle <= 1:
        return run.current_cycle

    for cycle in range(run.current_cycle - 1, 0, -1):
        if canvas_repo.list_responses_by_run(run.id, cycle=cycle):
            return cycle
    return max(1, run.current_cycle - 1)


def build_canvas_context(canvas_repo: CanvasRepository, run_id: int, cycle: int):
    """Split a run's canvas into filled/empty questions and a flattened text block.

    Shared by the phase advance gate and every AI feature (phase 1 recommendations,
    phase 3 overview, phase 4 evaluation), so they all read the canvas the same way.
    """
    questions = canvas_repo.list_questions()
    responses = canvas_repo.list_responses_by_run(run_id, cycle=cycle)
    responses_by_question_id = {response.question_id: response for response in responses}

    filled_items = []
    empty_questions = []

    for question in questions:
        response = responses_by_question_id.get(question.id)
        content = (response.content or '').strip() if response else ''
        if content:
            filled_items.append({'question': question, 'content': content})
        else:
            empty_questions.append(question)

    # Only the field titles go to the LLM: the legacy keys do not match what the fields
    # hold (e.g. 'risks' stores the research questions) and would mislead the model.
    context_lines = [f"{item['question'].title}: {item['content']}" for item in filled_items]
    context_text = '\n'.join(context_lines).strip()
    return filled_items, empty_questions, context_text
