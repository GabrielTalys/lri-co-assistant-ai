from app.core.config import settings


class LLMClient:
    def generate(self, prompt: str) -> str:
        raise NotImplementedError


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

    def generate(self, prompt: str) -> str:
        response = self.client.responses.create(
            model=settings.llm_model,
            input=prompt,
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


def get_llm_client() -> LLMClient:
    return OpenAILLMClient()
