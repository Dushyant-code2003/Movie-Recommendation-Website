#!/usr/bin/env python3
"""Start MovieMate: bootstrap models then run the production server."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"


def main():
    print("MovieMate startup\n" + "=" * 40)
    subprocess.run([sys.executable, "train_model.py"], cwd=BACKEND, check=True)
    print("\nStarting server at http://127.0.0.1:5000\n")
    subprocess.run([sys.executable, "app.py"], cwd=BACKEND)


if __name__ == "__main__":
    main()
