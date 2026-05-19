from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.file import (
    EditImageRequest,
    ImageVectorIndexRequest,
    MergeImageRequest,
    TextImageSearchRequest,
)
from app.services.file_service import FileService
from app.services.image_vector_service import ImageVectorIndexService


router = APIRouter(prefix="/api/file", tags=["文件模块"])


@router.post("/upload/image", response_model=ApiResponse)
def upload_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse:
    """上传当前登录用户的一张图片。"""
    try:
        data = FileService(db).upload_image(current_user.id, file)
        return ApiResponse(code=200, message="上传成功", data=data.model_dump())
    except ValueError as exc:
        return ApiResponse(code=400, message=str(exc), data=None)
    except Exception as exc:
        print(f"上传图片接口异常：{exc}")
        return ApiResponse(code=500, message="上传失败，请稍后重试", data=None)


@router.get("/my-images", response_model=ApiResponse)
def my_images(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse:
    """查询当前登录用户上传过的图片列表。"""
    data = FileService(db).list_my_images(current_user.id)
    return ApiResponse(
        code=200,
        message="操作成功",
        data=[item.model_dump() for item in data],
    )


@router.post("/edit", response_model=ApiResponse)
def edit_image(
    request: EditImageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse:
    """编辑当前登录用户的一张图片。"""
    try:
        data = FileService(db).edit_image(
            user_id=current_user.id,
            image=request.image,
            instruction=request.instruction,
        )
        return ApiResponse(code=200, message="图片编辑成功", data=data.model_dump())
    except ValueError as exc:
        return ApiResponse(code=400, message=str(exc), data=None)
    except Exception as exc:
        print(f"图片编辑接口异常：{exc}")
        return ApiResponse(code=500, message="图片编辑失败，请稍后重试", data=None)


@router.post("/merge", response_model=ApiResponse)
def merge_images(
    request: MergeImageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse:
    """合并当前登录用户的两张图片。"""
    try:
        data = FileService(db).merge_images(
            user_id=current_user.id,
            image1=request.image1,
            image2=request.image2,
            instruction=request.instruction,
        )
        return ApiResponse(code=200, message="图片合并成功", data=data.model_dump())
    except ValueError as exc:
        return ApiResponse(code=400, message=str(exc), data=None)
    except Exception as exc:
        print(f"图片合并接口异常：{exc}")
        return ApiResponse(code=500, message="图片合并失败，请稍后重试", data=None)


@router.post("/index-image-vector", response_model=ApiResponse)
def index_image_vector(
    request: ImageVectorIndexRequest,
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    """把图片描述和 CLIP 向量保存到 Redis，后续文搜图/图搜图会用到。"""
    if request.userId != current_user.id:
        return ApiResponse(code=403, message="不能为其他用户保存图片向量", data=None)

    try:
        data = ImageVectorIndexService().index_image(
            oss_url=request.ossUrl,
            user_id=current_user.id,
        )
        return ApiResponse(code=200, message="图片向量索引保存成功", data=data.model_dump())
    except ValueError as exc:
        return ApiResponse(code=400, message=str(exc), data=None)
    except RuntimeError as exc:
        return ApiResponse(code=500, message=str(exc), data=None)
    except Exception as exc:
        print(f"图片向量索引接口异常：{exc}")
        return ApiResponse(code=500, message="图片向量索引保存失败，请稍后重试", data=None)


@router.post("/search/text", response_model=ApiResponse)
def search_by_text(
    request: TextImageSearchRequest,
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    """文搜图：用户输入文字，返回 Redis 中最相似的图片。"""
    try:
        data = ImageVectorIndexService().search_by_text(
            user_id=current_user.id,
            query=request.query,
            top_k=request.topK,
        )
        return ApiResponse(code=200, message="文搜图成功", data=data.model_dump())
    except ValueError as exc:
        return ApiResponse(code=400, message=str(exc), data=None)
    except RuntimeError as exc:
        return ApiResponse(code=500, message=str(exc), data=None)
    except Exception as exc:
        print(f"文搜图接口异常：{exc}")
        return ApiResponse(code=500, message="文搜图失败，请稍后重试", data=None)


@router.post("/search/image", response_model=ApiResponse)
async def search_by_image(
    file: UploadFile | None = File(None),
    imageUrl: str | None = Form(None),
    topK: int = Form(10),
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    """图搜图：上传图片或传入图片地址，返回 Redis 中最相似的图片。"""
    try:
        service = ImageVectorIndexService()

        if file is not None:
            image_data = await file.read()
            data = service.search_by_image_data(
                user_id=current_user.id,
                image_data=image_data,
                top_k=topK,
            )
        elif imageUrl:
            data = service.search_by_image_url(
                user_id=current_user.id,
                image_url=imageUrl,
                top_k=topK,
            )
        else:
            return ApiResponse(code=400, message="请上传图片或填写 imageUrl", data=None)

        return ApiResponse(code=200, message="图搜图成功", data=data.model_dump())
    except ValueError as exc:
        return ApiResponse(code=400, message=str(exc), data=None)
    except RuntimeError as exc:
        return ApiResponse(code=500, message=str(exc), data=None)
    except Exception as exc:
        print(f"图搜图接口异常：{exc}")
        return ApiResponse(code=500, message="图搜图失败，请稍后重试", data=None)
