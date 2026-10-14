"""Cheap deterministic regression checks, without Atheris or mutation campaigns."""

import json
import sys
from pathlib import Path

from PIL import Image
from targets import TARGETS, production


def main() -> None:
    root = Path(__file__).resolve().parent / "corpus"
    total = 0
    for name, target in TARGETS.items():
        seeds = sorted((root / name).iterdir())
        assert seeds, f"empty corpus: {name}"
        for seed in seeds:
            data = seed.read_bytes()
            target(data)
            # Also exercise short truncations of valid binary samples.
            for length in (0, 1, 2, len(data) // 2, max(0, len(data) - 1)):
                target(data[:length])
            total += 6
    operations = {
        "capture-url": lambda data: production.capture_url(*json.loads(data)),
        "thumbnail": production.thumbnail,
        "paired-certificate": production.paired_fingerprint,
    }
    # Known positive/negative outcomes prevent a harness that rejects every seed
    # from passing its semantic checks vacuously.
    for case in json.loads((root.parent / "corpus.json").read_text()):
        data = (root / case["target"] / case["file"]).read_bytes()
        try:
            operations[case["target"]](data)
            accepted = True
        except (ValueError, OSError, Image.DecompressionBombError):
            accepted = False
        assert accepted == case["accepted"], case
    assert "homeassistant" not in sys.modules, "replay imported Home Assistant"
    print(f"Replayed {total} synthetic corpus/truncation cases offline")


if __name__ == "__main__":
    main()
