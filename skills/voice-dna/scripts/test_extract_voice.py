"""Tests for the voice-dna extractor. No network. Stdlib only."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import extract_voice as ev  # noqa: E402


class SkeletonTests(unittest.TestCase):
    def test_masks_content_words_and_keeps_function_words(self) -> None:
        skeleton = ev.skeleton("I don't think so.")
        self.assertEqual(skeleton, "I don't · so.")
        self.assertNotIn("think", skeleton)

    def test_keeps_punctuation_tight(self) -> None:
        skeleton = ev.skeleton("I keep the draft until Friday.")
        self.assertEqual(skeleton, "I · the · until ·.")
        self.assertNotIn("Friday", skeleton)
        self.assertNotIn("draft", skeleton)


class MannerismTests(unittest.TestCase):
    def test_repeated_frame_kept_topic_words_dropped(self) -> None:
        text = (
            "I don't think the xylophone should restart tonight. "
            "I don't think the xylophone should restart today."
        )
        patterns = [row["pattern"] for row in ev.mannerism_patterns(ev.words(text))]
        self.assertIn("i don't ·", patterns)
        blob = " ".join(patterns)
        self.assertNotIn("xylophone", blob)

    def test_generic_determiner_frame_dropped(self) -> None:
        text = "and the server crashed. and the server restarted."
        patterns = [row["pattern"] for row in ev.mannerism_patterns(ev.words(text))]
        self.assertNotIn("and the ·", patterns)

    def test_repeated_idiom_kept(self) -> None:
        text = (
            "The thing is we left early. Later, the thing is we came back."
        )
        patterns = [row["pattern"] for row in ev.mannerism_patterns(ev.words(text))]
        self.assertIn("the thing is", patterns)


class StatsTests(unittest.TestCase):
    def test_sentence_lengths(self) -> None:
        text = "Cats sleep. Dogs run fast. Birds fly high above trees and houses."
        stats = ev.stats_from_text(text)
        self.assertEqual(stats["sentence_words"]["count"], 3)
        self.assertEqual(stats["sentence_words"]["mean"], 4.0)
        self.assertEqual(stats["sentence_words"]["median"], 3.0)

    def test_code_fences_do_not_enter_the_profile(self) -> None:
        text = (
            "I don't think the plan holds. I don't think the plan holds at all.\n\n"
            "```\nxylophone xylophone xylophone\n```\n"
        )
        cleaned = ev.strip_noise(text)
        self.assertNotIn("xylophone", cleaned)
        self.assertIn("plan", cleaned)


class ScanTests(unittest.TestCase):
    def test_skips_node_modules_and_splits_raw_samples(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prose = (
                "I don't think the xylophone should restart tonight because it failed. "
                "I don't think the xylophone should restart today because it failed again. "
                "We waited. Then we checked the logs and went home without another try."
            )
            (root / "note.txt").write_text(prose, encoding="utf-8")
            nested = root / "node_modules"
            nested.mkdir()
            (nested / "junk.txt").write_text(
                "NODEONLYMARKER " * 30, encoding="utf-8"
            )
            out = root / "profile.json"
            summary = ev.scan_paths([root], out, min_words=20)
            profile = json.loads(out.read_text(encoding="utf-8"))
            samples = json.loads((root / "samples.json").read_text(encoding="utf-8"))
            self.assertGreaterEqual(summary["files"], 1)
            self.assertNotIn("NODEONLYMARKER", out.read_text(encoding="utf-8"))
            self.assertNotIn("xylophone", out.read_text(encoding="utf-8"))
            self.assertNotIn("node_modules", json.dumps(profile["sources"]))
            self.assertTrue(any("xylophone" in row["text"] for row in samples["exemplars"]))
            self.assertTrue(all("skeleton" in row for row in profile["exemplars"]))

    def test_pdf_goes_through_pdftotext(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "paper.pdf"
            pdf.write_bytes(b"%PDF-1.1 fake")
            out = Path(tmp) / "profile.json"

            def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                self.assertEqual(cmd[0], "pdftotext")
                self.assertIn(str(pdf), cmd)
                return subprocess.CompletedProcess(
                    cmd,
                    0,
                    stdout="I don't think the plan holds today. " * 8,
                    stderr="",
                )

            with mock.patch.object(ev.subprocess, "run", side_effect=fake_run):
                summary = ev.scan_paths([pdf], out, min_words=20)
            self.assertEqual(summary["files"], 1)
            profile = json.loads(out.read_text(encoding="utf-8"))
            self.assertGreater(profile["stats"]["words"], 20)


class ScoreTests(unittest.TestCase):
    def test_flags_sentence_length_far_from_profile(self) -> None:
        profile = {
            "version": 1,
            "stats": {
                "words": 2000,
                "sentence_words": {"mean": 12.0, "median": 11.0, "pct_short": 0.2, "pct_long": 0.1},
                "per_1000_words": {
                    "em_dash": 0.5,
                    "contraction": 20.0,
                    "first_person": 25.0,
                },
            },
        }
        draft = " ".join(
            [
                "Additionally this extremely long sentence keeps going and going with more "
                "clauses attached while the writer refuses to stop and adds another handful "
                "of words before the period."
            ]
            * 4
        )
        report = ev.score_text(profile, draft)
        flagged = {row["name"] for row in report["metrics"] if row["off"]}
        self.assertIn("sentence_words_mean", flagged)


if __name__ == "__main__":
    unittest.main()
