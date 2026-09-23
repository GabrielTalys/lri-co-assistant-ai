from __future__ import annotations

import re

from app.repositories import AISuggestionRepository, CanvasRepository, ParticipantRepository, RunRepository


class CanvasService:
    def __init__(
        self,
        run_repo: RunRepository,
        participant_repo: ParticipantRepository,
        canvas_repo: CanvasRepository,
        ai_repo: AISuggestionRepository,
    ):
        self.run_repo = run_repo
        self.participant_repo = participant_repo
        self.canvas_repo = canvas_repo
        self.ai_repo = ai_repo

    def _response_cycle_for_run(self, run) -> int:
        if run.current_phase != 2 or run.current_cycle <= 1:
            return run.current_cycle

        # Pivot follow-up: phase 2 should start from the previous cycle answers.
        # Some legacy runs may have skipped cycles; fallback to the latest cycle that
        # actually has responses so the canvas is always prefilled when possible.
        for cycle in range(run.current_cycle - 1, 0, -1):
            if self.canvas_repo.list_responses_by_run(run.id, cycle=cycle):
                return cycle
        return max(1, run.current_cycle - 1)

    def _slug(self, value: str) -> str:
        slug = re.sub(r'[^a-z0-9]+', '_', value.lower()).strip('_')
        return slug or 'canvas_item'

    def get_canvas_view(self, run_id: int):
        run = self.run_repo.get(run_id)
        if run is None:
            raise ValueError('Run not found')

        questions = self.canvas_repo.list_questions()
        cycle = self._response_cycle_for_run(run)
        responses = {r.question_id: r for r in self.canvas_repo.list_responses_by_run(run_id, cycle=cycle)}
        suggestions = {}
        if run.current_phase == 1:
            suggestions = {s.question_id: s for s in self.ai_repo.list_by_run(run_id, cycle=cycle)}

        items = []
        for question in questions:
            response = responses.get(question.id)
            suggestion = suggestions.get(question.id)
            items.append(
                {
                    'question_id': question.id,
                    'question_key': question.key,
                    'title': question.title,
                    'prompt_template': question.prompt_template,
                    'response': {
                        'participant_id': response.participant_id,
                        'content': response.content,
                        'updated_at': response.updated_at,
                    }
                    if response
                    else None,
                    'suggestion': {
                        'status': suggestion.status.value,
                        'context_hash': suggestion.context_hash,
                        'output': suggestion.output,
                        'error_message': suggestion.error_message,
                        'updated_at': suggestion.updated_at,
                    }
                    if suggestion
                    else None,
                }
            )
        return {'project_id': run_id, 'current_phase': run.current_phase, 'items': items}

    def submit_response(
        self,
        run_id: int,
        question_key: str,
        participant_id: int,
        content: str,
        background_tasks=None,
        allow_dynamic_questions: bool = False,
    ):
        run = self.run_repo.get(run_id)
        if run is None:
            raise ValueError('Run not found')

        participant = self.participant_repo.get(participant_id)
        if participant is None or participant.run_id != run_id:
            raise ValueError('Participant not found for this run')
        if participant.role != 'facilitator':
            raise ValueError('Only facilitators can edit canvas responses')

        question = self.canvas_repo.get_question_by_key(question_key)
        if question is None:
            if not allow_dynamic_questions:
                raise ValueError('Unknown canvas question key')
            normalized = self._slug(question_key)
            question = self.canvas_repo.get_question_by_key(normalized)
            if question is None:
                question = self.canvas_repo.create_question(
                    key=normalized,
                    title=question_key,
                    prompt_template=f'Provide content for {question_key}.',
                )

        response = self.canvas_repo.upsert_response(
            run_id=run_id,
            question_id=question.id,
            participant_id=participant_id,
            cycle=self._response_cycle_for_run(run),
            content=content,
        )

        if run.current_phase == 1:
            # The just-answered question should no longer keep an old suggestion.
            self.ai_repo.delete_for_question(
                run_id=run_id,
                question_id=question.id,
                cycle=self._response_cycle_for_run(run),
            )

        return response, question
