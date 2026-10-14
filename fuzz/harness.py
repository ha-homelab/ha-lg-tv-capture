"""Linux/Atheris mutation entry point; never starts an integration or transport."""

import sys

import atheris

with atheris.instrument_imports(include=["targets", "frame_validation"]):
    from targets import TARGETS


def main() -> None:
    target = TARGETS[sys.argv.pop(1)]
    atheris.Setup(sys.argv, target)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
