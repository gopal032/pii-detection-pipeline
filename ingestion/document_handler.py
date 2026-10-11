import os
from abc import ABC, abstractmethod
import docx
from PIL import Image
from pptx import Presentation
from pypdf import PdfReader
from docx.text.paragraph import Paragraph
from docx.table import Table
import re

def clean_extracted_text(text: str) -> str:
    """Cleans OCR artifacts and layout corruptions from PDF text extraction."""
    # Fix common OCR table-of-contents number corruptions
    text = re.sub(r'\b(al)\b', '11', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(1s\))\b', '15', text)
    # Normalize comparison abbreviations that trigger false-positive names
    text = re.sub(r'\bvs\.?\b', 'vs', text, flags=re.IGNORECASE)
    return text

class BaseDocumentHandler(ABC):
    """Abstract Base Class for all document handlers."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.filename = os.path.basename(file_path)

    @abstractmethod
    def get_file_type(self) -> str:
        """Return human-readable file category name."""
        pass

    @abstractmethod
    def get_page_count(self) -> int:
        """Return total number of pages/slides."""
        pass

    @abstractmethod
    def get_pages_text(self) -> list[str]:
        """Return list of text strings partitioned per page/slide."""
        pass


class TextDocumentHandler(BaseDocumentHandler):

    def get_file_type(self) -> str:
        return "Text Document (.txt)"

    def get_page_count(self) -> int:
        return 1

    def get_pages_text(self) -> list[str]:
        with open(self.file_path, "r", encoding="utf-8", errors="ignore") as f:
            return [f.read()]


class PDFDocumentHandler(BaseDocumentHandler):
    """Reads the text layer of each page and falls back to OCR for pages that have
    no real text (scanned PDFs, image-only pages, 'print to image' exports).

    OCR needs two things installed:
      pip install pymupdf pytesseract
      the Tesseract program itself (Windows: https://github.com/UB-Mannheim/tesseract/wiki)
    """

    OCR_DPI = 250          # render resolution used for OCR
    MIN_TEXT_CHARS = 25    # fewer real characters than this => treat page as image-only

    def get_file_type(self) -> str:
        return "PDF Document (.pdf)"

    def get_page_count(self) -> int:
        try:
            reader = PdfReader(self.file_path)
            return len(reader.pages)
        except Exception:
            return 0

    # ---- OCR helpers ---------------------------------------------------------
    @staticmethod
    def _configure_tesseract():
        import shutil
        import pytesseract

        cmd = os.environ.get("TESSERACT_CMD")
        if not cmd and not shutil.which("tesseract"):
            for candidate in (
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            ):
                if os.path.exists(candidate):
                    cmd = candidate
                    break
        if cmd:
            pytesseract.pytesseract.tesseract_cmd = cmd
        return pytesseract

    def _ocr_one(self, idx: int, pytesseract) -> str:
        """Render and OCR a single 0-based page (each call opens its own handle,
        so pages can be processed in parallel threads)."""
        try:
            import pymupdf  # PyMuPDF >= 1.24
        except ImportError:
            import fitz as pymupdf
        doc = pymupdf.open(self.file_path)
        try:
            zoom = self.OCR_DPI / 72.0
            pix = doc[idx].get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            return pytesseract.image_to_string(
                img, config="--psm 6 -c preserve_interword_spaces=1"
            ).strip()
        finally:
            doc.close()

    def _ocr_pages(self, page_numbers: list[int]) -> dict[int, str]:
        """OCR the given 0-based pages in parallel. Returns {page_index: text}."""
        from concurrent.futures import ThreadPoolExecutor

        pytesseract = self._configure_tesseract()
        workers = max(1, min(4, os.cpu_count() or 1))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            texts = list(pool.map(lambda i: self._ocr_one(i, pytesseract), page_numbers))
        return dict(zip(page_numbers, texts))

    # ---- public API ----------------------------------------------------------
    def get_pages_text(self) -> list[str]:
        try:
            reader = PdfReader(self.file_path)
            pages = []
            for page in reader.pages:
                try:
                    pages.append((page.extract_text() or "").strip())
                except Exception:
                    pages.append("")

            # Pages with no real text layer (whitespace-only counts as empty)
            need_ocr = [
                i for i, t in enumerate(pages)
                if len("".join(t.split())) < self.MIN_TEXT_CHARS
            ]

            if need_ocr:
                try:
                    ocr_text = self._ocr_pages(need_ocr)
                    for i, t in ocr_text.items():
                        pages[i] = t
                except Exception as ocr_err:
                    # Never hide the failure: say why the page is empty
                    for i in need_ocr:
                        pages[i] = (
                            f"[OCR unavailable - page {i + 1} is image-only: {ocr_err}]"
                        )

            return [
                t if t else f"[No text found on page {i + 1}]"
                for i, t in enumerate(pages)
            ]
        except Exception as e:
            return [f"Error reading PDF: {str(e)}"]


class WordDocumentHandler(BaseDocumentHandler):
    """
    Word extractor that walks the raw OOXML so that nothing is skipped:
    body paragraphs, tables (incl. nested), content controls (block and inline),
    tracked insertions, hyperlinks, text boxes, headers/footers, footnotes/endnotes.
    """

    W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

    def get_file_type(self) -> str:
        return "Word Document (.docx)"

    def get_page_count(self) -> int:
        try:
            doc = docx.Document(self.file_path)
            xml = doc.element.body.xml
            breaks = xml.count("lastRenderedPageBreak") + xml.count('w:type="page"')
            return max(1, breaks + 1)
        except Exception:
            return 1

    # ---- low-level helpers -------------------------------------------------
    def _local(self, el) -> str:
        tag = el.tag
        return tag.split("}")[-1] if isinstance(tag, str) else ""

    def _para_text(self, p) -> str:
        """All text of a w:p, including inline sdt, ins, hyperlink, smartTag, etc.
        Text boxes are skipped here (they are extracted as their own blocks)."""
        out = []

        def walk(el):
            name = self._local(el)
            if name == "t":
                out.append(el.text or "")
            elif name == "tab":
                out.append(" ")
            elif name in ("br", "cr"):
                out.append("\n")  # keep manual line breaks (e.g. one name per line in a cell)
            elif name in ("txbxContent", "del", "delText", "instrText", "pPr", "rPr"):
                return  # handled elsewhere / not visible text
            for child in el:
                walk(child)

        walk(p)
        return "".join(out).strip()

    def _textboxes(self, p):
        """Yield txbxContent elements nested in a paragraph (VML + DrawingML),
        de-duplicating the mc:AlternateContent Choice/Fallback copies."""
        seen_text = set()
        for tb in p.iter(self.W + "txbxContent"):
            key = "".join(t.text or "" for t in tb.iter(self.W + "t"))
            if key and key not in seen_text:
                seen_text.add(key)
                yield tb

    def _table_lines(self, tbl):
        lines = []
        for tr in tbl.findall(self.W + "tr"):
            cells = []
            for tc in self._row_cells(tr):
                parts = list(self._blocks(tc))
                cells.append("; ".join(seg.strip() for x in parts if x for seg in x.split("\n") if seg.strip()))
            if any(cells):
                lines.append(" | ".join(c for c in cells if c))
        return lines

    def _row_cells(self, el):
        # cells can be wrapped in sdt/customXml at row level
        for child in el:
            name = self._local(child)
            if name == "tc":
                yield child
            elif name in ("sdt", "customXml"):
                content = child.find(self.W + "sdtContent") if name == "sdt" else child
                if content is not None:
                    yield from self._row_cells(content)

    def _blocks(self, parent):
        """Yield text blocks (strings) in document order from a container."""
        for child in parent:
            name = self._local(child)
            if name == "p":
                txt = self._para_text(child)
                if txt:
                    yield txt
                for tb in self._textboxes(child):
                    yield from self._blocks(tb)
            elif name == "tbl":
                yield from self._table_lines(child)
            elif name == "sdt":
                content = child.find(self.W + "sdtContent")
                if content is not None:
                    yield from self._blocks(content)
            elif name in ("customXml", "smartTag", "ins", "moveTo", "txbxContent", "AlternateContent"):
                yield from self._blocks(child)

    # ---- public API ----------------------------------------------------------
    def get_pages_text(self) -> list[str]:
        try:
            doc = docx.Document(self.file_path)
            texts = list(self._blocks(doc.element.body))

            # headers / footers (deduplicated), footnotes, endnotes
            extra, seen = [], set()
            for section in doc.sections:
                for part in (
                    section.header, section.footer,
                    section.first_page_header, section.first_page_footer,
                    section.even_page_header, section.even_page_footer,
                ):
                    try:
                        for blk in self._blocks(part._element):
                            if blk not in seen:
                                seen.add(blk)
                                extra.append(blk)
                    except Exception:
                        continue
            for rel in doc.part.rels.values():
                if rel.reltype.endswith(("/footnotes", "/endnotes")):
                    try:
                        from lxml import etree
                        root = etree.fromstring(rel.target_part.blob)
                        for note in root:
                            for blk in self._blocks(note):
                                if blk not in seen:
                                    seen.add(blk)
                                    extra.append(blk)
                    except Exception:
                        continue
                # --- ADD OR MODIFY HERE ---
            raw_text = "\n".join(texts + extra)
            cleaned_text = clean_extracted_text(raw_text) # Calls your cleaning helper function
            return [cleaned_text]
  
        except Exception as e:
            return [f"Error reading Word document: {str(e)}"]


class PowerPointDocumentHandler(BaseDocumentHandler):
    """Extracts text from text boxes, tables, grouped shapes, charts' titles and
    speaker notes. Tables were previously skipped, which hid names/emails/phones."""

    def get_file_type(self) -> str:
        return "PowerPoint Presentation (.pptx)"

    def get_page_count(self) -> int:
        try:
            prs = Presentation(self.file_path)
            return len(prs.slides)
        except Exception:
            return 0

    def _shape_lines(self, shape) -> list[str]:
        """Return text lines for a shape, recursing into groups and tables."""
        from pptx.enum.shapes import MSO_SHAPE_TYPE

        lines = []

        # Grouped shapes: recurse
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            for child in shape.shapes:
                lines.extend(self._shape_lines(child))
            return lines

        # Tables (graphic frames) - one line per row, cells joined by " | "
        if getattr(shape, "has_table", False) and shape.has_table:
            for row in shape.table.rows:
                cells = []
                for cell in row.cells:
                    if cell.is_spanned:  # skip cells swallowed by a merge
                        continue
                    txt = " ".join(
                        p.text.strip()
                        for p in cell.text_frame.paragraphs
                        if p.text.strip()
                    )
                    cells.append(txt)
                if any(cells):
                    lines.append(" | ".join(cells))
            return lines

        # Charts: title text only (data labels are not PII-bearing text)
        if getattr(shape, "has_chart", False) and shape.has_chart:
            chart = shape.chart
            if chart.has_title and chart.chart_title.has_text_frame:
                t = chart.chart_title.text_frame.text.strip()
                if t:
                    lines.append(t)

        # Regular text frames (text boxes, placeholders, auto shapes)
        if getattr(shape, "has_text_frame", False) and shape.has_text_frame:
            for paragraph in shape.text_frame.paragraphs:
                text = paragraph.text.strip()
                if text:
                    lines.append(text)

        return lines

    def get_pages_text(self) -> list[str]:
        try:
            prs = Presentation(self.file_path)
            pages_text = []

            for slide in prs.slides:
                slide_text = []
                for shape in slide.shapes:
                    slide_text.extend(self._shape_lines(shape))

                # Speaker notes
                if slide.has_notes_slide:
                    notes = slide.notes_slide.notes_text_frame
                    if notes is not None and notes.text.strip():
                        slide_text.append("[Notes] " + notes.text.strip())

                content = (
                    "\n".join(slide_text)
                    if slide_text
                    else "[No selectable text on slide]"
                )
                pages_text.append(content)

            return (
                pages_text if pages_text else ["[Empty Presentation Uploaded]"]
            )
        except Exception as e:
            return [f"Error reading PowerPoint presentation: {str(e)}"]


class ImageDocumentHandler(BaseDocumentHandler):

    def get_file_type(self) -> str:
        ext = os.path.splitext(self.filename)[1].upper()
        return f"Image File ({ext})"

    def get_page_count(self) -> int:
        return 1

    def get_pages_text(self) -> list[str]:
        try:
            with Image.open(self.file_path) as img:
                return [
                    f"[Image File Uploaded]\nFormat: {img.format}\nDimensions: {img.width} x {img.height} px\nColor Mode: {img.mode}"
                ]
        except Exception as e:
            return [f"Error inspecting image: {str(e)}"]


class DocumentHandlerFactory:
    """Factory class to detect and return the appropriate Handler instance."""

    @staticmethod
    def get_handler(file_path: str) -> BaseDocumentHandler:
        ext = os.path.splitext(file_path)[1].lower()

        if ext == ".txt":
            return TextDocumentHandler(file_path)
        elif ext == ".pdf":
            return PDFDocumentHandler(file_path)
        elif ext in [".docx", ".doc"]:
            return WordDocumentHandler(file_path)
        elif ext in [".pptx", ".ppt"]:
            return PowerPointDocumentHandler(file_path)
        elif ext in [".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"]:
            return ImageDocumentHandler(file_path)
        else:
            raise ValueError(f"Unsupported file format: '{ext}'")