# The Slop Index — Dataset Research Report (verified July 2026)

All links verified live (or verified dead) via web search + fetch in July 2026. "Provenance-clean" = provably written pre-Nov-2022 (ChatGPT launch); most primaries predate it by a decade or more.

> **⚠️ Domain-4 update (post-research)**: the fourth domain changed from personal texts/SMS to **Slack/workplace chat**. Consequence: **DISCO Discord corpus (§4, verified live on Zenodo) is promoted to domain-4 primary**, with Ubuntu Dialogue IRC as supplement; **NUS SMS is demoted to supplement** (personal-SMS register). Two additional Slack-register candidates were NOT verified by this research pass and need checking: **GitterCom corpus** (Gitter developer-chat dataset, MSR) and **public Zulip archives** (e.g., Rust/Lean communities, pre-2022 slices).
>
> **⚠️ Social-baseline update (post-research)**: social ratio-baseline pivoted from Reddit-primary to **Twitter-primary** — Sentiment140 (2009) + archive.org Twitter Stream slices (prefer 2018 = post-280-char register; publish derived stats only, never redistribute tweet text). Rationale: X-style scenarios match the tweet register directly, the launch audience is on X, and it drops the ~2TB Pushshift torrent (and Reddit litigation-climate footnote) from the critical path. **Pushshift Reddit demoted to optional supplement** (small per-subreddit slices only); HN BigQuery remains the clean timestamped supplement. LinkedIn flavors unchanged (tell-rate + human votes, no ratio baseline).

---

## 0b. Detector-evasion / humanizer notes (added post-research)

Checked `github.com/AnonymousBazinga/humanizer` (July 2026): **404, zero Wayback snapshots, zero citations anywhere** — either deleted, private, or never public. Not citable; nothing usable. Relevant live sources found instead:

- **Pangram's own humanizer audit (Aug 2025)** — https://www.pangram.com/blog/humanizers-aug-25 — vendor-run, weight accordingly: claims >90% accuracy against 19 commercial humanizers, and cites third-party figures of Pangram 97% vs GPTZero 46% vs **Binoculars 7%** on humanized text. Implication for us: our open cross-check (Binoculars) is the brittle one under humanization, Pangram is not. v1 scores RAW model output so this doesn't affect the board, but it's the stated limitation if we ever add a humanizer-robustness column, and Binoculars disagreement on any future humanized set is expected behavior, not a contradiction.
- **Prior art to cite for detector evasion**: DAMAGE (arXiv:2501.03437, ACL GenAIDetect 2025) · "Humanizing Machine-Generated Content" (arXiv:2404.01907) · "Humanizing the Machine: Proxy Attacks to Mislead LLM Detectors" (arXiv:2410.19230) · "Detector-Evasive LLM Paraphrasing via Constrained Policy Optimization" (arXiv:2606.00392 — tests Binoculars/RADAR/Fast-DetectGPT, notably not Pangram).
- The June 2026 Nature-covered "Humanizer" academic-writing tool (Jie Ding, U. Minnesota; github.com/AIScientists-Dev/academic-humanizer) is a different thing; Pangram's CEO publicly claims Pangram still catches most of its output.

Potential sequel: a **"Humanizer column"** — run each model's outputs through a top commercial humanizer and report the Slop Score delta ("$X/mo to look human"). Adversarial, newsworthy, and tests the detector where it's actually contested.

## 1. EMAIL baselines

### Enron Email Corpus — CMU canonical ⭐ PRIMARY
- **Contents**: Raw maildir dumps from 150 Enron custodians (inbox/sent/deleted/personal folders); real corporate + personal register.
- **Size**: ~500K–517K messages; `enron_mail_20150507.tar.gz` (~423MB–1.7GB compressed, ~1.4–1.7GB unpacked).
- **Years**: 1999–2002 (FERC era; public since 2003).
- **Download**: https://www.cs.cmu.edu/~enron/ — **confirmed live**, still serving the 2015-05-07 tarball.
- **License**: Free, no registration, effectively public domain.
- **Gotchas**: No dedup; massive forward/duplicate chains; raw headers.
- **Fit**: **Primary.**

### EnronSent (cleaned subset) ⭐ PRIMARY
- **Contents**: Sent-mail folders only, headers/signatures/forward-cruft stripped — pure human-authored prose. Sent-only guarantees the custodian actually wrote the text.
- **Size**: 96,107 messages / 13.8M words / 25MB tar.gz.
- **Download**: http://wstyler.ucsd.edu/files/enronsentv1.tar.gz (landing: https://wstyler.ucsd.edu/enronsent/) — **confirmed live**.
- **License**: Public domain; cite Styler (2011).
- **Gotchas**: Sender identity and thread structure stripped — fine for style, useless for threading.
- **Fit**: **Primary** (best variant for the style baseline).

### Enron — Kaggle mirror — SUPPLEMENT
- Single 1.43GB `emails.csv` (500K+ rows) at https://www.kaggle.com/datasets/wcukierski/enron-email-dataset. `jivfur` re-upload adds **thread keys** (useful for scenario mining). Cite back to CMU.

### Avocado Research Email Collection (LDC2015T03) — SUPPLEMENT
- 2,033,740 items (614,461 emails), defunct IT company, mid-2000s. https://catalog.ldc.upenn.edu/LDC2015T03. Organizational License + EUA; fee login-gated (LDC text corpora typically ~$250–$3,000+ non-member). PII redacted; ~27 messages contain live ILOVEYOU malware. Second corporate source if budget allows.

### W3C Corpus (TREC Enterprise) — SUPPLEMENT
- ~174K parsed mailing-list emails (June 2004 crawl). NIST hosting **gone**; working mirror: https://tides.umiacs.umd.edu/webtrec/trecent/parsed_w3c_corpus.html + Cornell derivative https://www.cs.cornell.edu/~arb/data/pvc-email-W3C/. CJK encoding damage in parts 2–3. Dev-list register.

### Hillary Clinton emails — REJECT
- 7,945 OCR'd FOIA emails, heavily redacted, OCR artifacts, single public figure.

### Apache/LKML mailing list archives — SUPPLEMENT
- https://lists.apache.org/ mbox API (`api/mbox.lua?list=...&d=YYYY-MM`); LKML via https://lore.kernel.org/. Unlimited pre-2022 volume but self-assembled; dev register only.

### TREC 2007 Spam Corpus (ham subset) — SUPPLEMENT
- 25,220 ham. **UWaterloo canonical link dead (404)**; mirrors on Kaggle (`bayes2003/emails-for-spam-or-ham-classification-trec-2007`) and GitHub. Weakened provenance chain.

---

## 2. ESSAY/LONG-FORM baselines

### Blog Authorship Corpus (Schler et al.) ⭐ PRIMARY
- 681,288 posts / 19,320 blogger.com users / 140M+ words, age/gender/industry metadata. Scraped **August 2004**.
- Original live: https://u.cs.biu.ac.il/~koppel/BlogCorpus.htm; HF mirror https://huggingface.co/datasets/barilan/blog_authorship_corpus (960MB); Kaggle `rtatman/blog-authorship-corpus`.
- **License: free non-commercial research** — NC clause matters if Slop Index is commercial. Cite Schler et al. 2006.

### ASAP-AES (Kaggle 2012) ⭐ PRIMARY (school-essay register)
- ~12,978 hand-scored essays, grades 7–10, ≤2012. https://www.kaggle.com/competitions/asap-aes/data (accept competition rules).

### PERSUADE 2.0 / ASAP 2.0 — SUPPLEMENT (provenance verified clean)
- PERSUADE 2.0: 25K+ argumentative essays from state/national assessments **collected 2010–2020** — pre-ChatGPT by date. **CC BY 4.0.** https://github.com/scrosseye/persuade_corpus_2.0 + Kaggle `nbroad/persaude-corpus-2`. ASAP 2.0: 24,278 essays, same pre-2020 pool (12,871 overlap with PERSUADE — don't double-count): https://www.kaggle.com/datasets/lburleigh/asap-2-0.

### r/WritingPrompts (Fan et al. 2018) — SUPPLEMENT
- 303,358 prompt/story pairs (~200M words), 2012–2017. https://huggingface.co/datasets/euclaise/writingprompts (605MB). Fiction register; redistribution murky post-2023 Reddit ToS.

### ICNALE / ICLE — REJECT (L2 learner English, wrong register)
### IMDb Large Movie Review (2011) — SUPPLEMENT
- 100K reviews ≤2011, https://ai.stanford.edu/~amaas/data/sentiment/ (live), free.
### Amazon reviews — `fancyzhx/amazon_polarity` (≤March 2013, Apache 2.0) SUPPLEMENT; Amazon-Reviews-2023 REJECT unless timestamp-filtered <Nov 2022.
### Medium — https://huggingface.co/datasets/fabiochiu/medium-articles (2016–2022) — SUPPLEMENT, filter to pre-Oct-2022. Substack: no corpus exists.
### BNC — SUPPLEMENT-to-primary: ~100M words, early-90s British English, free XML via Oxford Text Archive https://www.natcorp.ox.ac.uk/getting/index.xml (~4GB TEI-XML). COCA: bulk full-text is paid; only if a formal reference corpus is needed.

---

## 3. SOCIAL MEDIA baselines

### Pushshift Reddit dumps ⭐ PRIMARY
- **2026 status**: official Pushshift-Reddit arrangement dead (2023); historical dumps live on **Academic Torrents**, maintained by u/Watchful1: "Reddit comments/submissions 2005-06 to 2022-12" + **per-subreddit splits** (much smaller); parsing scripts https://github.com/Watchful1/PushshiftDumps.
- ~1.99TB zstd NDJSON full; trim to **≤ Oct 2022**.
- No formal license; research-use norm. Reddit litigation climate (sued Perplexity/SerpApi/Oxylabs Oct 2025, Anthropic June 2025 — over *current commercial* scraping); no takedown of academic torrents as of July 2026. Flag to stakeholders.

### Sentiment140 ⭐ PRIMARY (Twitter register)
- 1.6M tweets, **2009**, full text embedded (no rehydration). https://www.kaggle.com/datasets/kazanova/sentiment140 + https://huggingface.co/datasets/stanfordnlp/sentiment140 (81.4MB). 15+ years unchallenged academic use.

### Hacker News (BigQuery) ⭐ PRIMARY for provenance
- `bigquery-public-data.hacker_news.full`, slice `WHERE timestamp < '2022-11-30'`. Free tier. Cleanest provenance mechanism of any social source (timestamped, no scraping controversy); tech-forum register.

### TweetEval — SUPPLEMENT (~123K short labeled tweets 2013–2018; patchwork licensing)
### archive.org Twitter Stream Grab — SUPPLEMENT (1% firehose 2011–Apr 2018, ~50GB/month raw; parsing-heavy; redistribution risk nonzero)
### Edinburgh Twitter Corpus — REJECT (withdrawn; ID-only rehydration dead)
### LinkedIn — REJECT — **gap confirmed**
- No usable-scale corpus exists. Legally radioactive: LinkedIn v. Proxycurl (2025, settled; vendor postmortem: "avoid LinkedIn-derived data entirely"); LinkedIn UA §8.2(4) reaches downstream consumers of scraped data. → LinkedIn-style slop scored via tell-rates + human votes, no ratio baseline (disclosed on the board).
### Facebook/Instagram — REJECT (nothing at scale; CrowdTangle shut down Aug 2024)

---

## 4. TEXTS/IM baselines

### NUS SMS Corpus ⭐ PRIMARY
- ~55.8K English + ~31.5K Chinese SMS, collected 2003/04–2015, Singaporean/Malaysian students. Original NUS host flaky; **live mirrors**: https://github.com/kite1988/nus-sms-corpus (SQL/XML) + https://www.kaggle.com/datasets/rtatman/the-national-university-of-singapore-sms-corpus (JSON). Cite Chen & Kan (2013). Narrow demographic, heavy Singlish — disclose.

### SMS Spam Collection ham subset — SUPPLEMENT
- 4,827 ham ≤2012, https://archive.ics.uci.edu/dataset/228/sms+spam+collection, CC BY 4.0. **3,375 messages overlap NUS — dedupe!**

### NPS Chat Corpus — SUPPLEMENT (ethics flag)
- 10,567 IRC posts, Oct–Nov 2006, via NLTK (`nps_chat.zip`). Includes teen chatrooms — minors' logs, unclear consent.

### Ubuntu Dialogue Corpus — SUPPLEMENT (~1M dialogues, Ubuntu IRC 2004–2012; tech-support register)
### DISCO (Discord) — SUPPLEMENT
- 1,508,093 messages / 28,712 conversations, 4 dev servers, published MSR 2022 (pre-cutoff). **Direct download**: https://zenodo.org/records/5886240 (103MB). The one ethically-clean Discord option.
### DailyDialog — REJECT (crawled from ESL teaching sites — semi-scripted, not organic)
### Cornell Movie-Dialogs — REJECT (scripted fiction)
### EmpatheticDialogues — SUPPLEMENT with caveat (MTurk crowdworker-written, 2019, CC BY-NC)
### Switchboard — REJECT (spoken register + LDC fee)
### WhatsApp/iMessage — REJECT (no ethical public corpus exists at scale)

---

## 5. KNOWN-AI calibration sets

### RAID ⭐ PRIMARY (general calibration)
- 11 LLMs × 8 domains × 4 decodings × 11 adversarial attacks; ~6M generations, ~16.7GB. https://huggingface.co/datasets/liamdugan/raid + https://github.com/liamdugan/raid. **MIT.** No email/social/IM domain (has Reddit + IMDb).

### MAGE ⭐ PRIMARY (model breadth)
- 447,674 texts, 10 human sources × **27 LLMs / 7 families**. https://huggingface.co/yaful/MAGE + https://github.com/yafuly/MAGE. **Apache-2.0.** DialogSum split ≈ closest to conversational register.

### HC3 — SUPPLEMENT ("generation-zero slop" anchor: Dec-2022 ChatGPT, ~24K QA pairs, CC-BY-SA)
### M4 / M4GT-Bench — SUPPLEMENT (lists "social media" as a domain — rare; data via Google Drive, **no license stated** — blocker until resolved)
### Ghostbuster data — SUPPLEMENT (https://github.com/vivek3141/ghostbuster-data)
### artem9k/ai-text-detection-pile — SUPPLEMENT, primary-adjacent for SOCIAL (1.33M rows incl. **a Twitter slice**, MIT)
### Defactify_Text_Dataset — SUPPLEMENT (modern generations: GPT-4o, Qwen-2, Gemma-2; license unlisted)
### DetectRL — SUPPLEMENT (verify HF release exists before depending on it)

### AI-generated EMAIL / SOCIAL / TEXTS — **CONFIRMED GAP**
Nothing purpose-built exists (only phishing generators + one paper with no public data). **We must self-generate the AI calibration corpora for email/social/texts by prompting current models** — controllable, since we own the generation pipeline; HC3 covers the GPT-3.5-era anchor.

---

## 6. SCENARIO sources

### enron_intent_dataset_verified ⭐ PRIMARY scenario seed
- 5,204 sentences labeled request/non-request, **MIT-licensed** relabel of the ParakweetLabs original. GitHub: vseledkin/enron_intent_dataset_verified. The only purpose-built, licensed email-request corpus found.
- DIY complement: Kaggle `jivfur/enron-emails` thread keys → filter to first-message-per-thread = real initiating requests at scale.
- No off-the-shelf "email writing prompts" dataset exists anywhere (confirmed).

### Kaggle Customer Support on Twitter — SUPPLEMENT
- ~3M tweets/replies, ~20 brands, ≤2017. CC BY-NC-SA (non-commercial clause). Intent-taxonomy mining only.

---

## Recommended stack

| Domain | Primary | Supplement | Rejected |
|---|---|---|---|
| **EMAIL** | CMU Enron maildir + **EnronSent** (sent-only) | Avocado ($), W3C mirror, Apache mbox, TREC07 ham | Clinton |
| **ESSAY** | **Blog Authorship Corpus (2004)** + ASAP-AES (2012) | PERSUADE 2.0 (CC BY), BNC, IMDb 2011, amazon_polarity ≤2013, Medium (date-filtered) | ICNALE/ICLE, Substack (none) |
| **SOCIAL** | **Pushshift Reddit ≤Oct 2022** + Sentiment140 + HN BigQuery | TweetEval, archive.org Twitter Stream | LinkedIn (none exists, radioactive), FB/IG, Edinburgh |
| **TEXTS/IM** | **NUS SMS** (mirrors) | UCI ham (dedupe vs NUS), NPS Chat (ethics flag), Ubuntu, DISCO Discord, EmpatheticDialogues | Cornell, Switchboard, DailyDialog, WhatsApp |
| **AI CALIBRATION** | **RAID** (MIT) + **MAGE** (Apache) | HC3, artem9k pile (Twitter slice), M4 (license TBD), Ghostbuster, Defactify | — |
| **SCENARIOS** | **enron_intent_dataset_verified** (MIT) + thread-keyed Enron starters | Customer Support on Twitter (NC) | — |

## Acquisition effort

- **Zero-friction (an afternoon, ~25GB)**: EnronSent, CMU Enron, Blog Corpus, Sentiment140, NUS SMS, UCI SMS, NPS Chat, IMDb, DISCO, RAID, MAGE, HC3, artem9k pile, enron_intent.
- **Light friction (1–2 days)**: HN BigQuery slice (GCP free tier), ASAP/PERSUADE (Kaggle rules), BNC (OTA form), Medium/Amazon date filtering, archive.org Twitter parsing.
- **Heavy (1–2 weeks)**: full Pushshift torrent (~2TB + zstd + date-trim) — **use per-subreddit splits instead for pilot/v1**; Apache mbox self-assembly.
- **Paid/gated (optional)**: Avocado (LDC), COCA bulk. Not required for v1.
- **Must-build**: AI-generated email/social/texts calibration corpora (self-generate; first-class workstream seeded by Enron-intent scenarios).

**Bottom line**: every domain has a viable, verified, free primary human baseline except LinkedIn-style social (structurally impossible — no corpus exists, scored via tell-rates + human votes, disclosed). Two real gaps: (1) AI-generated email/social calibration data → self-generate; (2) organic private texting beyond the NUS demographic → doesn't exist ethically at any scale.
