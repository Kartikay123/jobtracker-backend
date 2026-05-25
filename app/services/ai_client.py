"""AI client — async. Uses OpenAI gpt-4o-mini when OPENAI_API_KEY is set,
otherwise falls back to the keyword-matching stub so the app works without a key.
"""
import json
import re
from collections import Counter

from app.core.config import settings

# ---------------------------------------------------------------------------
# Lazy OpenAI client — only created when key is present
# ---------------------------------------------------------------------------
_openai_client = None

def _get_openai():
    global _openai_client
    if _openai_client is None and settings.OPENAI_API_KEY:
        from openai import AsyncOpenAI
        _openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_client


# ---------------------------------------------------------------------------
# Stub helpers (used when no API key)
# ---------------------------------------------------------------------------
_STOPWORDS = frozenset(
    """a an and or the of to in on with for at as by is are be been we you your
    our their this that these those it its from but if then so not no into via
    will would can could should may might must do does did have has had""".split()
)
_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z+\-#./0-9]{1,}")


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "") if t.lower() not in _STOPWORDS]


_QUESTION_TEMPLATES = [
    ("Walk me through a project where you used {role} skills.", "behavioral", "easy"),
    ("What would your first 90 days as a {role} look like?", "behavioral", "easy"),
    ("How do you prioritize tasks when everything feels urgent?", "behavioral", "easy"),
    ("Where do you see your career as a {role} going in the next 3 years?", "behavioral", "easy"),
    ("What drew you to the {role} field and what keeps you motivated?", "behavioral", "easy"),
    ("How would you debug a production incident as a {role}?", "behavioral", "medium"),
    ("Describe a tradeoff you made between speed and quality.", "behavioral", "medium"),
    ("Tell me about a time you disagreed with a teammate and how you resolved it.", "behavioral", "medium"),
    ("Describe a situation where you had to pick up an unfamiliar technology quickly.", "behavioral", "medium"),
    ("How do you handle feedback or criticism on your work?", "behavioral", "medium"),
    ("Tell me about a time you failed and what you learned from it.", "behavioral", "medium"),
    ("What's the most interesting bug you've fixed and how did you track it down?", "technical", "medium"),
    ("Explain a technical concept central to {role} work to a non-technical stakeholder.", "technical", "medium"),
    ("How do you ensure code quality and maintainability in your projects?", "technical", "medium"),
    ("Walk me through how you would approach performance optimization as a {role}.", "technical", "hard"),
    ("Design a small but realistic system relevant to a {role}'s typical work.", "system-design", "hard"),
    ("How would you scale a service that suddenly gets 10× its normal traffic?", "system-design", "hard"),
    ("What trade-offs would you consider when choosing between a monolith and microservices?", "system-design", "hard"),
    ("If you joined a team with significant technical debt, how would you approach it?", "behavioral", "medium"),
    ("How do you stay current with new developments in the {role} space?", "behavioral", "easy"),
]


# ---------------------------------------------------------------------------
# Public async API
# ---------------------------------------------------------------------------

async def match_resume(resume_text: str, job_description: str) -> dict:
    client = _get_openai()
    if client:
        rsp = await client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": (
                    "You are an expert resume reviewer. Given a resume and a job description, "
                    "return a JSON object with exactly these keys: "
                    "score (int 0-100), strengths (list of up to 5 strings), gaps (list of up to 5 strings). "
                    "Be specific and actionable."
                )},
                {"role": "user", "content": f"RESUME:\n{resume_text}\n\nJOB DESCRIPTION:\n{job_description}"},
            ],
        )
        return json.loads(rsp.choices[0].message.content)

    # --- stub fallback ---
    resume_tokens = set(_tokens(resume_text))
    jd_counts = Counter(_tokens(job_description))
    if not jd_counts:
        return {"score": 50, "strengths": [], "gaps": []}
    jd_keywords = [w for w, _ in jd_counts.most_common(40) if len(w) > 2][:12]
    if not jd_keywords:
        return {"score": 50, "strengths": [], "gaps": []}
    matched = [k for k in jd_keywords if k in resume_tokens]
    missing = [k for k in jd_keywords if k not in resume_tokens]
    raw = round((len(matched) / len(jd_keywords)) * 100)
    return {
        "score": max(5, min(98, raw)),
        "strengths": [m.title() for m in matched[:5]],
        "gaps": [m.title() for m in missing[:5]],
    }


async def generate_questions(role: str, job_description: str | None, count: int) -> list[dict]:
    client = _get_openai()
    if client:
        rsp = await client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": (
                    "You are an expert interviewer. Generate interview questions as a JSON object "
                    "with key 'questions', each item having: text (string), category "
                    "(one of: behavioral, technical, system-design), difficulty (one of: easy, medium, hard), "
                    "position (0-indexed int)."
                )},
                {"role": "user", "content": (
                    f"Generate exactly {count} interview questions for the role: {role}.\n"
                    + (f"Job description context:\n{job_description}" if job_description else "")
                )},
            ],
        )
        data = json.loads(rsp.choices[0].message.content)
        questions = data.get("questions", [])
        for i, q in enumerate(questions):
            q["position"] = i
        return questions[:count]

    # --- stub fallback ---
    role = role.strip() or "engineer"
    out: list[dict] = []
    for i in range(count):
        template, category, difficulty = _QUESTION_TEMPLATES[i % len(_QUESTION_TEMPLATES)]
        out.append({"text": template.format(role=role), "category": category, "difficulty": difficulty, "position": i})
    return out


async def generate_cover_letter(resume_text: str, job_description: str, user_name: str) -> str:
    client = _get_openai()
    if client:
        rsp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "You are an expert career coach and professional writer. "
                    "Write a compelling, personalized cover letter that is concise (3-4 paragraphs), "
                    "professional, and highlights the candidate's most relevant experience. "
                    "Do not use generic filler phrases. Return only the cover letter text, no subject line."
                )},
                {"role": "user", "content": (
                    f"Candidate name: {user_name}\n\n"
                    f"RESUME:\n{resume_text}\n\n"
                    f"JOB DESCRIPTION:\n{job_description}"
                )},
            ],
        )
        return rsp.choices[0].message.content.strip()

    # --- stub fallback ---
    return (
        f"Dear Hiring Manager,\n\n"
        f"I am writing to express my strong interest in the position described. "
        f"With my background and experience, I am confident I would be a valuable addition to your team.\n\n"
        f"Throughout my career, I have developed skills directly relevant to this role. "
        f"I am eager to bring my expertise and enthusiasm to your organization.\n\n"
        f"Thank you for considering my application. I look forward to discussing how I can contribute.\n\n"
        f"Sincerely,\n{user_name}"
    )
