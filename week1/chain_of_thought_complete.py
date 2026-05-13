import os
import re
from dotenv import load_dotenv
from ollama import chat

load_dotenv()

NUM_RUNS_TIMES = 5

# Chain-of-thought prompting: instead of asking for the answer directly (where the model
# often guesses wrong), scaffold the reasoning process so the model walks through the
# right algorithm step by step.
#
# The problem: 3^12345 mod 100 = 43, derived via:
#   1. Find the cycle: powers of 3 mod 100 repeat with period 20 (3^20 ≡ 1 mod 100)
#   2. Reduce the exponent: 12345 mod 20 = 5
#   3. Compute: 3^5 = 243 ≡ 43 mod 100
#
# Key design choices:
# 1. Step-by-step decomposition — instructs the model to break the problem into
#    sub-problems rather than jumping to an answer.
# 2. Modular exponentiation strategy — explicitly names the cyclic pattern / order
#    approach, the technique that makes this tractable for a small model.
# 3. Show arithmetic explicitly — reduces the chance of silent arithmetic errors
#    that occur when the model skips intermediate steps.
# 4. Verification step — prompts the model to check its answer before stating it.
# 5. Strict output format — ensures the final line is always "Answer: <number>"
#    so extract_final_answer() can reliably parse it.
YOUR_SYSTEM_PROMPT = """
You are a precise mathematical reasoning assistant. When solving problems, always work step by step using the following approach:

1. Identify the mathematical structure of the problem.
2. Break it into smaller sub-problems.
3. Apply relevant theorems or properties (e.g., modular arithmetic rules, Euler's theorem, cyclic patterns).
4. Show each arithmetic step explicitly.
5. Verify your answer before stating it.

For modular exponentiation problems specifically:
- Find the cycle length (order) of the base modulo n by computing successive powers until you return to 1.
- Reduce the exponent modulo the cycle length.
- Compute the final small power directly.

Always end your response with the final answer on its own line in the exact format:
Answer: <number>
"""


USER_PROMPT = """
Solve this problem, then give the final answer on the last line as "Answer: <number>".

what is 3^{12345} (mod 100)?
"""


# For this simple example, we expect the final numeric answer only
EXPECTED_OUTPUT = "Answer: 43"


def extract_final_answer(text: str) -> str:
    """Extract the final 'Answer: ...' line from a verbose reasoning trace.

    - Finds the LAST line that starts with 'Answer:' (case-insensitive)
    - Normalizes to 'Answer: <number>' when a number is present
    - Falls back to returning the matched content if no number is detected
    """
    matches = re.findall(r"(?mi)^\s*answer\s*:\s*(.+)\s*$", text)
    if matches:
        value = matches[-1].strip()
        # Prefer a numeric normalization when possible (supports integers/decimals)
        num_match = re.search(r"-?\d+(?:\.\d+)?", value.replace(",", ""))
        if num_match:
            return f"Answer: {num_match.group(0)}"
        return f"Answer: {value}"
    return text.strip()


def test_your_prompt(system_prompt: str) -> bool:
    """Run up to NUM_RUNS_TIMES and return True if any output matches EXPECTED_OUTPUT.

    Prints "SUCCESS" when a match is found.
    """
    for idx in range(NUM_RUNS_TIMES):
        print(f"Running test {idx + 1} of {NUM_RUNS_TIMES}")
        response = chat(
            model="llama3.1:8b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": USER_PROMPT},
            ],
            options={"temperature": 0.3},
        )
        output_text = response.message.content
        final_answer = extract_final_answer(output_text)
        if final_answer.strip() == EXPECTED_OUTPUT.strip():
            print("SUCCESS")
            return True
        else:
            print(f"Expected output: {EXPECTED_OUTPUT}")
            print(f"Actual output: {final_answer}")
    return False


if __name__ == "__main__":
    test_your_prompt(YOUR_SYSTEM_PROMPT)
