import json

from app.core.config import settings


class LLMClient:
    """`system` carries the persona/standing instructions (system prompt), kept apart
    from the task prompt so the model holds the specialist role more firmly."""

    def generate(self, prompt: str, *, system: str | None = None) -> str:
        raise NotImplementedError

    def generate_json(
        self,
        prompt: str,
        schema: dict,
        *,
        schema_name: str = 'response',
        system: str | None = None,
    ) -> dict:
        """Generate a response constrained to the given JSON schema and return it parsed.

        Used by the phase 3 specialist overviews and the phase 4 AI specialist
        evaluation, which need one well-formed entry per canvas field / metric —
        free-text parsing would be too fragile for that guarantee.
        """
        raise NotImplementedError


def _to_strict_openai_schema(schema: dict) -> dict:
    """Adapt a plain JSON Schema dict to OpenAI's `strict` structured-output rules.

    OpenAI's strict mode requires every object node to set `additionalProperties: False`
    and to list every one of its properties as `required`. Doing this recursively here
    keeps a single canonical schema dict as the source of truth instead of hand-maintaining
    a second, OpenAI-specific copy next to it.
    """
    if not isinstance(schema, dict):
        return schema

    adapted = dict(schema)
    if adapted.get('type') == 'object' and 'properties' in adapted:
        properties = {key: _to_strict_openai_schema(value) for key, value in adapted['properties'].items()}
        adapted['properties'] = properties
        adapted['required'] = list(properties.keys())
        adapted['additionalProperties'] = False
    return adapted


class OpenAILLMClient(LLMClient):
    def __init__(self):
        api_key = settings.openai_api_key.strip()
        if not api_key:
            raise RuntimeError('OPENAI_API_KEY is required for AI suggestions')

        from openai import OpenAI

        self.client = OpenAI(
            api_key=api_key,
            timeout=settings.llm_timeout_seconds,
        )

    def generate(self, prompt: str, *, system: str | None = None) -> str:
        response = self.client.responses.create(
            model=settings.llm_model,
            input=prompt,
            **({'instructions': system} if system else {}),
        )

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

        raise RuntimeError('OpenAI response did not contain any text output')

    def generate_json(
        self,
        prompt: str,
        schema: dict,
        *,
        schema_name: str = 'response',
        system: str | None = None,
    ) -> dict:
        strict_schema = _to_strict_openai_schema(schema)
        response = self.client.responses.create(
            model=settings.llm_model,
            input=prompt,
            **({'instructions': system} if system else {}),
            text={
                'format': {
                    'type': 'json_schema',
                    'name': schema_name,
                    'schema': strict_schema,
                    'strict': True,
                }
            },
        )

        text = (getattr(response, 'output_text', '') or '').strip()
        if not text:
            raise RuntimeError('OpenAI response did not contain any JSON output')
        return json.loads(text)


class GeminiLLMClient(LLMClient):
    def __init__(self):
        api_key = settings.gemini_api_key.strip()
        if not api_key:
            raise RuntimeError('GEMINI_API_KEY is required for AI suggestions')

        from google import genai
        from google.genai import types

        # The SDK only retries when retry_options is set; by default a single transient
        # 503 ("model is experiencing high demand") from the free tier fails the request.
        # Retries back off exponentially (2s, 4s, 8s, ... capped at 20s) on 408/429/5xx.
        self.client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                retry_options=types.HttpRetryOptions(
                    attempts=max(1, settings.gemini_retry_attempts),
                    initial_delay=2.0,
                    max_delay=20.0,
                ),
            ),
        )
        self.model = settings.gemini_model
        self.fallback_model = settings.gemini_fallback_model.strip()

    def _generate_content(self, **kwargs):
        from google.genai import errors

        try:
            return self.client.models.generate_content(model=self.model, **kwargs)
        except errors.APIError as exc:
            overloaded = exc.code == 429 or (exc.code or 0) >= 500
            if not overloaded or not self.fallback_model or self.fallback_model == self.model:
                raise
            return self.client.models.generate_content(model=self.fallback_model, **kwargs)

    def generate(self, prompt: str, *, system: str | None = None) -> str:
        from google.genai import types

        config = types.GenerateContentConfig(system_instruction=system) if system else None
        response = self._generate_content(contents=prompt, config=config)
        text = (getattr(response, 'text', '') or '').strip()
        if not text:
            raise RuntimeError('Gemini response did not contain any text output')
        return text

    def generate_json(
        self,
        prompt: str,
        schema: dict,
        *,
        schema_name: str = 'response',
        system: str | None = None,
    ) -> dict:
        from google.genai import types

        # The SDK's Schema type uses uppercase OpenAPI type names (OBJECT, STRING, ...),
        # not plain JSON Schema's lowercase ones. from_json_schema() is the SDK's own
        # sanctioned converter, so the canonical schema dict stays plain JSON Schema and
        # never needs a hand-written Gemini-specific copy.
        gemini_schema = types.Schema.from_json_schema(
            json_schema=types.JSONSchema.model_validate(schema),
            api_option='GEMINI_API',
        )
        response = self._generate_content(
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type='application/json',
                response_schema=gemini_schema,
            ),
        )
        text = (getattr(response, 'text', '') or '').strip()
        if not text:
            raise RuntimeError('Gemini response did not contain any JSON output')
        return json.loads(text)


def get_llm_client() -> LLMClient:
    provider = (settings.llm_provider or 'gemini').strip().lower()
    if provider == 'openai':
        return OpenAILLMClient()
    return GeminiLLMClient()
