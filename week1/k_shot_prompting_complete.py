import os
from dotenv import load_dotenv
from ollama import chat

load_dotenv()

NUM_RUNS_TIMES = 5

# K-shot prompting: provide k worked input→output examples before the real query
# so the model learns the pattern from demonstration rather than instruction alone.
#
# Challenges addressed:
# 1. Exact output format — the model must output *only* the reversed word with zero
#    extra text, which LLMs naturally resist. Examples demonstrate this behavior directly.
# 2. Long compound word — "httpstatus" (10 chars) is tricky; models sometimes mis-count
#    or reorder. Examples include words of varying lengths to show the pattern scales.
# 3. No explanation leakage — the system prompt reinforces "nothing else" both in prose
#    and by example, since mistral-nemo:12b tends to be chatty.
#
# The 5 examples (cat, python, hello, algorithm, stanford) cover short, medium, and longer
# words so the model generalizes rather than just copying a trivial 3-letter pattern.
YOUR_SYSTEM_PROMPT = """
You reverse the order of letters in a word. Output only the reversed word, nothing else — no punctuation, no explanation, no extra spaces.

Here are examples:

User: Reverse the order of letters in the following word. Only output the reversed word, no other text:

cat
Assistant: tac

User: Reverse the order of letters in the following word. Only output the reversed word, no other text:

python
Assistant: nohtyp

User: Reverse the order of letters in the following word. Only output the reversed word, no other text:

hello
Assistant: olleh

User: Reverse the order of letters in the following word. Only output the reversed word, no other text:

algorithm
Assistant: mhtirogla

User: Reverse the order of letters in the following word. Only output the reversed word, no other text:

stanford
Assistant: drofnats
"""

USER_PROMPT = """
Reverse the order of letters in the following word. Only output the reversed word, no other text:

httpstatus
"""


EXPECTED_OUTPUT = "sutatsptth"

def test_your_prompt(system_prompt: str) -> bool:
    """Run the prompt up to NUM_RUNS_TIMES and return True if any output matches EXPECTED_OUTPUT.

    Prints "SUCCESS" when a match is found.
    """
    for idx in range(NUM_RUNS_TIMES):
        print(f"Running test {idx + 1} of {NUM_RUNS_TIMES}")
        response = chat(
            model="mistral-nemo:12b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": USER_PROMPT},
            ],
            options={"temperature": 0.5},
        )
        output_text = response.message.content.strip()
        if output_text.strip() == EXPECTED_OUTPUT.strip():
            print("SUCCESS")
            return True
        else:
            print(f"Expected output: {EXPECTED_OUTPUT}")
            print(f"Actual output: {output_text}")
    return False

if __name__ == "__main__":
    test_your_prompt(YOUR_SYSTEM_PROMPT)
