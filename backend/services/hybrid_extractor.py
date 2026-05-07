"""
Hybrid Extraction Engine
Combines regex-based extraction with LLM-based semantic extraction
Includes cross-verification and evidence grounding
"""
from __future__ import annotations

import re
import json
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum

from backend.services.layout_analyzer import DocumentBlock, BlockType, TableBlock
from backend.services.llm_extractor import extract_with_llm, LLM_AVAILABLE


class ExtractionStatus(str, Enum):
    OK = "ok"
    MISSING = "missing"
    CONFLICT = "conflict"
    LOW_CONFIDENCE = "low_confidence"


@dataclass
class Evidence:
    """Evidence grounding for extracted values"""
    text: str                    # Exact text snippet
    page: int                    # Page number
    section: Optional[str]       # Section name
    block_type: Optional[str]    # paragraph, table, etc.
    confidence: float            # Evidence quality


@dataclass
class ExtractionResult:
    """Result of field extraction with evidence"""
    field: str
    value: Optional[Any]
    raw_text: Optional[str]
    confidence: float
    evidence: Optional[Evidence]
    extraction_method: str       # "regex", "llm", "hybrid"
    status: ExtractionStatus
    note: Optional[str] = None


@dataclass
class CriterionEvaluation:
    """Evaluation of a tender criterion against bidder data"""
    criterion_id: str
    criterion_label: str
    required_value: Optional[Any]
    extracted_value: Optional[Any]
    meets_requirement: Optional[bool]  # True/False/None (unknown)
    confidence: float
    status: ExtractionStatus
    evidence: Optional[Evidence]
    reasoning: str


class HybridExtractor:
    """
    Hybrid extraction engine combining regex and LLM
    """
    
    def __init__(self, field_patterns: Dict[str, List[re.Pattern]]):
        self.field_patterns = field_patterns
        self.llm_available = LLM_AVAILABLE
    
    def extract_field_regex(
        self,
        field: str,
        blocks: List[DocumentBlock]
    ) -> Optional[ExtractionResult]:
        """
        Extract field using regex patterns
        Returns first match with evidence
        """
        if field not in self.field_patterns:
            return None
        
        patterns = self.field_patterns[field]
        
        for block in blocks:
            if block.block_type in (BlockType.FOOTER, BlockType.HEADER):
                continue
            
            for pattern in patterns:
                match = pattern.search(block.content)
                if match:
                    # Extract value based on field type
                    value = self._parse_match_value(match, field)
                    
                    evidence = Evidence(
                        text=match.group(0)[:200],
                        page=block.page_number,
                        section=block.section_name,
                        block_type=block.block_type.value,
                        confidence=block.confidence
                    )
                    
                    return ExtractionResult(
                        field=field,
                        value=value,
                        raw_text=match.group(0),
                        confidence=block.confidence,
                        evidence=evidence,
                        extraction_method="regex",
                        status=ExtractionStatus.OK if value else ExtractionStatus.MISSING
                    )
        
        return None
    
    def extract_field_llm(
        self,
        field: str,
        chunks: List[Dict],
        context_hint: str = ""
    ) -> Optional[ExtractionResult]:
        """
        Extract field using LLM with section-aware chunks.
        Skips LLM entirely if no chunk contains any keyword for the field.
        """
        if not self.llm_available:
            return None

        # Pre-filter: only call LLM if at least one chunk contains ALL keywords
        # for the field.  Using ALL (not ANY) prevents false positives like
        # the word "card" alone triggering a PAN-card LLM call.
        # Min length >= 2 so short but specific words ("pan","gst","iso") are kept.
        field_keywords = [kw for kw in field.replace('_', ' ').split() if len(kw) >= 2]
        if field_keywords:
            has_keyword = any(
                all(kw in chunk['text'].lower() for kw in field_keywords)
                for chunk in chunks
            )
            if not has_keyword:
                return None  # All keywords not co-located — skip LLM

        # Find most relevant chunk (by section name)
        relevant_chunks = self._find_relevant_chunks(field, chunks)
        
        for chunk in relevant_chunks[:1]:  # Best-ranked chunk only
            chunk_text = chunk['text']
            section = chunk.get('section_name', 'Unknown')
            
            # Call LLM
            value, confidence, raw_response = extract_with_llm(
                chunk_text,
                field,
                context_hint=f"Section: {section}. {context_hint}"
            )
            
            if value is not None and confidence > 0.5:
                # Find evidence text in chunk
                evidence_text = self._find_evidence_in_text(chunk_text, field, value)
                
                evidence = Evidence(
                    text=evidence_text or raw_response[:200],
                    page=chunk['page_start'],
                    section=section,
                    block_type="llm_extracted",
                    confidence=confidence
                )
                
                return ExtractionResult(
                    field=field,
                    value=value,
                    raw_text=evidence_text,
                    confidence=confidence,
                    evidence=evidence,
                    extraction_method="llm",
                    status=ExtractionStatus.OK if confidence > 0.7 else ExtractionStatus.LOW_CONFIDENCE
                )
        
        return None
    
    def extract_field_hybrid(
        self,
        field: str,
        blocks: List[DocumentBlock],
        chunks: List[Dict],
        context_hint: str = ""
    ) -> ExtractionResult:
        """
        Hybrid extraction with cross-verification
        """
        # Try regex first (fast)
        regex_result = self.extract_field_regex(field, blocks)

        # Skip LLM entirely if regex already found a high-confidence result
        if regex_result and regex_result.confidence >= 0.85:
            return regex_result

        # Try LLM if available
        llm_result = None
        if self.llm_available:
            llm_result = self.extract_field_llm(field, chunks, context_hint)
        
        # Cross-verification
        if regex_result and llm_result:
            return self._cross_verify(regex_result, llm_result, field)
        elif regex_result:
            return regex_result
        elif llm_result:
            return llm_result
        else:
            # Not found
            return ExtractionResult(
                field=field,
                value=None,
                raw_text=None,
                confidence=0.0,
                evidence=None,
                extraction_method="none",
                status=ExtractionStatus.MISSING,
                note=f"Field '{field}' not found in document"
            )
    
    def _cross_verify(
        self,
        regex_result: ExtractionResult,
        llm_result: ExtractionResult,
        field: str
    ) -> ExtractionResult:
        """
        Cross-verify regex and LLM results
        """
        # Compare values
        regex_val = regex_result.value
        llm_val = llm_result.value
        
        # Normalize for comparison
        if isinstance(regex_val, (int, float)) and isinstance(llm_val, (int, float)):
            # Numeric comparison with tolerance
            tolerance = max(abs(regex_val), abs(llm_val)) * 0.1  # 10% tolerance
            values_match = abs(regex_val - llm_val) <= tolerance
        else:
            # String comparison
            values_match = str(regex_val).lower().strip() == str(llm_val).lower().strip()
        
        if values_match:
            # Agreement - boost confidence
            combined_confidence = min(
                (regex_result.confidence + llm_result.confidence) / 2 + 0.1,
                0.98
            )
            
            # Prefer regex evidence (more precise)
            return ExtractionResult(
                field=field,
                value=regex_val,
                raw_text=regex_result.raw_text,
                confidence=combined_confidence,
                evidence=regex_result.evidence,
                extraction_method="hybrid",
                status=ExtractionStatus.OK,
                note="Cross-verified: regex and LLM agree"
            )
        else:
            # Conflict - flag for review
            return ExtractionResult(
                field=field,
                value=regex_val if regex_result.confidence > llm_result.confidence else llm_val,
                raw_text=f"CONFLICT: Regex={regex_val}, LLM={llm_val}",
                confidence=min(regex_result.confidence, llm_result.confidence),
                evidence=regex_result.evidence if regex_result.confidence > llm_result.confidence else llm_result.evidence,
                extraction_method="hybrid",
                status=ExtractionStatus.CONFLICT,
                note=f"Conflict detected: regex found '{regex_val}', LLM found '{llm_val}'"
            )
    
    def _find_relevant_chunks(self, field: str, chunks: List[Dict]) -> List[Dict]:
        """Find chunks most likely to contain the field.
        Caches lowercased text per chunk to avoid repeated .lower() calls.
        """
        field_sections = {
            'annual_turnover': ['Financial', 'Technical'],
            'net_worth': ['Financial'],
            'bid_security': ['Financial', 'Administrative'],
            'experience_years': ['Technical'],
            'completed_projects': ['Technical'],
            'gst_registration': ['Compliance', 'Administrative'],
            'pan_card': ['Compliance', 'Administrative'],
            'iso_certification': ['Compliance', 'Technical'],
        }

        preferred_sections = field_sections.get(field, [])
        field_keywords = field.replace('_', ' ').split()

        scored_chunks = []
        for chunk in chunks:
            score = 0
            if chunk.get('section_name', '') in preferred_sections:
                score += 10
            # Cache lowercase once per chunk to avoid O(keywords) .lower() calls
            chunk_lower = chunk.get('_text_lower')
            if chunk_lower is None:
                chunk_lower = chunk['text'].lower()
                chunk['_text_lower'] = chunk_lower  # cache in-place
            for keyword in field_keywords:
                if keyword.lower() in chunk_lower:
                    score += 1
            scored_chunks.append((score, chunk))

        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        return [chunk for score, chunk in scored_chunks]
    
    def _find_evidence_in_text(self, text: str, field: str, value: Any) -> Optional[str]:
        """Find the specific text snippet that contains the value"""
        # Search for value in text
        value_str = str(value)
        
        # Try to find sentence containing value
        sentences = re.split(r'[.!?\n]+', text)
        for sentence in sentences:
            if value_str in sentence or field.replace('_', ' ') in sentence.lower():
                return sentence.strip()[:200]
        
        return None
    
    def _parse_match_value(self, match: re.Match, field: str) -> Optional[Any]:
        """Parse value from regex match based on field type"""
        # Financial fields
        if field in ('annual_turnover', 'net_worth', 'bid_security', 'performance_guarantee', 'similar_work_value'):
            try:
                num_str = match.group(1).replace(',', '')
                value = float(num_str)
                
                # Apply unit multiplier
                unit = match.group(2) if match.lastindex >= 2 else None
                if unit:
                    unit_map = {'crore': 1e7, 'lakh': 1e5, 'million': 1e6, 'cr': 1e7, 'l': 1e5}
                    value *= unit_map.get(unit.lower(), 1)
                
                return value
            except Exception:
                return None
        
        # Numeric fields
        elif field in ('experience_years', 'completed_projects', 'key_personnel', 'warranty_period'):
            try:
                return float(match.group(1).replace(',', ''))
            except Exception:
                return None
        
        # String fields (registration numbers, etc.)
        elif field in ('gst_registration', 'pan_card', 'msme_registration'):
            try:
                return match.group(1).strip() if match.lastindex >= 1 else match.group(0).strip()
            except Exception:
                return match.group(0).strip()
        
        # Boolean presence fields
        else:
            return True


def evaluate_criterion(
    criterion: Dict,
    extraction_result: ExtractionResult
) -> CriterionEvaluation:
    """
    Evaluate if extracted value meets criterion requirement
    """
    criterion_id = criterion.get('id', '')
    criterion_label = criterion.get('label', '')
    required_value = criterion.get('value')
    operator = criterion.get('operator', '>=')
    
    extracted_value = extraction_result.value
    
    # If no value extracted
    if extracted_value is None:
        return CriterionEvaluation(
            criterion_id=criterion_id,
            criterion_label=criterion_label,
            required_value=required_value,
            extracted_value=None,
            meets_requirement=None,
            confidence=0.0,
            status=ExtractionStatus.MISSING,
            evidence=None,
            reasoning=f"Required field '{criterion_label}' not found in bidder documents"
        )
    
    # Evaluate based on operator
    meets_requirement = None
    reasoning = ""
    
    if operator == "present":
        meets_requirement = bool(extracted_value)
        reasoning = f"Found: {extracted_value}" if meets_requirement else "Not found"
    
    elif operator in (">=", "<=", ">", "<", "=="):
        if required_value is None:
            meets_requirement = None
            reasoning = "Criterion threshold not defined"
        else:
            try:
                req_val = float(required_value)
                ext_val = float(extracted_value)
                
                if operator == ">=":
                    meets_requirement = ext_val >= req_val
                elif operator == "<=":
                    meets_requirement = ext_val <= req_val
                elif operator == ">":
                    meets_requirement = ext_val > req_val
                elif operator == "<":
                    meets_requirement = ext_val < req_val
                elif operator == "==":
                    meets_requirement = abs(ext_val - req_val) < 0.01
                
                if meets_requirement:
                    reasoning = f"Found {ext_val:,.0f} which satisfies {operator} {req_val:,.0f}"
                else:
                    reasoning = f"Found {ext_val:,.0f} which does NOT satisfy {operator} {req_val:,.0f}"
            
            except (ValueError, TypeError):
                meets_requirement = None
                reasoning = f"Could not compare values: {extracted_value} vs {required_value}"
    
    return CriterionEvaluation(
        criterion_id=criterion_id,
        criterion_label=criterion_label,
        required_value=required_value,
        extracted_value=extracted_value,
        meets_requirement=meets_requirement,
        confidence=extraction_result.confidence,
        status=extraction_result.status,
        evidence=extraction_result.evidence,
        reasoning=reasoning
    )
