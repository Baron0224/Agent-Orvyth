from collections import defaultdict, Counter
from pathlib import Path
import random

# Read the training text from the file beside this script.
data_path = Path(__file__).with_name("corpus.txt")
text = data_path.read_text(encoding="utf-8-sig")

# Count which character tends to follow each character.
next_chars = defaultdict(Counter)
for current_char, next_char in zip(text, text[1:]):
    if not current_char.isspace() and not next_char.isspace():
        next_chars[current_char][next_char] += 1

if not next_chars:
    raise ValueError("corpus.txt is empty; add some training text first.")

# Generate text using the learned character frequencies.
def generate(start_char="人", length=100):
    result = start_char
    for _ in range(length):
        choices = next_chars.get(result[-1])
        if not choices:
            break
        chars = list(choices.keys())
        weights = list(choices.values())
        result += random.choices(chars, weights=weights, k=1)[0]
    return result

print("Training text characters:", len(text))
print("Characters learned:", len(next_chars))
print("Generated text:")
print(generate())
