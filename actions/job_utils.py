import os

import streamlit as st

from jobs import job_runner


def ensure_audio_available(
    state,
    *,
    manager=None,
    allow_empty: bool = False,
    error_message: str = "Audio not loaded.",
    missing_message: str = "❌ Audio file is missing. Please re-import.",
) -> bool:
    """
    Validate that the current audio file exists.
    Returns True when the audio is ready, False otherwise.
    """
    current_path = getattr(state.audio, "current_path", None)
    if not current_path:
        if allow_empty:
            return True
        st.error(error_message)
        return False

    if not os.path.exists(current_path):
        state.audio.current_path = None
        state.audio.original_path = None
        state.audio.duration = 0.0
        state.audio.is_loaded = False
        state.audio.version += 1
        if manager is not None:
            manager.set_selection(0.0, 0.0, source="missing_audio")
        st.error(missing_message)
        return False

    return True


def check_background_job(
    job_id,
    session_key,
    *,
    on_completed,
    on_failed,
    on_running=None,
    on_terminal=None,
    terminal_statuses=("CANCELLED", "TIMEOUT", "EXPIRED", "UNKNOWN"),
):
    """
    Generic background job polling helper.
    Returns True if running, False otherwise.
    """
    if not job_id:
        return False

    info = job_runner.get_job(job_id) or {}
    status = info.get("status")

    if status == "RUNNING":
        if on_running:
            on_running(info)
        return True

    if status == "COMPLETED":
        on_completed(info)
        job_runner.clear_job(job_id)
        if session_key in st.session_state:
            del st.session_state[session_key]
        return False

    if status == "FAILED":
        on_failed(info)
        job_runner.clear_job(job_id)
        if session_key in st.session_state:
            del st.session_state[session_key]
        return False

    if status in terminal_statuses:
        handler = on_terminal or on_failed
        if handler:
            handler(info)
        job_runner.clear_job(job_id)
        if session_key in st.session_state:
            del st.session_state[session_key]
        return False

    return False
