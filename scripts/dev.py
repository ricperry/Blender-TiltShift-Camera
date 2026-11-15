#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded, local Blender development commands; Python standard library only."""
import argparse
import array
import fnmatch
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "work"
SOURCE = WORK / "blender"
PIN = "02f0899d78e374b63e7181d9061e1f7ab03419cc"
LIB_PIN = "e92f1a54a92c774fbeb0cf51c4652bc510d9a50a"
UPSTREAM = "https://projects.blender.org/blender/blender.git"
SCENES = ("grid", "tabletop", "facade", "measurable-targets")
ENV = dict(os.environ, CCACHE_DIR=str(WORK / "ccache"),
           BLENDER_USER_RESOURCES=str(WORK / "blender-user"),
           BLENDER_USER_CONFIG=str(WORK / "blender-user-config"),
           BLENDER_USER_EXTENSIONS=str(WORK / "blender-user/extensions"),
           BLENDER_USER_SCRIPTS=str(WORK / "blender-user/scripts"),
           BLENDER_USER_DATAFILES=str(WORK / "blender-user/datafiles"),
           XDG_CACHE_HOME=str(WORK / "cache"))
ASSET_PATTERNS = ("assets/*", "release/datafiles/*",
                  "scripts/startup/bl_app_templates_system/*", "tests/files/render/camera/*")


def run(argv, cwd=ROOT, capture=False):
    print("+", " ".join(map(str, argv)), flush=True)
    return subprocess.run(list(map(str, argv)), cwd=cwd, env=ENV, check=True,
                          text=True, stdout=subprocess.PIPE if capture else None).stdout


def verify_source():
    head = run(["git", "rev-parse", "HEAD"], SOURCE, True).strip()
    if head != PIN:
        raise ValueError(f"Expected source {PIN}; found {head}; refusing automatic checkout")
    origin = run(["git", "remote", "get-url", "origin"], SOURCE, True).strip()
    if origin != UPSTREAM:
        raise ValueError(f"Expected official origin {UPSTREAM}; found {origin}")
    tag = run(["git", "rev-parse", "v5.3.0^{commit}"], SOURCE, True).strip()
    if tag != PIN:
        raise ValueError("Release tag does not resolve to the recorded pin")
    version = run(["git", "show", f"{PIN}:source/blender/blenkernel/BKE_blender_version.h"],
                  SOURCE, True)
    for key, value in (("BLENDER_VERSION", "503"), ("BLENDER_VERSION_PATCH", "0"),
                       ("BLENDER_VERSION_CYCLE", "release")):
        if not re.search(rf"^#define {key}\s+{value}\s*$", version, re.MULTILINE):
            raise ValueError(f"Unexpected pinned {key}")
    gitlink = run(["git", "ls-tree", "HEAD", "lib/linux_x64"], SOURCE, True)
    if not gitlink.startswith(f"160000 commit {LIB_PIN}\t"):
        raise ValueError("Pinned Linux library gitlink does not match manifest")
    print("Source pin verified; this does not verify optional LFS media or library contents.")


def configure(backend, gui=False):
    verify_source()
    verify_libraries(required=True)
    missing = required_assets()
    if missing:
        raise ValueError(f"Required source LFS assets unavailable ({len(missing)}); run dependencies")
    args = ["/usr/bin/cmake", "-S", SOURCE, "-B", WORK / f"build-blender-{backend}", "-G", "Ninja",
            "-DCMAKE_BUILD_TYPE=Release", "-DWITH_LIBS_PRECOMPILED=ON",
            "-DWITH_CYCLES_NATIVE_ONLY=ON", f"-DWITH_HEADLESS={'OFF' if gui else 'ON'}",
            "-DWITH_COMPILER_CCACHE=ON", "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
            f"-DCMAKE_INSTALL_PREFIX={WORK / ('install-blender-' + backend)}",
            "-DWITH_CYCLES_DEVICE_CUDA=OFF", "-DWITH_CYCLES_DEVICE_OPTIX=OFF",
            "-DWITH_CYCLES_DEVICE_ONEAPI=OFF", "-DWITH_CYCLES_DEVICE_HIPRT=OFF",
            "-DWITH_CYCLES_DEVICE_HIP=ON",
            f"-DWITH_CYCLES_HIP_BINARIES={'ON' if backend == 'hip' else 'OFF'}"]
    if backend == "hip":
        args += ["-DCYCLES_HIP_BINARIES_ARCH=gfx1030", "-DHIP_ROOT_DIR=/usr",
                 "-DHIP_HIPCC_EXECUTABLE=/usr/bin/hipcc"]
    run(args)
    if backend == "hip":
        targets = run(["ninja", "-C", WORK / "build-blender-hip", "-t", "targets", "all"],
                      capture=True)
        if not any(line.startswith("cycles_kernel_hip:") for line in targets.splitlines()):
            raise ValueError("HIP configure omitted cycles_kernel_hip; refusing silent fallback")


def required_assets():
    files = run(["git", "lfs", "ls-files", "--name-only"], SOURCE, True).splitlines()
    needed = [name for name in files if any(fnmatch.fnmatchcase(name, pattern)
                                          for pattern in ASSET_PATTERNS)]
    missing = []
    for name in needed:
        path = SOURCE / name
        if not path.is_file():
            missing.append(name)
            continue
        with path.open('rb') as stream:
            if stream.read(127).startswith(b'version https://git-lfs.github.com/spec/v1'):
                missing.append(name)
    print(f"Required source LFS assets: {len(needed)-len(missing)}/{len(needed)} materialized; "
          "optional regression media excluded")
    return missing


def verify_libraries(required=False):
    lib = SOURCE / "lib/linux_x64"
    if not (lib / ".git").exists():
        if required:
            raise ValueError("Linux library checkout absent")
        print("Linux library checkout absent (not acquired by source verification).")
        return
    head = run(["git", "rev-parse", "HEAD"], lib, True).strip()
    if head != LIB_PIN:
        raise ValueError(f"Library gitlink differs: {head}")
    status = run(["git", "status", "--porcelain"], lib, True)
    if status.strip():
        raise ValueError("Linux dependency checkout is dirty; preserve and investigate it")


def compare(first, second, rmse_limit, max_limit):
    a, b = json.loads(first.read_text()), json.loads(second.read_text())
    if (a["scene"], a["width"], a["height"], a["seed"], a["samples"]) != (
            b["scene"], b["width"], b["height"], b["seed"], b["samples"]):
        raise ValueError("Scene, dimensions, seed and samples must match")
    for key in ("feature_enabled", "generator_sha256", "camera_settings",
                "blender_version", "blender_build_hash"):
        if a[key] != b[key]:
            raise ValueError(f"Comparison metadata differs: {key}")
    pixels = []
    for path, metadata in ((first, a), (second, b)):
        values = array.array("f")
        pixel_path = path.parent / metadata["pixels"]
        if hashlib.sha256(pixel_path.read_bytes()).hexdigest() != metadata['pixels_sha256']:
            raise ValueError("Pixel digest differs from metadata; incomplete or changed artifact set")
        with pixel_path.open("rb") as stream:
            values.fromfile(stream, a["width"] * a["height"] * 4)
            if stream.read(1):
                raise ValueError("Unexpected trailing pixel data")
        if sys.byteorder != metadata["byteorder"]:
            values.byteswap()
        if not all(math.isfinite(x) for x in values):
            raise ValueError("Nonfinite pixels")
        pixels.append(values)
    errors = [abs(x-y) for i, (x, y) in enumerate(zip(*pixels)) if i % 4 != 3]
    rmse = math.sqrt(sum(x*x for x in errors) / len(errors))
    maximum = max(errors)
    print(json.dumps({"rmse_rgb": rmse, "max_abs_rgb": maximum,
                      "rmse_limit": rmse_limit, "max_limit": max_limit}, indent=2))
    if rmse > rmse_limit or maximum > max_limit:
        raise ValueError("Pixel comparison exceeds explicit limits")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("check-deps", "acquire", "verify-source", "dependencies", "test-optics"):
        sub.add_parser(name)
    q = sub.add_parser("patch")
    q.add_argument("--milestone", choices=("m2", "m3", "m4"), default="m4",
                   help="Export a cumulative patch without overwriting earlier milestone evidence")
    for name in ("configure", "build"):
        q = sub.add_parser(name)
        q.add_argument("backend", choices=("cpu", "hip"))
        if name == "configure":
            q.add_argument("--gui", action="store_true", help="Require window-system development headers")
        if name == "build":
            q.add_argument("--jobs", type=int, default=4)
    for name in ("validate", "scenes", "render"):
        q = sub.add_parser(name)
        q.add_argument("--blender", type=Path, default=WORK / "install-blender-cpu/blender")
        q.add_argument("--require-feature", action="store_true")
        if name == "render":
            q.add_argument("--backend", choices=("cpu", "hip"), default="cpu")
            q.add_argument("--scene", choices=SCENES, default="measurable-targets")
            q.add_argument("--label", default="baseline")
    q = sub.add_parser("compare")
    q.add_argument("first", type=Path)
    q.add_argument("second", type=Path)
    q.add_argument("--rmse", type=float, default=0.003)
    q.add_argument("--max-abs", type=float, default=0.02)
    args = p.parse_args()
    if args.command == "check-deps":
        tools = {name: shutil.which(name) for name in
                 ("git", "git-lfs", "gcc", "g++", "ninja", "hipcc", "pkg-config")}
        tools.update({name: str(Path('/usr/bin') / name) if (Path('/usr/bin') / name).exists()
                      else None for name in ("cmake", "ctest")})
        print(json.dumps(tools, indent=2))
        if not all(tools[x] for x in ("git", "git-lfs", "g++", "ninja", "cmake", "ctest")):
            raise ValueError("Missing basic build tools; no packages installed")
    elif args.command == "acquire":
        if not SOURCE.exists():
            WORK.mkdir(exist_ok=True)
            ENV["GIT_LFS_SKIP_SMUDGE"] = "1"
            run(["git", "clone", "--branch", "v5.3.0", UPSTREAM, SOURCE])
        verify_source()
    elif args.command == "verify-source":
        verify_source()
        required_assets()
        print(run(["git", "status", "--short", "--ignore-submodules=all"], SOURCE, True))
        print(run(["git", "ls-tree", "HEAD", "lib/linux_x64"], SOURCE, True))
        verify_libraries()
    elif args.command == "dependencies":
        verify_source()
        run(["git", "lfs", "pull", "--include=" + ','.join(ASSET_PATTERNS)], SOURCE)
        run([sys.executable, "build_files/utils/make_update.py", "--no-blender"], SOURCE)
        verify_source()
        verify_libraries(required=True)
        run(["git", "lfs", "fsck"], SOURCE / "lib/linux_x64")
        if required_assets():
            raise ValueError("Required source LFS assets still absent after acquisition")
    elif args.command == "configure":
        configure(args.backend, args.gui)
    elif args.command == "build":
        if args.jobs < 1:
            raise ValueError("--jobs must be positive")
        run(["/usr/bin/cmake", "--build", WORK / f"build-blender-{args.backend}", "--target", "install",
             "--parallel", args.jobs])
    elif args.command == "test-optics":
        run(["/usr/bin/cmake", "-S", ROOT, "-B", WORK / "build-optics-ninja", "-G", "Ninja",
             "-DCMAKE_BUILD_TYPE=Debug"])
        run(["/usr/bin/cmake", "--build", WORK / "build-optics-ninja", "--parallel", "4"])
        run(["/usr/bin/ctest", "--test-dir", WORK / "build-optics-ninja", "--output-on-failure"])
    elif args.command in ("validate", "scenes", "render"):
        for name in ('BLENDER_USER_RESOURCES', 'BLENDER_USER_CONFIG', 'BLENDER_USER_EXTENSIONS',
                     'BLENDER_USER_SCRIPTS', 'BLENDER_USER_DATAFILES', 'XDG_CACHE_HOME'):
            Path(ENV[name]).mkdir(parents=True, exist_ok=True)
        cmd = [args.blender.resolve(), "--background", "-noaudio", "--factory-startup", "--python-exit-code", "1",
               "--python", ROOT / "scripts/blender_reference.py", "--", args.command]
        if args.require_feature:
            cmd += ["--require-feature"]
        if args.command == "render":
            if not args.label.replace("-", "").replace("_", "").isalnum():
                raise ValueError("Label must contain letters, numbers, hyphens or underscores")
            cmd += ["--backend", args.backend, "--scene", args.scene, "--label", args.label]
        run(cmd)
    elif args.command == "compare":
        if not all(math.isfinite(x) and x >= 0 for x in (args.rmse, args.max_abs)):
            raise ValueError("Comparison tolerances must be finite and nonnegative")
        compare(args.first, args.second, args.rmse, args.max_abs)
    elif args.command == "patch":
        verify_source()
        patch = run(["git", "diff", "--binary", "--no-ext-diff", "--ignore-submodules=all", PIN,
                     "--", ".", ":(exclude)lib", ":(exclude)tests/data"], SOURCE, True)
        if not patch.strip():
            raise ValueError("No tracked native changes; refusing empty patch")
        untracked = run(["git", "ls-files", "--others", "--exclude-standard"], SOURCE, True)
        # One explicitly reviewed new header is part of M2; export it without
        # staging or committing anything in the pinned upstream checkout.
        native_header = "intern/cycles/kernel/camera/tilt_shift_math.h"
        unknown = set(untracked.splitlines()) - {native_header}
        if unknown:
            raise ValueError(f"Unreviewed untracked source files: {sorted(unknown)}")
        if (SOURCE / native_header).read_bytes() != (ROOT / "src/native/tilt_shift_math.h").read_bytes():
            raise ValueError("Native test and kernel mathematical headers differ")
        if native_header in untracked.splitlines():
            new_file = subprocess.run(["git", "diff", "--no-index", "--binary", "--",
                                       "/dev/null", native_header], cwd=SOURCE, env=ENV,
                                      text=True, stdout=subprocess.PIPE, check=False)
            if new_file.returncode != 1:
                raise ValueError("Could not export reviewed native header")
            patch += new_file.stdout
        target = ROOT / ("patches/blender-v5.3.0-tilt-shift.patch" if args.milestone == "m2"
                         else f"patches/blender-v5.3.0-tilt-shift-{args.milestone}.patch")
        if args.milestone in ("m2", "m3") and target.exists():
            raise ValueError("M2/M3 patches are immutable evidence; use --milestone m4")
        target.write_text(patch)
        print(target)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
