from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User
from app.schemas.user import (
    AuthRequest,
    AuthResponse,
    SendVerificationCodeRequest,
    SendVerificationCodeResponse,
)
from app.services.email_service import EmailService
from app.services.jwt_service import JwtService
from app.services.password_service import PasswordService
from app.services.verification_code_service import VerificationCodeService


class UserService:
    """用户服务。

    当前保留：
    1. 用户数据存在数据库
    2. 验证码存在 Redis
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.email_service = EmailService()
        self.jwt_service = JwtService()
        self.password_service = PasswordService()
        self.verification_code_service = VerificationCodeService()

    def send_verification_code(
        self,
        request: SendVerificationCodeRequest,
    ) -> SendVerificationCodeResponse:
        """发送邮箱验证码。"""
        email = request.email

        if self.verification_code_service.has_valid_code(email):
            raise ValueError("验证码尚未过期，请勿重复发送")

        code = self.verification_code_service.generate_code()
        self.verification_code_service.save_code(email, code)

        success = self.email_service.send_verification_code(email, code)
        if not success:
            # 发邮件失败时，把刚写入 Redis 的验证码删掉，避免占住发送窗口
            self.verification_code_service.delete_code(email)
            raise RuntimeError("验证码发送失败，请稍后重试")

        return SendVerificationCodeResponse(
            send_to="***",
            expire_time=settings.verification_code_expire_seconds,
        )

    def auth(self, request: AuthRequest) -> AuthResponse:
        """统一认证逻辑。"""
        account = request.account.strip()
        is_email = "@" in account

        user = (
            self.db.query(User)
            .filter(or_(User.username == account, User.email == account))
            .first()
        )

        if is_email:
            code = (request.verification_code or "").strip()
            if not code:
                raise ValueError("验证码不能为空")

            if not self.verification_code_service.verify_code(account, code):
                raise ValueError("验证码不存在或已经过期")

            # 邮箱用户不存在，就自动注册
            if user is None:
                user = User(username=account, email=account)
                self.db.add(user)
                self.db.commit()
                self.db.refresh(user)

        else:
            password = request.password or ""
            if not password:
                raise ValueError("密码不能为空")

            # 用户名不存在，就自动注册
            if user is None:
                user = User(
                    username=account,
                    password_hash=self.password_service.hash_password(password),
                )
                self.db.add(user)
                self.db.commit()
                self.db.refresh(user)
            else:
                if not user.password_hash:
                    raise ValueError("当前账号未设置密码，请使用邮箱验证码登录")

                if not self.password_service.verify_password(password, user.password_hash):
                    raise ValueError("用户名或密码错误")

        return AuthResponse(
            user_id=user.id,
            username=user.username,
            email=user.email,
            token=self.jwt_service.generate_token(user),
        )
