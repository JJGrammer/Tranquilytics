"""Count lines in git-tracked text files (rough LOC)."""
from __future__ import annotations

import argparse
import os
import subprocess

BIN_EXT = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".ttf",
    ".woff",
    ".woff2",
    ".eot",
    ".pdf",
    ".zip",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--no-lockfiles",
        action="store_true",
        help="Exclude package-lock.json / poetry.lock style files from the count",
    )
    args = parser.parse_args()

    root = subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"],
        text=True,
    ).strip()
    files = subprocess.check_output(["git", "ls-files"], text=True, cwd=root).splitlines()
    if args.no_lockfiles:
        files = [
            f
            for f in files
            if not f.endswith("package-lock.json") and not f.endswith("poetry.lock")
        ]
    total = 0
    skipped = 0
    by_ext: dict[str, int] = {}
    for rel in files:
        ext = os.path.splitext(rel)[1].lower()
        if ext in BIN_EXT:
            skipped += 1
            continue
        path = os.path.join(root, rel)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "rb") as fh:
                raw = fh.read()
        except OSError:
            skipped += 1
            continue
        if b"\x00" in raw[:8192]:
            skipped += 1
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = raw.decode("latin-1")
            except Exception:
                skipped += 1
                continue
        n = text.count("\n")
        if text and not text.endswith("\n"):
            n += 1
        total += n
        key = ext or "(no ext)"
        by_ext[key] = by_ext.get(key, 0) + n

    print("LOC (tracked text files, NUL-free):", total)
    print("Files skipped (binary ext / NUL / unreadable):", skipped)
    print("Top extensions by LOC:")
    for k, v in sorted(by_ext.items(), key=lambda x: -x[1])[:15]:
        label = k if k else "(no ext)"
        print(f"  {label}: {v}")


if __name__ == "__main__":
    main()
