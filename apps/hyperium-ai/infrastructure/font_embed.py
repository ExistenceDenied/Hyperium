"""
Embed the Inter faces into generated Office files so they render identically on
any machine — the Python-side parity of admin-finance's docx font embedding.

- Word (.docx): OOXML font embedding via ODTTF-obfuscated parts (ISO/IEC 29500-1
  §17.8.1) + a fontTable + the `<w:embedTrueTypeFonts/>` setting.
- PowerPoint (.pptx): OOXML font embedding via raw `.fntdata` parts + a
  `<p:embeddedFontLst>` and `embedTrueTypeFonts="1"` on the presentation.

Both are best-effort: if the bundled fonts are missing the input is returned
unchanged, so document generation never fails on their account.
"""

from __future__ import annotations

import io
import re
import uuid
import zipfile
from pathlib import Path

_FONTS = Path(__file__).resolve().parent.parent / "assets" / "fonts"
_NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

# The 'Inter' family faces we embed (Regular / SemiBold-as-Bold / Italic / BoldItalic).
_REGULAR = "Inter-Regular.ttf"
_BOLD = "Inter-SemiBold.ttf"
_ITALIC = "Inter-Italic.ttf"
_BOLDITALIC = "Inter-SemiBoldItalic.ttf"

_DOCX_FACES = [(_REGULAR, "w:embedRegular"), (_BOLD, "w:embedBold"), (_ITALIC, "w:embedItalic")]
_PPTX_FACES = [
    (_REGULAR, "p:regular"),
    (_BOLD, "p:bold"),
    (_ITALIC, "p:italic"),
    (_BOLDITALIC, "p:boldItalic"),
]


def _obfuscate(data: bytes, guid: str) -> bytes:
    """ODTTF: XOR the first 32 bytes with the fontKey GUID's 16 bytes, reversed."""
    key = bytes.fromhex(guid.replace("{", "").replace("}", "").replace("-", ""))
    out = bytearray(data)
    for i in range(min(32, len(out))):
        out[i] ^= key[15 - (i % 16)]
    return bytes(out)


def _read_zip(data: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        return {name: zf.read(name) for name in zf.namelist()}


def _write_zip(parts: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in parts.items():
            zf.writestr(name, content)
    return buffer.getvalue()


def _have(files: list[tuple[str, str]]) -> bool:
    return _FONTS.is_dir() and all((_FONTS / f).is_file() for f, _ in files)


def embed_docx_fonts(docx: bytes) -> bytes:
    """Embed Inter into a .docx (ODTTF). Returns the input unchanged on failure."""
    if not _have(_DOCX_FACES):
        return docx
    try:
        parts = _read_zip(docx)
        rels, embeds = [], []
        for i, (fname, tag) in enumerate(_DOCX_FACES, start=1):
            guid = "{" + str(uuid.uuid4()).upper() + "}"
            parts[f"word/fonts/font{i}.odttf"] = _obfuscate((_FONTS / fname).read_bytes(), guid)
            rels.append(f'<Relationship Id="rId{i}" Type="{_NS_R}/font" Target="fonts/font{i}.odttf"/>')
            embeds.append(f'<{tag} r:id="rId{i}" w:fontKey="{guid}"/>')

        parts["word/fontTable.xml"] = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            f'<w:fonts xmlns:w="{_NS_W}" xmlns:r="{_NS_R}">'
            '<w:font w:name="Inter"><w:charset w:val="00"/><w:family w:val="swiss"/>'
            f'<w:pitch w:val="variable"/>{"".join(embeds)}</w:font></w:fonts>'
        ).encode()
        parts["word/_rels/fontTable.xml.rels"] = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'{"".join(rels)}</Relationships>'
        ).encode()

        content_types = parts["[Content_Types].xml"].decode()
        if 'Extension="odttf"' not in content_types:
            content_types = content_types.replace(
                "</Types>",
                '<Default Extension="odttf" ContentType="application/vnd.openxmlformats-officedocument.obfuscatedFont"/></Types>',
            )
        if "/word/fontTable.xml" not in content_types:
            content_types = content_types.replace(
                "</Types>",
                '<Override PartName="/word/fontTable.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.fontTable+xml"/></Types>',
            )
        parts["[Content_Types].xml"] = content_types.encode()

        settings = parts["word/settings.xml"].decode()
        if "embedTrueTypeFonts" not in settings:
            tag = "<w:embedTrueTypeFonts/>"
            # Insert in a schema-valid slot: after displayBackgroundShape/print*,
            # before the first element that follows embedTrueTypeFonts in the
            # CT_Settings sequence (proofState / defaultTabStop / compat / ...).
            if "<w:displayBackgroundShape/>" in settings:
                settings = settings.replace("<w:displayBackgroundShape/>", "<w:displayBackgroundShape/>" + tag)
            else:
                match = re.search(
                    r"<w:(proofState|characterSpacingControl|savePreviewPicture|defaultTabStop|compat|rsids|embedSystemFonts|saveSubsetFonts)\b",
                    settings,
                )
                if match:
                    settings = settings[: match.start()] + tag + settings[match.start() :]
                else:
                    settings = re.sub(r"(<w:settings\b[^>]*>)", r"\1" + tag, settings, count=1)
        parts["word/settings.xml"] = settings.encode()

        doc_rels = parts.get("word/_rels/document.xml.rels", b"").decode()
        if doc_rels and "relationships/fontTable" not in doc_rels:
            doc_rels = doc_rels.replace(
                "</Relationships>",
                f'<Relationship Id="rIdFontTable" Type="{_NS_R}/fontTable" Target="fontTable.xml"/></Relationships>',
            )
            parts["word/_rels/document.xml.rels"] = doc_rels.encode()

        return _write_zip(parts)
    except Exception:
        return docx


def embed_pptx_fonts(pptx: bytes) -> bytes:
    """Embed Inter into a .pptx (fntdata). Returns the input unchanged on failure."""
    if not _have(_PPTX_FACES):
        return pptx
    try:
        parts = _read_zip(pptx)
        rels, faces = [], []
        for i, (fname, element) in enumerate(_PPTX_FACES, start=1):
            rid = f"rIdFont{i}"
            parts[f"ppt/fonts/font{i}.fntdata"] = (_FONTS / fname).read_bytes()
            rels.append(f'<Relationship Id="{rid}" Type="{_NS_R}/font" Target="fonts/font{i}.fntdata"/>')
            faces.append(f'<{element} r:id="{rid}"/>')

        content_types = parts["[Content_Types].xml"].decode()
        if 'Extension="fntdata"' not in content_types:
            content_types = content_types.replace(
                "</Types>", '<Default Extension="fntdata" ContentType="application/x-fontdata"/></Types>'
            )
        parts["[Content_Types].xml"] = content_types.encode()

        pres_rels = parts["ppt/_rels/presentation.xml.rels"].decode()
        pres_rels = pres_rels.replace("</Relationships>", "".join(rels) + "</Relationships>")
        parts["ppt/_rels/presentation.xml.rels"] = pres_rels.encode()

        presentation = parts["ppt/presentation.xml"].decode()
        if "embedTrueTypeFonts" not in presentation:
            presentation = presentation.replace("<p:presentation ", '<p:presentation embedTrueTypeFonts="1" ', 1)
        font_list = f'<p:embeddedFontLst><p:embeddedFont><p:font typeface="Inter"/>{"".join(faces)}</p:embeddedFont></p:embeddedFontLst>'
        # CT_Presentation: embeddedFontLst precedes defaultTextStyle.
        if "<p:embeddedFontLst>" not in presentation:
            if "<p:defaultTextStyle>" in presentation:
                presentation = presentation.replace("<p:defaultTextStyle>", font_list + "<p:defaultTextStyle>", 1)
            else:
                presentation = presentation.replace("</p:presentation>", font_list + "</p:presentation>", 1)
        parts["ppt/presentation.xml"] = presentation.encode()

        return _write_zip(parts)
    except Exception:
        return pptx
