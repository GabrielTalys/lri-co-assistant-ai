from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import hashlib
import json
import logging

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import AISuggestionStatus
from app.repositories import AISuggestionRepository, CanvasRepository, ParticipantRepository, RunRepository
from app.services.ai_prompts import (
    DEFAULT_PERSONA,
    ENGLISH_ONLY_RULE,
    PANEL_MODERATOR_INSTRUCTION,
    Persona,
    build_system_instruction,
)
from app.services.canvas_context import build_canvas_context
from app.services.llm_client import get_llm_client

logger = logging.getLogger(__name__)


def _format_review(review: dict) -> str:
    suggestion_lines = '\n'.join(f'• {item}' for item in review['suggestions'])
    return f"Overview: {review['overview']}\nSuggestions:\n{suggestion_lines}"


def _format_panel_synthesis(synthesis: dict) -> str:
    lines = [f"Consensus: {synthesis['consensus']}"]
    if synthesis['divergence']:
        lines.append(f"Divergence: {synthesis['divergence']}")
    lines.append('Suggestions:')
    lines.extend(f"• [{item['role_title']}] {item['text']}" for item in synthesis['suggestions'])
    return '\n'.join(lines)


def _panel_synthesis_schema(field_ids: list[str], specialist_keys: list[str]) -> dict:
    # One required property per specialist (not a free list) guarantees exactly one
    # suggestion from each of them in every field.
    return {
        'type': 'object',
        'properties': {
            field_id: {
                'type': 'object',
                'properties': {
                    'consensus': {'type': 'string', 'minLength': 1},
                    'divergence': {'type': 'string'},
                    'suggestions': {
                        'type': 'object',
                        'properties': {
                            key: {'type': 'string', 'minLength': 1} for key in specialist_keys
                        },
                        'required': list(specialist_keys),
                    },
                },
                'required': ['consensus', 'divergence', 'suggestions'],
            }
            for field_id in field_ids
        },
        'required': list(field_ids),
    }


def _phase3_overview_schema(field_ids: list[str]) -> dict:
    return {
        'type': 'object',
        'properties': {
            field_id: {
                'type': 'object',
                'properties': {
                    'overview': {'type': 'string', 'minLength': 1},
                    'suggestions': {
                        'type': 'array',
                        'items': {'type': 'string', 'minLength': 1},
                        'minItems': 1,
                        'maxItems': 3,
                    },
                },
                'required': ['overview', 'suggestions'],
            }
            for field_id in field_ids
        },
        'required': list(field_ids),
    }


class AISuggestionService:
    PROMPT_VERSION = 'phase1-recommendations-v6'
    PHASE3_OVERVIEW_PROMPT_VERSION = 'phase3-overview-v3'

    def __init__(self, db: Session):
        self.db = db
        self.run_repo = RunRepository(db)
        self.canvas_repo = CanvasRepository(db)
        self.ai_repo = AISuggestionRepository(db)
        self.participant_repo = ParticipantRepository(db)
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
        return build_canvas_context(self.canvas_repo, run_id, cycle)

    def _specialist_system(self, specialist, specialists) -> str:
        persona = Persona(
            role_title=specialist.ai_persona_role or 'domain specialist',
            role_description=specialist.ai_persona_description,
        )
        other_roles = [p.ai_persona_role for p in specialists if p.id != specialist.id]
        return build_system_instruction(persona, other_roles)

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

    def _prompt_for_phase3_overview(self, targets_by_field_id: dict, context_text: str) -> str:
        targets = '\n'.join(
            f'- {field_id}: {question.title}' for field_id, question in targets_by_field_id.items()
        )
        return (
            'Phase 3 of the workshop: the team has reformulated the research problem in the canvas '
            'below. Review the requested canvas fields from your specialist perspective to help the '
            'facilitator strengthen them.\n\n'
            'Complete canvas (field title: content):\n'
            f'{context_text}\n\n'
            'Fields to review (JSON key: field title):\n'
            f'{targets}\n\n'
            'For each field to review return:\n'
            '- overview: 1 to 2 sentences on what the field currently states and how it holds up '
            'from your perspective, naming its specific strength or weakness.\n'
            '- suggestions: 1 to 3 concrete changes to that field, each tied to what the team wrote '
            'and to your expertise (what to add, cut or clarify, and why).\n'
            'Keep each field within about 60 to 110 words in total. Do not repeat the same point '
            'across fields; when a field is already solid from your perspective, say why briefly and '
            'suggest only what would still add value.\n'
            'Do not rewrite the field as final text to be pasted back, and do not use markdown.\n'
            f'{ENGLISH_ONLY_RULE}\n'
            'Respond only with JSON matching the required schema.'
        )

    def _request_phase3_review(self, system: str, targets_by_field_id: dict, context_text: str) -> dict:
        """One LLM call reviewing every target field from a single perspective.

        Touches no database state, so the panel can run several of these in parallel.
        """
        raw = self.llm_client.generate_json(
            self._prompt_for_phase3_overview(targets_by_field_id, context_text),
            schema=_phase3_overview_schema(list(targets_by_field_id)),
            schema_name='phase3_overview',
            system=system,
        )

        reviews: dict[str, dict] = {}
        for field_id, question in targets_by_field_id.items():
            entry = raw.get(field_id) or {}
            overview = str(entry.get('overview') or '').strip()
            suggestions = [str(item).strip() for item in entry.get('suggestions') or [] if str(item).strip()]
            if not overview or not suggestions:
                raise RuntimeError(f'LLM response did not contain overview text for {question.key}')
            reviews[field_id] = {'overview': overview, 'suggestions': suggestions}
        return reviews

    def _prompt_for_panel_synthesis(
        self,
        targets_by_field_id: dict,
        context_text: str,
        specialists_by_key: dict,
        reviews_by_key: dict[str, dict],
    ) -> str:
        panel = '\n'.join(
            f'- {key}: {specialist.ai_persona_role}' for key, specialist in specialists_by_key.items()
        )
        field_blocks = []
        for field_id, question in targets_by_field_id.items():
            lines = [f'{field_id} - {question.title}:']
            for key, specialist in specialists_by_key.items():
                review = reviews_by_key[key][field_id]
                suggestions = ' | '.join(review['suggestions'])
                lines.append(
                    f"  [{key} - {specialist.ai_persona_role}] Overview: {review['overview']} "
                    f'Suggestions: {suggestions}'
                )
            field_blocks.append('\n'.join(lines))
        reviews_text = '\n\n'.join(field_blocks)

        return (
            'Phase 3 of the workshop: each AI specialist on the panel reviewed the reformulated '
            'research problem independently. Consolidate their reviews into one panel overview per '
            'canvas field.\n\n'
            'Canvas (field title: content):\n'
            f'{context_text}\n\n'
            'Panel (JSON key: specialist):\n'
            f'{panel}\n\n'
            'Independent reviews, by field (JSON key - field title):\n'
            f'{reviews_text}\n\n'
            'For each field return:\n'
            '- consensus: 1 to 2 sentences with the concrete point where the specialists converge '
            '(what exactly is strong or missing, never a vague remark such as "needs to be more '
            'specific"). If they raised unrelated points, state the most important concern for the '
            'field and who raised it, without inventing agreement.\n'
            '- divergence: 1 to 2 sentences naming the specialists who disagree or prioritize '
            'differently and what that tension means for the team; an empty string when they '
            'genuinely do not diverge on this field.\n'
            '- suggestions: exactly one suggestion per specialist (one entry per panel JSON key): '
            "the most important change that specialist proposed for this field, keeping their "
            'concrete terms. A point several specialists made belongs in the consensus; then give '
            'each of them their most important other suggestion, so no two specialists repeat the '
            'same suggestion.\n'
            'When every specialist shares a point, refer to them together as the panel instead of '
            'listing every role title; name individual specialists in the text only to tell their '
            'positions apart, by their role in English (for example "the sales specialist"), never '
            'by their JSON key.\n'
            f'{ENGLISH_ONLY_RULE} This applies to every text value (consensus, divergence and '
            'suggestions).\n'
            'Keep each field within about 90 to 150 words in total.\n'
            'Respond only with JSON matching the required schema.'
        )

    def _request_panel_synthesis(
        self,
        targets_by_field_id: dict,
        context_text: str,
        reviews_by_specialist: list[tuple[object, dict]],
    ) -> dict:
        # Neutral ids, like the field ids, so long role titles never become JSON keys.
        specialists_by_key = {
            f'specialist_{index}': specialist
            for index, (specialist, _) in enumerate(reviews_by_specialist, start=1)
        }
        reviews_by_key = {
            f'specialist_{index}': reviews
            for index, (_, reviews) in enumerate(reviews_by_specialist, start=1)
        }
        raw = self.llm_client.generate_json(
            self._prompt_for_panel_synthesis(
                targets_by_field_id, context_text, specialists_by_key, reviews_by_key
            ),
            schema=_panel_synthesis_schema(list(targets_by_field_id), list(specialists_by_key)),
            schema_name='phase3_panel_synthesis',
            system=PANEL_MODERATOR_INSTRUCTION,
        )

        syntheses: dict[str, dict] = {}
        for field_id, question in targets_by_field_id.items():
            entry = raw.get(field_id) or {}
            consensus = str(entry.get('consensus') or '').strip()
            divergence = str(entry.get('divergence') or '').strip()
            raw_suggestions = entry.get('suggestions') or {}
            suggestions = [
                {
                    'role_title': specialist.ai_persona_role,
                    'text': str(raw_suggestions.get(key) or '').strip(),
                }
                for key, specialist in specialists_by_key.items()
            ]
            if not consensus or not all(item['text'] for item in suggestions):
                raise RuntimeError(f'LLM response did not contain the panel overview for {question.key}')
            syntheses[field_id] = {
                'consensus': consensus,
                'divergence': divergence,
                'suggestions': suggestions,
            }
        return syntheses

    def _generate_phase3_overviews(
        self,
        run_id: int,
        target_questions,
        context_text: str,
        specialist_id: int | None,
    ) -> dict:
        """Phase 3 overview for the target fields, from one of three sources.

        - specialist_id given: that AI specialist alone (1 call).
        - no AI specialist configured: the default methodologist persona (1 call).
        - otherwise the panel: every specialist reviews independently in parallel, then a
          moderator call consolidates them into one overview per field (specialists + 1 calls).
        """
        # Neutral ids instead of the legacy question keys, which would mislead the model.
        targets_by_field_id = {
            f'field_{index}': question for index, question in enumerate(target_questions, start=1)
        }

        def by_question_key(per_field: dict, formatter) -> dict[str, str]:
            return {
                question.key: formatter(per_field[field_id])
                for field_id, question in targets_by_field_id.items()
            }

        specialists = self.participant_repo.list_ai_specialists(run_id)
        result = {
            'mode': 'default',
            'specialist': None,
            'perspectives': [],
            'failed_specialists': [],
        }

        if specialist_id is not None:
            specialist = next((p for p in specialists if p.id == specialist_id), None)
            if specialist is None:
                raise ValueError('AI specialist not found')
            reviews = self._request_phase3_review(
                self._specialist_system(specialist, specialists), targets_by_field_id, context_text
            )
            return {
                **result,
                'mode': 'specialist',
                'specialist': specialist,
                'overviews': by_question_key(reviews, _format_review),
            }

        if not specialists:
            reviews = self._request_phase3_review(
                build_system_instruction(DEFAULT_PERSONA), targets_by_field_id, context_text
            )
            return {**result, 'overviews': by_question_key(reviews, _format_review)}

        # Systems are built up front: the worker threads must not touch the DB session.
        systems = [(specialist, self._specialist_system(specialist, specialists)) for specialist in specialists]
        with ThreadPoolExecutor(max_workers=len(systems)) as pool:
            futures = [
                (specialist, pool.submit(self._request_phase3_review, system, targets_by_field_id, context_text))
                for specialist, system in systems
            ]
        reviewed: list[tuple[object, dict]] = []
        last_error: Exception | None = None
        for specialist, future in futures:
            try:
                reviewed.append((specialist, future.result()))
            except Exception as exc:  # noqa: BLE001
                logger.warning('Phase 3 review failed for AI specialist %s: %s', specialist.id, exc)
                result['failed_specialists'].append(specialist.ai_persona_role)
                last_error = exc
        if not reviewed:
            raise last_error

        result['perspectives'] = [
            {
                'specialist_id': specialist.id,
                'role_title': specialist.ai_persona_role,
                'overviews': by_question_key(reviews, _format_review),
            }
            for specialist, reviews in reviewed
        ]
        if len(reviewed) == 1:
            # Nobody left to consolidate with: show the one review that came back.
            specialist, reviews = reviewed[0]
            return {
                **result,
                'mode': 'specialist',
                'specialist': specialist,
                'perspectives': [],
                'overviews': by_question_key(reviews, _format_review),
            }

        syntheses = self._request_panel_synthesis(targets_by_field_id, context_text, reviewed)
        return {**result, 'mode': 'panel', 'overviews': by_question_key(syntheses, _format_panel_synthesis)}

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
            suggestion_text = self.llm_client.generate(
                prompt, system=build_system_instruction(DEFAULT_PERSONA)
            )
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

    def generate_phase3_overview(self, run_id: int, specialist_id: int | None = None) -> dict:
        run = self._get_run_for_phase3_overview(run_id)
        cycle = self._response_cycle_for_run(run)
        filled_items, empty_questions, context_text = self._build_canvas_context(run_id, cycle)

        if empty_questions:
            raise ValueError('Fill every canvas field before requesting the overview')

        result = self._generate_phase3_overviews(
            run_id,
            [item['question'] for item in filled_items],
            context_text,
            specialist_id,
        )

        return {
            'generated_count': len(result['overviews']),
            'field_count': len(filled_items) + len(empty_questions),
            **self._phase3_response_fields(result),
        }

    @staticmethod
    def _phase3_response_fields(result: dict) -> dict:
        specialist = result['specialist']
        return {
            'overviews': result['overviews'],
            'mode': result['mode'],
            'specialist_id': specialist.id if specialist else None,
            'role_title': specialist.ai_persona_role if specialist else None,
            'perspectives': result['perspectives'],
            'failed_specialists': result['failed_specialists'],
        }

    def generate_phase3_canvas_overview(
        self,
        run_id: int,
        question_key: str,
        specialist_id: int | None = None,
    ) -> dict:
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
        result = self._generate_phase3_overviews(run_id, [question], context_text, specialist_id)
        fields = self._phase3_response_fields(result)

        return {
            'question_key': question.key,
            'overview_text': fields.pop('overviews')[question.key],
            **fields,
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
