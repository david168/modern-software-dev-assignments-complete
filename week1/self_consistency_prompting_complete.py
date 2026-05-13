import os
import re
from collections import Counter
from dotenv import load_dotenv
from ollama import chat

load_dotenv()

NUM_RUNS_TIMES = 5

# Self-consistency prompting: run the same prompt multiple times at high temperature
# to generate diverse reasoning paths, then majority-vote on the final answers.
#
# Why it works: individual runs at temperature=1 may take wrong detours, but correct
# reasoning paths tend to converge on the same answer, so the right answer
# accumulates more votes than any single wrong answer.
#
# Key design choices:
# 1. Explicit variable assignment step — instruct the model to label each quantity
#    (total distance, first stop position, second stop position) before doing
#    arithmetic. This prevents the common error of confusing "15 miles before the end"
#    with the distance between stops.
# 2. Derive position before computing difference — "second stop position = total - 15"
#    must be computed first; only then subtract the first stop. Models that skip this
#    step often answer 60 - 20 - 15 = 25 by luck, or 15 + 20 = 35 by mistake.
# 3. Verification step — ask the model to check that first_stop + gap + remaining = 60
#    before writing the answer. At high temperature this catches arithmetic drift.
# 4. Strict output format — "Answer: <number>" on the last line, matching what
#    extract_final_answer() expects. Repeated across both the system prompt and the
#    user prompt to reinforce it under temperature variance.
YOUR_SYSTEM_PROMPT = """
You are a precise math reasoning assistant. When solving word problems, follow these steps:

1. Identify and label all given quantities with variable names.
2. Compute each position or intermediate value step by step.
3. Verify your answer by checking that all parts sum to the total.
4. State the final answer on the last line in the exact format: Answer: <number>

Be careful with phrasing like "X miles before the end" — this means the stop is at
position (total_distance - X), not that the distance between stops is X.
"""

USER_PROMPT = """
Solve this problem, then give the final answer on the last line as "Answer: <number>".

Henry made two stops during his 60-mile bike trip. He first stopped after 20
miles. His second stop was 15 miles before the end of the trip. How many miles
did he travel between his first and second stops?
"""

EXPECTED_OUTPUT = "Answer: 25"


def extract_final_answer(text: str) -> str:
    """Extract the final 'Answer: ...' line from a verbose reasoning trace.

    - Finds the LAST line that starts with 'Answer:' (case-insensitive)
    - Normalizes to 'Answer: <number>' when a number is present
    - Falls back to returning the matched content if no number is detected
    """
    matches = re.findall(r"(?mi)^\s*answer\s*:\s*(.+)\s*$", text)
    if matches:
        value = matches[-1].strip()
        num_match = re.search(r"-?\d+(?:\.\d+)?", value.replace(",", ""))
        if num_match:
            return f"Answer: {num_match.group(0)}"
        return f"Answer: {value}"
    return text.strip()


def test_your_prompt(system_prompt: str) -> bool:
    """Run the prompt NUM_RUNS_TIMES, majority-vote on the extracted 'Answer: ...' lines.

    Prints "SUCCESS" if the majority answer equals EXPECTED_OUTPUT.
    """
    answers: list[str] = []
    for idx in range(NUM_RUNS_TIMES):
        print(f"Running test {idx + 1} of {NUM_RUNS_TIMES}")
        response = chat(
            model="llama3.1:8b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": USER_PROMPT},
            ],
            options={"temperature": 1},
        )
        output_text = response.message.content
        final_answer = extract_final_answer(output_text)
        print(f"Run {idx + 1} answer: {final_answer}")
        answers.append(final_answer.strip())

    if not answers:
        print("No answers produced.")
        return False

    counts = Counter(answers)
    majority_answer, majority_count = counts.most_common(1)[0]
    print(f"Majority answer: {majority_answer} ({majority_count}/{len(answers)})")

    if majority_answer.strip() == EXPECTED_OUTPUT.strip():
        print("SUCCESS")
        return True

    # Print distribution for debugging when majority does not match expected
    print(f"Expected output: {EXPECTED_OUTPUT}")
    print("Answer distribution:")
    for answer, count in counts.most_common():
        print(f"  {answer}: {count}")
    return False


if __name__ == "__main__":
    test_your_prompt(YOUR_SYSTEM_PROMPT)
