import logging
import streamlit as st
import streamlit.components.v1 as components
import os
from functools import lru_cache

logger = logging.getLogger(__name__)


try:
    from infra.local_audio_server import get_audio_url
except ImportError:
    import sys

    sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
    from infra.local_audio_server import get_audio_url


def _get_build_dir():
    parent_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(parent_dir, "waveform_ui")


@lru_cache(maxsize=1)
def _get_component_func():
    build_dir = _get_build_dir()
    return components.declare_component("audio_waveform_local", path=build_dir)


def audio_waveform(
    audio_file,
    height=200,
    start_time=0.0,
    end_time=10.0,
    key="waveform",
):
    try:
        if not os.path.exists(audio_file):
            return None

        # get_audio_url đã được thiết kế singleton bên infra, nên URL là ổn định.
        # Tuy nhiên, ta gọi nó ở đây là hợp lý.
        audio_url = get_audio_url(audio_file)

        component_func = _get_component_func()

        # Tạo settings dict.
        # Lưu ý: Python sẽ tạo dict mới mỗi lần gọi hàm,
        # nhưng Streamlit Frontend sẽ so sánh deep-equality của JSON arguments.
        # Vì vậy chỉ cần giá trị start_time/end_time không đổi, component sẽ KHÔNG reload.
        settings = {
            "wave_color": "#4facfe",
            "progress_color": "#00f2fe",
            "region_start": float(start_time),
            "region_end": float(end_time),
        }

        component_value = component_func(
            url=audio_url,
            height=height,
            settings=settings,
            key=key,
            default=None,
        )

        return component_value

    except Exception as e:
        logger.exception(
            "Error in audio_waveform component",
            extra={"error": str(e), "operation": "audio_waveform"},
        )
        return None
