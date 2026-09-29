import copy
import json
import logging

from app.core.config import settings


logger = logging.getLogger(__name__)


class LLMServiceError(RuntimeError):
    """AI provider failure with a user-safe message and a suggested HTTP status.

    Subclasses RuntimeError so callers that already catch RuntimeError keep working.
    The message never contains the API key, provider payloads, or stack traces.
    """

    def __init__(self, user_message: str, status_code: int = 502):
        super().__init__(user_message)
        self.user_message = user_message
        self.status_code = status_code


class LLMClient:
    def generate(self, prompt: str) -> str:
        raise NotImplementedError

    def generate_json(self, prompt: str, *, schema_name: str, schema: dict) -> dict:
        """Return a JSON object that follows `schema` (Structured Outputs)."""
        raise NotImplementedError


def _parse_json_object(text: str) -> dict:
    candidate = (text or '').strip()
    # Defensive: tolerate a Markdown code fence around the JSON object.
    if candidate.startswith('```'):
        candidate = candidate.split('\n', 1)[1] if '\n' in candidate else ''
        if candidate.rstrip().endswith('```'):
            candidate = candidate.rstrip()[:-3]
        candidate = candidate.strip()
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise LLMServiceError('The AI returned an invalid response (malformed JSON).') from exc
    if not isinstance(payload, dict):
        raise LLMServiceError('The AI returned an invalid response (expected a JSON object).')
    return payload


class OpenAILLMClient(LLMClient):
    def __init__(self):
        api_key = settings.openai_api_key.strip()
        if not api_key:
            raise LLMServiceError(
                'The AI service is not configured: OPENAI_API_KEY is missing on the server.',
                status_code=503,
            )

        from openai import OpenAI

        self.client = OpenAI(
            api_key=api_key,
            timeout=settings.llm_timeout_seconds,
        )

    def _create_response(self, **kwargs):
        import openai

        try:
            return self.client.responses.create(model=settings.llm_model, **kwargs)
        except openai.APITimeoutError as exc:
            self._log_failure(exc)
            raise LLMServiceError('The AI provider did not respond in time. Please try again.', 504) from exc
        except openai.APIConnectionError as exc:
            self._log_failure(exc)
            raise LLMServiceError('Could not reach the AI provider. Please try again later.', 503) from exc
        except (openai.AuthenticationError, openai.PermissionDeniedError) as exc:
            self._log_failure(exc)
            raise LLMServiceError(
                'The AI provider rejected the configured credentials. Check OPENAI_API_KEY.', 502
            ) from exc
        except openai.RateLimitError as exc:
            self._log_failure(exc)
            raise LLMServiceError(
                'The AI provider rate limit or quota was reached. Please try again in a moment.', 503
            ) from exc
        except openai.InternalServerError as exc:
            self._log_failure(exc)
            raise LLMServiceError('The AI provider is temporarily unavailable. Please try again later.', 503) from exc
        except openai.APIStatusError as exc:
            self._log_failure(exc)
            raise LLMServiceError('The AI provider returned an error while generating the response.', 502) from exc

    @staticmethod
    def _log_failure(exc: Exception) -> None:
        # Log only the error type and status: provider messages may echo parts of the key.
        logger.warning(
            'OpenAI request failed: %s (status=%s)',
            type(exc).__name__,
            getattr(exc, 'status_code', None),
        )

    @staticmethod
    def _extract_text(response) -> str:
        text = (getattr(response, 'output_text', '') or '').strip()
        if text:
            return text

        # Fallback for SDK response variants where `output_text` is empty.
        output = getattr(response, 'output', []) or []
        fragments = []
        for item in output:
            for content in getattr(item, 'content', []) or []:
                if getattr(content, 'type', '') == 'output_text':
                    fragments.append(getattr(content, 'text', ''))

        text = '\n'.join(fragment for fragment in fragments if fragment).strip()
        if text:
            return text

        raise LLMServiceError('The AI returned an empty response.')

    def generate(self, prompt: str) -> str:
        response = self._create_response(input=prompt)
        return self._extract_text(response)

    def generate_json(self, prompt: str, *, schema_name: str, schema: dict) -> dict:
        response = self._create_response(
            input=prompt,
            text={
                'format': {
                    'type': 'json_schema',
                    'name': schema_name,
                    'schema': schema,
                    'strict': True,
                }
            },
        )
        return _parse_json_object(self._extract_text(response))


class FakeLLMClient(LLMClient):
    """Deterministic offline client for local tests. Enabled only with LLM_MOCK=true."""

    ASSESSMENT = {
        'value': 6,
        'applicability': 5,
        'feasibility': 4,
        'comment': (
            'A proposta apresenta potencial de valor e aplicabilidade, '
            'mas sua viabilidade depende dos recursos disponíveis.'
        ),
    }

    def generate(self, prompt: str) -> str:
        if 'Overview:' in prompt:
            return (
                'Overview: [MOCK] Este canvas descreve o problema de forma coerente com o restante da formulação. '
                'Suggestions: [MOCK] Detalhe melhor os critérios de sucesso e os atores envolvidos.'
            )
        return '[MOCK] Sugestão simulada gerada sem chamar a OpenAI.'

    def generate_json(self, prompt: str, *, schema_name: str, schema: dict) -> dict:
        return copy.deepcopy(self.ASSESSMENT)


def get_llm_client() -> LLMClient:
    if settings.llm_mock:
        logger.warning('LLM_MOCK is enabled: using FakeLLMClient instead of OpenAI.')
        return FakeLLMClient()
    return OpenAILLMClient()
