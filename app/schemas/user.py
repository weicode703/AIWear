from pydantic import BaseModel, EmailStr, Field


class SendVerificationCodeRequest(BaseModel):
    """发送邮箱验证码请求体。"""

    email: EmailStr = Field(..., description="接收验证码的邮箱")


class SendVerificationCodeResponse(BaseModel):
    """发送邮箱验证码成功后的响应体。"""

    send_to: str = Field(..., description="脱敏后的收件信息")
    expire_time: int = Field(..., description="验证码有效期，单位秒")


class AuthRequest(BaseModel):
    """统一认证请求体。

    account 包含 @ 时走邮箱验证码登录，否则走用户名密码登录。
    """

    account: str = Field(..., description="用户名或邮箱")
    password: str | None = Field(default=None, description="用户名登录时使用的密码")
    verification_code: str | None = Field(default=None, description="邮箱登录时使用的验证码")


class AuthResponse(BaseModel):
    """统一认证成功后的响应体。"""

    user_id: int
    username: str
    email: str | None = None
    token: str


class CurrentUserResponse(BaseModel):
    """当前登录用户信息。"""

    user_id: int
    username: str
    email: str | None = None
