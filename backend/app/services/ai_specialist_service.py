import json

from app.repositories import CanvasRepository, ParticipantRepository, RunRepository
from app.services.llm_client import get_llm_client
from app.services.score_service import ScoreService


class AISpecialistService:
    def __init__(
        self,
        run_repo: RunRepository,
        participant_repo: ParticipantRepository,
        canvas_repo: CanvasRepository | None = None,
        score_service: ScoreService | None = None,
    ):
        self.run_repo = run_repo
        self.participant_repo = participant_repo
        self.canvas_repo = canvas_repo
        self.score_service = score_service

    def get_ai_specialist(self, run_id: int, owner_user_id: int):
        run = self.run_repo.get(run_id)
        if run is None or run.owner_user_id != owner_user_id:
            raise ValueError('Run not found')

        specialist = self.participant_repo.find_ai_by_run(run_id)
        if specialist is None:
            raise ValueError('AI specialist not found')
        return specialist

    def upsert_ai_specialist(
        self,
        run_id: int,
        owner_user_id: int,
        display_name: str,
        ai_specialty: str,
    ):
        # The Run row lock serializes specialist configuration for this Run.
        run = self.run_repo.get_for_update(run_id)
        if run is None or run.owner_user_id != owner_user_id:
            raise ValueError('Run not found')

        specialist = self.participant_repo.find_ai_by_run(run_id)
        if specialist is None:
            return self.participant_repo.create_ai_specialist(
                run_id=run_id,
                display_name=display_name,
                ai_specialty=ai_specialty,
            )

        return self.participant_repo.update_ai_specialist(
            specialist,
            display_name=display_name,
            ai_specialty=ai_specialty,
        )

    def _build_assessment_context(self, run_id: int, cycle: int) -> str:
        if self.canvas_repo is None:
            raise RuntimeError('Canvas repository is required for AI specialist assessment')

        questions = {question.id: question for question in self.canvas_repo.list_questions()}
        context_lines = []
        for response in self.canvas_repo.list_responses_by_run(run_id, cycle=cycle):
            content = (response.content or '').strip()
            question = questions.get(response.question_id)
            if question is not None and content:
                context_lines.append(f'{question.title} ({question.key}): {content}')
        return '\n'.join(context_lines).strip()

    def _prompt_for_assessment(self, run, specialist, context_text: str) -> str:
        specialist_name = (specialist.display_name or 'AI Specialist').strip()
        specialty = (specialist.ai_specialty or '').strip()
        return (
            'You are assessing a formulated research problem for a Lean Research Inception workshop.\n'
            f'You are acting as {specialist_name}, an AI specialist in {specialty}.\n'
            'Provide a general assessment and use the configured specialty as an additional perspective.\n'
            'Do not invent facts about the organization, market, customers, competitors, or data not present in the context.\n'
            'Base the assessment only on the provided context and make the justification clear about context limitations when relevant.\n'
            f'Current cycle: {run.current_cycle}.\n\n'
            'Problem context:\n'
            f'{context_text}\n\n'
            'Assess these criteria on an integer scale from 1 to 7:\n'
            '- value: potential to generate meaningful value for industrial practice\n'
            '- feasibility: realistic investigability with typically available resources\n'
            '- applicability: realistic applicability in industry scenarios\n\n'
            'Return only valid JSON with exactly these keys:\n'
            '{"value": 1, "feasibility": 1, "applicability": 1, "comment": "..."}\n'
            'All scores must be integers from 1 to 7. The comment must be non-empty and justify all three scores.\n'
            'Do not include markdown, extra text, Go/Pivot/Abort, or a final decision.'
        )

    def _parse_assessment_response(self, response_text: str) -> dict[str, int | str]:
        try:
            payload = json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise ValueError('AI specialist assessment returned invalid JSON') from exc

        if not isinstance(payload, dict) or set(payload) != {'value', 'feasibility', 'applicability', 'comment'}:
            raise ValueError('AI specialist assessment returned an invalid structure')

        scores: dict[str, int | str] = {}
        for key in ('value', 'feasibility', 'applicability'):
            score = payload.get(key)
            if isinstance(score, bool) or not isinstance(score, int) or not 1 <= score <= 7:
                raise ValueError('AI specialist assessment scores must be integers between 1 and 7')
            scores[key] = score

        comment = payload.get('comment')
        if not isinstance(comment, str) or not comment.strip():
            raise ValueError('AI specialist assessment requires a non-empty comment')
        scores['comment'] = comment.strip()
        return scores

    def generate_assessment(self, run_id: int, owner_user_id: int) -> dict:
        if self.canvas_repo is None or self.score_service is None:
            raise RuntimeError('AI specialist assessment dependencies are not configured')

        run = self.run_repo.get(run_id)
        if run is None or run.owner_user_id != owner_user_id:
            raise ValueError('Run not found')
        if not run.ai_mode_enabled:
            raise ValueError('AI mode is disabled for this project')
        if run.current_phase != 4:
            raise ValueError('AI specialist assessment is only available in phase 4')

        specialist = self.participant_repo.find_ai_by_run(run_id)
        if specialist is None or not specialist.is_ai or specialist.run_id != run_id:
            raise ValueError('AI specialist not found')

        metric_map = {
            'value': 'impact',
            'feasibility': 'feasibility',
            'applicability': 'alignment',
        }
        for metric_key in metric_map.values():
            if self.score_service.score_repo.get_by_metric(
                run_id=run_id,
                participant_id=specialist.id,
                metric_key=metric_key,
                cycle=run.current_cycle,
            ):
                raise ValueError('AI specialist assessment already exists for this cycle')

        context_text = self._build_assessment_context(run_id, run.current_cycle)
        if not context_text:
            raise ValueError('Problem context is required for AI specialist assessment')

        response_text = get_llm_client().generate(
            self._prompt_for_assessment(run, specialist, context_text)
        )
        assessment = self._parse_assessment_response(response_text)
        comment = str(assessment['comment'])
        scores = {}
        for response_key, metric_key in metric_map.items():
            score = self.score_service.submit_score(
                run_id=run_id,
                participant_id=specialist.id,
                metric_key=metric_key,
                value=int(assessment[response_key]),
                comment=comment,
            )
            scores[metric_key] = score.value

        return {
            'participant_id': specialist.id,
            'cycle': run.current_cycle,
            'scores': scores,
            'comment': comment,
        }
