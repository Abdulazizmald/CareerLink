"""Talk to a local model running in LM Studio, and get JSON back that always parses.

LM Studio exposes an OpenAI-compatible server, so this is a plain HTTP call with
`requests`. No SDK, no API key, nothing leaves the machine.

Why the schema matters more than the model. LM Studio enforces a JSON schema
through grammar-constrained decoding: the sampler is only allowed to emit tokens
that keep the output valid against the schema. So a 3B model at 4-bit produces
valid JSON for the same reason a train stays on rails, not because it is clever.
That means json.loads never fails, and it also means an `enum` in the schema is a
hard constraint rather than a request. The certification list below uses that: the
model picks from real certifications and cannot invent one.

What the schema does NOT fix is the quality of the words inside the fields. A 3B
model is small. So its job here is narrow: order and explain material that has
already been retrieved from the project's own data. It is never asked for a fact.

Same return convention as learn.py: (result, error). A result with no error means
the call worked. None with an error string means it did not, and the page says so
rather than showing an empty box.
"""

import json
import os

import requests

# LM Studio's default. Override without touching code if your server reports a
# different port in its Developer tab:
#     PowerShell:  $env:LM_STUDIO_URL = "http://localhost:1235/v1"
BASE = os.environ.get("LM_STUDIO_URL", "http://localhost:1234/v1").rstrip("/")
TIMEOUT = 120          # a 3B model on shared iGPU memory is not fast
MAX_TOKENS = 900


def models():
    """What LM Studio currently has loaded. Returns (ids, error).

    The model id is read from the server rather than written down here, because
    LM Studio names a build from its filename and that is not predictable.
    """
    try:
        r = requests.get(f"{BASE}/models", timeout=8)
    except requests.RequestException as e:
        return [], (
            f"cannot reach LM Studio at {BASE}: {e}\n"
            "  A refused connection means nothing is listening on that port.\n"
            "  In LM Studio: load your model, then Developer tab, then set Status\n"
            "  to Running. Check the port it reports; if it is not 1234, set\n"
            "  LM_STUDIO_URL to match.")
    if r.status_code != 200:
        return [], f"LM Studio returned HTTP {r.status_code}"
    ids = [m.get("id") for m in r.json().get("data", []) if m.get("id")]
    return ids, None if ids else (
        "LM Studio is running but no model is loaded. Load Ministral in the chat "
        "or Developer tab, then try again.")


def structured(system, user, schema, schema_name="result", model=None):
    """One chat call constrained to a JSON schema. Returns (dict, error)."""
    if model is None:
        ids, err = models()
        if err:
            return None, err
        model = ids[0]

    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        # temperature low because this is a formatting and ordering job, not a
        # creative one, and a small model wanders at higher settings
        "temperature": 0.2,
        "max_tokens": MAX_TOKENS,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": schema_name, "strict": True, "schema": schema},
        },
    }
    try:
        r = requests.post(f"{BASE}/chat/completions", json=payload, timeout=TIMEOUT)
    except requests.RequestException as e:
        return None, f"cannot reach LM Studio: {e}"

    if r.status_code != 200:
        # LM Studio explains itself in the body, and "model does not support
        # response_format" needs a different fix from "no model loaded"
        try:
            detail = r.json().get("error", {})
            detail = detail if isinstance(detail, str) else detail.get("message", "")
        except ValueError:
            detail = r.text[:200]
        return None, f"LM Studio returned HTTP {r.status_code}: {detail}"

    try:
        text = r.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError):
        return None, "LM Studio sent a response in an unexpected shape"

    try:
        return json.loads(text), None
    except json.JSONDecodeError:
        # should be unreachable with grammar-constrained decoding, but a schema
        # the server silently ignored would land here rather than crash a page
        return None, "the model returned text that is not valid JSON"


# --------------------------------------------------------------- study plan
def study_plan_schema(cert_names):
    """The shape a study plan must take.

    cert_names becomes an enum, which is the guardrail. Certifications come from
    certifications.csv, which is hand-checked. The model chooses which of them
    fit and in what order; it cannot produce a name that is not on the list.
    """
    return {
        "type": "object",
        "properties": {
            "summary": {"type": "string",
                        "description": "Two sentences on what this role does."},
            "steps": {
                "type": "array", "minItems": 3, "maxItems": 6,
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "why": {"type": "string",
                                "description": "One sentence on why this step comes here."},
                        "skills": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["title", "why", "skills"],
                    "additionalProperties": False,
                },
            },
            "certifications": {
                "type": "array", "maxItems": 3,
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "enum": cert_names},
                        "when": {"type": "string",
                                 "description": "Which step to take it after."},
                    },
                    "required": ["name", "when"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["summary", "steps", "certifications"],
        "additionalProperties": False,
    }


SYSTEM = (
    "You organise study plans from material that is given to you. You never "
    "introduce a technology, employer, certification or statistic that is not in "
    "the input. If the input does not support something, leave it out. Write "
    "plainly, in short sentences, with no marketing language."
)


def study_plan(role_label, description, skills, certs, model=None):
    """Order a role's own skills and certifications into a learning sequence.

    Everything the model sees comes from this project's data: the role's
    representative posting, the skills its postings actually asked for, and the
    hand-checked certifications for its job family. The model sequences them. It
    is not asked what the skills are or whether the certifications exist.
    """
    cert_names = [c["name"] for c in certs]
    if not cert_names:
        cert_names = ["none"]

    user = (
        f"Role: {role_label}\n\n"
        f"Skills its job adverts ask for, most common first:\n"
        + "\n".join(f"- {s['skill_name']} ({s['share_pct']}% of postings)"
                    for s in skills)
        + "\n\nCertifications available for this job family:\n"
        + "\n".join(f"- {c['name']} ({c['level']}, {c['provider']}): {c['focus']}"
                    for c in certs)
        + f"\n\nAn example job advert for this role:\n{description[:1200]}\n\n"
        "Group the skills above into 3 to 6 ordered learning steps, easiest "
        "foundations first. Every skill you mention must come from the list. "
        "Then pick at most 3 certifications from the list and say which step "
        "each one follows."
    )
    return structured(SYSTEM, user, study_plan_schema(cert_names), "study_plan",
                      model=model)


if __name__ == "__main__":
    ids, err = models()
    print("LM Studio models:", ids or err)
    if err:
        raise SystemExit(1)

    plan, err = study_plan(
        "Data Analyst",
        "We are looking for a data analyst to build dashboards and write SQL "
        "against our warehouse, working with stakeholders across finance.",
        [{"skill_name": "SQL", "share_pct": 71.0},
         {"skill_name": "Excel", "share_pct": 44.0},
         {"skill_name": "Tableau", "share_pct": 31.0},
         {"skill_name": "Python", "share_pct": 28.0}],
        [{"name": "Tableau Desktop Specialist", "level": "entry",
          "provider": "Tableau", "focus": "Core Tableau skills, no expiry"},
         {"name": "CompTIA Data+", "level": "entry", "provider": "CompTIA",
          "focus": "Vendor-neutral analytics fundamentals and reporting"}])
    if err:
        raise SystemExit(f"failed: {err}")
    print(json.dumps(plan, indent=2))

    names = {"Tableau Desktop Specialist", "CompTIA Data+"}
    picked = {c["name"] for c in plan["certifications"]}
    assert picked <= names, f"the model invented a certification: {picked - names}"
    print("\nno invented certifications: the enum held")
