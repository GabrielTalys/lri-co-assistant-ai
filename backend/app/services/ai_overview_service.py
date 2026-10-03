"""Phase 3: AI overview of the reformulated canvas, by one specialist or the whole panel."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import logging

from sqlalchemy.orm import Session

from app.repositories import CanvasRepository, ParticipantRepository, RunRepository
from app.services.ai_prompts import (
    DEFAULT_PERSONA,
    ENGLISH_ONLY_RULE,
    PANEL_MODERATOR_INSTRUCTION,
    build_system_instruction,
    specialist_system_instruction,
)
from app.services.canvas_context import build_canvas_context, response_cycle_for_run
from app.services.guards import get_ai_run
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


def _review_schema(field_ids: list[str]) -> dict:
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


def _prompt_for_review(targets_by_field_id: dict, context_text: str) -> str:
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


def _prompt_for_panel_synthesis(
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


class AIOverviewService:
    def __init__(self, db: Session):
        self.run_repo = RunRepository(db)
        self.canvas_repo = CanvasRepository(db)
        self.participant_repo = ParticipantRepository(db)
        self.llm_client = get_llm_client()

    def _request_review(self, system: str, targets_by_field_id: dict, context_text: str) -> dict:
        """One LLM call reviewing every target field from a single perspective.

        Touches no database state, so the panel can run several of these in parallel.
        """
        raw = self.llm_client.generate_json(
            _prompt_for_review(targets_by_field_id, context_text),
            schema=_review_schema(list(targets_by_field_id)),
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
            _prompt_for_panel_synthesis(targets_by_field_id, context_text, specialists_by_key, reviews_by_key),
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

    def generate_overview(self, run_id: int, specialist_id: int | None = None) -> dict:
        """Overview of every canvas field, from one of three sources.

        - specialist_id given: that AI specialist alone (1 call).
        - no AI specialist configured: the default methodologist persona (1 call).
        - otherwise the panel: every specialist reviews independently in parallel, then a
          moderator call consolidates them into one overview per field (specialists + 1 calls).
        """
        run = get_ai_run(self.run_repo, run_id, phase=3, phase_error='Overview is only available in phase 3')
        cycle = response_cycle_for_run(self.canvas_repo, run)
        filled_items, empty_questions, context_text = build_canvas_context(self.canvas_repo, run_id, cycle)
        if empty_questions:
            raise ValueError('Fill every canvas field before requesting the overview')

        # Neutral ids instead of the legacy question keys, which would mislead the model.
        targets_by_field_id = {
            f'field_{index}': item['question'] for index, item in enumerate(filled_items, start=1)
        }

        def by_question_key(per_field: dict, formatter) -> dict[str, str]:
            return {
                question.key: formatter(per_field[field_id])
                for field_id, question in targets_by_field_id.items()
            }

        def response(overviews: dict[str, str], mode: str = 'default', specialist=None, perspectives=(), failed=()):
            return {
                'generated_count': len(overviews),
                'field_count': len(filled_items),
                'overviews': overviews,
                'mode': mode,
                'specialist_id': specialist.id if specialist else None,
                'role_title': specialist.ai_persona_role if specialist else None,
                'perspectives': list(perspectives),
                'failed_specialists': list(failed),
            }

        specialists = self.participant_repo.list_ai_specialists(run_id)

        if specialist_id is not None:
            specialist = next((p for p in specialists if p.id == specialist_id), None)
            if specialist is None:
                raise ValueError('AI specialist not found')
            reviews = self._request_review(
                specialist_system_instruction(specialist, specialists), targets_by_field_id, context_text
            )
            return response(by_question_key(reviews, _format_review), 'specialist', specialist)

        if not specialists:
            reviews = self._request_review(
                build_system_instruction(DEFAULT_PERSONA), targets_by_field_id, context_text
            )
            return response(by_question_key(reviews, _format_review))

        # Systems are built up front: the worker threads must not touch the DB session.
        systems = [(specialist, specialist_system_instruction(specialist, specialists)) for specialist in specialists]
        with ThreadPoolExecutor(max_workers=len(systems)) as pool:
            futures = [
                (specialist, pool.submit(self._request_review, system, targets_by_field_id, context_text))
                for specialist, system in systems
            ]
        reviewed: list[tuple[object, dict]] = []
        failed: list[str] = []
        last_error: Exception | None = None
        for specialist, future in futures:
            try:
                reviewed.append((specialist, future.result()))
            except Exception as exc:  # noqa: BLE001
                logger.warning('Phase 3 review failed for AI specialist %s: %s', specialist.id, exc)
                failed.append(specialist.ai_persona_role)
                last_error = exc
        if not reviewed:
            raise last_error

        if len(reviewed) == 1:
            # Nobody left to consolidate with: show the one review that came back.
            specialist, reviews = reviewed[0]
            return response(by_question_key(reviews, _format_review), 'specialist', specialist, failed=failed)

        perspectives = [
            {
                'specialist_id': specialist.id,
                'role_title': specialist.ai_persona_role,
                'overviews': by_question_key(reviews, _format_review),
            }
            for specialist, reviews in reviewed
        ]
        syntheses = self._request_panel_synthesis(targets_by_field_id, context_text, reviewed)
        return response(by_question_key(syntheses, _format_panel_synthesis), 'panel', perspectives=perspectives, failed=failed)
