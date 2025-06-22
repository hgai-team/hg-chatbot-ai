import io
from typing import Tuple
from fastapi import UploadFile

async def parse_file(file: UploadFile) -> Tuple[str, io.BytesIO]:
    file_name = file.filename
    file_bytes = io.BytesIO(await file.read())
    return file_name, file_bytes
