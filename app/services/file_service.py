from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.file import FileRecord, ImageOperationRecord
from app.schemas.file import FileResponse, ImageOperationResponse, RecordResponse
from app.services.file_storage_service import FileStorageService
from app.services.image_operation_service import ImageGenerationService
from app.services.image_vector_service import ImageVectorIndexService


class FileService:
    """文件业务服务，负责文件入库、查询、编辑和合并记录。"""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.storage_service = FileStorageService()
        self.image_generation_service = ImageGenerationService()
        self.image_vector_service = ImageVectorIndexService()

    def upload_image(self, user_id: int, file: UploadFile) -> FileResponse:
        """上传图片，保存文件记录，并自动尝试写入图片向量库。"""
        storage_key, file_url, file_size = self.storage_service.save_image(user_id, file)

        record = FileRecord(
            user_id=user_id,
            file_name=file.filename or "image.png",
            file_type="image",
            storage_backend=settings.storage_backend.lower(),
            storage_key=storage_key,
            file_url=file_url,
            content_type=file.content_type,
            file_size=file_size,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)

        response = self.to_file_response(record)
        try:
            # 上传后立刻写入图片向量库，后续文搜图/图搜图才能搜到这张图。
            self.image_vector_service.index_image(
                oss_url=record.file_url,
                user_id=user_id,
            )
            response.vectorIndexed = True
            response.vectorIndexError = None
        except Exception as exc:
            # 向量入库依赖大模型和本地 CLIP，失败时不要影响上传本身。
            print(f"图片上传成功，但自动向量入库失败：{exc}")
            response.vectorIndexed = False
            response.vectorIndexError = str(exc)

        return response

    def list_my_images(self, user_id: int) -> list[FileResponse]:
        """查询当前用户上传过的图片。"""
        records = (
            self.db.query(FileRecord)
            .filter(FileRecord.user_id == user_id, FileRecord.file_type == "image")
            .order_by(FileRecord.created_at.desc())
            .all()
        )
        return [self.to_file_response(record) for record in records]

    def edit_image(self, user_id: int, image: str, instruction: str) -> ImageOperationResponse:
        """编辑当前用户的一张图片，并保存历史记录。"""
        self._ensure_user_owns_image(user_id, image)
        output_url = self.image_generation_service.edit_image(image, instruction)
        record = self._create_operation_record(
            user_id=user_id,
            action="edit",
            input_oss_url1=image,
            input_oss_url2=None,
            instruction=instruction,
            output_oss_url=output_url,
        )
        return self.to_operation_response(record)

    def merge_images(
        self,
        user_id: int,
        image1: str,
        image2: str,
        instruction: str,
    ) -> ImageOperationResponse:
        """合并当前用户的两张图片，并保存历史记录。"""
        self._ensure_user_owns_image(user_id, image1)
        self._ensure_user_owns_image(user_id, image2)
        if image1 == image2:
            raise ValueError("请选择两张不同的图片")

        output_url = self.image_generation_service.merge_images(image1, image2, instruction)
        record = self._create_operation_record(
            user_id=user_id,
            action="merge",
            input_oss_url1=image1,
            input_oss_url2=image2,
            instruction=instruction,
            output_oss_url=output_url,
        )
        return self.to_operation_response(record)

    def list_my_records(self, user_id: int) -> list[RecordResponse]:
        """查询当前用户的图片编辑/合并历史记录。"""
        records = (
            self.db.query(ImageOperationRecord)
            .filter(ImageOperationRecord.user_id == user_id)
            .order_by(ImageOperationRecord.created_at.desc())
            .all()
        )
        return [self.to_record_response(record) for record in records]

    def _ensure_user_owns_image(self, user_id: int, image_url: str) -> None:
        """确保用户只能操作自己上传过的图片。"""
        exists = (
            self.db.query(FileRecord)
            .filter(FileRecord.user_id == user_id, FileRecord.file_url == image_url)
            .first()
        )
        if exists is None:
            raise ValueError("只能操作自己上传过的图片")

    def _create_operation_record(
        self,
        user_id: int,
        action: str,
        input_oss_url1: str,
        input_oss_url2: str | None,
        instruction: str,
        output_oss_url: str,
    ) -> ImageOperationRecord:
        """创建一条图片处理历史记录。"""
        record = ImageOperationRecord(
            user_id=user_id,
            action=action,
            input_oss_url1=input_oss_url1,
            input_oss_url2=input_oss_url2,
            instruction=instruction,
            output_oss_url=output_oss_url,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def to_file_response(self, record: FileRecord) -> FileResponse:
        """把文件数据库记录转换成前端需要的字段格式。"""
        return FileResponse(
            id=record.id,
            fileName=record.file_name,
            fileType=record.file_type,
            ossUrl=record.file_url,
            url=record.file_url,
            filePath=record.file_url,
            storageBackend=record.storage_backend,
            createdAt=record.created_at,
        )

    def to_operation_response(self, record: ImageOperationRecord) -> ImageOperationResponse:
        """把图片处理记录转换成编辑/合并接口响应。"""
        return ImageOperationResponse(
            id=record.id,
            action=record.action,
            url=record.output_oss_url,
            saved_oss_url=record.output_oss_url,
            saveUrl=record.output_oss_url,
            outputOssUrl=record.output_oss_url,
        )

    def to_record_response(self, record: ImageOperationRecord) -> RecordResponse:
        """把图片处理记录转换成历史记录响应。"""
        return RecordResponse(
            id=record.id,
            action=record.action,
            inputOssUrl1=record.input_oss_url1,
            inputOssUrl2=record.input_oss_url2,
            instruction=record.instruction,
            outputOssUrl=record.output_oss_url,
            createdAt=record.created_at,
        )
