"""Untrusted document extraction in a short-lived, resource-bounded child process."""

import io
import json
import sys
import zipfile

from defusedxml.ElementTree import fromstring
from pypdf import PdfReader


def extract(data: bytes, kind: str) -> str:
    if kind == "pdf":
        if not data.startswith(b"%PDF-"):
            raise ValueError("Not a PDF")
        reader = PdfReader(io.BytesIO(data), strict=True)
        if reader.is_encrypted or len(reader.pages) > 50:
            raise ValueError("Encrypted or oversized PDF")
        parts = []
        for page in reader.pages:
            content = page.get_contents()
            if content and len(content.get_data()) > 8_000_000:
                raise ValueError("PDF page content is too large")
            parts.append(page.extract_text() or "")
        text = "\n".join(parts)
    else:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            files = archive.infolist()
            if len(files) > 1000 or sum(f.file_size for f in files) > 20_000_000:
                raise ValueError("DOCX archive too large")
            if any(f.flag_bits & 1 or (f.file_size > max(1, f.compress_size) * 100) for f in files):
                raise ValueError("Unsafe DOCX compression")
            names = {f.filename for f in files}
            if not {"[Content_Types].xml", "word/document.xml"} <= names:
                raise ValueError("Not a DOCX")
            if any("vbaproject" in n.lower() for n in names):
                raise ValueError("Macros are not supported")
            content_types = archive.read("[Content_Types].xml")
            if b"macroEnabled" in content_types:
                raise ValueError("Macros are not supported")
            for name in names:
                if name.endswith(".rels"):
                    rels = fromstring(archive.read(name))
                    if any(el.attrib.get("TargetMode", "").lower() == "external" for el in rels):
                        raise ValueError("Remove external document links before uploading")
            document = fromstring(archive.read("word/document.xml"))
            ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
            text = "\n".join("".join(t.text or "" for t in p.iter(ns + "t")) for p in document.iter(ns + "p"))
    if not text.strip():
        raise ValueError("No text found; upload a text-based PDF or DOCX")
    if len(text) > 100_000:
        raise ValueError("Too much document text")
    return text.strip()


def main() -> None:
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_CPU, (8, 8))
        data = sys.stdin.buffer.read(5 * 1024 * 1024 + 1)
        if len(data) > 5 * 1024 * 1024:
            raise ValueError("File too large")
        print(json.dumps({"text": extract(data, sys.argv[1])}))
    except Exception:
        print(
            json.dumps(
                {
                    "error": "Could not extract safe text. Use an unencrypted, text-based PDF or a DOCX without macros or external links."
                }
            )
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
