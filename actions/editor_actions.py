import streamlit as st
import os
import shutil
from pathlib import Path
from pydub import AudioSegment, silence

# Imports
from jobs import job_runner
from utils.os_utils import fmt_time
from state.session_manager import get_manager
from services.link_import_service import LinkImportService
from utils.constants import DATA_OUTPUT_DIR
from utils.logging_config import get_session_id
from actions.job_utils import check_background_job


# Helper getter để tránh truyền state quá nhiều
def get_state_objects():
    manager = get_manager()
    state = manager.state
    processor = st.session_state.processor
    return manager, state, processor


def check_denoise_job():
    """
    Kiểm tra trạng thái job background.
    Trả về True nếu đang chạy, False nếu đã xong hoặc không có job.
    """
    job_id = st.session_state.get("denoise_job_id")

    def _on_completed(info):
        manager = get_manager()
        state = manager.state
        processor = st.session_state.processor

        result = info["result"]
        output_path = result.get("output_path")

        if output_path:
            try:
                processor.load_audio(output_path)
                new_duration = processor.duration

                manager.set_audio(
                    path=output_path,
                    original_path=state.audio.original_path,
                    duration=new_duration,
                )
                st.toast(f"✅ Denoise Complete ({result.get('method_used')})!")

            except (FileNotFoundError, OSError):
                st.error("❌ Denoise finished but output file is missing/inaccessible.")
        else:
            st.error("❌ Denoise finished but no output path returned.")

        # Rerun một lần cuối để update UI với file mới
        st.rerun()

    def _on_failed(info):
        # 3. Xử lý lỗi
        error_msg = info.get("error")
        st.error(f"❌ Denoise Failed: {error_msg}")

    return check_background_job(
        job_id,
        "denoise_job_id",
        on_completed=_on_completed,
        on_failed=_on_failed,
    )


def auto_detect_content_callback():
    manager, state, processor = get_state_objects()
    try:
        current_file = state.audio.current_path
        if not current_file or not os.path.exists(current_file):
            return

        with st.spinner("🤖 AI is analyzing audio..."):
            seg = AudioSegment.from_file(current_file)
            nonsilent_ranges = silence.detect_nonsilent(
                seg, min_silence_len=500, silence_thresh=seg.dBFS - 16
            )

            if nonsilent_ranges:
                new_start = nonsilent_ranges[0][0] / 1000.0
                new_end = nonsilent_ranges[-1][1] / 1000.0
                manager.set_selection(new_start, new_end, source="auto_detect")
                st.toast(
                    f"🤖 Auto Detected: {fmt_time(new_start)} → {fmt_time(new_end)}"
                )
            else:
                st.warning("⚠️ Không tìm thấy nội dung rõ ràng.")
    except Exception as e:
        st.error(f"AI Error: {e}")


def denoise_audio_callback():
    """
    Callback xử lý khi bấm nút Denoise.
    Thực hiện: Snapshot History -> Gửi Job chạy nền -> Rerun UI để hiển thị trạng thái 'Running'.
    """
    from services.denoise_service import DenoiseService

    manager, state, processor = get_state_objects()

    # 1. Validation: Kiểm tra file có tồn tại không
    if not state.audio.current_path or not os.path.exists(state.audio.current_path):
        st.error("Audio not loaded or file missing.")
        return

    # 2. Push History (Snapshot): Lưu lại trạng thái hiện tại để có thể Undo sau này
    # Quan trọng: Phải lưu trước khi submit job
    manager.push_history(
        current_path=state.audio.current_path,
        original_path=state.audio.original_path,
        duration=state.audio.duration,
    )

    # 3. Lazy Import: Chỉ load thư viện xử lý nặng khi thực sự cần dùng
    # 4. Submit Job: Gửi tác vụ vào ThreadPool (Chạy nền)
    # Lưu ý: Truyền hàm và tham số, KHÔNG gọi hàm () ngay lập tức
    job_id = job_runner.submit(
        DenoiseService.denoise_audio,  # Hàm cần chạy
        input_path=state.audio.current_path,  # Tham số 1
        method="auto",  # Kwargs: Tự động chọn thuật toán
        strength=0.6,  # Kwargs: Cường độ lọc
    )

    # 5. Update UI State: Lưu Job ID để UI (editor_view) biết mà hiển thị loading/polling
    st.session_state["denoise_job_id"] = job_id

    # 6. Feedback & Rerun: Thông báo và load lại UI để nút bấm chuyển sang trạng thái Disable
    st.toast("🚀 Denoise started in background...")


def check_trim_job():
    """Kiểm tra job Trim Silence, gọi đầu UI render"""
    job_id = st.session_state.get("trim_job_id")

    def _on_completed(info):
        manager = get_manager()
        state = manager.state
        processor = st.session_state.processor

        result = info["result"]
        output_path = result.get("output_path")

        if output_path and os.path.exists(output_path):
            # 1. Load Audio Mới
            processor.load_audio(output_path)
            new_duration = processor.duration

            # 2. Update State
            # Cần xử lý vùng chọn cũ (clamp) để tránh lỗi out of bounds
            old_start = state.selection.start
            old_end = state.selection.end

            manager.set_audio(
                path=output_path,
                original_path=state.audio.original_path,  # Giữ original gốc
                duration=new_duration,
            )

            # Restore selection hợp lý
            if result.get("is_trimmed"):
                # Reset về full file nếu file thay đổi nhiều
                # Hoặc clamp:
                new_sel_end = min(old_end, new_duration)
                if new_sel_end > old_start:
                    manager.set_selection(old_start, new_sel_end, source="trim_keep")

            st.toast("✂️ Trim Silence Complete!")
        else:
            st.error("❌ Trim finished but output missing.")

        st.rerun()

    def _on_failed(info):
        # Lấy message lỗi từ job_runner
        error_msg = info.get("error", "Unknown error")
        st.error(f"❌ Trim Failed: {error_msg}")

    return check_background_job(
        job_id,
        "trim_job_id",
        on_completed=_on_completed,
        on_failed=_on_failed,
    )


def _run_import_task(url: str, session_id: str) -> str:
    """
    Task chạy ngầm để download audio.
    Trả về đường dẫn file đã tải (string).
    """
    # LinkImportService đã có sẵn logic retry, validation và timeout
    downloaded_path = LinkImportService.download_audio_from_url(url)
    return str(downloaded_path.resolve())


# --- NEW: TRIM SUBMIT CALLBACK ---
def trim_silence_callback():
    manager, state, processor = get_state_objects()

    # 1. Validation
    if not state.audio.current_path or not os.path.exists(state.audio.current_path):
        st.error("Audio not loaded.")
        return

    # 2. Push History (Undo point)
    manager.push_history(
        current_path=state.audio.current_path,
        original_path=state.audio.original_path,
        duration=state.audio.duration,
    )

    # 3. Lazy Import & Submit Job
    from services.trim_silence_service import TrimSilenceService

    job_id = job_runner.submit(
        TrimSilenceService.trim_silence,  # Function
        input_path=state.audio.current_path,
        # Các tham số mặc định (có thể lấy từ UI settings nếu cần)
        silence_thresh_db=-40.0,
        min_silence_len_ms=400,
        keep_silence_ms=150,
    )

    # 4. Update State
    st.session_state["trim_job_id"] = job_id
    st.toast("✂️ Trim started in background...")


def crop_audio_callback():
    manager, state, processor = get_state_objects()
    try:
        # 1. Lấy thông số từ State
        start = state.selection.start
        end = state.selection.end
        fmt = st.session_state.export_format

        # Xử lý bitrate cho MP3
        raw_bitrate = st.session_state.get("export_bitrate", "320k")
        export_bitrate_param = None
        if fmt == "mp3":
            s_bitrate = str(raw_bitrate).lower().strip()
            if not s_bitrate.endswith("k"):
                s_bitrate += "k"
            export_bitrate_param = s_bitrate

        # 2. Lưu History (Undo point) trước khi thực hiện
        manager.push_history(
            current_path=state.audio.current_path,
            original_path=state.audio.original_path,
            duration=state.audio.duration,
        )

        # 3. Tạo tên file output
        current_name = Path(state.audio.current_path).name

        # --- BẮT ĐẦU PHẦN CODE ĐÃ ĐƯỢC HOÀN THIỆN ---

        # Làm sạch tên file (bỏ prefix original_ nếu có)
        clean_name = (
            current_name.replace("original_", "", 1)
            if current_name.startswith("original_")
            else current_name
        )
        stem = Path(clean_name).stem

        # Tạo tên file mới với timestamp cắt
        new_filename = f"crop_{int(start)}-{int(end)}_{stem}.{fmt}"

        # Xác định đường dẫn output (Sử dụng DATA_OUTPUT_DIR đã được import)
        final_output_path = DATA_OUTPUT_DIR / new_filename

        # Lấy tùy chọn hành động sau khi crop
        mode = st.session_state.get("after_crop", "Stay on source")

        # 4. Cắt Audio (Cut)
        # Gọi AudioProcessor để cắt file
        temp_cut_path = processor.cut_audio(
            start_time=start,
            end_time=end,
            output_filename=str(final_output_path.resolve()),
            export_format=fmt,
            bitrate=export_bitrate_param,
        )

        # Nếu processor trả về path khác (do temp), move về đúng chỗ
        if Path(temp_cut_path).absolute() != final_output_path.absolute():
            shutil.move(temp_cut_path, final_output_path)

        st.session_state.last_crop_output = str(final_output_path)

        # 5. Xử lý logic sau khi cắt (Load ngay hoặc chỉ Save)
        if mode == "Load cropped file":
            # Load file vừa cắt vào processor
            processor.load_audio(str(final_output_path))
            new_duration = processor.duration

            # Cập nhật State (Giữ original_path để bảo toàn context file gốc)
            manager.set_audio(
                path=str(final_output_path),
                original_path=state.audio.original_path,
                duration=new_duration,
            )
            st.toast(f"✅ Loaded ({fmt.upper()}): {new_filename}")
        else:
            # Chỉ thông báo đã lưu
            st.toast(f"💾 Saved to Output: {new_filename}")

    except Exception as e:
        st.error(f"❌ Error: {str(e)}")


def undo_audio_callback():
    manager, state, processor = get_state_objects()

    # 1. Lấy History Entry từ Manager
    prev_entry = manager.pop_history()

    if prev_entry:
        # [FIX BUG-014] Atomic Load: Try to load directly, handle missing file gracefully
        try:
            # 2. LOAD LẠI AUDIO TỪ DISK
            processor.load_audio(prev_entry.path)

            # 3. Restore Audio State
            manager.set_audio(
                path=prev_entry.path,
                original_path=prev_entry.original_path,
                duration=prev_entry.duration,
            )

            # 4. Restore Selection State
            manager.set_selection(
                start=prev_entry.view_start, end=prev_entry.view_end, source="undo"
            )

            st.toast("↩️ Undone successfully")

        except (FileNotFoundError, OSError):
            st.error("❌ History file missing from disk. Cannot undo.")
        except Exception as e:
            st.error(f"Undo Error: {e}")
    else:
        st.warning("No history to undo.")


def reset_audio_callback():
    manager, state, processor = get_state_objects()
    if state.audio.original_path:
        processor.load_audio(state.audio.original_path)
        dur = processor.duration
        st.session_state.history = []
        manager.set_audio(
            path=state.audio.original_path,
            original_path=state.audio.original_path,
            duration=dur,
        )
        st.toast("🔄 Reset to original")


def handle_import_from_link(url: str):
    """
    Callback nút 'Download Link'.
    Non-blocking: Chỉ submit job và update UI state.
    """
    if not url or not url.strip().startswith(("http://", "https://")):
        st.error("⚠️ URL không hợp lệ (phải bắt đầu bằng http/https).")
        return

    manager, state, processor = get_state_objects()
    session_id = get_session_id()

    # Submit Job
    job_id = job_runner.submit(_run_import_task, url=url.strip(), session_id=session_id)

    # Update State
    st.session_state["import_job_id"] = job_id
    st.toast("⬇️ Bắt đầu tải xuống trong nền...")


def check_import_job():
    """
    Kiểm tra trạng thái job Import Link.
    Được gọi bởi Fragment trong UI.
    """
    job_id = st.session_state.get("import_job_id")
    if not job_id:
        return False

    info = job_runner.get_job(job_id)
    status = info.get("status")

    if status == "RUNNING":
        return True

    elif status == "COMPLETED":
        # Lấy kết quả (path file)
        path_str = info["result"]

        if path_str and os.path.exists(path_str):
            try:
                manager, state, processor = get_state_objects()

                # Load Audio Metadata (Duration)
                duration = processor.load_audio(path_str)

                # Update Global State
                manager.set_audio(
                    path=path_str,
                    original_path=path_str,
                    duration=duration,
                    source_url=job_runner.get_job(job_id).get("kwargs", {}).get("url"),
                )

                st.toast("✅ Import thành công!")
            except Exception as e:
                st.error(f"❌ Lỗi khi đọc file tải về: {e}")
        else:
            st.error("❌ Download báo thành công nhưng không thấy file.")

        # Cleanup
        job_runner.clear_job(job_id)
        if "import_job_id" in st.session_state:
            del st.session_state["import_job_id"]

        # Rerun để hiển thị Waveform mới
        st.rerun()
        return False

    elif status == "FAILED":
        error_msg = info.get("error")
        st.error(f"❌ Download thất bại: {error_msg}")

        # Cleanup
        job_runner.clear_job(job_id)
        if "import_job_id" in st.session_state:
            del st.session_state["import_job_id"]

        return False

    return False
