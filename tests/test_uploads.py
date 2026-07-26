from __future__ import annotations

from interfaces.web.multipart import boundary_of, parse_files
from interfaces.web.server import ReviewApp


def test_boundary_is_extracted_from_the_content_type():
    assert boundary_of("multipart/form-data; boundary=----abc") == "----abc"
    assert boundary_of('multipart/form-data; boundary="xyz"') == "xyz"
    assert boundary_of("text/plain") is None


def _multipart(boundary: str, parts) -> bytes:
    body = b""
    for filename, content in parts:
        body += b"--" + boundary.encode() + b"\r\n"
        body += (
            b'Content-Disposition: form-data; name="files"; filename="'
            + filename.encode()
            + b'"\r\n'
        )
        body += b"Content-Type: application/octet-stream\r\n\r\n"
        body += content + b"\r\n"
    body += b"--" + boundary.encode() + b"--\r\n"
    return body


def test_parse_files_preserves_text_and_binary_content():
    boundary = "BOUNDARY"
    text = b"line1\r\nline2\r\n"  # content that itself ends in a newline
    binary = b"\x00\x01\x02PK"

    files = parse_files(
        _multipart(boundary, [("a.txt", text), ("b.bin", binary)]), boundary
    )

    assert ("a.txt", text) in files
    assert ("b.bin", binary) in files


def test_upload_saves_files_into_the_uploads_folder(tmp_path):
    app = ReviewApp(service=None, projects=None, workspace=tmp_path)

    code, redirect = app.upload(
        "/files",
        [("invoice.xlsx", b"data"), ("../evil.txt", b"x")],
    )

    assert code == 303 and redirect == "/files"
    assert (tmp_path / "uploads" / "invoice.xlsx").read_bytes() == b"data"
    # A traversal filename is reduced to its base name, never escaping uploads.
    assert (tmp_path / "uploads" / "evil.txt").is_file()
    assert not (tmp_path / "evil.txt").exists()


def test_files_page_lists_uploads_and_how_to_reference_them(tmp_path):
    (tmp_path / "uploads").mkdir()
    (tmp_path / "uploads" / "report.pdf").write_bytes(b"x")
    app = ReviewApp(service=None, projects=None, workspace=tmp_path)

    code, body = app.get("/files", {})

    assert code == 200
    assert "report.pdf" in body
    assert "uploads/report.pdf" in body  # shows how the agent refers to it
