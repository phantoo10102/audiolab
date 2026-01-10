# Project Bloat Audit Report

> Snapshot date: 2025-02-14
> Baseline: `git ls-files` (tracked files only)

## Audit summary

### Repo structure (top-level)
| Directory | Files | Approx LOC |
| --- | ---:| ---:|
| .gitignore | 1 | 15 |
| .vscode | 1 | 3 |
| actions | 3 | 902 |
| app.py | 1 | 95 |
| BLOAT_AUDIT_REPORT.md | 1 | 100 |
| components | 2 | 462 |
| config.yaml.bak | 1 | 62 |
| infra | 1 | 98 |
| jobs | 1 | 202 |
| pipelines | 3 | 309 |
| scripts | 1 | 64 |
| services | 9 | 1865 |
| state | 3 | 331 |
| tests | 15 | 1405 |
| tools | 2 | 131 |
| ui | 5 | 838 |
| utils | 10 | 1582 |
| VAD_AUDIT_REPORT.md | 1 | 45 |

### Top 10 largest areas (by LOC)
1. services (1865 LOC)
2. utils (1582 LOC)
3. tests (1405 LOC)
4. actions (902 LOC)
5. ui (838 LOC)
6. components (462 LOC)
7. state (331 LOC)
8. pipelines (309 LOC)
9. jobs (202 LOC)
10. tools (131 LOC)

### Top churn files (last 30 commits)
1. services/whisperx_service.py (6)
2. utils/console_noise.py (4)
3. infra/local_audio_server.py (4)
4. actions/whisperx_actions.py (4)
5. services/settings_service.py (4)
6. tests/test_whisperx_vad.py (4)
7. app.py (3)
8. tests/test_whisperx_models_dir.py (3)
9. utils/logging_config.py (3)
10. ui/editor_view.py (3)

## Findings (bloat signals)

1. **Repeated background-job polling patterns**: `check_*_job` logic is implemented separately in multiple action modules with similar control flow and session-state handling, creating maintenance overhead. Examples: `actions/editor_actions.py` (`check_denoise_job`, `check_trim_job`) and `actions/separation_actions.py` (`check_separation_job`).
2. **Duplicate output-path fallback logic**: `services/denoise_service.py` and `services/trim_silence_service.py` both contain inline `OUTPUT_DIR` fallback blocks and local output-path handling instead of sharing a single helper. This increases drift risk for output layout changes.
3. **Large single-file UI surface**: `ui/editor_view.py` is the largest UI file and mixes job polling, UI layout, and direct file IO. This centralizes many responsibilities and makes growth likely.
4. **Overlapping pipeline/service responsibilities**: `pipelines/separation_pipeline.py` runs the Demucs subprocess and `services/separation_service.py` repeats output scanning/selection logic, implying split ownership of output conventions and extra maintenance surface.
5. **Repeated import clutter**: `pipelines/separation_pipeline.py` contains duplicated imports (`os`, `time`, `concurrent.futures`), which is a minor but visible sign of file churn and weak boundaries.
6. **Utility concentration**: `utils/file_manager.py` and `utils/subtitle_postprocess.py` are both large, multi-responsibility modules, suggesting growing grab-bag utilities rather than clear functional boundaries.
7. **Backup/config artifact tracked**: `config.yaml.bak` is tracked at repo root, likely a stale backup that can confuse configuration ownership.

## Recommendations (prioritized, low-risk)

### Do now (1–2 hours)
- Consolidate background-job polling into a shared helper (e.g., `actions/job_status.py`) and have `editor_actions`, `separation_actions`, `whisperx_actions` call it. Scope: no behavioral changes, just shared logic.
- Normalize output-path handling: move `OUTPUT_DIR` fallback + output path creation into `utils/constants` or `utils/file_manager` and re-use across services.
- Clean repeated import clutter in `pipelines/separation_pipeline.py` as a quick readability win.

### Do later (half-day)
- Split `ui/editor_view.py` into smaller view components (import section, waveform, controls, export) and centralize job status indicators in one helper.
- Introduce a dedicated `services/output_paths.py` (or similar) for building run-specific output folders (e.g., whisperx, separation) to avoid divergent conventions.

### Defer / larger refactors
- Rework `utils/file_manager.py` and `utils/subtitle_postprocess.py` into smaller, single-purpose modules (requires careful test coverage).
- Re-evaluate service/pipeline boundaries (e.g., pipeline returns standardized artifacts to avoid manual scanning in services).

## Guardrails (no new dependencies)

1. **Module ownership rules**
   - `ui/` should only contain Streamlit rendering logic and must call `actions/` for side effects.
   - `actions/` can own background-job orchestration and session-state changes.
   - `services/` should be stateless, side-effect-free business logic (no Streamlit usage).
   - `pipelines/` should only encapsulate long-running CLI/model execution and return structured results.

2. **New file checklist**
   - Every new module needs a short module docstring describing responsibility.
   - Avoid adding new utility functions to `utils/` unless there is a single clear owner or module.
   - If new output paths are created, they must route through a shared helper.

3. **Optional lightweight check**
   - Add a CI step (or pre-commit manual step) that runs `python tools/bloat_audit.py` and flags if any top-level directory exceeds an agreed LOC delta threshold.

## How to run the script

```bash
python tools/bloat_audit.py
python tools/bloat_audit.py --depth 2
python tools/bloat_audit.py --churn-commits 50
```
