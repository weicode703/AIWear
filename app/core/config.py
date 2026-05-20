import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(override=True)


class Settings:
    """统一管理项目配置，其他模块不要到处直接读 os.getenv。"""

    def __init__(self) -> None:
        # 数据库和 Redis
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./aiwear.db")
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

        # JWT 登录令牌配置
        self.jwt_secret = os.getenv("JWT_SECRET", "replace-with-your-secret")
        self.jwt_expire_hours = int(os.getenv("JWT_EXPIRE_HOURS", "2"))

        # 邮箱验证码配置
        self.email_enabled = os.getenv("EMAIL_ENABLED", "false").lower() == "true"
        self.smtp_host = os.getenv("SMTP_HOST", "")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.smtp_from_email = os.getenv("SMTP_FROM_EMAIL", "")
        self.verification_code_expire_seconds = int(
            os.getenv("VERIFICATION_CODE_EXPIRE_SECONDS", "300")
        )

        # 文件存储配置：OSS 没开通前，先使用本地 uploads 目录。
        self.storage_backend = os.getenv("STORAGE_BACKEND", "local")
        self.upload_dir = Path(os.getenv("UPLOAD_DIR", "./uploads")).resolve()
        self.local_file_base_url = os.getenv("LOCAL_FILE_BASE_URL", "/uploads")

        # 本地 CLIP 模型目录，用来把图片转成 512 维向量。
        self.clip_model_dir = Path(
            os.getenv("CLIP_MODEL_DIR", "./models/clip-vit-base-patch16")
        ).resolve()
        self.image_search_min_score = float(os.getenv("IMAGE_SEARCH_MIN_SCORE", "0.25"))

        # 阿里百炼 / DashScope 模型配置，用来调用 qwen-vl-max。
        self.dashscope_api_key = os.getenv("DASHSCOPE_API_KEY", "")

        # 阿里 OSS 预留配置，申请完成后再填。
        self.oss_endpoint = os.getenv("OSS_ENDPOINT", "")
        self.oss_bucket = os.getenv("OSS_BUCKET", "")
        self.oss_access_key_id = os.getenv("OSS_ACCESS_KEY_ID", "")
        self.oss_access_key_secret = os.getenv("OSS_ACCESS_KEY_SECRET", "")
        self.oss_base_url = os.getenv("OSS_BASE_URL", "")


settings = Settings()
