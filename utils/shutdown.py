import atexit
import logging

from infra import local_audio_server
from jobs import job_runner

logger = logging.getLogger(__name__)


def cleanup_on_exit():
    try:
        local_audio_server.stop_audio_server()
    except Exception as exc:
        logger.warning(
            "Failed to stop audio server",
            extra={"operation": "shutdown_audio_server", "error": str(exc)},
        )
    try:
        job_runner.shutdown(reason="CANCELLED")
    except Exception as exc:
        logger.warning(
            "Failed to shutdown job runner",
            extra={"operation": "shutdown_job_runner", "error": str(exc)},
        )


def register_shutdown_handlers():
    atexit.register(cleanup_on_exit)
