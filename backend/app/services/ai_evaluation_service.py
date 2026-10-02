from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories import CanvasRepository, InviteRepository, ParticipantRepository, RunRepository, ScoreRepository
from app.services.ai_prompts import Persona, build_system_instruction
from app.services.canvas_context import build_canvas_context
from app.services.llm_client import get_llm_client
from app.services.score_service import ScoreService

METRIC_KEYS = ('impact', 'feasibility', 'alignment')

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
        for metric in METRIC_KEYS
    },
    'required': list(METRIC_KEYS),
}


def _prompt_for_ai_evaluation(context_text: str) -> str:
    metric_lines = '\n'.join(f'- {key}: {desc}' for key, desc in METRIC_DESCRIPTIONS.items())

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
        'Respond only with JSON matching the required schema.'
    )


class AIEvaluationService:
    def __init__(self, db: Session):
        self.db = db
        self.run_repo = RunRepository(db)
        self.participant_repo = ParticipantRepository(db)
        self.score_repo = ScoreRepository(db)
        self.canvas_repo = CanvasRepository(db)
        self.score_service = ScoreService(
            run_repo=self.run_repo,
            participant_repo=self.participant_repo,
            score_repo=self.score_repo,
            invite_repo=InviteRepository(db),
        )
        self.llm_client = get_llm_client()

    def generate_ai_evaluation(self, run_id: int, owner_user_id: int, specialist_id: int) -> dict:
        run = self.run_repo.get(run_id)
        if run is None or run.owner_user_id != owner_user_id:
            raise ValueError('Run not found')
        if not run.ai_mode_enabled:
            raise ValueError('AI mode is disabled for this project')
        if run.current_phase != 4:
            raise ValueError('AI evaluation is only available in phase 4')

        ai_participant = self.participant_repo.get_ai_specialist(run_id, specialist_id)
        if ai_participant is None:
            raise ValueError('AI specialist not found')

        existing_metrics = {
            row.metric_key
            for row in self.score_repo.list_by_participant(
                run_id=run_id, participant_id=ai_participant.id, cycle=run.current_cycle
            )
        }
        if existing_metrics:
            raise ValueError('AI evaluation already recorded for this cycle. Reset it first.')

        _filled_items, empty_questions, context_text = build_canvas_context(
            self.canvas_repo, run_id, run.current_cycle
        )
        if empty_questions:
            raise ValueError('Fill every canvas field before generating the AI evaluation')

        # Other specialists' roles (never their scores) keep each evaluation focused on
        # what its own expertise adds; the assessment itself stays blind.
        other_roles = [
            p.ai_persona_role
            for p in self.participant_repo.list_ai_specialists(run_id)
            if p.id != ai_participant.id
        ]
        system = build_system_instruction(
            Persona(
                role_title=ai_participant.ai_persona_role or 'domain specialist',
                role_description=ai_participant.ai_persona_description,
            ),
            other_roles,
        )
        raw = self.llm_client.generate_json(
            _prompt_for_ai_evaluation(context_text),
            schema=PHASE4_AI_EVALUATION_SCHEMA,
            schema_name='phase4_ai_evaluation',
            system=system,
        )

        scores_out: dict[str, dict] = {}
        for metric in METRIC_KEYS:
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
