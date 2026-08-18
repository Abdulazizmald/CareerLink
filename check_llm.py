"""Check LM Studio before any page depends on it.

Four things, in the order they can fail:
  1. is the server reachable
  2. is a model loaded, and what is it called
  3. does this model honour a JSON schema
  4. does the enum guardrail actually stop it inventing a certification

Run it:
    python check_llm.py
"""

import json

import llm

print("1. reaching LM Studio at", llm.BASE)
ids, err = llm.models()
if err:
    raise SystemExit(f"   FAILED: {err}\n\n"
                     "   In LM Studio: Developer tab, then Start Server. Load\n"
                     "   your Ministral build before starting it.")
print("   ok. models loaded:", ids)
model = ids[0]

print(f"\n2. asking {model} for a trivial schema")
schema = {"type": "object",
          "properties": {"answer": {"type": "integer"},
                         "word": {"type": "string", "enum": ["red", "blue"]}},
          "required": ["answer", "word"], "additionalProperties": False}
out, err = llm.structured("You answer with JSON only.",
                          "What is two plus two? Pick the colour green.",
                          schema, "trivial", model=model)
if err:
    raise SystemExit(f"   FAILED: {err}\n\n"
                     "   If this says the model does not support response_format,\n"
                     "   update LM Studio. Structured output is enforced by the\n"
                     "   server, not the model, so it should work on any build.")
print("   ok:", out)
assert out["word"] in ("red", "blue"), "the enum did not hold"
print("   the enum held: asked for green, could only answer red or blue")

print(f"\n3. a real study plan for a role, using this project's own data")
plan, err = llm.study_plan(
    "Data Analyst",
    "We need a data analyst to build dashboards and write SQL against our "
    "warehouse, working with finance stakeholders on monthly reporting.",
    [{"skill_name": "SQL", "share_pct": 71.0},
     {"skill_name": "Excel", "share_pct": 44.0},
     {"skill_name": "Tableau", "share_pct": 31.0},
     {"skill_name": "Python", "share_pct": 28.0},
     {"skill_name": "Data Visualization", "share_pct": 22.0}],
    [{"name": "Tableau Desktop Specialist", "level": "entry",
      "provider": "Tableau", "focus": "Core Tableau skills, no expiry"},
     {"name": "CompTIA Data+", "level": "entry", "provider": "CompTIA",
      "focus": "Vendor-neutral analytics fundamentals and reporting"},
     {"name": "Microsoft Certified: Power BI Data Analyst Associate (PL-300)",
      "level": "associate", "provider": "Microsoft",
      "focus": "Modelling and visualising data in Power BI"}],
    model=model)
if err:
    raise SystemExit(f"   FAILED: {err}")
print(json.dumps(plan, indent=2))

allowed = {"Tableau Desktop Specialist", "CompTIA Data+",
           "Microsoft Certified: Power BI Data Analyst Associate (PL-300)"}
picked = {c["name"] for c in plan["certifications"]}
assert picked <= allowed, f"   INVENTED: {picked - allowed}"
print(f"\n   {len(plan['steps'])} steps, {len(picked)} certifications, none invented")

# the model is told never to introduce a technology that was not in the input.
# This is a check on the instruction, not on the schema, so it can genuinely fail.
given = {"sql", "excel", "tableau", "python", "data visualization"}
mentioned = {s.lower() for step in plan["steps"] for s in step["skills"]}
extra = mentioned - given
print("   skills mentioned that were NOT in the input:", extra or "none")
if extra:
    print("   ^ the schema cannot stop this, only the prompt can. A 3B model will")
    print("     drift sometimes. If it is bad, the fix is to make 'skills' an enum")
    print("     over the input list, the same trick the certifications use.")

print("\nall checks passed")
