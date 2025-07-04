from pydantic import BaseModel, Field, HttpUrl
from typing import Type

class ToolDefinition(BaseModel):
    name: str
    description: str
    args_schema: Type[BaseModel]

    def to_json_schema(self) -> dict:
        schema = self.args_schema.model_json_schema()
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": schema.get("properties", {}),
                "required": schema.get("required", [])
            }
        }

class CommentAnalyze(BaseModel):
    """
    Mô hình dữ liệu cho các tham số đầu vào của công cụ phân tích bình luận.
    """
    video_url: HttpUrl = Field(
        ...,
        description="Đường link URL đầy đủ của video YouTube cần phân tích."
    )

    user_request: str = Field(
        None,
        description=(
            "Yêu cầu cụ thể của người dùng về việc phân tích. "
            "Ví dụ: 'tóm tắt các bình luận tiêu cực', 'tìm các chủ đề chính đang được thảo luận', 'liệt kê những câu hỏi thường gặp nhất trong bình luận'. "
            "**Nếu trường hợp có lịch sử hội thoại cần xem xét lại tổng thể  để xem yêu cầu cụ thể của người dùng về việc phân tích là gì, và sau đó viết lại một cách rõ ràng.**"
            "**Nếu để trống, hệ thống sẽ tự động thực hiện phân tích và trích xuất các insight chính.**"
        )
    )
