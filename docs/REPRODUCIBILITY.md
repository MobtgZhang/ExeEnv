# Reproducibility contract

The supported unit of reproduction is the normalized saved observation, not an inference service. Run `python reproduce.py --no-figures` for a standard-library reconstruction and `python reproduce.py` for plots as well. Verification is strict: use ordinary Python, not optimized execution (`python -O`), because scientific consistency checks use assertions.

## Inputs and identities

The primary cohort has 120 frozen Lab-Bench tasks across five families. Questions, fixed options, supplied evidence, and strict reference answers are released together. `public_task()` explicitly removes reference answers and evaluator metadata before constructing prompts. Scoring occurs after a workflow returns. Saved evidence is a fixed projection, not a new retrieval experiment.

`request.path` is a stable public identity such as R00001. Shared references to that identity preserve the original one-to-many execution relationship. `request_hash` and `source_record_sha256` are historical provenance anchors. Because role aliases replace concrete identifiers and provider envelopes are removed, those historical hashes cannot be recomputed from public projections. Public file integrity is checked separately by `MANIFEST.json`. A checksum is neither a signature nor proof of freeze time.

`consumes` records successful usage; `depends_on` includes failures. Missing failed-request usage remains null, not zero billed cost. Physical reported tokens sum returned request identities once; logical usage sums every consuming edge. Reasoning and cached token details are subsets and must not be added again.

## Independent computations

The analyzer loads the seven relations into a fresh SQLite database, checks referential integrity, and recomputes scores from released references. It executes six SQL queries and separately recomputes partition transitions, Wilson intervals, macro accuracy, paired exact McNemar tests, and Holm adjustment. Model-scored panel votes are aggregated without relabeling them as expert truth.

The four-stage implementation reconstructs messages and compares them to saved requests before returning the saved completion. Saved tool observations are supplied as observations; no generated code is executed. Successful CURE prompts use the original public input, draft-withheld ledger/checker calls, and finalization context. Agreement uses only preceding answers; fallback is restricted to downstream failures after a returned nonempty draft. Explicit empty finals retain their historical zero-score behavior.

Fault sensitivity enumerates all 16 four-stage masks for every completed saved trajectory and four policies. Independent and common loss weights use exact fractions. The curves do not synthesize new responses; completion-conditioned trajectories are not an unbiased sample of future service performance.

Only after these computations does the analyzer read `expected/` and compare output cells. A failing comparison is an error, never a reason to overwrite the expected values. No random seed is necessary for this deterministic enumeration/replay.

## Validation and portability

The release was tested on Linux with CPython 3.12, SQLite from Python, and the pinned optional plotting libraries. Run `python -m unittest discover -s tests -v`; run the complete reproduction for data-level checks. `docs/VALIDATION.json` records an actual copy-and-run validation in a second directory. Byte comparisons cover deterministic tables and the report; SQLite physical storage is validated logically rather than compared byte for byte. PDF/PNG portability can depend on font and graphics-library versions.

Nothing in `CURE/` imports the private research workspace or reads configuration from its parent directory. Generated results, virtual environments, caches, and local configuration are excluded by `.gitignore`.
