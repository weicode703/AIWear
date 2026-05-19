import smtplib
from email.message import EmailMessage

from app.core.config import settings


class EmailService:
    """负责发送验证码邮件。"""

    def send_verification_code(self, to_email: str, code: str) -> bool:
        """发送验证码邮件。

        如果本地没有配置真实邮箱服务，就直接把验证码打印出来。
        这样你学习阶段也能先跑通。
        """
        if not settings.email_enabled:
            print(f"[开发模式] 发送到邮箱 {to_email} 的验证码是：{code}")
            return True

        try:
            message = EmailMessage()
            message["Subject"] = "【AIWear】邮箱验证码"
            message["From"] = settings.smtp_from_email
            message["To"] = to_email
            message.set_content(
                f"尊敬的用户，您好！\n\n"
                f"您的验证码是：{code}\n\n"
                f"验证码有效期 5 分钟。"
            )

            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                server.starttls()
                server.login(settings.smtp_username, settings.smtp_password)
                server.send_message(message)

            return True
        except Exception as exc:
            print(f"发送验证码邮件失败：{exc}")
            return False
