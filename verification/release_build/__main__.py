"""Maintainer runner for E14.2 build verification (not shipped in the wheel)."""

from verification.release_build.runner import main

if __name__ == "__main__":
    raise SystemExit(main())
