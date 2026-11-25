# Data provenance, attribution, and reuse

## Primary scientific tasks

The primary 120-question projection derives from **LAB-Bench** by Jon M. Laurent, Joseph D. Janizek, Michael Ruzo, Michaela M. Hinks, Michael J. Hammerling, Siddharth Narayanan, Manvitha Ponnapati, Andrew D. White, and Samuel G. Rodriques (2024):

- Dataset: <https://huggingface.co/datasets/futurehouse/lab-bench>
- Upstream dataset license: **Creative Commons Attribution–ShareAlike 4.0 International** (CC BY-SA 4.0): <https://creativecommons.org/licenses/by-sa/4.0/>
- Original benchmark paper: *LAB-Bench: Measuring Capabilities of Language Models for Biology Research*, <https://arxiv.org/abs/2407.10362>.

The upstream dataset card declares CC BY-SA 4.0. The included task/evidence projection and source excerpts in saved prompts retain that attribution and applicable share-alike terms. Questions are sampled and projected into fixed question/options/evidence records; images are not supplied. Reference labels, choice order, and truncation match the archived experiment. This package does not reproduce official leaderboard evaluation. Third-party scientific articles and protocols referenced in upstream evidence retain their own authorship and rights; a dataset license is not a claim to ownership of every cited source.

## Normalized execution observations

The research authors produced saved candidate answers, generated condition claims, tool observations, timing, and reported usage. This release replaces generator/panel identifiers with roles, replaces private request paths with stable IDs, and excludes service envelopes/configuration, raw errors, and opaque fields. `data/provenance.json` records source-file hashes and transformations. Original hashes identify the historical inputs; public hashes in `MANIFEST.json` bind transformed files.

Supplementary GAIA/clinical/web question and answer text is not redistributed. Supplementary CSV files contain minimal outcomes, roles, strata, and reported measurements. The trajectory file contains only match/nonempty/agreement flags required to enumerate saved-trajectory loss masks.

## Code rights

No project-wide software license has been selected by the authors in this release. This package does not invent a license on their behalf or transfer third-party rights. Public availability is not by itself a grant of unrestricted code reuse. The repository owners should select an appropriate software license before granting broader permissions. Dataset attribution and CC BY-SA obligations apply separately from any future code license.
