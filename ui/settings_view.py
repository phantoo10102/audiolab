import streamlit as st

from utils.constants import DATA_MODELS_DIR

# [FIX] Import SettingsManager instead of settings_service
from services.settings_service import settings_manager
from state.session_manager import get_manager


def render_settings_view():
    st.title("⚙️ Advanced Settings")
    st.info(
        """
    📁 **Configuration Files**
    - `config.yaml` - System defaults (read-only via UI)
    - `data/config/user_settings.yaml` - Your settings (saved by this UI)

    Your settings in user_settings.yaml override config.yaml values.
    """
    )

    # Load settings into session state if missing
    if "form_settings" not in st.session_state:
        st.session_state.form_settings = settings_manager.load_settings()
        # Decrypt token for display
        encrypted_token = st.session_state.form_settings["credentials"]["hf_token"]
        st.session_state.decrypted_token = settings_manager.decrypt_token(
            encrypted_token
        )

    current_settings = st.session_state.form_settings

    # --- SECTION 1: CREDENTIALS ---

    # --- SECTION 2: WHISPERX ADVANCED ---
    with st.expander("🎙️ WhisperX Advanced", expanded=False):
        st.caption("These settings apply globally to all WhisperX runs.")
        current_settings.setdefault("whisperx", {})
        default_models_dir = str(DATA_MODELS_DIR / "whisperx")
        if not current_settings["whisperx"].get("models_dir"):
            current_settings["whisperx"]["models_dir"] = default_models_dir

        # Device selection
        current_settings["models"]["device"] = st.selectbox(
            "Compute Device",
            ["cuda", "cpu"],
            index=0 if current_settings["models"].get("device") == "cuda" else 1,
            help="GPU (cuda) is faster but requires NVIDIA GPU. CPU works everywhere.",
        )
        if st.button("🔌 Test Device Compatibility", key="btn_test_device"):
            selected_device = current_settings["models"]["device"]
            is_valid, msg = settings_manager.validate_device(selected_device)
            if is_valid:
                st.success(msg)
            else:
                st.error(msg)
                st.warning(
                    "⚠️ Nếu bạn lưu cài đặt này, ứng dụng có thể bị lỗi khi chạy WhisperX."
                )

        # WhisperX models folder
        current_settings["whisperx"]["models_dir"] = st.text_input(
            "WhisperX Models Folder",
            value=current_settings["whisperx"].get("models_dir", ""),
            placeholder="D:\\AI_Space\\models\\whisperx or ./data/models/whisperx",
            help=(
                "Path to cache WhisperX models. Leave blank to use "
                "the default data/models/whisperx folder."
            ),
        )
        current_settings["whisperx"]["vad_enabled"] = st.checkbox(
            "Enable VAD",
            value=current_settings["whisperx"].get("vad_enabled", False),
            help="Toggle voice activity detection for WhisperX.",
        )
        current_settings["whisperx"]["vad_token"] = st.text_input(
            "VAD token",
            value=current_settings["whisperx"].get("vad_token", ""),
            type="password",
            help="Hugging Face token used to download pyannote VAD pipeline (gated).",
        )

        # VAD Settings
        st.markdown("**Voice Activity Detection (VAD)**")
        current_settings["processing"]["vad_threshold"] = st.slider(
            "VAD Threshold",
            0.0,
            1.0,
            current_settings["processing"].get("vad_threshold", 0.5),
            step=0.05,
            help="Higher = stricter voice detection. Set to 0.0 to disable VAD.",
        )

        # Diarization Settings
        st.markdown("**Speaker Diarization**")
        current_settings["processing"]["enable_diarization"] = st.checkbox(
            "Enable Speaker Diarization",
            value=current_settings["processing"].get("enable_diarization", False),
            help="Requires HuggingFace token. Identifies different speakers.",
        )

        new_token = st.session_state.decrypted_token

        if current_settings["processing"]["enable_diarization"]:
            c_min, c_max = st.columns(2)
            col1, col2 = st.columns([3, 1])
            with c_min:
                current_settings["processing"]["min_speakers"] = st.number_input(
                    "Min Speakers",
                    1,
                    10,
                    current_settings["processing"].get("min_speakers", 1),
                )
            with c_max:
                current_settings["processing"]["max_speakers"] = st.number_input(
                    "Max Speakers",
                    1,
                    10,
                    current_settings["processing"].get("max_speakers", 5),
                )

            with col1:
                new_token = st.text_input(
                    "HuggingFace Access Token",
                    value=st.session_state.decrypted_token,
                    type="password",
                    help="Required for Diarization. Starts with 'hf_'. Encrypted at rest.",
                    key="input_hf_token",
                )

            with col2:
                st.write("")
                st.write("")
                if st.button("🔌 Test Token"):
                    is_valid, msg = settings_manager.validate_hf_token(new_token)
                    if is_valid:
                        st.success(msg)
                    else:
                        st.error(msg)

            if new_token:
                if new_token.startswith("hf_"):
                    st.caption("✅ Format valid")
                else:
                    st.caption("❌ Invalid format (must start with 'hf_')")

    # --- ACTION BUTTONS ---
    st.divider()
    manager = get_manager()
    has_active_session = manager.state.audio.is_loaded

    if has_active_session:
        st.warning(
            "⚠️ Lưu ý: Lưu cài đặt sẽ tải lại trang và làm mới phiên làm việc hiện tại (Audio sẽ bị reset)."
        )

    b_col1, b_col2 = st.columns([1, 1])

    with b_col1:
        if st.button("💾 Save Settings", type="primary", use_container_width=True):
            sel_device = current_settings["models"]["device"]
            dev_valid, dev_msg = settings_manager.validate_device(sel_device)

            if not dev_valid:
                st.error(f"Warning: {dev_msg}")
                st.warning(
                    "⚠️ Đang lưu cài đặt không hợp lệ. Hãy cân nhắc chuyển về CPU."
                )
            # 1. Update Token (Encrypt)
            if new_token != st.session_state.decrypted_token:
                encrypted = settings_manager.encrypt_token(new_token)
                current_settings["credentials"]["hf_token"] = encrypted
                st.session_state.decrypted_token = new_token

            # 2. Save
            if settings_manager.save_settings(current_settings):
                st.toast("✅ Settings saved to config.yaml", icon="✅")
                st.caption("♻️ Configuration updated. Restart app if needed.")
                st.session_state.user_settings = current_settings
            else:
                st.error("Failed to save settings.")

    with b_col2:
        if st.button("🔄 Reset to Defaults", use_container_width=True):
            settings_manager.reset_to_defaults()
            del st.session_state.form_settings
            st.session_state.decrypted_token = ""
            st.rerun()
