from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories import AISuggestionRepository, CanvasRepository, ParticipantRepository, RunRepository
from app.services.canvas_context import response_cycle_for_run
from app.services.guards import get_run, get_run_participant


class CanvasService:
    def __init__(self, db: Session):
        self.run_repo = RunRepository(db)
        self.participant_repo = ParticipantRepository(db)
        self.canvas_repo = CanvasRepository(db)
        self.ai_repo = AISuggestionRepository(db)

    def get_canvas_view(self, run_id: int):
        run = get_run(self.run_repo, run_id)

        questions = self.canvas_repo.list_questions()
        cycle = response_cycle_for_run(self.canvas_repo, run)
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

    def submit_response(self, run_id: int, question_key: str, participant_id: int, content: str):
        run = get_run(self.run_repo, run_id)
        participant = get_run_participant(self.participant_repo, run_id, participant_id)
        if participant.role != 'facilitator':
            raise ValueError('Only facilitators can edit canvas responses')

        question = self.canvas_repo.get_question_by_key(question_key)
        if question is None:
            raise ValueError('Unknown canvas question key')

        cycle = response_cycle_for_run(self.canvas_repo, run)
        response = self.canvas_repo.upsert_response(
            run_id=run_id,
            question_id=question.id,
            participant_id=participant_id,
            cycle=cycle,
            content=content,
        )

        if run.current_phase == 1:
            # The just-answered question should no longer keep an old suggestion.
            self.ai_repo.delete_for_question(run_id=run_id, question_id=question.id, cycle=cycle)

        return response, question
