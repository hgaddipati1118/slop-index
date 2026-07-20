# Human baselines

The Slop Index measures each model against **real human writing that provably predates ChatGPT
(before Oct 2022)**, so no model could have shaped the reference. This directory ships only the
**derived statistics** the scorer reads, `<domain>/stats.json` (word-frequency tables, tell rates,
paragraph-variance means, etc.). The raw corpora are **not** redistributed: they are large (~1.4GB)
and carry their own third-party licenses. Rebuild them from source with the steps below.

`docs/DATASETS.md` is the full provenance report (sources, licenses, status, rejects). Summary of
the primary sources actually used:

| Domain | Primary corpus | Source | License |
|---|---|---|---|
| Email | **EnronSent** (cleaned Enron subset) | http://wstyler.ucsd.edu/files/enronsentv1.tar.gz | Public domain (cite Styler 2011) |
| Essay | **Blog Authorship Corpus** + **ASAP-AES** | HF `barilan/blog_authorship_corpus`; Kaggle `asap-aes` | Blog: non-commercial research; ASAP: competition rules. Prefer **PERSUADE 2.0** (CC BY 4.0) if commercial |
| Social | **Sentiment140** (2009 tweets) + archived Twitter Stream | HF `stanfordnlp/sentiment140`; archive.org Twitter Stream Grab | 15+ yr academic use; publish derived stats only |
| Chat | **DISCO** Discord corpus | (see DATASETS.md) | derived stats only |

## Rebuild `stats.json` from source

For each domain:

1. **Download** the raw corpus into `baselines/<domain>/raw/` (URLs above / in `DATASETS.md`).
2. **Filter** to clean, pre-Oct-2022, register-appropriate text:
   ```bash
   python baselines/<domain>/filter.py        # -> baselines/<domain>/clean.jsonl (+ filter_funnel.json)
   ```
   Each `filter.py` handles dedup, date cutoffs, length/register filters, and PII stripping for its
   corpus. `filter_funnel.json` (committed) records how many rows survived each stage.
3. **Compute stats:**
   ```bash
   python baselines/compute_stats.py          # -> baselines/<domain>/stats.json
   ```
   `compare_pilot.py` diffs baseline stats against a model run (used during design).

## Non-negotiable rules

- **Pre-Oct-2022 only.** If you can't prove a text predates ChatGPT, drop it.
- **Never redistribute corpus text.** Commit derived stats only; the raw `clean.jsonl` and `raw/`
  are gitignored on purpose.
- **No `wordfreq` / no post-2022 frequency tables** as the reference, they are contaminated with
  model output and will silently deflate the tell signal. This bit us once; see
  `docs/PILOT_FINDINGS.md`.
