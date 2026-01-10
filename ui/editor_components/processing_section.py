import streamlit as st

from actions import editor_actions
from actions import separation_actions


def render_processing_section(state, is_processing):
    with st.container(border=True):
        st.markdown("#### 🛠️ Tools")
        st.button(
            "✂️ Auto Trim Silence",
            use_container_width=True,
            disabled=not state.audio.is_loaded or is_processing,
            on_click=editor_actions.trim_silence_callback,
        )
        st.button(
            "🧹 AI Denoise",
            use_container_width=True,
            disabled=not state.audio.is_loaded or is_processing,
            on_click=editor_actions.denoise_audio_callback,
        )

    with st.container(border=True):
        st.markdown("#### 🎸 Separation")
        has_res = (
            "separation_result" in st.session_state
            and st.session_state.separation_result
        )
        opts = (
            [s.name for s in st.session_state.separation_result.stems]
            if has_res
            else ["No result"]
        )

        st.selectbox(
            "Stems",
            opts,
            key="sep_selected_stem_name",
            disabled=not has_res or is_processing,
        )

        st.button(
            "🚀 Run Separation",
            use_container_width=True,
            disabled=not state.audio.is_loaded or is_processing,
            on_click=separation_actions.start_separation_callback,
        )

        if has_res:
            st.button(
                "📥 Load Stem",
                use_container_width=True,
                disabled=is_processing,
                on_click=separation_actions.load_selected_stem_callback,
            )
