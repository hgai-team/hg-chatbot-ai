from typing import Dict, Any

from .cmt_ytb import comment_analyze
from .vid_ytb import video_analyze

from .schema import (
    ToolDefinition,
    CommentAnalyze,
    VideoAnalyze
)

comment_analyzer_tool = ToolDefinition(
    name="comment_analyze",
    description="Phân tích bình luận của một video YouTube dựa trên một yêu cầu cụ thể từ người dùng.",
    args_schema=CommentAnalyze
)

video_analyzer_tool = ToolDefinition(
    name="video_analyze",
    description="Phân tích nội dung của một video YouTube dựa trên một yêu cầu cụ thể từ người dùng.",
    args_schema=VideoAnalyze
)

TOOLS = [
    comment_analyzer_tool,
    video_analyzer_tool
]

TOOL_FUNCTIONS: Dict[str, Any] = {
    "video_analyze": video_analyze,
    "comment_analyze": comment_analyze,
}
