# FILE: scripts/migrate_user_settings.py
import yaml
import shutil
from pathlib import Path


def migrate():
    """
    Hợp nhất data/config/user_settings.yaml vào config.yaml gốc
    """
    root_dir = Path(__file__).parent.parent
    config_path = root_dir / "config.yaml"
    user_settings_path = root_dir / "data" / "config" / "user_settings.yaml"

    # 1. Kiểm tra file
    if not config_path.exists():
        print("❌ config.yaml không tồn tại!")
        return False

    if not user_settings_path.exists():
        print("ℹ️ Không tìm thấy user_settings.yaml. Không cần di trú.")
        return True

    print(f"🔄 Đang di trú settings từ {user_settings_path} sang {config_path}...")

    # 2. Load dữ liệu
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

        with open(user_settings_path, "r", encoding="utf-8") as f:
            user_settings = yaml.safe_load(f) or {}
    except Exception as e:
        print(f"❌ Lỗi khi đọc file YAML: {e}")
        return False

    # 3. Deep Merge (Ghi đè config bằng user settings)
    def deep_merge(base, update):
        for k, v in update.items():
            if isinstance(v, dict) and k in base:
                deep_merge(base[k], v)
            else:
                base[k] = v

    deep_merge(config, user_settings)

    # 4. Backup config cũ
    backup_path = config_path.with_suffix(".yaml.bak")
    shutil.copy(config_path, backup_path)
    print(f"📦 Đã backup config cũ tại: {backup_path}")

    # 5. Ghi file mới
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(
            config, f, default_flow_style=False, sort_keys=False, allow_unicode=True
        )

    print("✅ Di trú thành công! config.yaml đã được cập nhật.")
    print("⚠️  LƯU Ý: config.yaml giờ chứa thông tin mật. Đừng commit file này lên Git!")
    return True


if __name__ == "__main__":
    migrate()
