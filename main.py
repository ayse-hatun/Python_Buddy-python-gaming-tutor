"""
Python Buddy - learn Python by playing.
FastAPI backend. Runs on localhost only.

Run:  python main.py      (or: uvicorn main:app --reload)
Open: http://127.0.0.1:8000
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import requests
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

BASE = Path(__file__).resolve().parent

try:  # optional: read keys from a .env file
    from dotenv import load_dotenv
    load_dotenv(BASE / ".env")
except ImportError:
    pass

from google import genai
from google.genai import types

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-lite")

# One or more keys; if one fails (quota etc.) the next is tried.
KEYS = [
    v.strip() for v in (
        os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
        os.getenv("OPENROUTER_API_KEY"),
        os.getenv("GEMINI_API_KEY_2") or os.getenv("GEMINI_API_KEY2"),
        os.getenv("GEMINI_API_KEY_3") or os.getenv("GEMINI_API_KEY3"),
    ) if v and v.strip()
]

app = FastAPI(title="Python Buddy")

# --------------------------------------------------------------------------
#  QUESTS  (answers stay on the server)
# --------------------------------------------------------------------------
QUESTS = [
    {
        "id": "hello", "title": "Hello, World", "emoji": "👋",
        "intro": "Print text and store values.",
        "questions": [
            {"q": "Which line prints Hello on screen?",
             "options": ['print("Hello")', 'echo "Hello"', 'say("Hello")', 'Hello.print()'],
             "answer": 0, "why": "print() shows text. Text goes inside quotes."},
            {"q": "What does this print?", "code": "x = 5\ny = x + 2\nprint(y)",
             "options": ["5", "7", "x + 2", "Error"],
             "answer": 1, "why": "y becomes 5 + 2, which is 7."},
            {"q": "Which is a valid variable name?",
             "options": ["2score", "my-score", "my_score", "class"],
             "answer": 2, "why": "No leading digits, no dashes, and no keywords like class."},
        ],
        "duel": {"prompt": "Print exactly: Hello, Python!",
                 "starter": "# write your code below\n",
                 "expected": "Hello, Python!",
                 "hint": 'Use print("...") with quotes.'},
    },
    {
        "id": "math", "title": "Number Cave", "emoji": "🔢",
        "intro": "Math operators in Python.",
        "questions": [
            {"q": "What is 7 // 2 ?", "options": ["3.5", "3", "4", "2"],
             "answer": 1, "why": "// is floor division. It drops the decimal part."},
            {"q": "What is 2 ** 3 ?", "options": ["6", "5", "8", "9"],
             "answer": 2, "why": "** is power: 2 x 2 x 2 = 8."},
            {"q": "What is 10 % 3 ?", "options": ["1", "3", "0", "3.33"],
             "answer": 0, "why": "% gives the remainder. 10 / 3 leaves 1."},
        ],
        "duel": {"prompt": "Store 6 in a and 7 in b. Print a * b.",
                 "starter": "a = \nb = \n",
                 "expected": "42",
                 "hint": "a = 6, b = 7, then print(a * b)."},
    },
    {
        "id": "strings", "title": "String Forest", "emoji": "🌲",
        "intro": "Work with text.",
        "questions": [
            {"q": "What does this print?", "code": 'print("py" * 3)',
             "options": ["py3", "pypypy", "py py py", "Error"],
             "answer": 1, "why": "* repeats a string."},
            {"q": 'What does len("game") return?', "options": ["3", "4", "5", "game"],
             "answer": 1, "why": "len counts characters: g-a-m-e = 4."},
            {"q": 'What is "Python"[0] ?', "options": ["P", "y", "Python", "0"],
             "answer": 0, "why": "Counting starts at 0, so index 0 is the first letter."},
        ],
        "duel": {"prompt": "name is given. Print: Hello, Neo!  (use the variable)",
                 "starter": 'name = "Neo"\n',
                 "expected": "Hello, Neo!",
                 "hint": 'Try print("Hello, " + name + "!") or an f-string.'},
    },
    {
        "id": "if", "title": "Decision Gate", "emoji": "🚪",
        "intro": "Make your code choose.",
        "questions": [
            {"q": "What does this print?",
             "code": 'if 5 > 3:\n    print("A")\nelse:\n    print("B")',
             "options": ["A", "B", "A and B", "Nothing"],
             "answer": 0, "why": "5 > 3 is True, so the if-block runs."},
            {"q": "Which keyword adds a second condition?",
             "options": ["elseif", "elif", "else if", "also"],
             "answer": 1, "why": "Python uses elif."},
            {"q": "What is 3 == 3.0 ?", "options": ["True", "False", "Error", "None"],
             "answer": 0, "why": "== compares values. 3 and 3.0 are equal."},
        ],
        "duel": {"prompt": "score is 75. Print Pass if score is 50 or more, otherwise print Fail.",
                 "starter": "score = 75\n",
                 "expected": "Pass",
                 "hint": 'if score >= 50: print("Pass")  else: print("Fail")'},
    },
    {
        "id": "loops", "title": "Loop Tower", "emoji": "🗼",
        "intro": "Repeat things without copy-paste.",
        "questions": [
            {"q": "What does this print?", "code": "for i in range(3):\n    print(i)",
             "options": ["1 2 3", "0 1 2", "0 1 2 3", "3 3 3"],
             "answer": 1, "why": "range(3) gives 0, 1, 2."},
            {"q": "What is list(range(1, 4)) ?",
             "options": ["[1, 2, 3, 4]", "[1, 2, 3]", "[0, 1, 2, 3]", "[2, 3, 4]"],
             "answer": 1, "why": "The start is included, the stop is not."},
            {"q": "Which keyword stops a loop early?",
             "options": ["stop", "exit", "break", "end"],
             "answer": 2, "why": "break jumps out of the loop."},
        ],
        "duel": {"prompt": "Print the numbers 1 to 5, one per line.",
                 "starter": "for i in range():\n    print(i)\n",
                 "expected": "1\n2\n3\n4\n5",
                 "hint": "range(1, 6) starts at 1 and stops before 6."},
    },
    {
        "id": "lists", "title": "List Dungeon", "emoji": "📜",
        "intro": "Store many items in one place.",
        "questions": [
            {"q": "What does this print?",
             "code": 'fruits = ["a", "b", "c"]\nprint(fruits[-1])',
             "options": ["a", "b", "c", "Error"],
             "answer": 2, "why": "-1 means the last item."},
            {"q": "Which method adds an item to the end of a list?",
             "options": ["add()", "append()", "push()", "insert_end()"],
             "answer": 1, "why": "append() adds to the end."},
            {"q": "What does this print?", "code": "print([1, 2, 3][1:])",
             "options": ["[1]", "[2, 3]", "[1, 2]", "[3]"],
             "answer": 1, "why": "[1:] starts at index 1 and goes to the end."},
        ],
        "duel": {"prompt": "Print the list nums sorted from small to large.",
                 "starter": "nums = [3, 1, 2]\n",
                 "expected": "[1, 2, 3]",
                 "hint": "print(sorted(nums))"},
    },
    {
        "id": "functions", "title": "Function Forge", "emoji": "🔨",
        "intro": "Build your own tools.",
        "questions": [
            {"q": "Which keyword defines a function?",
             "options": ["func", "define", "def", "function"],
             "answer": 2, "why": "Python uses def."},
            {"q": "What does this print?",
             "code": "def f(x):\n    return x * 2\n\nprint(f(2))",
             "options": ["2", "4", "None", "Error"],
             "answer": 1, "why": "f(2) returns 2 * 2 = 4."},
            {"q": "What does a function with no return give back?",
             "options": ["0", '""', "None", "Error"],
             "answer": 2, "why": "No return means Python returns None."},
        ],
        "duel": {"prompt": "Finish double(n) so it returns n * 2. Then the last line prints double(21).",
                 "starter": "def double(n):\n    pass\n\nprint(double(21))\n",
                 "expected": "42",
                 "hint": "Replace pass with return n * 2."},
    },
    {
        "id": "boss", "title": "Boss: Bug Dragon", "emoji": "🐉", "boss": True,
        "intro": "Mix everything you learned.",
        "questions": [
            {"q": "What does this print?",
             "code": "total = 0\nfor n in [1, 2, 3]:\n    total += n\nprint(total)",
             "options": ["3", "6", "123", "0"],
             "answer": 1, "why": "The loop adds 1 + 2 + 3 = 6."},
            {"q": "What does this print?",
             "code": 'def greet(name):\n    return "Hi " + name\n\nprint(greet("Ada"))',
             "options": ["Hi name", "Hi Ada", "greet", "None"],
             "answer": 1, "why": 'name is "Ada", so it returns "Hi Ada".'},
            {"q": "What does this print?",
             "code": 'x = 10\nif x > 5 and x < 8:\n    print("A")\nelse:\n    print("B")',
             "options": ["A", "B", "Both", "Error"],
             "answer": 1, "why": "x < 8 is False. 'and' needs both True, so else runs."},
            {"q": "What does this print?",
             "code": "nums = [1, 2, 3]\nnums.append(4)\nprint(len(nums))",
             "options": ["3", "4", "5", "Error"],
             "answer": 1, "why": "append makes the list 4 items long."},
        ],
        "duel": {"prompt": "Print 1 to 6, one per line, but print Fizz instead of multiples of 3.",
                 "starter": "for i in range(1, 7):\n    \n",
                 "expected": "1\n2\nFizz\n4\n5\nFizz",
                 "hint": 'if i % 3 == 0: print("Fizz")  else: print(i)'},
    },
]
QUEST_BY_ID = {q["id"]: q for q in QUESTS}


# --------------------------------------------------------------------------
#  Code runner  (local use only: not a hardened sandbox)
# --------------------------------------------------------------------------
def run_python(code: str) -> tuple[bool, str]:
    if not code.strip():
        return False, "Write some Python first."
    path = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            path = f.name
        r = subprocess.run(
            [sys.executable, "-I", "-X", "utf8", path],
            capture_output=True, text=True, encoding="utf-8",
            timeout=3, cwd=tempfile.gettempdir(), stdin=subprocess.DEVNULL,
        )
        if r.returncode == 0:
            return True, (r.stdout.strip() or "(ran fine, nothing printed)")[:2000]
        return False, "Python error:\n" + r.stderr.strip()[-1200:]
    except subprocess.TimeoutExpired:
        return False, "Timed out after 3 seconds. Check for an infinite loop."
    except Exception as e:  # noqa
        return False, f"Runner error: {e}"
    finally:
        if path and os.path.exists(path):
            os.remove(path)


def _norm(s: str) -> str:
    return "\n".join(line.rstrip() for line in s.strip().splitlines())


def _is_hardcoded(code: str, expected: str) -> bool:
    """Return True if the code is likely just printing the expected answer verbatim."""
    import re
    stripped = code.strip()
    # Only flag single-statement code that literally contains the expected output
    lines = [l.strip() for l in stripped.splitlines() if l.strip() and not l.strip().startswith('#')]
    if len(lines) > 1:
        return False
    # Check if the single line is a bare print with the literal expected value
    expected_clean = expected.strip().replace('\n', ' ')
    pattern = re.compile(
        r'^print\s*\(\s*[\'"]' + re.escape(expected_clean) + r'[\'"]\s*\)$'
    )
    return bool(pattern.match(lines[0])) if lines else False


CODE_REVIEW_PROMPT = """
You are a strict Python tutor grading a beginner's coding exercise.

Task description: {prompt}
Expected output: {expected}
Starter code given to the student:
```python
{starter}
```
Student's submitted code:
```python
{code}
```

Your job: check whether the student's code uses CORRECT LOGIC to solve the task.
Do NOT just check if the output matches — verify the actual code logic line by line.

Check ALL of these:
1. Does the code actually implement what the task asks? (e.g. if asked to use a loop, did they use a loop?)
2. Does the code use variables, operators, control flow, or functions as the task requires?
3. Is the code NOT just a hardcoded print statement that dumps the expected output literally?
4. Does the code follow the intent of any starter code provided? (e.g. if a function skeleton is given, did they complete it properly?)
5. Would the code still work correctly if the input values were changed? (conceptual check)

Reply with EXACTLY one of these (no extra text):
- LOGIC_OK — if the code genuinely solves the task with proper logic
- HARDCODED — if the code just prints the expected output literally without real logic
- BAD_LOGIC — if the output might match but the logic is wrong, hacky, or doesn't follow the task requirements

Reply ONLY with one of those three words. No explanation.
"""


# --------------------------------------------------------------------------
#  Chat prompt  (short answers, game voice, accepts beginner to advanced coding)
# --------------------------------------------------------------------------
SYSTEM_PROMPT = """
You are Python Buddy, a friendly game coach who teaches coding, centered around Python.

SCOPE & TOPICS
- Accept and answer coding questions across ALL skill levels—from beginner fundamentals up to advanced programming, design patterns, asyncio, performance, memory management, algorithms, data structures, and architecture.
- Your primary focus is Python, but you CAN and SHOULD answer questions about connected coding topics (such as databases/SQL, APIs, web backends, data structures, Git, system design, or computer science concepts connected with Python/coding). Connect them back to Python where appropriate.
- If asked about topics completely unrelated to coding/tech (like movies, sports, food), politely redirect: "I'm your coding coach, so let's stick to Python and programming. What do you want to level up on?"

STYLE (very important)
- Keep replies punchy, clear, and engaging: usually under 80 words, not counting code.
- Match the user's technical level: if they ask an advanced question, provide an advanced, technically accurate explanation instead of oversimplifying.
- At most ONE clean code example, max 8 lines, in a ```python block when helpful.
- No bulky headings or long lists. At most one emoji.
- End with ONE tiny question or mini-mission so the player acts next.
- Light game voice ("mission", "nice hit", "level up"). Do not overdo it.

MODES (follow only the current one)
- Learn: explain the requested topic matching the user's depth (beginner to advanced), then ask one check question.
- Practice: give ONE small mission (write 1-4 lines). Wait for their attempt. Hint if stuck. Review their code briefly.
- Quiz: ask ONE question at a time as A/B/C choices or a short answer. Wait. Then give a one-line why and ask the next one.
- Debug: name the cause in 1-2 sentences, show only the fixed line, explain in one short sentence.
- If the player just switched modes, an opening question was already shown. Do not repeat it.

PERSONALIZATION & ADAPTIVE COACHING
- Check the player context for: target difficulty level (Beginner/Intermediate/Advanced), whether they are learning from scratch for the first time, focus topic, and any specific confusion they have.
- If the player is learning from scratch for the first time: assume zero prior CS background, use clear everyday metaphors, avoid unexplained jargon, and take gentle, bite-sized steps.
- If the player is intermediate or advanced: skip over basic definitions, talk directly about implementation patterns, Pythonic idioms, and edge cases.
- If the player stated a specific confusion (e.g. "how loops terminate", "difference between list and tuple"): directly address, clarify, and dispel that confusion in your response and check questions!

REACTION TAGS
- Only when the latest message answers a question YOU asked (quiz or practice) and you have checked it,
  start the reply with exactly [CORRECT] or [WRONG]. Never use the tags otherwise.
- The app shows its own celebration, so keep praise to a few words.

HONESTY
- Never claim code was run. Never call an answer correct without checking it.
- If unsure about a Python detail, say so.
"""

MODE_HINTS = {
    "Learn": "Learn mode. Teach the topic they gave. Short.",
    "Practice": "Practice mode. One small mission at a time.",
    "Quiz": "Quiz mode. One question at a time. Wait for the answer.",
    "Debug": "Debug mode. Find the bug, show the minimal fix.",
}


def build_contents(history: list[dict], final_text: str):
    items: list[list[str]] = []
    for h in history[-12:]:
        role = "user" if h.get("role") == "user" else "model"
        text = str(h.get("content", "")).strip()
        if not text:
            continue
        if items and items[-1][0] == role:
            items[-1][1] += "\n" + text
        else:
            items.append([role, text])
    while items and items[0][0] == "model":
        items.pop(0)
    if items and items[-1][0] == "user":
        items[-1][1] += "\n" + final_text
    else:
        items.append(["user", final_text])
    return [types.Content(role=r, parts=[types.Part(text=t)]) for r, t in items]


def generate_openrouter(key: str, history: list[dict], final_text: str) -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for h in history[-12:]:
        role = "user" if h.get("role") == "user" else "assistant"
        text = str(h.get("content", "")).strip()
        if text:
            messages.append({"role": role, "content": text})
    messages.append({"role": "user", "content": final_text})

    models_to_try = [
        os.getenv("OPENROUTER_MODEL"),
        "google/gemini-2.0-flash-lite",
        "google/gemini-2.5-flash",
    ]
    models_to_try = [m for m in models_to_try if m]

    last_err = None
    for model in models_to_try:
        try:
            r = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "HTTP-Referer": "http://127.0.0.1:8000",
                    "X-Title": "Python Buddy",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": 0.6,
                    "max_tokens": 400,
                },
                timeout=15,
            )
            if r.status_code == 200:
                data = r.json()
                choices = data.get("choices", [])
                if choices and "message" in choices[0]:
                    return choices[0]["message"]["content"]
            last_err = f"OpenRouter HTTP {r.status_code}: {r.text[:200]}"
        except Exception as e:
            last_err = str(e)
    raise RuntimeError(last_err or "OpenRouter request failed")


def generate_gemini(client, contents) -> str:
    try:
        r = client.models.generate_content(
            model=MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.6,
                max_output_tokens=400,
            ),
        )
        if r.text:
            return r.text
    except Exception as e:
        if "thinking" in str(e).lower():
            r = client.models.generate_content(
                model=MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.6,
                    max_output_tokens=400,
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                ),
            )
            if r.text:
                return r.text
        raise e
    return ""


# --------------------------------------------------------------------------
#  API
# --------------------------------------------------------------------------
class ChatIn(BaseModel):
    message: str
    history: list[dict] = []
    mode: str = "Learn"
    player: dict = {}


class CheckIn(BaseModel):
    quest_id: str
    index: int
    choice: int


class CodeIn(BaseModel):
    quest_id: str = ""
    code: str


@app.get("/")
def home():
    return FileResponse(BASE / "index.html")


@app.get("/api/quests")
def quests():
    out = []
    for q in QUESTS:
        out.append({
            "id": q["id"], "title": q["title"], "emoji": q["emoji"],
            "intro": q["intro"], "boss": q.get("boss", False),
            "questions": [
                {"q": m["q"], "code": m.get("code", ""), "options": m["options"]}
                for m in q["questions"]
            ],
            "duel": q["duel"],
        })
    return out


@app.post("/api/check")
def check(body: CheckIn):
    quest = QUEST_BY_ID.get(body.quest_id)
    if not quest or not (0 <= body.index < len(quest["questions"])):
        raise HTTPException(404, "Unknown question")
    m = quest["questions"][body.index]
    return {"correct": body.choice == m["answer"], "answer": m["answer"], "why": m["why"]}


@app.post("/api/run")
def run(body: CodeIn):
    ok, out = run_python(body.code)
    return {"ok": ok, "output": out}


@app.post("/api/check_code")
def check_code(body: CodeIn):
    quest = QUEST_BY_ID.get(body.quest_id)
    if not quest:
        raise HTTPException(404, "Unknown quest")
    ok, out = run_python(body.code)
    if not ok:
        return {"ok": False, "output": out, "feedback": ""}

    output_matches = _norm(out) == _norm(quest["duel"]["expected"])
    if not output_matches:
        return {"ok": False, "output": out, "feedback": "Output doesn't match. Check your code and try again."}

    # Fast-path hardcode rejection (no AI call needed)
    if _is_hardcoded(body.code, quest["duel"]["expected"]):
        return {
            "ok": False,
            "output": out,
            "feedback": "🚫 Hardcoded answer detected! Write real code that calculates the result.",
        }

    # AI logic review — MANDATORY. Output matching alone is not enough.
    if not KEYS:
        raise HTTPException(503, "Logic review requires an API key. Set GEMINI_API_KEY.")

    prompt_text = CODE_REVIEW_PROMPT.format(
        prompt=quest["duel"]["prompt"],
        expected=quest["duel"]["expected"],
        starter=quest["duel"]["starter"],
        code=body.code,
    )

    verdict = None
    last_err = None
    for key in KEYS:
        try:
            if key.startswith("sk-or-") or key.startswith("sk-"):
                verdict = generate_openrouter(key, [], prompt_text)
            else:
                contents = build_contents([], prompt_text)
                client = genai.Client(api_key=key)
                verdict = generate_gemini(client, contents)
            if verdict:
                break
        except Exception as e:
            last_err = e
            continue

    if not verdict:
        raise HTTPException(502, f"Logic review failed: {str(last_err)[:200]}")

    verdict = verdict.strip().upper()

    if verdict.startswith("HARDCODED"):
        return {
            "ok": False,
            "output": out,
            "feedback": "🚫 Your output is right, but you just hardcoded the answer. Use real code logic!",
        }
    if verdict.startswith("BAD_LOGIC"):
        return {
            "ok": False,
            "output": out,
            "feedback": "⚠️ Output matches, but your logic doesn't follow the task. Re-read the prompt and try a different approach.",
        }
    # LOGIC_OK
    return {"ok": True, "output": out, "feedback": ""}


# --------------------------------------------------------------------------
#  Flash Challenge generation (AI-generated MCQ based on chat topics)
# --------------------------------------------------------------------------
FLASH_CHALLENGE_PROMPT = """
You are a Python quiz generator. Based on the recent chat conversation below,
generate ONE multiple-choice question that tests the Python topic(s) discussed.

The question should:
- Be directly related to what was discussed in the chat
- Test understanding of the Python concept (not trivia)
- Have exactly 4 options labeled A, B, C, D
- Have exactly one correct answer
- Include a short code snippet if relevant
- Include a brief explanation of why the correct answer is right

Recent chat:
{chat_summary}

Reply in EXACTLY this JSON format (no extra text, no markdown fences):
{{"topic": "short topic name", "emoji": "relevant emoji", "question": "the question text", "code": "optional python code or empty string", "options": ["option A", "option B", "option C", "option D"], "answer": 0, "why": "short explanation"}}

Rules:
- "answer" is the 0-based index of the correct option
- "code" should be a short Python snippet if the question involves reading code, otherwise empty string
- Keep question and options concise
- Reply with ONLY the JSON object, nothing else
"""


class FlashIn(BaseModel):
    history: list[dict] = []


@app.post("/api/flash_challenge")
def flash_challenge(body: FlashIn):
    if not KEYS:
        raise HTTPException(503, "No API key. Set GEMINI_API_KEY.")
    if not body.history:
        raise HTTPException(400, "No chat history provided.")

    # Build a summary of recent chat for the AI
    recent = body.history[-20:]  # last 20 messages for context
    chat_summary = "\n".join(
        f"{'User' if h.get('role') == 'user' else 'Buddy'}: {str(h.get('content', ''))[:300]}"
        for h in recent
    )
    prompt_text = FLASH_CHALLENGE_PROMPT.format(chat_summary=chat_summary)

    import json as _json
    last_err = None
    for key in KEYS:
        try:
            if key.startswith("sk-or-") or key.startswith("sk-"):
                raw = generate_openrouter(key, [], prompt_text)
            else:
                contents = build_contents([], prompt_text)
                client = genai.Client(api_key=key)
                raw = generate_gemini(client, contents)
            if raw:
                # Strip markdown fences if present
                raw = raw.strip()
                if raw.startswith("```"):
                    raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
                if raw.endswith("```"):
                    raw = raw[:-3]
                raw = raw.strip()
                data = _json.loads(raw)
                # Validate structure
                assert "question" in data and "options" in data and "answer" in data
                assert isinstance(data["options"], list) and len(data["options"]) == 4
                assert isinstance(data["answer"], int) and 0 <= data["answer"] <= 3
                return data
        except Exception as e:
            last_err = e
            continue

    raise HTTPException(502, f"Flash challenge generation failed: {str(last_err)[:200]}")


@app.post("/api/chat")
def chat(body: ChatIn):
    if not KEYS:
        raise HTTPException(503, "No API key found. Set GEMINI_API_KEY (see README).")

    mode = body.mode if body.mode in MODE_HINTS else "Learn"
    p = body.player or {}
    ctx_parts = [
        MODE_HINTS[mode],
        f"Player level {p.get('level', 1)} ({p.get('title', 'Newbie')})",
        f"Current quest: {p.get('quest') or 'none'}",
    ]
    if p.get("difficulty"):
        ctx_parts.append(f"Target difficulty: {p.get('difficulty')}")
    if p.get("scratch"):
        ctx_parts.append(f"Learning from scratch: {p.get('scratch')}")
    if p.get("topic"):
        ctx_parts.append(f"Focus topic: {p.get('topic')}")
    if p.get("confusion"):
        ctx_parts.append(f"User confusion: {p.get('confusion')}")

    final = (
        f"[Game context: {'; '.join(ctx_parts)}]\n\n"
        f"Player says:\n{body.message[:2000]}"
    )

    last = None
    for key in KEYS:
        try:
            if key.startswith("sk-or-") or key.startswith("sk-"):
                text = generate_openrouter(key, body.history, final)
            else:
                contents = build_contents(body.history, final)
                client = genai.Client(api_key=key)
                text = generate_gemini(client, contents)

            if text:
                text = text.strip()
                verdict = None
                for tag in ("CORRECT", "WRONG"):
                    if f"[{tag}]" in text:
                        verdict = tag
                        text = text.replace(f"[{tag}]", "").strip()
                return {"reply": text, "verdict": verdict}
        except Exception as e:  # noqa
            last = e
            continue

    raise HTTPException(502, f"AI request failed: {str(last)[:200]}")


if __name__ == "__main__":
    if not KEYS:
        print("WARNING: no GEMINI_API_KEY set. Quests work, but chat will be offline.")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
