"""Phase 1: AI recommendation for an empty canvas field, cached per canvas content."""

from __future__ import annotations

import hashlib
import json

from sqlalchemy.orm import Session

from app.models import AISuggestionStatus
from app.repositories import AISuggestionRepository, CanvasRepository, RunRepository
from app.services.ai_prompts import DEFAULT_PERSONA, ENGLISH_ONLY_RULE, build_system_instruction
from app.services.canvas_context import build_canvas_context, response_cycle_for_run
from app.services.guards import get_ai_run
from app.services.llm_client import get_llm_client


class AISuggestionService:
    # Part of the cache key: bump it whenever the prompt changes so cached
    # recommendations are generated again.
    PROMPT_VERSION = 'phase1-recommendations-v6'

    def __init__(self, db: Session):
        self.run_repo = RunRepository(db)
        self.canvas_repo = CanvasRepository(db)
        self.ai_repo = AISuggestionRepository(db)
        self.llm_client = get_llm_client()

    def _prompt_for_question(self, question, context_text: str) -> str:
        prompt_template = question.prompt_template or f'Provide content for {question.title}.'
        field_specific_instruction = ''
        if question.key == 'method':
            field_specific_instruction = (
                'Include 1 to 3 academic references relevant to the problem.\n'
                'Citations must be inline in a short format like '
                '"Kim et al. The emerging role of data scientists on software development teams. ICSE, 2016."\n'
                'Do not invent DOI links or URLs.\n'
            )
        elif question.key == 'hypotheses':
            field_specific_instruction = (
                'Return 3 to 5 groups of people involved, never more than 5.\n'
                'Each item should name one stakeholder group and briefly state its role or motivation.\n'
                'Start directly with the groups, without any lead-in sentence.\n'
            )
        return (
            'You are assisting a Lean Research Inception workshop facilitator.\n'
            'Use only the filled canvas fields below as context.\n'
            f'Target empty field: {question.title}.\n'
            f'Instruction for this field: {prompt_template}\n\n'
            'Filled fields:\n'
            f'{context_text}\n\n'
            'Return only the recommendation text for the target field.\n'
            "Write it as concrete content for this team's problem: reuse the specific people, "
            'contexts, tools and constraints they wrote, never a generic template that would fit '
            'any project.\n'
            'Keep the answer concise, ideally around 100 to 150 words.\n'
            f'{ENGLISH_ONLY_RULE}\n'
            'Do not prepend the field name, canvas key, labels, headings, bullets, or quotes.\n'
            'Do not mention any other field names in the opening of the answer.\n'
            'Do not begin with introductory framing or by restating the prompt.\n'
            'Avoid openings such as "The challenges associated with..." or '
            '"Define the objectives of the research problem...".\n'
            'Start directly with the substantive answer.'
            f'\n{field_specific_instruction}'
        )

    def _context_hash(self, filled_items) -> str:
        payload = {
            'prompt_version': self.PROMPT_VERSION,
            'filled_items': sorted(
                ({'question_key': item['question'].key, 'content': item['content']} for item in filled_items),
                key=lambda item: item['question_key'],
            ),
        }
        serialized = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(serialized.encode('utf-8')).hexdigest()

    def generate_recommendation_for_question(self, run_id: int, question_key: str) -> dict:
        run = get_ai_run(
            self.run_repo,
            run_id,
            phase=1,
            phase_error='Recommendations are only available in phase 1',
        )
        cycle = response_cycle_for_run(self.canvas_repo, run)
        filled_items, empty_questions, context_text = build_canvas_context(self.canvas_repo, run_id, cycle)
        if not filled_items:
            raise ValueError('Fill at least one field before requesting recommendations')

        question = next((question for question in empty_questions if question.key == question_key), None)
        if question is None:
            if self.canvas_repo.get_question_by_key(question_key) is None:
                raise ValueError('Unknown canvas question key')
            raise ValueError('Recommendations are only available for empty fields')

        context_hash = self._context_hash(filled_items)
        cached = self.ai_repo.get(run_id=run_id, question_id=question.id, cycle=cycle)
        if (
            cached
            and cached.context_hash == context_hash
            and cached.status == AISuggestionStatus.SUCCEEDED
            and cached.output
            and cached.output.get('text')
        ):
            return {
                'question_key': question.key,
                'suggested_text': cached.output['text'],
                'status': cached.status.value,
            }

        # A failed call raises before anything is written, so the request rolls back.
        suggestion_text = self.llm_client.generate(
            self._prompt_for_question(question, context_text),
            system=build_system_instruction(DEFAULT_PERSONA),
        )
        self.ai_repo.upsert(
            run_id=run_id,
            question_id=question.id,
            cycle=cycle,
            status=AISuggestionStatus.SUCCEEDED,
            context_hash=context_hash,
            output={'text': suggestion_text, 'question_key': question.key},
        )
        return {
            'question_key': question.key,
            'suggested_text': suggestion_text,
            'status': AISuggestionStatus.SUCCEEDED.value,
        }
