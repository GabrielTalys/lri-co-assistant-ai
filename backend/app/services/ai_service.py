from __future__ import annotations

from datetime import datetime
import hashlib
import json

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import AISuggestionStatus
from app.repositories import AISuggestionRepository, CanvasRepository, RunRepository
from app.services.llm_client import get_llm_client


class AISuggestionService:
    PROMPT_VERSION = 'phase1-recommendations-v4'
    PHASE3_OVERVIEW_PROMPT_VERSION = 'phase3-overview-v1'

    def __init__(self, db: Session):
        self.db = db
        self.run_repo = RunRepository(db)
        self.canvas_repo = CanvasRepository(db)
        self.ai_repo = AISuggestionRepository(db)
        self.llm_client = get_llm_client()

    def _response_cycle_for_run(self, run) -> int:
        if run.current_phase == 2 and run.current_cycle > 1:
            return max(1, run.current_cycle - 1)
        return run.current_cycle

    def _get_run_for_recommendations(self, run_id: int, *, enforce_phase1: bool):
        run = self.run_repo.get(run_id)
        if run is None:
            raise ValueError('Run not found')
        if not run.ai_mode_enabled:
            raise ValueError('AI mode is disabled for this project')
        if enforce_phase1 and run.current_phase != 1:
            raise ValueError('Recommendations are only available in phase 1')
        return run

    def _get_run_for_phase3_overview(self, run_id: int):
        run = self.run_repo.get(run_id)
        if run is None:
            raise ValueError('Run not found')
        if not run.ai_mode_enabled:
            raise ValueError('AI mode is disabled for this project')
        if run.current_phase != 3:
            raise ValueError('Overview is only available in phase 3')
        return run

    def _build_canvas_context(self, run_id: int, cycle: int):
        questions = self.canvas_repo.list_questions()
        responses = self.canvas_repo.list_responses_by_run(run_id, cycle=cycle)
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

        context_lines = [
            f"{item['question'].title} ({item['question'].key}): {item['content']}"
            for item in filled_items
        ]
        context_text = '\n'.join(context_lines).strip()
        return filled_items, empty_questions, context_text

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
            'Keep the answer concise, ideally around 100 to 150 words.\n'
            'Do not prepend the field name, canvas key, labels, headings, bullets, or quotes.\n'
            'Do not mention any other field names in the opening of the answer.\n'
            'Do not begin with introductory framing or by restating the prompt.\n'
            'Avoid openings such as "The challenges associated with..." or '
            '"Define the objectives of the research problem...".\n'
            'Start directly with the substantive answer.'
            f'\n{field_specific_instruction}'
        )

    def _prompt_for_phase3_overview(self, question, question_content: str, context_text: str) -> str:
        return (
            'You are assisting a Lean Research Inception workshop facilitator.\n'
            'Review one fully completed phase 3 canvas in the context of the whole formulated problem.\n'
            f'Target canvas: {question.title} ({question.key}).\n'
            'Current content of the target canvas:\n'
            f'{question_content}\n\n'
            'Complete phase 3 context:\n'
            f'{context_text}\n\n'
            'Return only the analysis for the target canvas.\n'
            'Use exactly this structure:\n'
            'Overview: <short synthesis of what this canvas currently expresses and how it contributes to the problem formulation>\n'
            'Suggestions: <short suggestions to strengthen, clarify, or refine this canvas>\n'
            'Keep the answer concise, ideally 80 to 140 words total.\n'
            'Do not use bullets, numbering, markdown headings, quotes, or extra sections.\n'
            'Do not rewrite the canvas as if it were final text to be pasted back.\n'
            'Focus on helping the researcher analyze the current canvas critically.\n'
            'Start directly with "Overview:".'
        )

    def compute_context_hash(self, run_id: int, cycle: int) -> str:
        filled_items, _, _ = self._build_canvas_context(run_id, cycle)
        payload = {
            'prompt_version': self.PROMPT_VERSION,
            'filled_items': [
                {
                    'question_key': item['question'].key,
                    'content': item['content'],
                }
                for item in filled_items
            ],
        }
        payload['filled_items'].sort(key=lambda item: item['question_key'])
        serialized = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(serialized.encode('utf-8')).hexdigest()

    def _mark_existing_suggestion_stale_if_needed(
        self,
        *,
        run_id: int,
        question_id: int,
        cycle: int,
        context_hash: str,
    ) -> None:
        existing = self.ai_repo.get(run_id=run_id, question_id=question_id, cycle=cycle)
        if existing and existing.context_hash != context_hash and existing.status in {
            AISuggestionStatus.QUEUED,
            AISuggestionStatus.RUNNING,
        }:
            self.ai_repo.upsert(
                run_id=run_id,
                question_id=question_id,
                cycle=cycle,
                status=AISuggestionStatus.STALE,
                context_hash=existing.context_hash,
                output=existing.output,
                error_message=existing.error_message,
            )

    def _generate_recommendation_for_question(
        self,
        *,
        run_id: int,
        cycle: int,
        question,
        context_hash: str,
        context_text: str,
    ) -> dict:
        existing = self.ai_repo.get(run_id=run_id, question_id=question.id, cycle=cycle)
        if (
            existing
            and existing.context_hash == context_hash
            and existing.status == AISuggestionStatus.SUCCEEDED
            and existing.output
            and existing.output.get('text')
        ):
            return {
                'question_key': question.key,
                'suggested_text': existing.output.get('text', ''),
                'status': existing.status.value,
            }

        self._mark_existing_suggestion_stale_if_needed(
            run_id=run_id,
            question_id=question.id,
            cycle=cycle,
            context_hash=context_hash,
        )

        self.ai_repo.upsert(
            run_id=run_id,
            question_id=question.id,
            cycle=cycle,
            status=AISuggestionStatus.QUEUED,
            context_hash=context_hash,
            output=None,
            error_message=None,
        )
        self.ai_repo.upsert(
            run_id=run_id,
            question_id=question.id,
            cycle=cycle,
            status=AISuggestionStatus.RUNNING,
            context_hash=context_hash,
            output=None,
            error_message=None,
        )

        prompt = self._prompt_for_question(question, context_text)

        try:
            suggestion_text = self.llm_client.generate(prompt)
            self.ai_repo.upsert(
                run_id=run_id,
                question_id=question.id,
                cycle=cycle,
                status=AISuggestionStatus.SUCCEEDED,
                context_hash=context_hash,
                output={'text': suggestion_text, 'question_key': question.key},
                error_message=None,
            )
            return {
                'question_key': question.key,
                'suggested_text': suggestion_text,
                'status': AISuggestionStatus.SUCCEEDED.value,
            }
        except Exception as exc:  # noqa: BLE001
            self.ai_repo.upsert(
                run_id=run_id,
                question_id=question.id,
                cycle=cycle,
                status=AISuggestionStatus.FAILED,
                context_hash=context_hash,
                output=None,
                error_message=str(exc),
            )
            raise

    def generate_recommendation_for_question(self, run_id: int, question_key: str) -> dict:
        run = self._get_run_for_recommendations(run_id, enforce_phase1=True)
        cycle = self._response_cycle_for_run(run)
        filled_items, empty_questions, context_text = self._build_canvas_context(run_id, cycle)
        if not filled_items:
            raise ValueError('Fill at least one field before requesting recommendations')

        target_question = next((question for question in empty_questions if question.key == question_key), None)
        if target_question is None:
            known_question = self.canvas_repo.get_question_by_key(question_key)
            if known_question is None:
                raise ValueError('Unknown canvas question key')
            raise ValueError('Recommendations are only available for empty fields')

        context_hash = self.compute_context_hash(run_id, cycle=cycle)
        payload = self._generate_recommendation_for_question(
            run_id=run_id,
            cycle=cycle,
            question=target_question,
            context_hash=context_hash,
            context_text=context_text,
        )
        return payload

    def generate_recommendations_for_run(self, run_id: int) -> dict:
        run = self._get_run_for_recommendations(run_id, enforce_phase1=True)
        cycle = self._response_cycle_for_run(run)
        filled_items, empty_questions, context_text = self._build_canvas_context(run_id, cycle)
        if not filled_items:
            raise ValueError('Fill at least one field before requesting recommendations')

        context_hash = self.compute_context_hash(run_id, cycle=cycle)
        generated_suggestions = {}

        for question in empty_questions:
            try:
                payload = self._generate_recommendation_for_question(
                    run_id=run_id,
                    cycle=cycle,
                    question=question,
                    context_hash=context_hash,
                    context_text=context_text,
                )
                generated_suggestions[question.key] = {
                    'suggested_text': payload['suggested_text'],
                    'status': payload['status'],
                }
            except Exception:  # noqa: BLE001
                pass

        # Keep timestamps monotonic for consumers.
        now = datetime.utcnow()
        for suggestion in self.ai_repo.list_by_run(run_id, cycle=cycle):
            suggestion.updated_at = now
        self.db.flush()
        return {
            'generated_count': len(generated_suggestions),
            'filled_count': len(filled_items),
            'empty_count': len(empty_questions),
            'suggestions': generated_suggestions,
        }

    def generate_phase3_overview(self, run_id: int) -> dict:
        run = self._get_run_for_phase3_overview(run_id)
        cycle = self._response_cycle_for_run(run)
        filled_items, empty_questions, context_text = self._build_canvas_context(run_id, cycle)

        if empty_questions:
            raise ValueError('Fill every canvas field before requesting the overview')

        overviews = {}
        for item in filled_items:
            question = item['question']
            prompt = self._prompt_for_phase3_overview(
                question,
                item['content'],
                context_text,
            )
            overview_text = self.llm_client.generate(prompt).strip()
            if not overview_text:
                raise RuntimeError(f'LLM response did not contain overview text for {question.key}')
            overviews[question.key] = overview_text

        return {
            'generated_count': len(overviews),
            'field_count': len(filled_items) + len(empty_questions),
            'overviews': overviews,
        }

    def generate_phase3_canvas_overview(self, run_id: int, question_key: str) -> dict:
        run = self._get_run_for_phase3_overview(run_id)
        cycle = self._response_cycle_for_run(run)
        filled_items, empty_questions, context_text = self._build_canvas_context(run_id, cycle)

        if empty_questions:
            raise ValueError('Fill every canvas field before requesting the overview')

        target_item = next(
            (item for item in filled_items if item['question'].key == question_key),
            None,
        )
        if target_item is None:
            raise ValueError('Unknown canvas question key')

        question = target_item['question']
        prompt = self._prompt_for_phase3_overview(
            question,
            target_item['content'],
            context_text,
        )
        overview_text = self.llm_client.generate(prompt).strip()
        if not overview_text:
            raise RuntimeError(f'LLM response did not contain overview text for {question.key}')

        return {
            'question_key': question.key,
            'overview_text': overview_text,
        }

    def refresh_suggestions_for_run(self, run_id: int) -> None:
        try:
            self.generate_recommendations_for_run(run_id)
        except ValueError:
            return


def refresh_suggestions_background(run_id: int) -> None:
    with SessionLocal() as db:
        service = AISuggestionService(db)
        service.refresh_suggestions_for_run(run_id)
        db.commit()
