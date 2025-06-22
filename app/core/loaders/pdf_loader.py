import io
import fitz
import base64

from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Union
from llama_index.core.readers.base import BaseReader
from core.base import Document
from PIL import Image

PDF_LOADER_DPI = 40

def convert_page_to_thumbnail(page: fitz.Page, dpi: int = PDF_LOADER_DPI) -> str:
    pm = page.get_pixmap(dpi=dpi)
    img = Image.frombytes("RGB", [pm.width, pm.height], pm.samples)
    return convert_image_to_base64(img)


def convert_pixmap_to_base64(pix: fitz.Pixmap) -> str:
    if pix.n < 5:  # RGB
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    else:  # CMYK or alpha
        pix = fitz.Pixmap(fitz.csRGB, pix)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    return convert_image_to_base64(img)


def convert_image_to_base64(img: Image.Image) -> str:
    img_bytes = BytesIO()
    img.save(img_bytes, format="PNG")
    img_base64 = base64.b64encode(img_bytes.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{img_base64}"


class PyMuPDFReader(BaseReader):
    def load_data(
        self,
        file: Union[str, Path, io.BytesIO],
        extra_info: Optional[Dict] = None,
    ) -> List[Document]:

        if not isinstance(file, (str, Path, io.BytesIO)):
            raise TypeError("Input 'file' must be a string, Path, or io.BytesIO stream.")

        doc = fitz.open(stream=file if isinstance(file, io.BytesIO) else None,
                            filename=file if isinstance(file, (str, Path)) else None)

        if extra_info and not isinstance(extra_info, dict):
            raise TypeError("extra_info must be a dictionary.")

        documents: List[Document] = []
        seen_xrefs = set()

        for page_index in range(doc.page_count):
            page = doc.load_page(page_index)
            text = page.get_text()
            thumbnail = convert_page_to_thumbnail(page)

            embedded_images: List[str] = []
            images_info = page.get_images(full=True)
            for img_info in images_info:
                xref = img_info[0]
                if xref in seen_xrefs:
                    continue
                seen_xrefs.add(xref)

                try:
                    pix = fitz.Pixmap(doc, xref)
                    embedded_base64 = convert_pixmap_to_base64(pix)
                    embedded_images.append(embedded_base64)
                    pix = None
                except Exception as e:
                    print(f"Error while processing image xref={xref} trang {page_index}: {e}")
                    continue

            documents.append(
                Document(
                    text=text,
                    metadata={
                        "type": "page",
                        "page_index": page_index,
                        "thumbnail": thumbnail,
                        "embedded_images": embedded_images,
                        **(extra_info or {}),
                    },
                )
            )

        doc.close()

        return documents
