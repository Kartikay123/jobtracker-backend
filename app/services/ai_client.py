"""AI client.

CURRENT STATE: STUB. Returns plausible-but-fake results so we can develop the
plumbing (rate limiting, persistence, response shape) without paying an API
provider yet.

# ---------------------------------------------------------------------------
# How to plug in a real provider (e.g. OpenAI):
#
# 1. requirements.txt:   + openai==1.54.0
# 2. .env / Render env:  OPENAI_API_KEY=sk-...
# 3. app/core/config.py: add `OPENAI_API_KEY: str | None = None`
# 4. Replace the body of `match_resume` with something like:
#
#    from openai import AsyncOpenAI
#    _client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
#
#    async def match_resume(resume_text, job_description) -> dict:
#        rsp = await _client.chat.completions.create(
#            model="gpt-4o-mini",
#            response_format={"type": "json_object"},
#            messages=[
#                {"role": "system", "content": "You are a resume reviewer. "
#                 "Return JSON {score:int 0-100, strengths:[str], gaps:[str]}."},
#                {"role": "user", "content":
#                    f"RESUME:\n{resume_text}\n\nJOB:\n{job_description}"},
#            ],
#        )
#        return json.loads(rsp.choices[0].message.content)
#
# 5. The function signature and return shape stay the same — every call site
#    (rate limiter, DB persistence, schema serialization) keeps working.
# 6. Make these `async` calls — when latency goes from ~0ms to 5-30s, also
#    move them to the arq worker (Step 9 pattern) so the request thread
#    isn't tied up. Add a `GET /api/tasks/:id` endpoint that polls
#    arq's job result.
# ---------------------------------------------------------------------------
"""

import re
from collections import Counter

# Tokens we never want to count as "skills".
_STOPWORDS = frozenset(
    """a an and or the of to in on with for at as by is are be been we you your
    our their this that these those it its from but if then so not no into via
    will would can could should may might must do does did have has had""".split()
)

_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z+\-#./0-9]{1,}")


def _tokens(text: str) -> list[str]:
    return [
        t.lower() for t in _TOKEN_RE.findall(text or "") if t.lower() not in _STOPWORDS
    ]


# ---------- Resume match ----------
def match_resume(resume_text: str, job_description: str) -> dict:
    """Return a fake-but-plausible match score + strengths + gaps.

    Algorithm: tokenize both, take the JD's most-common tokens (proxy for
    'skills the job wants'), see how many appear in the resume.

    Score = (matched / requested) * 100, clamped 5..98 so we never claim
    perfection or zero — leaves room for "this is a stub" feel.
    """
    resume_tokens = set(_tokens(resume_text))
    jd_counts = Counter(_tokens(job_description))
    if not jd_counts:
        return {"score": 50, "strengths": [], "gaps": []}

    # Top 12 JD-frequent terms with len > 2 — proxy for "wanted skills".
    jd_keywords = [w for w, _ in jd_counts.most_common(40) if len(w) > 2][:12]
    if not jd_keywords:
        return {"score": 50, "strengths": [], "gaps": []}

    matched = [k for k in jd_keywords if k in resume_tokens]
    missing = [k for k in jd_keywords if k not in resume_tokens]

    raw = round((len(matched) / len(jd_keywords)) * 100)
    score = max(5, min(98, raw))

    return {
        "score": score,
        "strengths": [m.title() for m in matched[:5]],
        "gaps": [m.title() for m in missing[:5]],
    }


# ---------- Interview question generation ----------
_QUESTION_TEMPLATES = [
    # Behavioral — easy
    ("Walk me through a project where you used {role} skills.", "behavioral", "easy"),
    ("What would your first 90 days as a {role} look like?", "behavioral", "easy"),
    ("How do you prioritize tasks when everything feels urgent?", "behavioral", "easy"),
    ("Where do you see your career as a {role} going in the next 3 years?", "behavioral", "easy"),
    ("What drew you to the {role} field and what keeps you motivated?", "behavioral", "easy"),
    # Behavioral — medium
    ("How would you debug a production incident as a {role}?", "behavioral", "medium"),
    ("Describe a tradeoff you made between speed and quality.", "behavioral", "medium"),
    ("Tell me about a time you disagreed with a teammate and how you resolved it.", "behavioral", "medium"),
    ("Describe a situation where you had to pick up an unfamiliar technology quickly.", "behavioral", "medium"),
    ("How do you handle feedback or criticism on your work?", "behavioral", "medium"),
    ("Tell me about a time you failed and what you learned from it.", "behavioral", "medium"),
    # Technical — medium / hard
    ("What's the most interesting bug you've fixed and how did you track it down?", "technical", "medium"),
    ("Explain a technical concept central to {role} work to a non-technical stakeholder.", "technical", "medium"),
    ("How do you ensure code quality and maintainability in your projects?", "technical", "medium"),
    ("Walk me through how you would approach performance optimization as a {role}.", "technical", "hard"),
    # System design — hard
    ("Design a small but realistic system relevant to a {role}'s typical work.", "system-design", "hard"),
    ("How would you scale a service that suddenly gets 10× its normal traffic?", "system-design", "hard"),
    ("What trade-offs would you consider when choosing between a monolith and microservices?", "system-design", "hard"),
    # Situational
    ("If you joined a team with significant technical debt, how would you approach it?", "behavioral", "medium"),
    ("How do you stay current with new developments in the {role} space?", "behavioral", "easy"),
]


def generate_questions(role: str, job_description: str | None, count: int) -> list[dict]:
    """Return `count` plausible interview questions for the given role."""
    role = role.strip() or "engineer"
    out: list[dict] = []
    for i in range(count):
        template, category, difficulty = _QUESTION_TEMPLATES[i % len(_QUESTION_TEMPLATES)]
        out.append(
            {
                "text": template.format(role=role),
                "category": category,
                "difficulty": difficulty,
                "position": i,
            }
        )
    return out
