import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nlp.parser import IntentSlotParser


def main() -> None:
    parser = argparse.ArgumentParser(description="Run intent parser on sample text.")
    parser.add_argument("text", help="Prompt to parse.")
    args = parser.parse_args()

    parser_model = IntentSlotParser()
    result = parser_model.parse(args.text)
    print(f"Intent: {result.intent} (confidence={result.confidence:.2f})")
    print("Slots:")
    for key, value in result.slots.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
