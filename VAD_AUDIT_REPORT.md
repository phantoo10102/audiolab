# WhisperX VAD Audit Report

## Summary
The current codebase does **not** contain a confirmed, version-stable API for enabling WhisperX/Faster-Whisper VAD (pyannote) at transcription time or model-load time. The UI toggle is wired, but the runtime uses a compatibility shim that skips unsupported VAD kwargs. As a result, VAD may be a no-op depending on the installed WhisperX/Faster-Whisper versions.

## Repo audit findings
### Where the WhisperX pipeline is created
- `services/whisperx_service.py` is the single place where the model is created and stored as `self.model` using `whisperx.load_model(...)`. There are no VAD-related options passed at load time in this repo.
- `self.model` is expected to be whatever object `whisperx.load_model(...)` returns (likely a FasterWhisperPipeline or similar), and transcription is performed via `self.model.transcribe(...)`.

### Where transcription is invoked
- `actions/whisperx_actions.py` calls `whisperx_service.transcribe(...)` with `vad_filter` derived from UI state.
- `services/whisperx_service.py` calls `self.model.transcribe(...)` and dynamically inspects the signature to decide whether to pass `vad_filter` or `vad`.
- There are no other WhisperX transcription entry points in the repo.

### VAD-related integration points in repo
- The only VAD usage is the UI toggle and the optional `vad_filter` / `vad` kwarg compatibility layer in `services/whisperx_service.py`.
- There is no repo-local implementation of pyannote VAD or any `whisperx.vad` helper usage.
- The only other “VAD” references are to silence trimming (pydub) and diarization settings (which are unrelated to WhisperX VAD filtering).

## Why VAD is currently ambiguous
- The runtime error observed (`TypeError: FasterWhisperPipeline.transcribe() got an unexpected keyword argument 'vad_filter'`) indicates the installed pipeline does **not** accept `vad_filter` at transcription time.
- The repo does not show any alternative supported mechanism (e.g., `vad_model`, `vad_options`, or `whisperx.vad` utilities) wired at model creation or preprocessing.
- Without knowing the installed WhisperX/Faster-Whisper versions and the signature of the actual pipeline class, it is not possible to confidently enable VAD without risking runtime errors or no-ops.

## Information needed to implement correct VAD wiring
Please provide the following outputs from the runtime environment:

1) **Version information**
```bash
python -c "import whisperx, inspect; import faster_whisper; print('whisperx', getattr(whisperx,'__version__',None)); print('faster_whisper', getattr(faster_whisper,'__version__',None))"
```

2) **Actual pipeline signature**
```bash
python -c "import inspect; import whisperx; from whisperx.asr import FasterWhisperPipeline; print(inspect.signature(FasterWhisperPipeline.transcribe))"
```

3) **Confirm model load path**
- Please confirm whether `services/whisperx_service.py::load_model()` is the only code path used to create the pipeline in your deployment (or share the actual entry point if different).

## Next steps once info is available
- If the signature includes a VAD kwarg (e.g., `vad_filter`, `vad`, or `vad_options`), wire it directly in `services/whisperx_service.py` and update tests to assert correct propagation.
- If the pipeline expects VAD configuration at model creation, adjust `whisperx.load_model(...)` to pass supported VAD options and update UI wiring accordingly.
- If VAD is not supported by the installed versions, consider upgrading WhisperX/Faster-Whisper to versions that expose a VAD API or implement a preprocessing step prior to transcription.
