"""Test bounded extraction independently of source publication."""

import base64
from io import BytesIO

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from acg_agent_platform.models.platform import ExtractDocument
from acg_agent_platform.services.documents import extract_document


def request(data: bytes, name: str = "test.pdf") -> ExtractDocument:
    return ExtractDocument(filename=name, data_base64=base64.b64encode(data).decode())


def test_text_pdf_is_extracted_without_ocr() -> None:
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
    )
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 20 200 Td (Invoice total 12400.00 EUR) Tj ET")
    page[NameObject("/Contents")] = stream
    buffer = BytesIO()
    writer.write(buffer)
    assert "12400.00" in extract_document(request(buffer.getvalue()))


@pytest.mark.parametrize(
    "data,name",
    [
        (b"bad PDF", "bad.pdf"),
        (b"anything", "run.exe"),
        (b"\x00binary text here", "binary.txt"),
        (b"\xff\xfe", "broken.txt"),
    ],
)
def test_invalid_documents_rejected(data: bytes, name: str) -> None:
    with pytest.raises(ValueError):
        extract_document(request(data, name))


def test_blank_pdf_requires_ocr_or_manual_input() -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    buffer = BytesIO()
    writer.write(buffer)
    with pytest.raises(ValueError):
        extract_document(request(buffer.getvalue()))


def test_eml_extracts_plain_body_without_attachment_processing() -> None:
    data = (
        b"From: a@example.com\r\nContent-Type: text/plain; charset=utf-8\r\n"
        b"\r\nVPN support request."
    )
    assert "VPN support request" in extract_document(request(data, "mail.eml"))
