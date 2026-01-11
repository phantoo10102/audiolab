# Architecture rules (anti-bloat)

- Dependency flow: `ui/` → `actions/` → `services/` or `pipelines/` → `utils/` + `infra/` + `state/`.
- UI should only call into `actions` (not `services` or `job_runner` directly).
- `services` and `pipelines` must not import Streamlit.
- Do not duplicate polling logic; use the shared job helper in `actions/job_utils.py`.
- Place subtitle + alignment logic in `utils/` (e.g., `utils/subtitle_postprocess.py`).
- Place background job orchestration in `jobs/job_runner.py`.
- Place subprocess/CLI interactions in `services/` or `pipelines/` only.
