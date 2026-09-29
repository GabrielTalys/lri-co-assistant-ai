"""End-to-end tests for the AI Specialist layer (Phase 2 -> Phase 5), using the fake LLM."""

import httpx
import openai
import pytest
from sqlalchemy import select

from app.domain.canvas_keys import CANVAS_KEYS
from app.models import Decision, Participant, Score
from app.services import ai_service, ai_specialist_service
from app.services.llm_client import FakeLLMClient, LLMServiceError, OpenAILLMClient, _parse_json_object

SPECIALTY = 'Especialista em Vendas'
HUMAN_SCORES = {'impact': 4, 'feasibility': 6, 'alignment': 3}
# FakeLLMClient: value=6 -> impact, feasibility=4, applicability=5 -> alignment.
AI_SCORES = {'impact': 6, 'feasibility': 4, 'alignment': 5}


class RecordingFakeLLM(FakeLLMClient):
    def __init__(self, assessment=None, error=None):
        self.prompts = []
        self.assessment = assessment
        self.error = error

    def generate(self, prompt):
        self.prompts.append(prompt)
        if self.error:
            raise self.error
        return super().generate(prompt)

    def generate_json(self, prompt, *, schema_name, schema):
        self.prompts.append(prompt)
        if self.error:
            raise self.error
        if self.assessment is not None:
            return dict(self.assessment)
        return super().generate_json(prompt, schema_name=schema_name, schema=schema)


class Flow:
    """Drives one project through the public API as the facilitator and an invited human."""

    def __init__(self, client, headers, *, ai_mode_enabled=True):
        self.client = client
        self.headers = headers
        response = client.post(
            '/projects',
            json={'title': 'AI specialist test', 'ai_mode_enabled': ai_mode_enabled},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        self.id = response.json()['id']
        participants = client.get(f'/projects/{self.id}/participants', headers=headers).json()
        self.facilitator_id = next(p['id'] for p in participants if p['role'] == 'facilitator')
        self.human_id = None

    def fill_canvas(self):
        for key in CANVAS_KEYS:
            response = self.client.put(
                f'/projects/{self.id}/canvas/{key}',
                json={'participant_id': self.facilitator_id, 'content': f'Conteúdo do campo {key} sobre vendas B2B.'},
                headers=self.headers,
            )
            assert response.status_code == 200, response.text

    def advance(self, expected_phase):
        response = self.client.post(f'/projects/{self.id}/advance-phase', headers=self.headers)
        assert response.status_code == 200, response.text
        assert response.json()['current_phase'] == expected_phase
        return response.json()

    def invite_human(self):
        response = self.client.post(f'/projects/{self.id}/invites', json={'name': 'maria silva'}, headers=self.headers)
        assert response.status_code == 200, response.text
        token = response.json()['invite_url'].rstrip('/').rsplit('/', 1)[-1]
        accepted = self.client.post(f'/invites/{token}/accept', json={})
        assert accepted.status_code == 200, accepted.text
        self.human_id = accepted.json()['participant_id']

    def configure_ai(self, name='Ana IA', specialty=SPECIALTY):
        return self.client.put(
            f'/projects/{self.id}/ai-specialist',
            json={'display_name': name, 'ai_specialty': specialty},
            headers=self.headers,
        )

    def to_phase(self, phase, *, with_ai=True):
        self.fill_canvas()
        self.advance(2)
        self.invite_human()
        if with_ai:
            assert self.configure_ai().status_code == 200
        for next_phase in range(3, phase + 1):
            self.advance(next_phase)

    def score_human(self, scores=HUMAN_SCORES):
        for metric_key, value in scores.items():
            response = self.client.post(
                f'/projects/{self.id}/scores',
                json={
                    'participant_id': self.human_id,
                    'metric_key': metric_key,
                    'value': value,
                    'comment': f'Comentário humano {metric_key}',
                },
            )
            assert response.status_code == 200, response.text

    def generate_ai_assessment(self):
        return self.client.post(f'/projects/{self.id}/ai-specialist/assessment', headers=self.headers)

    def scores(self):
        response = self.client.get(f'/projects/{self.id}/scores', headers=self.headers)
        assert response.status_code == 200, response.text
        return response.json()

    def set_ai_mode(self, enabled):
        response = self.client.patch(f'/projects/{self.id}', json={'ai_mode_enabled': enabled}, headers=self.headers)
        assert response.status_code == 200, response.text


def _ai_participants(db_session, run_id):
    return db_session.scalars(select(Participant).where(Participant.run_id == run_id, Participant.is_ai.is_(True))).all()


def _scores(db_session, run_id, participant_id=None, cycle=None):
    stmt = select(Score).where(Score.run_id == run_id)
    if participant_id is not None:
        stmt = stmt.where(Score.participant_id == participant_id)
    if cycle is not None:
        stmt = stmt.where(Score.cycle == cycle)
    return db_session.scalars(stmt).all()


@pytest.fixture
def recording_llm(monkeypatch):
    fake = RecordingFakeLLM()
    monkeypatch.setattr(ai_service, 'get_llm_client', lambda: fake)
    monkeypatch.setattr(ai_specialist_service, 'get_llm_client', lambda: fake)
    return fake


# --- Test 1: Phase 2 configuration ------------------------------------------------


def test_phase2_configure_and_update_specialist_without_duplicates(client, auth_headers, db_session):
    flow = Flow(client, auth_headers)
    flow.fill_canvas()
    flow.advance(2)

    assert client.get(f'/projects/{flow.id}/ai-specialist', headers=auth_headers).status_code == 404

    created = flow.configure_ai(name='Ana IA', specialty=SPECIALTY)
    assert created.status_code == 200, created.text
    body = created.json()
    assert body['display_name'] == 'Ana IA'
    assert body['ai_specialty'] == SPECIALTY
    assert body['is_ai'] is True and body['role'] == 'ai_specialist'
    assert body['user_id'] is None and body['email'] is None

    updated = flow.configure_ai(name='Ana IA', specialty='Especialista em Marketing')
    assert updated.status_code == 200
    assert updated.json()['id'] == body['id']
    assert client.get(f'/projects/{flow.id}/ai-specialist', headers=auth_headers).json()['ai_specialty'] == (
        'Especialista em Marketing'
    )
    assert len(_ai_participants(db_session, flow.id)) == 1

    blank = flow.configure_ai(name='  ', specialty=SPECIALTY)
    assert blank.status_code == 422


# --- Test 2: Phase 3 uses the specialty without replacing the general analysis -----


def test_phase3_overview_prompt_includes_specialty(client, auth_headers, recording_llm):
    flow = Flow(client, auth_headers)
    flow.to_phase(3)

    response = client.post(f'/projects/{flow.id}/canvas/overview', headers=auth_headers)
    assert response.status_code == 200, response.text
    assert response.json()['generated_count'] == len(CANVAS_KEYS)
    assert len(recording_llm.prompts) == len(CANVAS_KEYS)
    for prompt in recording_llm.prompts:
        assert SPECIALTY in prompt
        assert 'does not replace the general analysis' in prompt
        # Original general analysis is still requested.
        assert 'Complete phase 3 context:' in prompt
        assert 'Overview: <short synthesis' in prompt

    single = client.post(f'/projects/{flow.id}/canvas/problem/overview', headers=auth_headers)
    assert single.status_code == 200, single.text
    assert SPECIALTY in recording_llm.prompts[-1]


def test_phase3_overview_without_specialist_keeps_original_prompt(client, auth_headers, recording_llm):
    flow = Flow(client, auth_headers)
    flow.to_phase(3, with_ai=False)

    response = client.post(f'/projects/{flow.id}/canvas/problem/overview', headers=auth_headers)
    assert response.status_code == 200, response.text
    assert 'Additional specialist perspective' not in recording_llm.prompts[-1]


def test_phase3_overview_provider_error_returns_clear_message(client, auth_headers, monkeypatch):
    flow = Flow(client, auth_headers)
    flow.to_phase(3)
    fake = RecordingFakeLLM(error=LLMServiceError('The AI provider did not respond in time. Please try again.', 504))
    monkeypatch.setattr(ai_service, 'get_llm_client', lambda: fake)

    response = client.post(f'/projects/{flow.id}/canvas/problem/overview', headers=auth_headers)
    assert response.status_code == 504
    assert response.json()['detail'].startswith('Could not generate the AI overview.')


# --- Test 3: Phase 4 assessment ---------------------------------------------------


def test_phase4_ai_assessment_is_validated_and_persisted(client, auth_headers, db_session, recording_llm):
    flow = Flow(client, auth_headers)
    flow.to_phase(4)

    response = flow.generate_ai_assessment()
    assert response.status_code == 200, response.text
    body = response.json()
    assert body['scores'] == AI_SCORES
    assert body['comment'] == FakeLLMClient.ASSESSMENT['comment']
    assert body['cycle'] == 1

    prompt = recording_llm.prompts[-1]
    assert SPECIALTY in prompt
    assert 'Brazilian Portuguese' in prompt
    assert 'Go/Pivot/Abort' in prompt

    ai = _ai_participants(db_session, flow.id)[0]
    rows = _scores(db_session, flow.id, participant_id=ai.id)
    assert {row.metric_key: row.value for row in rows} == AI_SCORES
    assert all(isinstance(row.value, int) and 1 <= row.value <= 7 for row in rows)
    assert all(row.cycle == 1 and row.comment == body['comment'] for row in rows)

    again = flow.generate_ai_assessment()
    assert again.status_code == 400
    assert 'already exists' in again.json()['detail']


@pytest.mark.parametrize(
    'bad_payload',
    [
        {'value': 8, 'feasibility': 4, 'applicability': 5, 'comment': 'x'},
        {'value': 0, 'feasibility': 4, 'applicability': 5, 'comment': 'x'},
        {'value': 5.5, 'feasibility': 4, 'applicability': 5, 'comment': 'x'},
        {'value': '6', 'feasibility': 4, 'applicability': 5, 'comment': 'x'},
        {'value': True, 'feasibility': 4, 'applicability': 5, 'comment': 'x'},
        {'value': 6, 'feasibility': 4, 'applicability': 5, 'comment': '   '},
        {'value': 6, 'feasibility': 4, 'applicability': 5},
        {'value': 6, 'feasibility': 4, 'applicability': 5, 'comment': 'x', 'decision': 'GO'},
    ],
)
def test_phase4_invalid_ai_output_saves_nothing(client, auth_headers, db_session, monkeypatch, bad_payload):
    flow = Flow(client, auth_headers)
    flow.to_phase(4)
    fake = RecordingFakeLLM(assessment=bad_payload)
    monkeypatch.setattr(ai_specialist_service, 'get_llm_client', lambda: fake)

    response = flow.generate_ai_assessment()
    assert response.status_code == 502
    assert response.json()['detail'].startswith('Could not generate the AI specialist assessment.')
    assert _scores(db_session, flow.id) == []


def test_phase4_missing_api_key_returns_503_without_saving(client, auth_headers, db_session, monkeypatch):
    from app.core.config import settings

    flow = Flow(client, auth_headers)
    flow.to_phase(4)
    monkeypatch.setattr(settings, 'llm_mock', False)
    monkeypatch.setattr(settings, 'openai_api_key', '')

    response = flow.generate_ai_assessment()
    assert response.status_code == 503
    assert 'OPENAI_API_KEY' in response.json()['detail']
    assert 'Traceback' not in response.text
    assert _scores(db_session, flow.id) == []


def test_phase4_provider_auth_error_does_not_leak_key(client, auth_headers, db_session, monkeypatch):
    secret = 'sk-test-SECRET-123'
    request = httpx.Request('POST', 'https://api.openai.com/v1/responses')
    error = openai.AuthenticationError(
        f'Incorrect API key provided: {secret}',
        response=httpx.Response(401, request=request),
        body=None,
    )
    openai_client = OpenAILLMClient.__new__(OpenAILLMClient)
    openai_client.client = _StubOpenAI(error=error)
    monkeypatch.setattr(ai_specialist_service, 'get_llm_client', lambda: openai_client)

    flow = Flow(client, auth_headers)
    flow.to_phase(4)
    response = flow.generate_ai_assessment()
    assert response.status_code == 502
    assert secret not in response.text
    assert 'OPENAI_API_KEY' in response.json()['detail']
    assert _scores(db_session, flow.id) == []


# --- OpenAI client: structured outputs and error mapping (no network) -------------


class _StubResponses:
    def __init__(self, error=None, output_text=''):
        self.error = error
        self.output_text = output_text
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return type('Resp', (), {'output_text': self.output_text, 'output': []})()


class _StubOpenAI:
    def __init__(self, error=None, output_text=''):
        self.responses = _StubResponses(error=error, output_text=output_text)


def _openai_client(stub):
    llm = OpenAILLMClient.__new__(OpenAILLMClient)
    llm.client = stub
    return llm


def test_openai_generate_json_uses_strict_json_schema():
    stub = _StubOpenAI(output_text='{"value": 6, "feasibility": 4, "applicability": 5, "comment": "ok"}')
    result = _openai_client(stub).generate_json(
        'prompt',
        schema_name='ai_specialist_assessment',
        schema=ai_specialist_service.ASSESSMENT_SCHEMA,
    )
    assert result == {'value': 6, 'feasibility': 4, 'applicability': 5, 'comment': 'ok'}
    text_format = stub.responses.calls[0]['text']['format']
    assert text_format['type'] == 'json_schema'
    assert text_format['strict'] is True
    assert text_format['schema']['additionalProperties'] is False
    assert set(text_format['schema']['required']) == {'value', 'feasibility', 'applicability', 'comment'}


def test_markdown_fenced_json_is_parsed():
    fenced = '```json\n{"value": 6, "feasibility": 4, "applicability": 5, "comment": "ok"}\n```'
    assert _parse_json_object(fenced)['value'] == 6
    with pytest.raises(LLMServiceError):
        _parse_json_object('not json')


def _request():
    return httpx.Request('POST', 'https://api.openai.com/v1/responses')


@pytest.mark.parametrize(
    'error, expected_status',
    [
        (openai.APITimeoutError(request=_request()), 504),
        (openai.APIConnectionError(request=_request()), 503),
        (openai.AuthenticationError('bad key', response=httpx.Response(401, request=_request()), body=None), 502),
        (openai.RateLimitError('rate limited', response=httpx.Response(429, request=_request()), body=None), 503),
        (openai.InternalServerError('down', response=httpx.Response(500, request=_request()), body=None), 503),
        (openai.BadRequestError('bad request', response=httpx.Response(400, request=_request()), body=None), 502),
    ],
)
def test_openai_errors_are_mapped(error, expected_status):
    with pytest.raises(LLMServiceError) as excinfo:
        _openai_client(_StubOpenAI(error=error)).generate('prompt')
    assert excinfo.value.status_code == expected_status


def test_openai_empty_response_is_an_error():
    with pytest.raises(LLMServiceError):
        _openai_client(_StubOpenAI(output_text='')).generate('prompt')


# --- Test 4: manual scores for the AI participant are rejected ---------------------


def test_manual_score_for_ai_participant_is_rejected(client, auth_headers, db_session):
    flow = Flow(client, auth_headers)
    flow.to_phase(4)
    ai = _ai_participants(db_session, flow.id)[0]
    payload = {'participant_id': ai.id, 'metric_key': 'impact', 'value': 7, 'comment': 'manual'}

    anonymous = client.post(f'/projects/{flow.id}/scores', json=payload)
    as_owner = client.post(f'/projects/{flow.id}/scores', json=payload, headers=auth_headers)
    assert anonymous.status_code == 403
    assert as_owner.status_code == 403
    assert _scores(db_session, flow.id) == []

    flow.score_human()
    rows = _scores(db_session, flow.id, participant_id=flow.human_id)
    assert {row.metric_key: row.value for row in rows} == HUMAN_SCORES


# --- Test 5: AI mode disabled -----------------------------------------------------


def test_ai_mode_disabled_excludes_ai_without_deleting_history(client, auth_headers, db_session):
    flow = Flow(client, auth_headers)
    flow.to_phase(4)
    assert flow.generate_ai_assessment().status_code == 200
    flow.score_human()

    flow.set_ai_mode(False)
    data = flow.scores()
    assert data['ai_specialist_configured'] is True
    assert data['ai_specialist_active'] is False
    assert data['required_respondents'] == 1 and data['completed_respondents'] == 1
    assert data['all_done'] is True
    assert data['criteria']['impact']['count'] == 1
    assert data['criteria']['impact']['median'] == HUMAN_SCORES['impact']
    assert all(not entry['is_ai'] for entry in data['individual_assessments'])
    assert all(entry['participant_id'] != _ai_participants(db_session, flow.id)[0].id for entry in data['comments'])

    ai = _ai_participants(db_session, flow.id)[0]
    assert len(_scores(db_session, flow.id, participant_id=ai.id)) == 3  # history kept

    blocked = flow.generate_ai_assessment()
    assert blocked.status_code == 400

    flow.set_ai_mode(True)
    data = flow.scores()
    assert data['ai_specialist_active'] is True and data['ai_assessment_completed'] is True
    assert data['criteria']['impact']['count'] == 2


def test_ai_disabled_does_not_block_human_flow(client, auth_headers):
    flow = Flow(client, auth_headers)
    flow.to_phase(4)  # AI configured but never assessed
    flow.set_ai_mode(False)
    flow.score_human()

    data = flow.scores()
    assert data['all_done'] is True
    flow.advance(5)


def test_pending_ai_assessment_is_reported_separately(client, auth_headers):
    flow = Flow(client, auth_headers)
    flow.to_phase(4)
    flow.score_human()

    data = flow.scores()
    assert data['ai_specialist_active'] is True
    assert data['ai_assessment_completed'] is False
    assert data['all_done'] is False  # the active AI specialist is still a respondent

    assert flow.generate_ai_assessment().status_code == 200
    data = flow.scores()
    assert data['ai_assessment_completed'] is True
    assert data['all_done'] is True


# --- Test 6: Phase 5 results ------------------------------------------------------


def test_phase5_shows_human_and_ai_and_decision_stays_human(client, auth_headers, db_session):
    flow = Flow(client, auth_headers)
    flow.to_phase(4)
    flow.score_human()
    assert flow.generate_ai_assessment().status_code == 200
    flow.advance(5)

    data = flow.scores()
    entries = {entry['is_ai']: entry for entry in data['individual_assessments']}
    ai_entry, human_entry = entries[True], entries[False]
    assert ai_entry['participant_label'] == 'Ana IA'
    assert ai_entry['ai_specialty'] == SPECIALTY
    assert {k: v['score'] for k, v in ai_entry['scores'].items()} == AI_SCORES
    assert all(v['comment'] for v in ai_entry['scores'].values())
    assert human_entry['participant_label'] == 'Maria Silva'
    assert {k: v['score'] for k, v in human_entry['scores'].items()} == HUMAN_SCORES

    for metric_key in AI_SCORES:
        assert data['criteria'][metric_key]['count'] == 2
        assert data['criteria'][metric_key]['median'] == (AI_SCORES[metric_key] + HUMAN_SCORES[metric_key]) / 2

    assert db_session.scalars(select(Decision).where(Decision.run_id == flow.id)).all() == []
    assert flow.generate_ai_assessment().status_code == 400  # not available outside phase 4

    decided = client.post(f'/projects/{flow.id}/decision', json={'decision': 'GO'}, headers=auth_headers)
    assert decided.status_code == 200, decided.text
    assert decided.json()['decision'] == 'GO'


# --- Test 7: cycles ---------------------------------------------------------------


def test_previous_cycle_scores_are_not_mixed(client, auth_headers, db_session):
    flow = Flow(client, auth_headers)
    flow.to_phase(4)
    flow.score_human()
    assert flow.generate_ai_assessment().status_code == 200
    flow.advance(5)

    pivot = client.post(f'/projects/{flow.id}/decision', json={'decision': 'PIVOT'}, headers=auth_headers)
    assert pivot.status_code == 200, pivot.text
    assert pivot.json()['current_cycle'] == 2 and pivot.json()['current_phase'] == 2
    flow.advance(3)
    flow.advance(4)

    data = flow.scores()
    assert data['individual_assessments'] == []
    assert data['criteria']['impact']['count'] == 0
    assert data['ai_assessment_completed'] is False

    response = flow.generate_ai_assessment()
    assert response.status_code == 200, response.text
    assert response.json()['cycle'] == 2
    assert len(_scores(db_session, flow.id, cycle=1)) == 6  # cycle 1 untouched
    assert len(_scores(db_session, flow.id, cycle=2)) == 3
    assert flow.scores()['criteria']['impact']['count'] == 1
