#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Acquire pinned Blender and apply the cumulative M4 patch without discarding work."""
import argparse
import subprocess
import sys

import dev


PATCH = dev.ROOT / "patches/blender-v5.3.0-tilt-shift-m4.patch"
NATIVE_HEADER = "intern/cycles/kernel/camera/tilt_shift_math.h"


def prepare_source():
    """Accept only the clean pin or the exact, unstaged published patch."""
    dev.verify_source()
    staged = dev.run(["git", "diff", "--cached", "--name-only"], dev.SOURCE, True)
    if staged.strip():
        raise ValueError("Source index has staged changes; preserve them before preparing Blender")
    status = dev.run(["git", "status", "--porcelain", "--untracked-files=all",
                      "--ignore-submodules=all"], dev.SOURCE, True)
    if not status.strip():
        dev.run(["git", "apply", "--check", PATCH], dev.SOURCE)
        dev.run(["git", "apply", PATCH], dev.SOURCE)
        print("Applied cumulative M4 patch to the clean, verified source pin.")
        return

    # Reproduce the exporter without touching the source index or object store.
    # A reverse-apply check alone could accept unrelated edits outside patch hunks.
    untracked = dev.run(["git", "ls-files", "--others", "--exclude-standard"],
                        dev.SOURCE, True).splitlines()
    if untracked != [NATIVE_HEADER]:
        raise ValueError("Source contains other or missing untracked files; refusing to alter it")
    current = dev.run(["git", "diff", "--binary", "--no-ext-diff",
                       "--ignore-submodules=all", dev.PIN, "--", ".",
                       ":(exclude)lib", ":(exclude)tests/data"], dev.SOURCE, True)
    header = subprocess.run(["git", "diff", "--no-index", "--binary", "--",
                             "/dev/null", NATIVE_HEADER], cwd=dev.SOURCE, env=dev.ENV,
                            text=True, stdout=subprocess.PIPE, check=False)
    if header.returncode != 1 or current + header.stdout != PATCH.read_text():
        raise ValueError("Source differs from the exact cumulative M4 patch; no files changed")
    print("Exact cumulative M4 patch already present; no source files changed.")


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Default: large official source clone only, then patch. "
               "--with-dependencies also downloads large precompiled libraries and LFS assets. "
               "No build, package installation, reset, commit or system Blender changes.")
    parser.add_argument("--with-dependencies", action="store_true",
                        help="also acquire pinned Linux libraries and required source LFS assets")
    args = parser.parse_args()
    dev.run([sys.executable, dev.ROOT / "scripts/dev.py", "acquire"])
    prepare_source()
    if args.with_dependencies:
        dev.run([sys.executable, dev.ROOT / "scripts/dev.py", "dependencies"])
    print("Ready for the fresh M4 build in docs/build-instructions.md.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
