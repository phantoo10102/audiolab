# tools/smoke_imports.py
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import components.audio_waveform
    import ui.waveform_view
    import ui.editor_view
    import ui.layout
    import services, pipelines, jobs, state, utils, infra

    print("OK: imports are clean.")


if __name__ == "__main__":
    main()
