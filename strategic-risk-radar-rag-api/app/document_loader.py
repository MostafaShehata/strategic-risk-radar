from io import BytesIO
import json
import re
import xml.etree.ElementTree as ET

from pypdf import PdfReader


class DocumentParser:
    def parse_bytes(self, filename: str, content: bytes, content_type: str | None = None) -> tuple[str, str]:
        document_type = self.detect_type(filename, content_type)
        if document_type == "pdf":
            return document_type, self.parse_pdf(content)
        if document_type == "json":
            return document_type, self.parse_json(content)
        if document_type == "xml":
            return document_type, self.parse_xml(content)
        return "text", self.parse_text(content)

    def detect_type(self, filename: str, content_type: str | None) -> str:
        lowered_name = filename.casefold()
        lowered_type = (content_type or "").casefold()
        if lowered_name.endswith(".pdf") or "pdf" in lowered_type:
            return "pdf"
        if lowered_name.endswith(".json") or "json" in lowered_type:
            return "json"
        if lowered_name.endswith(".xml") or "xml" in lowered_type:
            return "xml"
        return "text"

    def parse_pdf(self, content: bytes) -> str:
        reader = PdfReader(BytesIO(content))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(page.strip() for page in pages if page.strip())

    def parse_json(self, content: bytes) -> str:
        data = json.loads(content.decode("utf-8"))
        return "\n".join(self.flatten_json(data))

    def parse_xml(self, content: bytes) -> str:
        root = ET.fromstring(content.decode("utf-8"))
        return "\n".join(value for value in self.flatten_xml(root) if value)

    def parse_text(self, content: bytes) -> str:
        return content.decode("utf-8", errors="ignore")

    def flatten_json(self, value, prefix: str = "") -> list[str]:
        if isinstance(value, dict):
            rows = []
            for key, child in value.items():
                child_prefix = f"{prefix}.{key}" if prefix else str(key)
                rows.extend(self.flatten_json(child, child_prefix))
            return rows
        if isinstance(value, list):
            rows = []
            for index, child in enumerate(value):
                rows.extend(self.flatten_json(child, f"{prefix}[{index}]"))
            return rows
        if value is None:
            return []
        return [f"{prefix}: {value}" if prefix else str(value)]

    def flatten_xml(self, element: ET.Element, prefix: str = "") -> list[str]:
        name = f"{prefix}.{element.tag}" if prefix else element.tag
        rows = [f"{name}: {element.text.strip()}"] if element.text and element.text.strip() else []
        for child in element:
            rows.extend(self.flatten_xml(child, name))
        return rows


class TextChunker:
    def __init__(self, max_words: int) -> None:
        self.max_words = max_words

    def chunk_text(self, text: str) -> list[str]:
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
        chunks: list[str] = []
        current: list[str] = []
        for paragraph in paragraphs or [text]:
            words = paragraph.split()
            while len(words) > self.max_words:
                chunks.append(" ".join(words[:self.max_words]))
                words = words[self.max_words:]
            if len(current) + len(words) > self.max_words and current:
                chunks.append(" ".join(current))
                current = []
            current.extend(words)
        if current:
            chunks.append(" ".join(current))
        return chunks
