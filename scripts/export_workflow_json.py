#!/usr/bin/env python3
"""
PURPOSE:
    Export ONB test cases in workflow-based structure to JSON.

    This reorganizes test cases from technical categories (SAVE, STEP, FORM, GENE)
    into workflow sections that guide testers through natural form completion.

R EQUIVALENT:
    Similar to using dplyr::group_by() and tidyr::nest() to create nested data
    structures, then jsonlite::toJSON() for export.

WHY THIS APPROACH:
    Non-technical testers find workflow-based organization easier to follow.
    Instead of jumping between technical categories, they can complete each
    walkthrough from start to finish.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime


def get_workflow_sections(conn: sqlite3.Connection) -> list:
    """
    PURPOSE:
        Retrieve workflow section definitions from the reference table.

    RETURNS:
        list: List of dicts with section metadata
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT section_code, section_name, section_description, guidance_text, display_order
        FROM uat_workflow_sections
        ORDER BY display_order
    """)

    sections = []
    for row in cursor.fetchall():
        sections.append({
            "code": row[0],
            "name": row[1],
            "description": row[2],
            "guidance": row[3],
            "display_order": row[4]
        })

    return sections


def get_tests_for_section(conn: sqlite3.Connection, section_code: str) -> list:
    """
    PURPOSE:
        Retrieve all test cases for a specific workflow section.

    PARAMETERS:
        section_code (str): The workflow section code (e.g., 'P4M', 'GRX')

    RETURNS:
        list: List of test case dicts ordered by workflow_order
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            test_id,
            title,
            workflow_order,
            category as original_category,
            test_type,
            test_steps,
            expected_results,
            prerequisites,
            priority,
            test_status
        FROM uat_test_cases
        WHERE test_id LIKE 'ONB-%'
          AND workflow_section = ?
        ORDER BY workflow_order
    """, (section_code,))

    tests = []
    for row in cursor.fetchall():
        tests.append({
            "test_id": row[0],
            "title": row[1],
            "workflow_order": row[2],
            "original_category": row[3],
            "test_type": row[4],
            "test_steps": row[5],
            "expected_results": row[6],
            "prerequisites": row[7],
            "priority": row[8],
            "test_status": row[9]
        })

    return tests


def export_workflow_json(db_path: str, output_path: str) -> dict:
    """
    PURPOSE:
        Export all ONB test cases organized by workflow sections.

    PARAMETERS:
        db_path (str): Path to the SQLite database
        output_path (str): Path for the output JSON file

    RETURNS:
        dict: Summary statistics of the export

    WHY THIS APPROACH:
        Creates a nested structure where testers can easily navigate
        through sections in order, rather than hunting for tests
        across technical categories.
    """
    # Connect to database
    conn = sqlite3.connect(db_path)

    # Build the export structure
    export_data = {
        "cycle_name": "ONB Questionnaire v1",
        "structure": "workflow",
        "exported_date": datetime.now().isoformat(),
        "sections": []
    }

    # Get workflow sections and their tests
    sections = get_workflow_sections(conn)

    # Track statistics for summary
    stats = {}

    for section in sections:
        tests = get_tests_for_section(conn, section["code"])

        # Only include sections that have tests
        if tests:
            section_data = {
                "code": section["code"],
                "name": section["name"],
                "description": section["description"],
                "guidance": section["guidance"],
                "test_count": len(tests),
                "tests": tests
            }
            export_data["sections"].append(section_data)
            stats[section["code"]] = len(tests)

    # Calculate totals
    export_data["total_tests"] = sum(stats.values())

    # Write to file with nice formatting
    # indent=2 for readability, ensure_ascii=False to preserve special chars
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)

    conn.close()

    return {
        "output_file": output_path,
        "total_tests": export_data["total_tests"],
        "sections": stats
    }


if __name__ == "__main__":
    # Paths relative to project root
    project_root = Path(__file__).parent.parent
    db_path = project_root / "data" / "client_product_database.db"
    output_path = project_root / "outputs" / "onb_test_cases_workflow.json"

    # Run export
    result = export_workflow_json(str(db_path), str(output_path))

    # Print summary
    print("=" * 60)
    print("ONB Test Cases - Workflow Export Complete")
    print("=" * 60)
    print(f"\nOutput file: {result['output_file']}")
    print(f"Total tests: {result['total_tests']}")
    print("\nTests per section:")
    for section, count in result['sections'].items():
        print(f"  {section}: {count}")
    print("=" * 60)
