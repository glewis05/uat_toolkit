# importers/nccn_notation_parser.py
# ============================================================================
# NCCN TEST NOTATION PARSER
# ============================================================================
# PURPOSE: Parse NCCN test case notation into structured, executable data.
#
# TEST NOTATION FORMAT:
#   "POS: PHX: Prostate Cancer, Gleason 8 (aggressive)"
#   "NEG: FDR: Breast Cancer, age 45 AND SDR: Ovarian Cancer"
#
# NOTATION KEY:
#   POS/NEG     = Expected outcome (should/shouldn't trigger rule)
#   PHX         = Patient History (patient's own cancer)
#   FDR         = First Degree Relative (parent, sibling, child)
#   SDR         = Second Degree Relative (grandparent, aunt/uncle, niece/nephew)
#   TDR         = Third Degree Relative (cousin, great-grandparent)
#   AND         = Multiple conditions (joins separate entries)
#
# AVIATION ANALOGY:
#   Like parsing a mission briefing into discrete waypoints and actions.
#   Each condition becomes a specific checkbox or dropdown selection
#   in the assessment form, similar to preflight checklist items.
#
# ============================================================================

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class CancerCondition:
    """
    PURPOSE:
        Represents a single cancer condition from the test notation.
    
    FIELDS:
        cancer_type: The type of cancer (e.g., "Prostate", "Breast")
        age_diagnosed: Age at diagnosis if specified
        gleason_score: Gleason score for prostate cancer (7, 8, 9, etc.)
        is_aggressive: Whether marked as aggressive
        is_metastatic: Whether cancer was metastatic
        additional_notes: Any extra qualifiers in parentheses
    """
    cancer_type: str
    age_diagnosed: Optional[int] = None
    gleason_score: Optional[int] = None
    is_aggressive: Optional[bool] = None
    is_metastatic: Optional[bool] = None
    additional_notes: Optional[str] = None


@dataclass
class RelativeEntry:
    """
    PURPOSE:
        Represents a relative (or patient) entry with their conditions.
    
    FIELDS:
        relationship: PHX, FDR, SDR, TDR, or specific like "Mother", "Father"
        relationship_type: Normalized type (patient, first_degree, second_degree, third_degree)
        specific_relative: If specified, the actual relative (e.g., "Mother")
        conditions: List of cancer conditions for this person
        is_same_relative: Whether this is the same person as previous entry
    """
    relationship: str
    relationship_type: str
    specific_relative: Optional[str] = None
    conditions: List[CancerCondition] = field(default_factory=list)
    is_same_relative: bool = False


@dataclass
class ParsedTestCase:
    """
    PURPOSE:
        Complete parsed representation of an NCCN test case notation.
    
    FIELDS:
        expected_outcome: 'positive' (should trigger) or 'negative' (shouldn't trigger)
        entries: List of RelativeEntry objects representing each person's conditions
        raw_notation: Original notation string for reference
        target_rule: NCCN rule being tested (if extractable)
        platform: P4M or Px4M
        parse_errors: Any warnings or issues during parsing
    """
    expected_outcome: str
    entries: List[RelativeEntry] = field(default_factory=list)
    raw_notation: str = ""
    target_rule: Optional[str] = None
    platform: Optional[str] = None
    parse_errors: List[str] = field(default_factory=list)


# ============================================================================
# MAPPING CONSTANTS
# ============================================================================

# Maps notation prefixes to relationship types
# PHX = Patient History, FDR = First Degree, etc.
RELATIONSHIP_MAP = {
    'PHX': 'patient',
    'PATIENT': 'patient',
    'FDR': 'first_degree',
    'FIRST DEGREE': 'first_degree',
    'SDR': 'second_degree', 
    'SECOND DEGREE': 'second_degree',
    'TDR': 'third_degree',
    'THIRD DEGREE': 'third_degree',
}

# Maps outcome prefixes to normalized values
OUTCOME_MAP = {
    'POS': 'positive',
    'POSITIVE': 'positive',
    'NEG': 'negative',
    'NEGATIVE': 'negative',
    'DEP': 'deprecated',
    'DEPRECATED': 'deprecated',
}

# Cancer type normalization
# Maps variations in notation to standardized cancer types
CANCER_TYPE_MAP = {
    # Prostate variations
    'PROSTATE': 'Prostate',
    'PROSTATE CANCER': 'Prostate',
    
    # Breast variations
    'BREAST': 'Breast',
    'BREAST CANCER': 'Breast',
    'MALE BREAST': 'Male Breast',
    'MALE BREAST CANCER': 'Male Breast',
    
    # Colorectal variations
    'COLON': 'Colorectal',
    'COLON CANCER': 'Colorectal',
    'COLORECTAL': 'Colorectal',
    'COLORECTAL CANCER': 'Colorectal',
    'RECTAL': 'Colorectal',
    
    # Ovarian variations
    'OVARIAN': 'Ovarian',
    'OVARIAN CANCER': 'Ovarian',
    'OVARY': 'Ovarian',
    
    # Endometrial variations
    'ENDOMETRIAL': 'Endometrial',
    'ENDOMETRIAL CANCER': 'Endometrial',
    'UTERINE': 'Endometrial',
    
    # Pancreatic variations
    'PANCREATIC': 'Pancreatic',
    'PANCREATIC CANCER': 'Pancreatic',
    'PANCREAS': 'Pancreatic',
    
    # Kidney/Renal variations
    'RENAL': 'Kidney',
    'RENAL CANCER': 'Kidney',
    'KIDNEY': 'Kidney',
    'KIDNEY CANCER': 'Kidney',
    
    # New Q4 2025 additions
    'MESOTHELIOMA': 'Mesothelioma',
    'UVEAL MELANOMA': 'Uveal Melanoma',
    'MELANOMA OF EYE': 'Uveal Melanoma',
    'EYE MELANOMA': 'Uveal Melanoma',
    
    # Gastric
    'GASTRIC': 'Gastric',
    'GASTRIC CANCER': 'Gastric',
    'STOMACH': 'Gastric',
}


# ============================================================================
# PARSER FUNCTIONS
# ============================================================================

def parse_test_notation(
    notation: str,
    target_rule: str = None,
    platform: str = None
) -> ParsedTestCase:
    """
    PURPOSE:
        Parse an NCCN test case notation string into structured data.
        This is the main entry point for the parser.
    
    R EQUIVALENT:
        Like tidyr::separate() followed by purrr::map() to extract components.
    
    PARAMETERS:
        notation (str): The raw notation string, e.g., 
                        "POS: PHX: Prostate Cancer, Gleason 8"
        target_rule (str): Optional NCCN rule ID being tested
        platform (str): Optional platform (P4M, Px4M)
    
    RETURNS:
        ParsedTestCase: Structured representation of the test case
    
    AVIATION ANALOGY:
        Like parsing a mission briefing into discrete waypoints.
        "POS: PHX: Prostate, Gleason 8" becomes:
        - Mission outcome: Positive (weapon should fire)
        - Target 1: Patient, Prostate cancer, Gleason 8
    
    WHY THIS APPROACH:
        - Handles notation variations (POS vs POSITIVE, etc.)
        - Extracts all relevant attributes (age, Gleason, etc.)
        - Returns structured data that Chrome instruction generator can use
        - Captures parse errors without failing completely
    
    EXAMPLES:
        >>> result = parse_test_notation("POS: PHX: Prostate Cancer, Gleason 8")
        >>> result.expected_outcome
        'positive'
        >>> result.entries[0].relationship_type
        'patient'
        >>> result.entries[0].conditions[0].gleason_score
        8
    """
    result = ParsedTestCase(
        expected_outcome='unknown',
        raw_notation=notation,
        target_rule=target_rule,
        platform=platform
    )
    
    if not notation or not notation.strip():
        result.parse_errors.append("Empty notation string")
        return result
    
    # Clean up the notation
    notation = notation.strip()
    
    # Step 1: Extract outcome (POS/NEG) from the beginning
    outcome, remainder = _extract_outcome(notation)
    result.expected_outcome = outcome
    
    if not remainder:
        result.parse_errors.append("No conditions found after outcome")
        return result
    
    # Step 2: Split by AND to get individual entries
    # "PHX: Prostate AND FDR: Breast" → ["PHX: Prostate", "FDR: Breast"]
    entry_strings = _split_by_and(remainder)
    
    # Step 3: Parse each entry into RelativeEntry objects
    for entry_str in entry_strings:
        entry = _parse_single_entry(entry_str)
        if entry:
            result.entries.append(entry)
        else:
            result.parse_errors.append(f"Failed to parse entry: {entry_str}")
    
    return result


def _extract_outcome(notation: str) -> Tuple[str, str]:
    """
    PURPOSE:
        Extract the POS/NEG outcome prefix from notation.
    
    PARAMETERS:
        notation (str): Full notation string
    
    RETURNS:
        Tuple[str, str]: (normalized_outcome, remainder_of_string)
    
    EXAMPLES:
        "POS: PHX: Prostate" → ('positive', 'PHX: Prostate')
        "NEG: FDR: Breast"   → ('negative', 'FDR: Breast')
    """
    # Pattern: POS: or POSITIVE: at start (case insensitive)
    pattern = r'^(POS|NEG|POSITIVE|NEGATIVE|DEP|DEPRECATED)\s*:\s*'
    match = re.match(pattern, notation, re.IGNORECASE)
    
    if match:
        outcome_raw = match.group(1).upper()
        outcome = OUTCOME_MAP.get(outcome_raw, 'unknown')
        remainder = notation[match.end():].strip()
        return outcome, remainder
    
    # No explicit outcome found - return unknown
    return 'unknown', notation


def _split_by_and(notation: str) -> List[str]:
    """
    PURPOSE:
        Split notation into separate entries by AND keyword.
        Handles "same FDR" and "same SDR" as single combined entries.
    
    PARAMETERS:
        notation (str): Notation without the POS/NEG prefix
    
    RETURNS:
        List[str]: Individual entry strings
    
    EXAMPLES:
        "PHX: Prostate AND FDR: Breast" → ["PHX: Prostate", "FDR: Breast"]
        "FDR: Colon AND same FDR: Endometrial" → ["FDR: Colon", "same FDR: Endometrial"]
    """
    # Split by AND (with optional whitespace)
    # BUT preserve "same FDR" type references
    parts = re.split(r'\s+AND\s+', notation, flags=re.IGNORECASE)
    return [p.strip() for p in parts if p.strip()]


def _parse_single_entry(entry_str: str) -> Optional[RelativeEntry]:
    """
    PURPOSE:
        Parse a single entry like "PHX: Prostate Cancer, Gleason 8"
        into a RelativeEntry object.
    
    PARAMETERS:
        entry_str (str): Single entry string (no AND)
    
    RETURNS:
        RelativeEntry or None if parsing fails
    
    EXAMPLES:
        "PHX: Prostate Cancer, Gleason 8" → RelativeEntry(relationship='PHX', ...)
        "same FDR: Endometrial" → RelativeEntry(is_same_relative=True, ...)
    """
    if not entry_str:
        return None
    
    # Check for "same" prefix indicating same relative as previous
    is_same = False
    if entry_str.lower().startswith('same '):
        is_same = True
        entry_str = entry_str[5:].strip()  # Remove "same "
    
    # Pattern: RELATIONSHIP: conditions
    # e.g., "PHX: Prostate Cancer, Gleason 8"
    # e.g., "FDR: Breast Cancer, age 45"
    pattern = r'^(PHX|FDR|SDR|TDR|PATIENT)\s*:\s*(.+)$'
    match = re.match(pattern, entry_str, re.IGNORECASE)
    
    if not match:
        # Try to parse without relationship prefix (assume PHX)
        return RelativeEntry(
            relationship='PHX',
            relationship_type='patient',
            conditions=[_parse_condition(entry_str)],
            is_same_relative=is_same
        )
    
    relationship = match.group(1).upper()
    condition_str = match.group(2).strip()
    
    # Normalize relationship type
    relationship_type = RELATIONSHIP_MAP.get(relationship, 'unknown')
    
    # Parse the condition(s)
    condition = _parse_condition(condition_str)
    
    return RelativeEntry(
        relationship=relationship,
        relationship_type=relationship_type,
        conditions=[condition] if condition else [],
        is_same_relative=is_same
    )


def _parse_condition(condition_str: str) -> CancerCondition:
    """
    PURPOSE:
        Parse a condition string into a CancerCondition object.
        Extracts cancer type, age, Gleason score, and other attributes.
    
    PARAMETERS:
        condition_str (str): Condition like "Prostate Cancer, Gleason 8 (aggressive)"
    
    RETURNS:
        CancerCondition with extracted attributes
    
    EXAMPLES:
        "Prostate Cancer, Gleason 8" → CancerCondition(cancer_type='Prostate', gleason_score=8)
        "Breast Cancer, age 45"      → CancerCondition(cancer_type='Breast', age_diagnosed=45)
    """
    result = CancerCondition(cancer_type='Unknown')
    
    if not condition_str:
        return result
    
    # Extract parenthetical notes first (e.g., "(aggressive)", "(same patient)")
    notes_match = re.search(r'\(([^)]+)\)', condition_str)
    if notes_match:
        notes = notes_match.group(1).lower()
        result.additional_notes = notes_match.group(1)
        
        # Check for aggressive indicator
        if 'aggressive' in notes:
            result.is_aggressive = True
        elif 'non-aggressive' in notes or 'non aggressive' in notes:
            result.is_aggressive = False
            
        # Check for metastatic
        if 'metastatic' in notes:
            result.is_metastatic = True
            
        # Remove parenthetical from condition string for further parsing
        condition_str = condition_str[:notes_match.start()] + condition_str[notes_match.end():]
    
    # Extract age if present
    # Patterns: "age 45", "age: 45", "diagnosed at 45"
    age_match = re.search(r'age[:\s]+(\d+)', condition_str, re.IGNORECASE)
    if age_match:
        result.age_diagnosed = int(age_match.group(1))
    
    # Extract Gleason score if present (prostate-specific)
    # Patterns: "Gleason 8", "Gleason: 8", "Gleason score 8"
    gleason_match = re.search(r'gleason[:\s]*(?:score[:\s]*)?\s*(\d+)', condition_str, re.IGNORECASE)
    if gleason_match:
        result.gleason_score = int(gleason_match.group(1))
        # Gleason 7+ is generally considered aggressive
        if result.is_aggressive is None and result.gleason_score >= 7:
            result.is_aggressive = True
    
    # Extract cancer type
    # Remove age and gleason patterns, then clean up
    cancer_str = condition_str
    cancer_str = re.sub(r',?\s*age[:\s]+\d+', '', cancer_str, flags=re.IGNORECASE)
    cancer_str = re.sub(r',?\s*gleason[:\s]*(?:score[:\s]*)?\s*\d+', '', cancer_str, flags=re.IGNORECASE)
    cancer_str = re.sub(r'\s*,\s*$', '', cancer_str)  # Trailing comma
    cancer_str = cancer_str.strip()
    
    # Normalize cancer type
    cancer_upper = cancer_str.upper()
    result.cancer_type = CANCER_TYPE_MAP.get(cancer_upper, cancer_str)
    
    return result


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def notation_to_dict(parsed: ParsedTestCase) -> Dict:
    """
    PURPOSE:
        Convert ParsedTestCase to a plain dictionary for JSON serialization
        or passing to the Chrome instruction generator.
    
    PARAMETERS:
        parsed (ParsedTestCase): The parsed test case
    
    RETURNS:
        dict: Dictionary representation suitable for JSON/instruction generation
    
    WHY THIS APPROACH:
        - Dataclasses don't serialize directly to JSON
        - Chrome instruction generator expects plain dicts
        - Easier to inspect/debug as dict
    """
    return {
        'expected_outcome': parsed.expected_outcome,
        'target_rule': parsed.target_rule,
        'platform': parsed.platform,
        'raw_notation': parsed.raw_notation,
        'parse_errors': parsed.parse_errors,
        'entries': [
            {
                'relationship': entry.relationship,
                'relationship_type': entry.relationship_type,
                'specific_relative': entry.specific_relative,
                'is_same_relative': entry.is_same_relative,
                'conditions': [
                    {
                        'cancer_type': cond.cancer_type,
                        'age_diagnosed': cond.age_diagnosed,
                        'gleason_score': cond.gleason_score,
                        'is_aggressive': cond.is_aggressive,
                        'is_metastatic': cond.is_metastatic,
                        'additional_notes': cond.additional_notes,
                    }
                    for cond in entry.conditions
                ]
            }
            for entry in parsed.entries
        ]
    }


def validate_notation(notation: str) -> Dict:
    """
    PURPOSE:
        Validate a notation string and return any issues found.
        Useful for checking test case data quality.
    
    PARAMETERS:
        notation (str): The notation string to validate
    
    RETURNS:
        dict: {
            'valid': bool,
            'errors': list of error messages,
            'warnings': list of warning messages,
            'parsed': dict representation if valid
        }
    
    WHY THIS APPROACH:
        - Separate validation from parsing for cleaner error handling
        - Returns actionable feedback for fixing notation issues
        - Can be used in batch validation of test case data
    """
    result = {
        'valid': True,
        'errors': [],
        'warnings': [],
        'parsed': None
    }
    
    if not notation or not notation.strip():
        result['valid'] = False
        result['errors'].append("Notation is empty")
        return result
    
    # Parse the notation
    parsed = parse_test_notation(notation)
    
    # Check for parse errors
    if parsed.parse_errors:
        result['warnings'].extend(parsed.parse_errors)
    
    # Check outcome was extracted
    if parsed.expected_outcome == 'unknown':
        result['warnings'].append("No POS/NEG outcome prefix found")
    
    # Check we have at least one entry
    if not parsed.entries:
        result['valid'] = False
        result['errors'].append("No conditions/entries found in notation")
        return result
    
    # Check each entry has conditions
    for i, entry in enumerate(parsed.entries):
        if not entry.conditions:
            result['warnings'].append(f"Entry {i+1} has no conditions")
        else:
            for j, cond in enumerate(entry.conditions):
                if cond.cancer_type == 'Unknown':
                    result['warnings'].append(f"Entry {i+1}, condition {j+1}: Unknown cancer type")
    
    result['parsed'] = notation_to_dict(parsed)
    return result


# ============================================================================
# CLI INTERFACE (for testing)
# ============================================================================

if __name__ == '__main__':
    import sys
    import json
    
    # Test notations
    test_cases = [
        "POS: PHX: Prostate Cancer, Gleason 8 (aggressive)",
        "NEG: TDR: Prostate, Gleason 5 (non-aggressive)",
        "POS: FDR: Breast Cancer, age 45 AND SDR: Ovarian Cancer",
        "POS: PHX: Colon Cancer AND PHX: Endometrial Cancer (same patient)",
        "NEG: PHX: Prostate (no Gleason specified)",
        "POS: FDR: Renal Cancer AND same FDR: Mesothelioma",
    ]
    
    # If argument provided, use that instead
    if len(sys.argv) > 1:
        test_cases = [' '.join(sys.argv[1:])]
    
    print("=" * 70)
    print("  NCCN NOTATION PARSER TEST")
    print("=" * 70)
    
    for notation in test_cases:
        print(f"\nInput: {notation}")
        print("-" * 50)
        
        result = parse_test_notation(notation)
        result_dict = notation_to_dict(result)
        
        print(json.dumps(result_dict, indent=2))
        print()
