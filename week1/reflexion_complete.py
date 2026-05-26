import os
import re
from typing import Callable, List, Tuple
from dotenv import load_dotenv
from ollama import chat

load_dotenv()

NUM_RUNS_TIMES = 1

SYSTEM_PROMPT = """
You are a coding assistant. Output ONLY a single fenced Python code block that defines
the function is_valid_password(password: str) -> bool. No prose or comments.
Keep the implementation minimal.
"""

# Reflexion prompting: a two-phase self-correction loop.
#
# Phase 1 — initial generation: the model writes a first-attempt implementation.
# Phase 2 — reflexion: the model receives its own code plus structured failure
#   diagnostics, then rewrites to fix the identified issues.
#
# The two TODOs:
#   1. YOUR_REFLEXION_PROMPT — system prompt for the fix step. Must instruct the
#      model to reason about each failure before rewriting, and to output ONLY a
#      fenced code block (no prose) so extract_code_block() can parse it.
#   2. your_build_reflexion_context — constructs the user message that feeds both
#      the broken code and the exact failure messages into the reflexion prompt.
#      Giving the model its own code lets it make targeted edits; giving it the
#      per-case failure messages tells it *which* rule was violated on *which* input,
#      so it can fix the right condition rather than guessing.
#
# Key design choices:
# 1. Show the failing code verbatim — the model can see exactly what it wrote and
#    make a minimal, targeted fix rather than rewriting from scratch blindly.
# 2. List each failure with input, expected value, and violated rule — vague feedback
#    like "it failed" leads to random rewrites; specific diagnostics guide the fix.
# 3. "Think through each failure before rewriting" — prompts the model to reason
#    step-by-step in the reflexion step, improving fix accuracy.
# 4. Output constraint repeated — small models forget formatting rules between turns,
#    so the reflexion prompt re-states "fenced code block only, no prose."
YOUR_REFLEXION_PROMPT = """
You are a coding assistant fixing a broken Python function.

You will be given:
1. The current (broken) implementation of is_valid_password(password: str) -> bool
2. A list of test failures with the input, expected result, and which rule was violated

Your task:
- Think through each failure to understand which condition in the code is wrong or missing.
- Rewrite the function to pass all test cases.
- Output ONLY a single fenced Python code block. No explanation, no prose, nothing else.

Password rules (inferred from failures):
- At least 8 characters long
- Contains at least one uppercase letter
- Contains at least one lowercase letter
- Contains at least one digit
- Contains at least one special character from: !@#$%^&*()-_
- Contains no whitespace
"""


def your_build_reflexion_context(prev_code: str, failures: List[str]) -> str:
    """Build the user message for the reflexion step using prev_code and failures.

    Includes the broken code verbatim and each failure with its diagnostic so
    the model can make targeted fixes rather than rewriting blindly.
    """
    failure_block = "\n".join(f"- {f}" for f in failures)
    return (
        f"Here is the current implementation:\n"
        f"```python\n{prev_code}\n```\n\n"
        f"The following test cases failed:\n{failure_block}\n\n"
        f"Fix the function so all test cases pass. "
        f"Output only the corrected fenced Python code block."
    )


# Ground-truth test suite used to evaluate generated code
SPECIALS = set("!@#$%^&*()-_")
TEST_CASES: List[Tuple[str, bool]] = [
    ("Password1!", True),       # valid
    ("password1!", False),      # missing uppercase
    ("Password!", False),       # missing digit
    ("Password1", False),       # missing special
]


def extract_code_block(text: str) -> str:
    m = re.findall(r"```python\n([\s\S]*?)```", text, flags=re.IGNORECASE)
    if m:
        return m[-1].strip()
    m = re.findall(r"```\n([\s\S]*?)```", text)
    if m:
        return m[-1].strip()
    return text.strip()


def load_function_from_code(code_str: str) -> Callable[[str], bool]:
    namespace: dict = {}
    exec(code_str, namespace)  # noqa: S102 (executing controlled code from model for exercise)
    func = namespace.get("is_valid_password")
    if not callable(func):
        raise ValueError("No callable is_valid_password found in generated code")
    return func


def evaluate_function(func: Callable[[str], bool]) -> Tuple[bool, List[str]]:
    failures: List[str] = []
    for pw, expected in TEST_CASES:
        try:
            result = bool(func(pw))
        except Exception as exc:
            failures.append(f"Input: {pw} → raised exception: {exc}")
            continue

        if result != expected:
            # Compute diagnostic based on ground-truth rules
            reasons = []
            if len(pw) < 8:
                reasons.append("length < 8")
            if not any(c.islower() for c in pw):
                reasons.append("missing lowercase")
            if not any(c.isupper() for c in pw):
                reasons.append("missing uppercase")
            if not any(c.isdigit() for c in pw):
                reasons.append("missing digit")
            if not any(c in SPECIALS for c in pw):
                reasons.append("missing special")
            if any(c.isspace() for c in pw):
                reasons.append("has whitespace")

            failures.append(
                f"Input: {pw} → expected {expected}, got {result}. Failing checks: {', '.join(reasons) or 'unknown'}"
            )

    return (len(failures) == 0, failures)


def generate_initial_function(system_prompt: str) -> str:
    response = chat(
        model="llama3.1:8b",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Provide the implementation now."},
        ],
        options={"temperature": 0.2},
    )
    return extract_code_block(response.message.content)


def apply_reflexion(
    reflexion_prompt: str,
    build_context: Callable[[str, List[str]], str],
    prev_code: str,
    failures: List[str],
) -> str:
    reflection_context = build_context(prev_code, failures)
    print(f"REFLECTION CONTEXT: {reflection_context}, {reflexion_prompt}")
    response = chat(
        model="llama3.1:8b",
        messages=[
            {"role": "system", "content": reflexion_prompt},
            {"role": "user", "content": reflection_context},
        ],
        options={"temperature": 0.2},
    )
    return extract_code_block(response.message.content)


def run_reflexion_flow(
    system_prompt: str,
    reflexion_prompt: str,
    build_context: Callable[[str, List[str]], str],
) -> bool:
    # 1) Generate initial function
    initial_code = generate_initial_function(system_prompt)
    print("Initial code:\n" + initial_code)
    func = load_function_from_code(initial_code)
    passed, failures = evaluate_function(func)
    if passed:
        print("SUCCESS (initial implementation passed all tests)")
        return True
    else:
        print(f"FAILURE (initial implementation failed some tests): {failures}")

    # 2) Single reflexion iteration
    improved_code = apply_reflexion(reflexion_prompt, build_context, initial_code, failures)
    print("\nImproved code:\n" + improved_code)
    improved_func = load_function_from_code(improved_code)
    passed2, failures2 = evaluate_function(improved_func)
    if passed2:
        print("SUCCESS")
        return True

    print("Tests still failing after reflexion:")
    for f in failures2:
        print("- " + f)
    return False


if __name__ == "__main__":
    run_reflexion_flow(SYSTEM_PROMPT, YOUR_REFLEXION_PROMPT, your_build_reflexion_context)
