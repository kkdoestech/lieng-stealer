#!/usr/bin/env python3
"""Check that the course in this folder still matches the code.

Usage (from anywhere):
    python3 learning/verify_course.py                 # whole course, including coverage
    python3 learning/verify_course.py 07-expected-value.md 08-range-finder.md

Checks:
    1. Every relative link points to a file or folder that exists.
    2. Every line anchor (#L12 or #L12-L30) is inside the target file, and every
       heading anchor (#some-heading) matches a heading in the target Markdown file.
    3. Every excerpt labelled with 📍 is identical to the lines it cites.
    4. Every lesson (NN-*.md) has the sections of the lesson template.
    5. (Whole course only) every source file is linked from at least one page.

Exit code 0 means everything matched; 1 means at least one problem was printed.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

COURSE_DIR = Path(__file__).resolve().parent
REPO_ROOT = COURSE_DIR.parent

LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
LINE_ANCHOR = re.compile(r"^L(\d+)(?:-L(\d+))?$")
EXCERPT_LABEL = re.compile(r"^📍 \[`([^`]+?):(\d+)(?:-(\d+))?`\]\(([^)\s]+)\)\s*$")
FENCE = re.compile(r"^\s*(```|~~~)")

LESSON_SECTIONS = (
    "Where this fits",
    "Reading order",
    "Walkthrough",
    "Weak spots",
    "Try it",
    "Exercises",
    "Quiz",
    "Recap",
)

# Files every reader of the codebase should meet at least once.
SOURCE_GLOBS = (
    "backend/app.py",
    "backend/Procfile",
    "backend/requirements.txt",
    "backend/data/winrates.json",
    "backend/src/*.py",
    "backend/tests/test_*.py",
    "frontend/index.html",
    "frontend/package.json",
    "frontend/vite.config.js",
    "frontend/.oxlintrc.json",
    "frontend/src/*.js",
    "frontend/src/*.jsx",
    "frontend/src/*.css",
)
SKIP_SOURCES = {"backend/src/__init__.py"}


def github_slug(heading: str) -> str:
    """Approximate GitHub's heading anchor: lowercase, drop punctuation and emoji, spaces to dashes."""
    text = re.sub(r"`|\*\*?|__", "", heading.strip().lower())
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def heading_slugs(md_path: Path) -> set[str]:
    slugs: set[str] = set()
    seen: dict[str, int] = {}
    in_code = False
    for line in md_path.read_text(encoding="utf-8").splitlines():
        if FENCE.match(line):
            in_code = not in_code
            continue
        if in_code or not line.startswith("#"):
            continue
        slug = github_slug(line.lstrip("#"))
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        slugs.add(slug if count == 0 else f"{slug}-{count}")
    return slugs


def split_blocks(lines: list[str]) -> list[bool]:
    """For each line, True if it sits inside (or on the fence of) a fenced code block."""
    inside = []
    in_code = False
    for line in lines:
        if FENCE.match(line):
            inside.append(True)
            in_code = not in_code
        else:
            inside.append(in_code)
    return inside


def check_links(md: Path, lines: list[str], in_code: list[bool], problems: list[str],
                linked: set[Path]) -> None:
    for number, line in enumerate(lines, start=1):
        if in_code[number - 1]:
            continue
        for target in LINK.findall(line):
            if re.match(r"^[a-z]+:", target) or target.startswith("#"):
                if target.startswith("#") and target[1:] not in heading_slugs(md):
                    problems.append(f"{md.name}:{number}: no heading for in-page anchor {target}")
                continue
            path_part, _, anchor = target.partition("#")
            resolved = (md.parent / path_part).resolve()
            if not resolved.exists():
                problems.append(f"{md.name}:{number}: link target does not exist: {target}")
                continue
            linked.add(resolved)
            if not anchor:
                continue
            match = LINE_ANCHOR.match(anchor)
            if match:
                if resolved.is_dir():
                    problems.append(f"{md.name}:{number}: line anchor on a folder: {target}")
                    continue
                total = len(resolved.read_text(encoding="utf-8").splitlines())
                start = int(match.group(1))
                end = int(match.group(2) or start)
                if not 1 <= start <= end <= total:
                    problems.append(
                        f"{md.name}:{number}: lines {start}-{end} outside {path_part} ({total} lines)"
                    )
            elif resolved.suffix == ".md":
                if anchor not in heading_slugs(resolved):
                    problems.append(f"{md.name}:{number}: no heading '#{anchor}' in {path_part}")
            else:
                problems.append(f"{md.name}:{number}: unknown anchor format: {target}")


def check_excerpts(md: Path, lines: list[str], problems: list[str]) -> int:
    checked = 0
    for index, line in enumerate(lines):
        label = EXCERPT_LABEL.match(line)
        if not label:
            if line.startswith("📍"):
                problems.append(f"{md.name}:{index + 1}: 📍 line does not match the label format")
            continue
        shown_path, start_text, end_text, target = label.groups()
        start = int(start_text)
        end = int(end_text or start)
        path_part, _, anchor = target.partition("#")
        expected_anchor = f"L{start}" if start == end else f"L{start}-L{end}"
        if anchor != expected_anchor:
            problems.append(f"{md.name}:{index + 1}: label says {start}-{end} but link anchor is #{anchor}")
        resolved = (md.parent / path_part).resolve()
        if not resolved.is_file():
            problems.append(f"{md.name}:{index + 1}: excerpt source missing: {path_part}")
            continue
        if not str(resolved).endswith(shown_path):
            problems.append(f"{md.name}:{index + 1}: label path {shown_path} differs from link {path_part}")
        # The fenced block must follow, optionally after one blank line.
        j = index + 1
        if j < len(lines) and not lines[j].strip():
            j += 1
        if j >= len(lines) or not FENCE.match(lines[j]):
            problems.append(f"{md.name}:{index + 1}: 📍 label is not followed by a code block")
            continue
        block = []
        k = j + 1
        while k < len(lines) and not FENCE.match(lines[k]):
            block.append(lines[k].rstrip())
            k += 1
        source = [l.rstrip() for l in resolved.read_text(encoding="utf-8").splitlines()]
        wanted = source[start - 1:end]
        if block != wanted:
            first_diff = next(
                (n for n, (a, b) in enumerate(zip(block, wanted)) if a != b),
                min(len(block), len(wanted)),
            )
            problems.append(
                f"{md.name}:{index + 1}: excerpt differs from {path_part}:{start}-{end} "
                f"(first difference at excerpt line {first_diff + 1}; "
                f"{len(block)} lines shown, {len(wanted)} cited)"
            )
        checked += 1
    return checked


def check_template(md: Path, lines: list[str], problems: list[str]) -> None:
    headings = [l[3:].strip() for l in lines if l.startswith("## ")]
    for section in LESSON_SECTIONS:
        if not any(section in h for h in headings):
            problems.append(f"{md.name}: missing section '## … {section}'")
    text = "\n".join(lines)
    if "> **Goal:**" not in text:
        problems.append(f"{md.name}: missing '> **Goal:**' header line")
    if "**Next:**" not in text:
        problems.append(f"{md.name}: missing '**Next:**' footer")


def source_files() -> set[Path]:
    found: set[Path] = set()
    for pattern in SOURCE_GLOBS:
        for path in REPO_ROOT.glob(pattern):
            if path.relative_to(REPO_ROOT).as_posix() not in SKIP_SOURCES:
                found.add(path.resolve())
    return found


def main(argv: list[str]) -> int:
    whole_course = not argv
    pages = sorted(COURSE_DIR.glob("*.md")) if whole_course else [COURSE_DIR / a for a in argv]
    problems: list[str] = []
    linked: set[Path] = set()
    excerpts = 0
    for md in pages:
        if not md.is_file():
            problems.append(f"{md.name}: file not found")
            continue
        lines = md.read_text(encoding="utf-8").splitlines()
        in_code = split_blocks(lines)
        check_links(md, lines, in_code, problems, linked)
        excerpts += check_excerpts(md, lines, problems)
        if re.match(r"^\d\d-", md.name):
            check_template(md, lines, problems)

    if whole_course:
        for path in sorted(source_files() - linked):
            problems.append(f"coverage: {path.relative_to(REPO_ROOT)} is not linked from any page")

    for problem in problems:
        print(problem)
    print(f"\nChecked {len(pages)} page(s), {excerpts} excerpt(s): "
          f"{'OK' if not problems else f'{len(problems)} problem(s)'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
