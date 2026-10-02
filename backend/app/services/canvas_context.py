from __future__ import annotations

from app.repositories import CanvasRepository


def build_canvas_context(canvas_repo: CanvasRepository, run_id: int, cycle: int):
    """Split a run's canvas into filled/empty questions and a flattened text block.

    Shared between phase 1/3 AI suggestion generation (AISuggestionService) and
    the phase 4 AI specialist evaluation (AIEvaluationService), so both features
    build their LLM context the same way.
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
