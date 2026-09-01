# 02 — AI Integration (Zero-Cost LLM Stack)

## Model Selection — Free-Tier Reality Check
"GPT-5.5" in your original doc isn't a free option. For a $0 budget, use one of these instead:

| Provider | Model | Free Tier | Notes |
|---|---|---|---|
| **Google Gemini** | `gemini-2.0-flash` (or latest flash) | Generous free daily quota via AI Studio API key | Best free option for structured generation + JSON mode |
| **Groq** | Llama 3.x / Mixtral | Free API, very fast inference | Great for high-volume, low-latency generation |
| **OpenRouter** | Various free-tagged models | Some models fully free | Good fallback/rotation option |
| **Local (Ollama)** | Llama 3.1 8B / Phi-3 | 100% free, runs on your own machine | No rate limits, but needs local compute; not viable on a free cloud runner |

**Recommendation:** Gemini Flash as primary (best quality-to-cost), Groq as fallback if you hit Gemini's daily cap. Both have official Python SDKs and OpenAI-compatible endpoints, so swapping providers is a config change, not a rewrite.

```python
# services/llm.py
import os, google.generativeai as genai

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-2.0-flash")

def generate_email(prompt: str) -> str:
    resp = model.generate_content(prompt)
    return resp.text.strip()
```

Abstract behind a single `services/llm.py` interface with a `generate(prompt: str) -> str` function so you can swap providers later without touching agent code.

## Resume Matching — Skip the Vector DB
At your scale (one resume, dozens of JDs/day), a full ChromaDB deployment is overkill. Two cheap approaches, cheapest first:

**Option A — Keyword + TF-IDF overlap (no API calls, instant, free)**
```python
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

def match_score(resume_text: str, jd_text: str) -> float:
    vec = TfidfVectorizer(stop_words="english").fit([resume_text, jd_text])
    matrix = vec.transform([resume_text, jd_text])
    return float(cosine_similarity(matrix[0], matrix[1])[0][0])
```
Good enough as a first-pass filter to cut LLM calls on obviously irrelevant JDs before you ever burn a free-tier request on them.

**Option B — Embedding similarity (still free)**
Use Gemini's or a free `sentence-transformers` model (`all-MiniLM-L6-v2`, runs locally, no API) for a better semantic score than TF-IDF, still $0:
```python
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("all-MiniLM-L6-v2")

def embed_score(resume_text, jd_text):
    embs = model.encode([resume_text, jd_text])
    from numpy import dot
    from numpy.linalg import norm
    return dot(embs[0], embs[1]) / (norm(embs[0]) * norm(embs[1]))
```
**Recommended pipeline:** TF-IDF as a cheap pre-filter (>40% → proceed), then embedding score as the real gate (>70% → generate email). This two-stage filter means you only spend LLM calls on genuinely relevant jobs — important since free tiers are quota-capped.

## Prompt Design (Structured, Not Freeform)
Freeform prompts drift in tone/length over time. Lock the output format:

```python
# prompts/email.txt
SYSTEM = """You are writing a cold outreach email from a job candidate to a recruiter.
Rules:
- Under 150 words.
- Professional, not obsequious.
- Mention exactly one project relevant to the JD.
- No exclamation points. No "I am writing to express my interest" boilerplate.
- Output ONLY the email body, no subject line, no preamble."""

USER_TEMPLATE = """Candidate profile:
{candidate_profile}

Job description:
{jd_text}

Recruiter name: {recruiter_name}
Company: {company}
"""
```

```python
def build_prompt(candidate_profile, jd_text, recruiter_name, company):
    return SYSTEM + "\n\n" + USER_TEMPLATE.format(
        candidate_profile=candidate_profile, jd_text=jd_text,
        recruiter_name=recruiter_name, company=company,
    )
```

Ask for **plain text output**, not JSON, for the email body — JSON mode is better reserved for structured extraction tasks (see below), since forcing prose into JSON fields tends to make emails read stiffly.

## Structured Extraction Tasks (use JSON mode here)
For tasks like "classify this reply as Interview / Rejected / Need Info / No Reply," force JSON output — this is where structured mode earns its keep:

```python
CLASSIFY_PROMPT = """Classify this recruiter email reply into exactly one category:
INTERVIEW, REJECTED, NEED_INFO, NO_REPLY, OTHER.
Respond with ONLY valid JSON: {{"category": "...", "confidence": 0.0-1.0}}

Email: {email_text}"""
```
Parse defensively:
```python
import json, re

def classify_reply(email_text: str) -> dict:
    raw = generate_email(CLASSIFY_PROMPT.format(email_text=email_text))
    cleaned = re.sub(r"```json|```", "", raw).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"category": "OTHER", "confidence": 0.0}
```

## Cost/Quota Guardrails
- Cache LLM outputs per `(job_hash)` in the DB — never regenerate an email for a job you've already processed, even on reruns.
- Track daily LLM call count in a simple counter table; hard-stop the graph if you approach the free-tier daily limit, logging a warning instead of erroring out mid-batch.
- Log every prompt + response to disk/DB for the first few weeks — you'll want to eyeball tone drift and tune the prompt, not guess at it.

## What NOT to build yet
- **Resume tailoring per JD** (rewriting your resume live) and **automatic cover letter generation** are listed as "extra features" in your plan — treat them as v2. They multiply LLM calls per job and add real failure surface (a bad auto-rewritten resume is worse than no rewrite). Ship the core send loop first, working reliably for 1–2 weeks, before adding these.
