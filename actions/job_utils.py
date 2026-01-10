import streamlit as st

from jobs import job_runner


def check_background_job(
    job_id,
    session_key,
    *,
    on_completed,
    on_failed,
    on_running=None,
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

    return False
