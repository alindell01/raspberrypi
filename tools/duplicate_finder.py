#!/usr/bin/env python3
"""Scan one or more directories and report groups of duplicate files.

Files are considered duplicates when they share the same size and the same
SHA-256 hash of their contents. Hashing only happens for files whose size
collides with at least one other file, which keeps large trees fast.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator


CHUNK_SIZE = 1 << 20  # 1 MiB


@dataclass
class ScanOptions:
    roots: list[Path]
    min_size: int = 1
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    follow_symlinks: bool = False
    hash_algo: str = "sha256"


@dataclass
class ScanStats:
    files_seen: int = 0
    files_considered: int = 0
    files_hashed: int = 0
    bytes_hashed: int = 0
    errors: list[str] = field(default_factory=list)


def iter_files(opts: ScanOptions, stats: ScanStats) -> Iterator[Path]:
    seen_inodes: set[tuple[int, int]] = set()
    for root in opts.roots:
        if not root.exists():
            stats.errors.append(f"path does not exist: {root}")
            continue
        if root.is_file():
            yield root
            continue
        for dirpath, dirnames, filenames in os.walk(
            root, followlinks=opts.follow_symlinks
        ):
            # Apply directory excludes in-place so os.walk skips them.
            dirnames[:] = [
                d for d in dirnames if not _matches_any(d, opts.exclude)
            ]
            for name in filenames:
                path = Path(dirpath) / name
                stats.files_seen += 1
                if _matches_any(name, opts.exclude):
                    continue
                if opts.include and not _matches_any(name, opts.include):
                    continue
                try:
                    st = path.lstat()
                except OSError as exc:
                    stats.errors.append(f"stat failed for {path}: {exc}")
                    continue
                if not opts.follow_symlinks and os.path.islink(path):
                    continue
                # Skip hardlink duplicates that point at the same inode.
                key = (st.st_dev, st.st_ino)
                if key in seen_inodes:
                    continue
                seen_inodes.add(key)
                if st.st_size < opts.min_size:
                    continue
                stats.files_considered += 1
                yield path


def _matches_any(name: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(name, pat) for pat in patterns)


def _hash_file(path: Path, algo: str, stats: ScanStats) -> str | None:
    hasher = hashlib.new(algo)
    try:
        with path.open("rb") as fh:
            while True:
                chunk = fh.read(CHUNK_SIZE)
                if not chunk:
                    break
                hasher.update(chunk)
                stats.bytes_hashed += len(chunk)
    except OSError as exc:
        stats.errors.append(f"read failed for {path}: {exc}")
        return None
    stats.files_hashed += 1
    return hasher.hexdigest()


def find_duplicates(
    opts: ScanOptions,
) -> tuple[list[list[Path]], ScanStats]:
    stats = ScanStats()
    by_size: dict[int, list[Path]] = defaultdict(list)
    for path in iter_files(opts, stats):
        try:
            by_size[path.stat().st_size].append(path)
        except OSError as exc:
            stats.errors.append(f"stat failed for {path}: {exc}")

    groups: list[list[Path]] = []
    for size, paths in by_size.items():
        if len(paths) < 2:
            continue
        by_hash: dict[str, list[Path]] = defaultdict(list)
        for path in paths:
            digest = _hash_file(path, opts.hash_algo, stats)
            if digest is not None:
                by_hash[digest].append(path)
        for digest, dupes in by_hash.items():
            if len(dupes) >= 2:
                groups.append(sorted(dupes))

    # Largest wasted-space groups first.
    groups.sort(
        key=lambda g: (g[0].stat().st_size * (len(g) - 1), len(g)),
        reverse=True,
    )
    return groups, stats


def _human_bytes(num: int) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]
    size = float(num)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:,.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{num} B"


def _print_text(
    groups: list[list[Path]],
    stats: ScanStats,
    out=sys.stdout,
) -> None:
    if not groups:
        out.write("No duplicates found.\n")
    else:
        total_waste = 0
        for idx, group in enumerate(groups, start=1):
            size = group[0].stat().st_size
            waste = size * (len(group) - 1)
            total_waste += waste
            out.write(
                f"\n[{idx}] {len(group)} copies, "
                f"{_human_bytes(size)} each, "
                f"{_human_bytes(waste)} reclaimable\n"
            )
            for path in group:
                out.write(f"    {path}\n")
        out.write(
            f"\nTotal reclaimable space: {_human_bytes(total_waste)}\n"
        )

    out.write(
        f"\nScanned {stats.files_seen} files "
        f"({stats.files_considered} considered, "
        f"{stats.files_hashed} hashed, "
        f"{_human_bytes(stats.bytes_hashed)} read).\n"
    )
    if stats.errors:
        out.write(f"Encountered {len(stats.errors)} errors:\n")
        for err in stats.errors:
            out.write(f"  ! {err}\n")


def _print_json(
    groups: list[list[Path]],
    stats: ScanStats,
    out=sys.stdout,
) -> None:
    payload = {
        "groups": [
            {
                "size_bytes": g[0].stat().st_size,
                "count": len(g),
                "reclaimable_bytes": g[0].stat().st_size * (len(g) - 1),
                "paths": [str(p) for p in g],
            }
            for g in groups
        ],
        "stats": {
            "files_seen": stats.files_seen,
            "files_considered": stats.files_considered,
            "files_hashed": stats.files_hashed,
            "bytes_hashed": stats.bytes_hashed,
            "errors": stats.errors,
        },
    }
    json.dump(payload, out, indent=2)
    out.write("\n")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Find duplicate files across one or more directories using "
            "size + content hash."
        ),
    )
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="One or more directories (or files) to scan.",
    )
    parser.add_argument(
        "--min-size",
        type=int,
        default=1,
        help="Ignore files smaller than this many bytes (default: 1).",
    )
    parser.add_argument(
        "--include",
        action="append",
        default=[],
        metavar="GLOB",
        help="Only consider filenames matching this glob (repeatable).",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="GLOB",
        help="Skip filenames or directory names matching this glob (repeatable).",
    )
    parser.add_argument(
        "--follow-symlinks",
        action="store_true",
        help="Follow symbolic links while walking directories.",
    )
    parser.add_argument(
        "--hash",
        dest="hash_algo",
        default="sha256",
        help="Hash algorithm understood by hashlib (default: sha256).",
    )
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Emit machine-readable JSON instead of a text report.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    opts = ScanOptions(
        roots=[p.resolve() for p in args.paths],
        min_size=max(0, args.min_size),
        include=args.include,
        exclude=args.exclude,
        follow_symlinks=args.follow_symlinks,
        hash_algo=args.hash_algo,
    )
    try:
        hashlib.new(opts.hash_algo)
    except (ValueError, TypeError) as exc:
        print(f"error: unknown hash algorithm '{opts.hash_algo}': {exc}",
              file=sys.stderr)
        return 2

    groups, stats = find_duplicates(opts)
    if args.as_json:
        _print_json(groups, stats)
    else:
        _print_text(groups, stats)
    return 0 if not stats.errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
