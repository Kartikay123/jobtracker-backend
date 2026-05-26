"""AI client — async. Uses OpenAI gpt-4o-mini when OPENAI_API_KEY is set,
otherwise falls back to the keyword-matching stub so the app works without a key.

If the OpenAI call fails for any reason (invalid key, no credits, network,
JSON parse error), we log the error and fall back to the stub so the user
gets a usable result instead of a 500.
"""
import json
import logging
import re
from collections import Counter

from app.core.config import settings

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy OpenAI client — only created when key is present.
# Wrapped in try/except so a bad import / version mismatch never 500s the app.
# ---------------------------------------------------------------------------
_openai_client = None
_openai_import_failed = False


def _get_openai():
    global _openai_client, _openai_import_failed
    if _openai_import_failed or not settings.OPENAI_API_KEY:
        return None
    if _openai_client is None:
        try:
            from openai import AsyncOpenAI
            _openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        except Exception as e:  # noqa: BLE001
            log.warning("OpenAI client init failed (falling back to stub): %s", e)
            _openai_import_failed = True
            return None
    return _openai_client


# ---------------------------------------------------------------------------
# Stub helpers (used when no API key OR when OpenAI call fails)
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
# Stub implementations (also used as fallbacks if OpenAI fails)
# ---------------------------------------------------------------------------

def _stub_match_resume(resume_text: str, job_description: str) -> dict:
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


def _stub_generate_questions(role: str, count: int) -> list[dict]:
    role = role.strip() or "engineer"
    out: list[dict] = []
    for i in range(count):
        template, category, difficulty = _QUESTION_TEMPLATES[i % len(_QUESTION_TEMPLATES)]
        out.append({
            "text": template.format(role=role),
            "category": category,
            "difficulty": difficulty,
            "position": i,
        })
    return out


def _stub_cover_letter(user_name: str) -> str:
    return (
        f"Dear Hiring Manager,\n\n"
        f"I am writing to express my strong interest in the position described. "
        f"With my background and experience, I am confident I would be a valuable addition to your team.\n\n"
        f"Throughout my career, I have developed skills directly relevant to this role. "
        f"I am eager to bring my expertise and enthusiasm to your organization.\n\n"
        f"Thank you for considering my application. I look forward to discussing how I can contribute.\n\n"
        f"Sincerely,\n{user_name}"
    )


# ---------------------------------------------------------------------------
# Public async API (OpenAI with stub fallback on any failure)
# ---------------------------------------------------------------------------

async def match_resume(resume_text: str, job_description: str) -> dict:
    client = _get_openai()
    if client:
        try:
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
        except Exception as e:  # noqa: BLE001
            log.warning("OpenAI match_resume failed, using stub: %s", e)
    return _stub_match_resume(resume_text, job_description)


async def generate_questions(role: str, job_description: str | None, count: int) -> list[dict]:
    client = _get_openai()
    if client:
        try:
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
            # Normalize position field
            for i, q in enumerate(questions):
                q["position"] = i
                q.setdefault("category", "behavioral")
                q.setdefault("difficulty", "medium")
            if questions:
                return questions[:count]
            log.warning("OpenAI returned no questions, using stub")
        except Exception as e:  # noqa: BLE001
            log.warning("OpenAI generate_questions failed, using stub: %s", e)
    return _stub_generate_questions(role, count)


async def generate_cover_letter(resume_text: str, job_description: str, user_name: str) -> str:
    client = _get_openai()
    if client:
        try:
            rsp = await client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.4,  # lower = more grounded in resume facts
                messages=[
                    {"role": "system", "content": (
                        "You are an expert career writer. Write a highly tailored, evidence-based "
                        "cover letter that proves the candidate is a strong match for THIS specific job.\n\n"
                        "STRICT RULES — follow exactly:\n"
                        "1. Read the JOB DESCRIPTION carefully. Identify the top 3-5 specific "
                        "requirements (skills, tools, responsibilities, years of experience).\n"
                        "2. Read the RESUME carefully. Pull out concrete work experiences, project "
                        "names, technologies, metrics, and achievements that DIRECTLY map to those "
                        "requirements.\n"
                        "3. For every claim you make, reference a specific item from the resume — "
                        "a project name, a company, a measurable result (numbers, %, scale, impact). "
                        "Never invent details that are not in the resume.\n"
                        "4. Match the language to the job description. If the JD says 'RAG pipeline', "
                        "'vector search', 'OAuth2', 'CI/CD' — use those exact phrases when you have "
                        "supporting evidence in the resume.\n"
                        "5. Avoid all generic filler: NO 'I am writing to express my interest', "
                        "NO 'I am a hard worker', NO 'team player', NO 'passionate about'. Replace "
                        "those with specific evidence.\n\n"
                        "STRUCTURE (4 short paragraphs, ~300 words total):\n"
                        "• Paragraph 1 — Hook (2-3 sentences): name the role and the company if "
                        "given, then state the single strongest reason you fit, backed by one "
                        "specific resume highlight.\n"
                        "• Paragraph 2 — Direct skill match: pick 2-3 requirements from the JD "
                        "and pair each with a specific project / experience / metric from the resume.\n"
                        "• Paragraph 3 — Broader value: mention 1-2 additional differentiators "
                        "from the resume (achievement, leadership, unique tech stack) that go "
                        "beyond the must-haves.\n"
                        "• Paragraph 4 — Close (1-2 sentences): brief, confident, action-oriented. "
                        "Avoid 'thank you for considering'.\n\n"
                        "Tone: confident, concrete, professional, never desperate. "
                        "Sign off with the candidate's name. Return ONLY the cover letter text — "
                        "no subject line, no markdown, no preamble."
                    )},
                    {"role": "user", "content": (
                        f"Candidate name: {user_name}\n\n"
                        f"=== RESUME ===\n{resume_text}\n\n"
                        f"=== JOB DESCRIPTION ===\n{job_description}\n\n"
                        f"Now write the cover letter following the rules above. "
                        f"Prioritise concrete evidence from the resume that directly answers "
                        f"the job description's requirements."
                    )},
                ],
            )
            return rsp.choices[0].message.content.strip()
        except Exception as e:  # noqa: BLE001
            log.warning("OpenAI generate_cover_letter failed, using stub: %s", e)
    return _stub_cover_letter(user_name)
