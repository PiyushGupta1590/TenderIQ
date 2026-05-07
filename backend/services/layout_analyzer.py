"""
Layout & Structure Understanding Module
Detects sections, tables, and document structure for layout-aware processing
"""
from __future__ import annotations

import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import pdfplumber
from PIL import Image


class BlockType(str, Enum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    LIST = "list"
    FOOTER = "footer"
    HEADER = "header"


@dataclass
class DocumentBlock:
    """Structured document block with layout information"""
    block_type: BlockType
    content: str
    page_number: int
    section_name: Optional[str] = None
    subsection_name: Optional[str] = None
    bbox: Optional[Tuple[float, float, float, float]] = None  # (x0, y0, x1, y1)
    table_data: Optional[List[List[str]]] = None  # For table blocks
    confidence: float = 1.0


@dataclass
class TableBlock:
    """Structured table with headers and rows"""
    headers: List[str]
    rows: List[List[str]]
    page_number: int
    section_name: Optional[str] = None
    bbox: Optional[Tuple[float, float, float, float]] = None


# Section heading patterns (government tender documents)
_SECTION_PATTERNS = [
    # Financial sections
    (re.compile(r"^(?:SECTION|PART|CLAUSE)\s+[A-Z0-9]+[:\s]*(?:FINANCIAL|TURNOVER|NET\s+WORTH)", re.IGNORECASE), "Financial"),
    (re.compile(r"^FINANCIAL\s+(?:REQUIREMENTS|CRITERIA|ELIGIBILITY)", re.IGNORECASE), "Financial"),
    
    # Technical sections
    (re.compile(r"^(?:SECTION|PART|CLAUSE)\s+[A-Z0-9]+[:\s]*(?:TECHNICAL|EXPERIENCE)", re.IGNORECASE), "Technical"),
    (re.compile(r"^TECHNICAL\s+(?:REQUIREMENTS|CRITERIA|ELIGIBILITY|SPECIFICATIONS)", re.IGNORECASE), "Technical"),
    
    # Compliance sections
    (re.compile(r"^(?:SECTION|PART|CLAUSE)\s+[A-Z0-9]+[:\s]*(?:COMPLIANCE|DOCUMENTS|CERTIFICATES)", re.IGNORECASE), "Compliance"),
    (re.compile(r"^(?:COMPLIANCE|STATUTORY|MANDATORY)\s+(?:REQUIREMENTS|DOCUMENTS)", re.IGNORECASE), "Compliance"),
    
    # Administrative sections
    (re.compile(r"^(?:SECTION|PART|CLAUSE)\s+[A-Z0-9]+[:\s]*(?:ADMINISTRATIVE|GENERAL)", re.IGNORECASE), "Administrative"),
    (re.compile(r"^(?:GENERAL|ADMINISTRATIVE)\s+(?:REQUIREMENTS|INFORMATION)", re.IGNORECASE), "Administrative"),
    
    # Eligibility sections
    (re.compile(r"^(?:SECTION|PART|CLAUSE)\s+[A-Z0-9]+[:\s]*ELIGIBILITY", re.IGNORECASE), "Eligibility"),
    (re.compile(r"^ELIGIBILITY\s+CRITERIA", re.IGNORECASE), "Eligibility"),
]

# Heading detection patterns
_HEADING_PATTERNS = [
    re.compile(r"^(?:SECTION|PART|CHAPTER|CLAUSE|ANNEXURE)\s+[A-Z0-9]+", re.IGNORECASE),
    re.compile(r"^[A-Z][A-Z\s]{10,}$"),  # ALL CAPS lines
    re.compile(r"^\d+\.\s+[A-Z][A-Za-z\s]{5,}$"),  # Numbered headings
]


def _is_heading(line: str, font_size: Optional[float] = None) -> bool:
    """Detect if a line is a heading"""
    line = line.strip()
    
    # Empty or too short
    if len(line) < 3:
        return False
    
    # Check patterns
    for pattern in _HEADING_PATTERNS:
        if pattern.match(line):
            return True
    
    # Font size heuristic (if available)
    if font_size and font_size > 12:
        return True
    
    # All caps and reasonable length
    if line.isupper() and 5 <= len(line) <= 100:
        return True
    
    return False


def _detect_section_name(line: str) -> Optional[str]:
    """Detect section category from heading"""
    for pattern, section_name in _SECTION_PATTERNS:
        if pattern.search(line):
            return section_name
    return None


def _is_footer_header(line: str, page_height: float, y_pos: float) -> bool:
    """Detect if line is in header/footer region"""
    # Top 5% or bottom 5% of page
    if y_pos < page_height * 0.05:
        return True
    if y_pos > page_height * 0.95:
        return True
    
    # Common footer/header patterns
    footer_patterns = [
        r"^Page\s+\d+",
        r"^\d+\s+of\s+\d+$",
        r"^Confidential",
        r"^Tender\s+(?:No|Ref)",
    ]
    for pattern in footer_patterns:
        if re.search(pattern, line, re.IGNORECASE):
            return True
    
    return False


def analyze_pdf_layout(pdf_path: str) -> List[DocumentBlock]:
    """
    Analyze PDF layout and extract structured blocks
    Returns list of DocumentBlock objects with section awareness
    """
    blocks = []
    current_section = None
    current_subsection = None
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            page_height = page.height
            
            # Extract text with position information
            words = page.extract_words()
            
            # Group words into lines
            lines = _group_words_into_lines(words)
            
            # Extract tables
            tables = page.extract_tables()
            if tables:
                for table in tables:
                    if table and len(table) > 1:
                        # First row as headers
                        headers = [str(cell).strip() if cell else "" for cell in table[0]]
                        rows = [[str(cell).strip() if cell else "" for cell in row] for row in table[1:]]
                        
                        # Create table text, ensuring all cells are strings
                        table_text = "\n".join([" | ".join([str(cell) if cell is not None else "" for cell in row]) for row in table])
                        
                        blocks.append(DocumentBlock(
                            block_type=BlockType.TABLE,
                            content=table_text,
                            page_number=page_num,
                            section_name=current_section,
                            subsection_name=current_subsection,
                            table_data=table,
                            confidence=0.95
                        ))
            
            # Process text lines
            for line_data in lines:
                line_text = line_data['text']
                y_pos = line_data['y']
                
                # Skip empty lines
                if not line_text.strip():
                    continue
                
                # Skip headers/footers
                if _is_footer_header(line_text, page_height, y_pos):
                    continue
                
                # Check if heading
                if _is_heading(line_text):
                    # Detect section name
                    detected_section = _detect_section_name(line_text)
                    if detected_section:
                        current_section = detected_section
                        current_subsection = None
                    else:
                        current_subsection = line_text.strip()
                    
                    blocks.append(DocumentBlock(
                        block_type=BlockType.HEADING,
                        content=line_text.strip(),
                        page_number=page_num,
                        section_name=current_section,
                        subsection_name=current_subsection,
                        confidence=0.90
                    ))
                else:
                    # Regular paragraph
                    blocks.append(DocumentBlock(
                        block_type=BlockType.PARAGRAPH,
                        content=line_text.strip(),
                        page_number=page_num,
                        section_name=current_section,
                        subsection_name=current_subsection,
                        confidence=0.95
                    ))
    
    return blocks


def _group_words_into_lines(words: List[Dict]) -> List[Dict]:
    """Group words into lines based on vertical position"""
    if not words:
        return []
    
    # Sort by vertical position
    words_sorted = sorted(words, key=lambda w: (w['top'], w['x0']))
    
    lines = []
    current_line = []
    current_y = words_sorted[0]['top']
    y_tolerance = 3  # pixels
    
    for word in words_sorted:
        if abs(word['top'] - current_y) <= y_tolerance:
            current_line.append(word)
        else:
            # New line
            if current_line:
                line_text = " ".join([str(w.get('text', '')) for w in current_line if w.get('text')])
                lines.append({
                    'text': line_text,
                    'y': current_y,
                    'x0': min(w['x0'] for w in current_line),
                    'x1': max(w['x1'] for w in current_line),
                })
            current_line = [word]
            current_y = word['top']
    
    # Add last line
    if current_line:
        line_text = " ".join([str(w.get('text', '')) for w in current_line if w.get('text')])
        lines.append({
            'text': line_text,
            'y': current_y,
            'x0': min(w['x0'] for w in current_line),
            'x1': max(w['x1'] for w in current_line),
        })
    
    return lines


def create_smart_chunks(blocks: List[DocumentBlock], max_chunk_size: int = 2000) -> List[Dict]:
    """
    Create intelligent chunks based on section boundaries
    Each chunk includes section context
    """
    chunks = []
    current_chunk = []
    current_size = 0
    current_section = None
    current_page = 1
    
    for block in blocks:
        block_size = len(block.content)
        
        # Start new chunk on section boundary or size limit
        if ((block.block_type == BlockType.HEADING and current_chunk) or
            (current_size + block_size > max_chunk_size and current_chunk)):
            # Save current chunk
            chunk_text = "\n".join([b.content for b in current_chunk if b.content])
            chunks.append({
                'text': chunk_text,
                'section_name': current_section,
                'page_start': current_page,
                'page_end': current_chunk[-1].page_number if current_chunk else current_page,
                'blocks': current_chunk,
            })
            current_chunk = []
            current_size = 0
        
        # Update section tracking
        if block.section_name:
            current_section = block.section_name
        if not current_chunk:
            current_page = block.page_number
        
        current_chunk.append(block)
        current_size += block_size
    
    # Add final chunk
    if current_chunk:
        chunk_text = "\n".join([b.content for b in current_chunk if b.content])
        chunks.append({
            'text': chunk_text,
            'section_name': current_section,
            'page_start': current_page,
            'page_end': current_chunk[-1].page_number,
            'blocks': current_chunk,
        })
    
    return chunks


def extract_tables_from_pdf(pdf_path: str) -> List[TableBlock]:
    """
    Extract all tables from PDF with structure preservation
    """
    tables = []
    current_section = None
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            # Track section from text
            text = page.extract_text() or ""
            for line in text.split('\n'):
                detected = _detect_section_name(line)
                if detected:
                    current_section = detected
                    break
            
            # Extract tables
            page_tables = page.extract_tables()
            if page_tables:
                for table in page_tables:
                    if table and len(table) > 1:
                        headers = [str(cell).strip() if cell else "" for cell in table[0]]
                        rows = [[str(cell).strip() if cell else "" for cell in row] for row in table[1:]]
                        
                        tables.append(TableBlock(
                            headers=headers,
                            rows=rows,
                            page_number=page_num,
                            section_name=current_section,
                        ))
    
    return tables
