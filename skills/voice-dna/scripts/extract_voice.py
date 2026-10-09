#!/usr/bin/env python3
"""Measure writing mannerisms from local files. No network and no API token.

The profile stores rhythm: sentence length, punctuation rates, function-word
frames, and skeletons. Content words are masked so a later rewrite can copy
cadence without copying the corpus's subjects.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

FUNCTION: frozenset[str] = frozenset(
    """
    a an the
    and or but nor so yet
    of to in on at by from with as into over after before about
    between through during without within until than then for
    that this these those
    it its it's
    i me my mine myself i'm i've i'd i'll
    we our ours ourselves we're we've we'd we'll
    you your yours yourself you're you've you'd you'll
    he him she her hers they them their his
    who whom whose which what when where why how
    if because while although though unless since whether
    not no don't doesn't didn't isn't aren't wasn't weren't
    won't can't couldn't shouldn't wouldn't haven't hasn't hadn't
    do does did be is am are was were been being
    have has had will would can could should may might must shall
    just only also even still already always never often sometimes
    maybe perhaps really very too here there now again once
    oh well
    """.split()
)

PRONOUNS: frozenset[str] = frozenset(
    """
    i me my mine myself we our ours you your yours he him she her hers
    they them their his who whom whose which it its
    i'm i've i'd i'll we're we've you're you've it's
    """.split()
)
NEGATIONS: frozenset[str] = frozenset(
    """
    not no don't doesn't didn't isn't aren't wasn't weren't
    won't can't couldn't shouldn't wouldn't haven't hasn't hadn't
    """.split()
)
CONJUNCTIONS: frozenset[str] = frozenset(
    "and but or nor so yet because although though while if unless whether since".split()
)
DISCOURSE: frozenset[str] = frozenset(
    "maybe perhaps still already really actually honestly".split()
)
GENERIC: frozenset[str] = frozenset(
    line.strip()
    for line in """
    and the ·
    or the ·
    in the ·
    of the ·
    to the ·
    on the ·
    for the ·
    the · of
    a · of
    an · of
    it is ·
    this is ·
    that is ·
    there is ·
    """.splitlines()
    if line.strip()
)
IDIOMS: frozenset[tuple[str, ...]] = frozenset(
    {
        ("which", "is", "to", "say"),
        ("the", "thing", "is"),
        ("mind", "you"),
        ("as", "it", "were"),
        ("sort", "of"),
        ("kind", "of"),
    }
)
FIRST_PERSON: frozenset[str] = frozenset(
    "i me my mine myself i'm i've i'd i'll".split()
)

TEXT_SUFFIXES: frozenset[str] = frozenset({".txt", ".md", ".markdown", ".text"})
PDF_SUFFIXES: frozenset[str] = frozenset({".pdf"})
TEXTUTIL_SUFFIXES: frozenset[str] = frozenset({".docx", ".rtf", ".html", ".htm"})
SKIP_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        "node_modules",
        "venv",
        ".venv",
        "dist",
        "build",
        "__pycache__",
        ".Trash",
        "Library",
    }
)
TOKEN_RE = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)?|[^\s\w]", re.UNICODE)
WORD_RE = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)?", re.UNICODE)
NO_SPACE_BEFORE: frozenset[str] = frozenset(list(".,;:!?%)]}"))
MAX_BYTES = 2_000_000
SHORT_SENTENCE = 8
LONG_SENTENCE = 25
MEAN_OFF = 5.0
SHORT_OFF = 0.2
EM_DASH_OFF = 3.0
CONTRACTION_OFF = 10.0


def norm_word(token: str) -> str:
    return token.replace("’", "'").replace("‘", "'").lower()


def words(text: str) -> list[str]:
    return [norm_word(match) for match in WORD_RE.findall(text)]


def strip_noise(text: str) -> str:
    """Drop markup that would masquerade as prose."""
    if text.startswith("---\n"):
        text = re.sub(r"^---\n.*?\n---\n", "", text, count=1, flags=re.DOTALL)
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`[^`\n]+`", " ", text)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def split_paragraphs(text: str) -> list[str]:
    parts = re.split(r"\n\s*\n", text.strip())
    return [part.strip() for part in parts if part.strip()]


def _is_word_token(token: str) -> bool:
    return bool(WORD_RE.fullmatch(token))


def detokenize(tokens: list[str]) -> str:
    if not tokens:
        return ""
    out = tokens[0]
    for token in tokens[1:]:
        previous = out[-1] if out else ""
        if token in NO_SPACE_BEFORE or (previous and previous in "([{\"'“"):
            out += token
        else:
            out += " " + token
    return out


def skeleton(text: str) -> str:
    """Keep function words and punctuation. Replace content words with ·."""
    rendered: list[str] = []
    for token in TOKEN_RE.findall(text):
        if _is_word_token(token):
            rendered.append(token if norm_word(token) in FUNCTION else "·")
        else:
            rendered.append(token)
    return detokenize(rendered)


def _qualifies(pattern: tuple[str, ...]) -> bool:
    function_tokens = [token for token in pattern if token != "·"]
    if len(function_tokens) < 2:
        return False
    if pattern.count("·") / len(pattern) > 0.5:
        return False
    joined = " ".join(pattern)
    if joined.strip() in GENERIC or joined in GENERIC:
        return False
    return any(
        token in PRONOUNS or token in NEGATIONS or token in CONJUNCTIONS or token in DISCOURSE
        for token in function_tokens
    )


def mannerism_patterns(tokens: list[str], min_count: int = 2) -> list[dict[str, object]]:
    """Repeated frames such as 'i don't ·', not repeated topics."""
    counts: Counter[str] = Counter()
    upper = len(tokens)
    for size in (2, 3, 4, 5):
        if upper < size:
            continue
        for index in range(upper - size + 1):
            gram = tuple(tokens[index : index + size])
            if gram in IDIOMS:
                counts[" ".join(gram)] += 1
                continue
            if size < 3:
                continue
            masked = tuple(token if token in FUNCTION else "·" for token in gram)
            if _qualifies(masked):
                counts[" ".join(masked)] += 1
    rows: list[dict[str, object]] = [
        {"pattern": pattern, "count": count}
        for pattern, count in counts.most_common()
        if count >= min_count
    ]
    return rows[:15]


def _median(values: list[int]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _per_1000(count: int, total_words: int) -> float:
    if total_words <= 0:
        return 0.0
    return round(1000.0 * count / total_words, 2)


def stats_from_text(text: str) -> dict[str, object]:
    cleaned = strip_noise(text)
    sentences = split_sentences(cleaned)
    lengths = [len(words(sentence)) for sentence in sentences]
    lengths = [length for length in lengths if length > 0]
    token_list = words(cleaned)
    total = len(token_list)
    em_dashes = cleaned.count("—") + cleaned.count("--")
    contractions = sum(1 for token in token_list if "'" in token)
    first_person = sum(1 for token in token_list if token in FIRST_PERSON)
    short = sum(1 for length in lengths if length <= SHORT_SENTENCE)
    long = sum(1 for length in lengths if length >= LONG_SENTENCE)
    sentence_count = len(lengths)
    mean = round(sum(lengths) / sentence_count, 2) if sentence_count else 0.0
    return {
        "words": total,
        "sentence_words": {
            "count": sentence_count,
            "mean": mean,
            "median": _median(lengths),
            "pct_short": round(short / sentence_count, 3) if sentence_count else 0.0,
            "pct_long": round(long / sentence_count, 3) if sentence_count else 0.0,
        },
        "per_1000_words": {
            "em_dash": _per_1000(em_dashes, total),
            "contraction": _per_1000(contractions, total),
            "first_person": _per_1000(first_person, total),
        },
    }


def _mean(values: list[int]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def pick_exemplars(text: str) -> list[dict[str, object]]:
    """Three rhythm buckets. Raw text stays out of the profile."""
    candidates: list[tuple[float, str]] = []
    for paragraph in split_paragraphs(text):
        sentences = split_sentences(paragraph)
        lengths = [len(words(sentence)) for sentence in sentences if words(sentence)]
        total = sum(lengths)
        if len(lengths) < 2 or total < 30 or total > 160:
            continue
        candidates.append((_mean(lengths), paragraph))
    if not candidates:
        return []
    candidates.sort(key=lambda item: item[0])
    chosen_indexes = {0, len(candidates) // 2, len(candidates) - 1}
    buckets = {0: "short", len(candidates) // 2: "mid", len(candidates) - 1: "long"}
    exemplars: list[dict[str, object]] = []
    seen: set[str] = set()
    for index in sorted(chosen_indexes):
        mean_length, paragraph = candidates[index]
        if paragraph in seen:
            continue
        seen.add(paragraph)
        exemplars.append(
            {
                "bucket": buckets[index],
                "sentence_words_mean": round(mean_length, 2),
                "skeleton": skeleton(paragraph),
                "text": paragraph,
            }
        )
    return exemplars


def _read_pdf(path: Path) -> str:
    if shutil.which("pdftotext") is None:
        raise RuntimeError(f"pdftotext is not installed; cannot read {path.name}")
    proc = subprocess.run(
        ["pdftotext", "-q", "-enc", "UTF-8", "-layout", str(path), "-"],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or "").strip() or f"pdftotext failed for {path}"
        raise RuntimeError(detail)
    return proc.stdout


def _read_textutil(path: Path) -> str:
    if shutil.which("textutil") is None:
        raise RuntimeError(f"textutil is not available; cannot read {path.name}")
    proc = subprocess.run(
        ["textutil", "-convert", "txt", "-stdout", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or "").strip() or f"textutil failed for {path}"
        raise RuntimeError(detail)
    return proc.stdout


def read_document(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in PDF_SUFFIXES:
        return _read_pdf(path)
    if suffix in TEXTUTIL_SUFFIXES:
        return _read_textutil(path)
    return path.read_text(encoding="utf-8", errors="replace")


def iter_documents(paths: list[Path]) -> list[Path]:
    found: list[Path] = []
    allowed = TEXT_SUFFIXES | PDF_SUFFIXES | TEXTUTIL_SUFFIXES
    for path in paths:
        if path.is_file():
            if path.suffix.lower() in allowed:
                found.append(path)
            continue
        if not path.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(path, followlinks=False):
            dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS and not name.startswith(".")]
            for filename in filenames:
                candidate = Path(dirpath) / filename
                if candidate.suffix.lower() in allowed and not candidate.is_symlink():
                    found.append(candidate)
    return found


def _document_text(path: Path) -> str:
    if path.stat().st_size > MAX_BYTES:
        raise RuntimeError(f"{path} is larger than {MAX_BYTES} bytes")
    return strip_noise(read_document(path))


def build_profile(documents: list[tuple[str, str]]) -> tuple[dict[str, object], dict[str, object]]:
    chunks = [text for _, text in documents if text.strip()]
    combined = "\n\n".join(chunks)
    token_list = words(combined)
    exemplars = pick_exemplars(combined)
    profile: dict[str, object] = {
        "version": 1,
        "sources": [{"path": label, "words": len(words(text))} for label, text in documents],
        "stats": stats_from_text(combined),
        "mannerisms": mannerism_patterns(token_list),
        "exemplars": [
            {
                "bucket": row["bucket"],
                "sentence_words_mean": row["sentence_words_mean"],
                "skeleton": row["skeleton"],
            }
            for row in exemplars
        ],
    }
    samples: dict[str, object] = {
        "exemplars": [{"bucket": row["bucket"], "text": row["text"]} for row in exemplars]
    }
    return profile, samples


def scan_paths(paths: list[Path], out: Path, min_words: int = 40) -> dict[str, object]:
    documents: list[tuple[str, str]] = []
    warnings: list[str] = []
    for path in iter_documents(paths):
        try:
            text = _document_text(path)
        except (OSError, RuntimeError, UnicodeError) as exc:
            warnings.append(f"{path}: {exc}")
            continue
        if len(words(text)) < min_words:
            continue
        documents.append((str(path), text))
    if not documents:
        raise SystemExit("no prose found (need txt, md, or pdf with enough words)")
    profile, samples = build_profile(documents)
    profile["warnings"] = warnings
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    samples_path = out.parent / "samples.json"
    samples_path.write_text(json.dumps(samples, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    stats = profile["stats"]
    assert isinstance(stats, dict)
    word_count = int(stats["words"])
    return {
        "files": len(documents),
        "words": word_count,
        "profile": str(out),
        "samples": str(samples_path),
        "thin": word_count < 800,
    }


def score_text(profile: dict[str, object], text: str) -> dict[str, object]:
    draft = stats_from_text(text)
    raw_stats = profile.get("stats")
    if not isinstance(raw_stats, dict):
        raise SystemExit("profile is missing stats")
    sentence = raw_stats.get("sentence_words")
    rates = raw_stats.get("per_1000_words")
    draft_sentence = draft["sentence_words"]
    draft_rates = draft["per_1000_words"]
    if not isinstance(sentence, dict) or not isinstance(rates, dict):
        raise SystemExit("profile stats are incomplete")
    if not isinstance(draft_sentence, dict) or not isinstance(draft_rates, dict):
        raise SystemExit("draft stats are incomplete")

    def metric(name: str, profile_value: float, draft_value: float, off: bool) -> dict[str, object]:
        return {
            "name": name,
            "profile": profile_value,
            "draft": draft_value,
            "delta": round(draft_value - profile_value, 2),
            "off": off,
        }

    p_mean = float(sentence.get("mean", 0.0))
    d_mean = float(draft_sentence.get("mean", 0.0))
    p_short = float(sentence.get("pct_short", 0.0))
    d_short = float(draft_sentence.get("pct_short", 0.0))
    p_dash = float(rates.get("em_dash", 0.0))
    d_dash = float(draft_rates.get("em_dash", 0.0))
    p_contraction = float(rates.get("contraction", 0.0))
    d_contraction = float(draft_rates.get("contraction", 0.0))
    p_first = float(rates.get("first_person", 0.0))
    d_first = float(draft_rates.get("first_person", 0.0))
    first_off = (p_first > 15 and d_first < 2) or (p_first < 2 and d_first > 15)
    profile_words = int(raw_stats.get("words", 0))
    return {
        "words": draft["words"],
        "profile_words": profile_words,
        "thin_profile": profile_words < 800,
        "metrics": [
            metric("sentence_words_mean", p_mean, d_mean, abs(d_mean - p_mean) > MEAN_OFF),
            metric("pct_short", p_short, d_short, abs(d_short - p_short) > SHORT_OFF),
            metric("em_dash_per_1000", p_dash, d_dash, d_dash > p_dash + EM_DASH_OFF),
            metric(
                "contraction_per_1000",
                p_contraction,
                d_contraction,
                abs(d_contraction - p_contraction) > CONTRACTION_OFF,
            ),
            metric("first_person_per_1000", p_first, d_first, first_off),
        ],
    }


def _scan_stdin(out: Path, min_words: int) -> dict[str, object]:
    text = strip_noise(sys.stdin.read())
    if len(words(text)) < min_words:
        raise SystemExit("no prose found on stdin")
    profile, samples = build_profile([("<stdin>", text)])
    profile["warnings"] = []
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    samples_path = out.parent / "samples.json"
    samples_path.write_text(json.dumps(samples, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    stats = profile["stats"]
    assert isinstance(stats, dict)
    word_count = int(stats["words"])
    return {
        "files": 1,
        "words": word_count,
        "profile": str(out),
        "samples": str(samples_path),
        "thin": word_count < 800,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="extract_voice")
    sub = parser.add_subparsers(dest="cmd", required=True)

    scan = sub.add_parser("scan", help="build a mannerism profile from files")
    scan.add_argument("paths", nargs="*", type=Path)
    scan.add_argument("--stdin", action="store_true")
    scan.add_argument("--out", type=Path, required=True)
    scan.add_argument("--min-words", type=int, default=40)

    score = sub.add_parser("score", help="compare a draft to a profile")
    score.add_argument("--profile", type=Path, required=True)
    score.add_argument("--file", type=Path)
    score.add_argument("--stdin", action="store_true")

    args = parser.parse_args(argv)
    if args.cmd == "scan":
        if args.stdin:
            summary = _scan_stdin(args.out, args.min_words)
        elif args.paths:
            summary = scan_paths(args.paths, args.out, args.min_words)
        else:
            raise SystemExit("pass file or directory paths, or --stdin")
        print(json.dumps(summary, indent=2))
        return 0

    if not args.profile.is_file():
        raise SystemExit(f"profile not found: {args.profile}")
    profile = json.loads(args.profile.read_text(encoding="utf-8"))
    if not isinstance(profile, dict):
        raise SystemExit("profile JSON must be an object")
    if args.stdin:
        draft = sys.stdin.read()
    elif args.file is not None:
        draft = args.file.read_text(encoding="utf-8")
    else:
        raise SystemExit("pass --file or --stdin")
    print(json.dumps(score_text(profile, draft), indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:
        raise SystemExit(0) from None
