---
name: voice-dna
description: |
  Rewrite text in a specific person's mannerisms instead of generic "human" or
  Wikipedia-plain prose. Use this whenever the user wants their own voice,
  personal style, voice transfer, Voice DNA, mannerisms, or a humanizer pass
  that sounds like them rather than like a cleaned-up chatbot. Also use it when
  they mention blader/humanizer, AI-isms, writing samples, uploaded papers,
  PDFs, or txt files as style references, few-shot rhythm, or "make this sound
  like me." Scans a local corpus on macOS or Linux (txt, md, pdf, and on macOS
  docx/rtf/html) with a script that needs no API token, builds a mannerism
  profile, and replaces AI patterns with that profile's rhythm.
license: MIT
metadata:
  version: "1.0.0"
---

# Voice DNA

Generic humanizer deletes AI tells and replaces them with plain prose. Plain prose is still a model voice: even sentence lengths, no contractions, no first person, no odd punctuation. This skill replaces the tells with mannerisms measured from the user's own writing.

The measurement script does not call a model and does not need an API token. The rewrite still happens in the agent, but the profile is the constraint, not a vibe.

## What the profile is

`~/.config/voice-dna/profile.json` stores rhythm only:

- sentence-length mean, median, and the share of short and long sentences
- em dashes, contractions, and first person, each per 1,000 words
- repeated function-word frames (`i don't ·`), not repeated topics
- up to three exemplar **skeletons**, where `·` stands for a content word

`samples.json` next to the profile holds the raw paragraphs those skeletons came from. That file exists so a person can audit the scan. Opening it during a rewrite teaches the model the corpus's subjects, and the model will copy the nouns. Leave it closed unless the user asks to inspect the profile.

## Build or refresh the profile

Do this when the user hands you files, a folder, or pasted samples, or when they say the profile is stale. Do not scan the home directory, mail, or `~/Library` unless they named that path.

```bash
python3 ~/.claude/skills/voice-dna/scripts/extract_voice.py scan \
  /path/to/writing /path/to/paper.pdf \
  --out ~/.config/voice-dna/profile.json
```

Pasted samples and uploads: write them to a temp `.txt` (or keep the PDF), scan that path, then delete the temp file. The profile stays. Stdin works too: `--stdin --out ~/.config/voice-dna/profile.json`.

Accepted inputs: `.txt`, `.md`, `.markdown`, `.pdf` (via `pdftotext`). On macOS, `.docx`, `.rtf`, and `.html` go through `textutil`. Directories are walked. `node_modules`, `.git`, virtualenvs, and `Library` are skipped. Fenced code blocks are stripped before measuring, so a repo of notes does not train the profile on source code.

If the summary says `"thin": true` (under 800 words), say so in one line and still rewrite. A thin profile is a weak prior, not a reason to fall back to generic humanizer prose.

Reuse an existing profile when the user did not pass new samples.

## Rewrite

1. Read `profile.json`. Do not read the source corpus and do not read `samples.json`.
2. Read `~/.claude/skills/humanizer/SKILL.md` as a **detection** list. The numbered patterns are what to remove. The "After" examples are the wrong replacement voice: they are neutral on purpose.
3. Draft a rewrite that keeps every fact, name, number, date, and citation in the source. Do not invent any. Opinions already in the source may stay. Do not add new factual claims to create personality.
4. Match the profile, not a caricature of it.
   - Sentence-length mean and the short/long mix should land near `stats`. Vary length the way `pct_short` and `pct_long` say. Do not make every sentence the mean.
   - If `first_person` per 1,000 words is under 2, do not add "I". If it is high and the draft has none, first person is allowed only as stance on claims already present.
   - Match contraction rate and em-dash rate. A profile that uses em dashes overrides humanizer §14. A profile near zero means cut them.
   - Mannerism frames are habits, not a quota. Use one when it carries a sentence that was an AI tell. Sprinkling every frame is how a rewrite becomes a parody.
5. Few-shot from `exemplars[].skeleton` only. Each `·` is a word you supply from the **draft's** meaning. If a content word is not in the draft, it does not belong in the rewrite, even if you remember it from somewhere else.
6. Run the detector. Thresholds live in the script; do not re-judge them by feel.

```bash
python3 ~/.claude/skills/voice-dna/scripts/extract_voice.py score \
  --profile ~/.config/voice-dna/profile.json \
  --file /path/to/draft.txt
```

Stdin works: pipe the draft with `--stdin`. If any metric has `"off": true`, revise once and score again. Then stop. A second sanding pass pulls the prose back toward neutral.

Leave code blocks, frontmatter, link targets, and quoted text alone. Humanize the prose around them.

## Why skeletons instead of sample paragraphs

A raw paragraph teaches the subject and the rhythm together. Asked to "write like this," a model copies the nouns, the names, and the claims, then still sounds like itself in the sentences that are new. Masking content words leaves the cadence: where the pronouns sit, how soon the sentence turns, which little words it leans on. The draft, not the corpus, fills the blanks.

## Output

**Pasted text.** Deliver the final prose, then one line listing metric names that were still `off` after the revision. No pattern lecture.

**File.** Rewrite the file so it contains only the final prose. In the conversation, give that same one-line score note.

**Embedded.** Another task asked for prose. Return only the final prose. Still run the score internally.

## Check the script

From the skill directory:

```bash
python3 -m unittest scripts/test_extract_voice.py
```
