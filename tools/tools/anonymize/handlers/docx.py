"""
tools/handlers/docx.py - Tai lieu Word (.docx).

Word cat mot doan van thanh nhieu "run" theo dinh dang, nen mot email co the bi
xe lam doi (`lore` + `toa@isb.ac.th`). Vi vay ta gop van ban cua ca doan lai roi
moi xu ly; doan nao thuc su thay doi thi don ket qua vao run dau tien.
Doan khong chua thong tin nhay cam duoc giu nguyen tuyet doi.

Quet ca than bai, bang bieu, text box, dau trang va chan trang.
"""

from __future__ import annotations

import io

from ..core import AnonymizeError, Cipher
from .base import Handler, transform_text

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class DocxHandler(Handler):
    name = "docx"
    label = "Word (.docx)"
    suffixes = (".docx",)
    binary = True

    def process(self, raw: bytes, cipher: Cipher, mode: str, strict: bool = False) -> bytes:
        try:
            import docx
        except ImportError as exc:
            raise AnonymizeError(
                "Can cai python-docx de xu ly .docx:  pip install python-docx"
            ) from exc

        document = docx.Document(io.BytesIO(raw))
        for part in self._parts(document):
            for paragraph in part.iter(W + "p"):
                self._process_paragraph(paragraph, cipher, mode, strict)

        buf = io.BytesIO()
        document.save(buf)
        return buf.getvalue()

    # -- chi tiet -------------------------------------------------------
    @staticmethod
    def _parts(document):
        """Than bai + moi dau trang / chan trang cua tung section."""
        yield document.element.body
        for section in document.sections:
            for area in (
                "header", "footer",
                "first_page_header", "first_page_footer",
                "even_page_header", "even_page_footer",
            ):
                try:
                    element = getattr(section, area)._element
                except (AttributeError, ValueError, KeyError):
                    continue
                if element is not None:
                    yield element

    @staticmethod
    def _process_paragraph(paragraph, cipher: Cipher, mode: str, strict: bool) -> None:
        nodes = [t for t in paragraph.iter(W + "t")]
        if not nodes:
            return
        original = "".join(node.text or "" for node in nodes)
        if not original.strip():
            return

        updated = transform_text(original, cipher, mode, strict)
        if updated == original:
            return                      # khong dung toi -> giu nguyen dinh dang

        nodes[0].text = updated
        nodes[0].set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        for node in nodes[1:]:
            node.text = ""
