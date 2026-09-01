from __future__ import annotations

import os

from tenacity import retry, stop_after_attempt, wait_exponential


class LLMConfigError(RuntimeError):
    pass


@retry(wait=wait_exponential(min=2, max=20), stop=stop_after_attempt(3))
def generate(prompt: str) -> str:
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        import google.generativeai as genai

        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(prompt)
        if not response.text:
            raise RuntimeError("Gemini returned empty text.")
        return response.text.strip()

    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        from openai import OpenAI

        model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
        client = OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1")
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=2500
        )
        text = response.choices[0].message.content
        if not text:
            raise RuntimeError("Groq returned empty text.")
        return text.strip()

    raise LLMConfigError("Set GEMINI_API_KEY or GROQ_API_KEY before running generation.")
