"""Phase 4: an AI specialist scores the formulated problem like a human evaluator."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.metrics import ASSESSMENT_METRICS
from app.repositories import CanvasRepository, ParticipantRepository, RunRepository, ScoreRepository
from app.services.ai_prompts import ENGLISH_ONLY_RULE, specialist_system_instruction
from app.services.canvas_context import build_canvas_context
from app.services.guards import get_ai_run
from app.services.llm_client import get_llm_client
from app.services.score_service import ScoreService

METRIC_DESCRIPTIONS = {
    'impact': 'how valuable would addressing this problem be for industrial practice?',
    'feasibility': 'how feasible is it to investigate with typically available resources?',
    'alignment': 'how applicable/adoptable would the results be in real industry scenarios?',
}

PHASE4_AI_EVALUATION_SCHEMA = {
    'type': 'object',
    'properties': {
        metric: {
            'type': 'object',
            'properties': {
                'score': {'type': 'integer', 'minimum': 1, 'maximum': 7},
                'comment': {'type': 'string', 'minLength': 1},
            },
            'required': ['score', 'comment'],
        }
        for metric in ASSESSMENT_METRICS
    },
    'required': list(ASSESSMENT_METRICS),
}


def _prompt_for_ai_evaluation(context_text: str) -> str:
    metric_lines = '\n'.join(f'- {key}: {METRIC_DESCRIPTIONS[key]}' for key in ASSESSMENT_METRICS)

    return (
        'Phase 4 of the workshop: you are independently assessing the fully formulated research '
        "problem below, exactly as a human expert respondent would, without seeing any other "
        "participant's scores or comments.\n\n"
        'Formulated problem (canvas field title: content):\n'
        f'{context_text}\n\n'
        'Score the problem on 3 metrics, each from 1 (lowest) to 7 (highest):\n'
        f'{metric_lines}\n\n'
        'Use the whole scale honestly from your perspective: 1-2 serious flaws, 3 below '
        'expectations, 4 mixed, 5 solid with clear gaps, 6-7 strong. Do not default to the middle.\n'
        'For every metric write a comment of 2 to 4 sentences that justifies the score from your '
        'specialist perspective: point to the specific canvas content that drove the score, explain '
        'it with knowledge from your domain, and name the single change that would raise the score.\n'
        f'{ENGLISH_ONLY_RULE}\n'
        'Respond only with JSON matching the required schema.'
    )


class AIEvaluationService:
    def __init__(self, db: Session):
        self.run_repo = RunRepository(db)
        self.participant_repo = ParticipantRepository(db)
        self.score_repo = ScoreRepository(db)
        self.canvas_repo = CanvasRepository(db)
        self.score_service = ScoreService(db)
        self.llm_client = get_llm_client()

    def generate_ai_evaluation(self, run_id: int, owner_user_id: int, specialist_id: int) -> dict:
        run = get_ai_run(
            self.run_repo,
            run_id,
            phase=4,
            phase_error='AI evaluation is only available in phase 4',
            owner_user_id=owner_user_id,
        )

        ai_participant = self.participant_repo.get_ai_specialist(run_id, specialist_id)
        if ai_participant is None:
            raise ValueError('AI specialist not found')

        if self.score_repo.list_by_participant(run_id=run_id, participant_id=ai_participant.id, cycle=run.current_cycle):
            raise ValueError('AI evaluation already recorded for this cycle. Reset it first.')

        _filled_items, empty_questions, context_text = build_canvas_context(
            self.canvas_repo, run_id, run.current_cycle
        )
        if empty_questions:
            raise ValueError('Fill every canvas field before generating the AI evaluation')

        # The assessment stays blind: the system prompt knows the other specialists'
        # roles, never their scores.
        raw = self.llm_client.generate_json(
            _prompt_for_ai_evaluation(context_text),
            schema=PHASE4_AI_EVALUATION_SCHEMA,
            schema_name='phase4_ai_evaluation',
            system=specialist_system_instruction(ai_participant, self.participant_repo.list_ai_specialists(run_id)),
        )

        scores_out: dict[str, dict] = {}
        for metric in ASSESSMENT_METRICS:
            entry = raw.get(metric) or {}
            value = entry.get('score')
            comment = str(entry.get('comment') or '').strip()
            if not isinstance(value, int) or not (1 <= value <= 7) or not comment:
                raise RuntimeError(f'AI evaluation response was malformed for metric "{metric}"')
            self.score_service.submit_score(
                run_id=run_id,
                participant_id=ai_participant.id,
                metric_key=metric,
                value=value,
                comment=comment,
            )
            scores_out[metric] = {'value': value, 'comment': comment}

        return {
            'participant_id': ai_participant.id,
            'role_title': ai_participant.ai_persona_role,
            'scores': scores_out,
        }
