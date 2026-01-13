#!/usr/bin/env python3
"""
PURPOSE:
    Generate personalized UAT tracker HTML files for each tester.

    This script reads test assignments from the database and creates
    individual tracker HTML files for each tester assigned to a UAT cycle.

R EQUIVALENT:
    Similar to using dplyr::group_by(assigned_to) then purrr::walk() to
    generate an HTML file for each group using an RMarkdown template.

USAGE:
    python scripts/generate_tester_trackers.py <cycle_id> [formspree_id]

EXAMPLE:
    python scripts/generate_tester_trackers.py UAT-NCCN-Q4-2025 mqeekjjz

OUTPUT:
    docs/<cycle-folder>/
        index.html            # Tester selection page
        tracker-kim.html      # Kim's personalized tracker
        tracker-lily.html     # Lily's personalized tracker
        ...

WHY THIS APPROACH:
    Static HTML files on GitHub Pages means:
    - No server infrastructure to maintain
    - Testers can work offline (localStorage)
    - Simple deployment via git push
    - Each tester gets their own URL to bookmark
"""

import json
import sqlite3
import sys
import re
from datetime import datetime
from pathlib import Path


# =====================================================
# PATH CONFIGURATION
# =====================================================
# Like R's here::here() for project-relative paths
SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
DB_PATH = REPO_ROOT / "data" / "client_product_database.db"
DOCS_PATH = REPO_ROOT / "docs"
TEMPLATE_PATH = DOCS_PATH / "templates" / "workflow-tracker-template.html"


def slugify(text: str) -> str:
    """
    PURPOSE:
        Convert text to URL-safe slug.

    PARAMETERS:
        text (str): Text to convert (e.g., "Kim Childers")

    RETURNS:
        str: URL-safe slug (e.g., "kim-childers")

    R EQUIVALENT:
        stringr::str_to_lower() %>% str_replace_all("[^a-z0-9]+", "-")
    """
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text


def get_cycle_info(cursor, cycle_id: str) -> dict:
    """
    PURPOSE:
        Get UAT cycle metadata from the database.

    PARAMETERS:
        cursor: SQLite cursor
        cycle_id (str): The cycle identifier (e.g., "UAT-NCCN-Q4-2025")

    RETURNS:
        dict: Cycle metadata or None if not found
    """
    cursor.execute("""
        SELECT
            cycle_id, name, uat_type, status,
            target_launch_date, clinical_pm, clinical_pm_email
        FROM uat_cycles
        WHERE cycle_id = ?
    """, (cycle_id,))

    row = cursor.fetchone()
    if not row:
        return None

    return {
        "cycle_id": row[0],
        "cycle_name": row[1],
        "uat_type": row[2],
        "status": row[3],
        "target_date": row[4] or "TBD",
        "clinical_pm": row[5],
        "clinical_pm_email": row[6]
    }


def get_testers_for_cycle(cursor, cycle_id: str) -> list:
    """
    PURPOSE:
        Get distinct testers assigned to this cycle.

    PARAMETERS:
        cursor: SQLite cursor
        cycle_id (str): The cycle identifier

    RETURNS:
        list: List of tester email addresses

    WHY THIS APPROACH:
        We query DISTINCT assigned_to from uat_test_cases where
        the test is linked to this cycle. This works because
        assignments are stored directly on the test case record.
    """
    cursor.execute("""
        SELECT DISTINCT assigned_to
        FROM uat_test_cases
        WHERE uat_cycle_id = ?
        AND assigned_to IS NOT NULL
        AND assigned_to != ''
        ORDER BY assigned_to
    """, (cycle_id,))

    return [row[0] for row in cursor.fetchall()]


def get_tests_for_tester(cursor, cycle_id: str, tester: str) -> list:
    """
    PURPOSE:
        Get all test cases assigned to a specific tester.

    PARAMETERS:
        cursor: SQLite cursor
        cycle_id (str): The cycle identifier
        tester (str): Tester email address

    RETURNS:
        list: List of test case dictionaries
    """
    cursor.execute("""
        SELECT
            test_id,
            title,
            workflow_section,
            workflow_order,
            category,
            test_type,
            test_steps,
            expected_results,
            prerequisites,
            priority,
            compliance_framework,
            assignment_type,
            profile_id,
            platform,
            persona,
            target_rule,
            patient_conditions
        FROM uat_test_cases
        WHERE uat_cycle_id = ?
        AND assigned_to = ?
        ORDER BY
            CASE workflow_section
                WHEN 'P4M' THEN 1
                WHEN 'PR4M' THEN 2
                WHEN 'GRX' THEN 3
                WHEN 'DRAFT' THEN 4
                WHEN 'EDGE' THEN 5
                WHEN 'POS' THEN 1
                WHEN 'NEG' THEN 2
                WHEN 'DEP' THEN 3
                ELSE 6
            END,
            workflow_order,
            test_id
    """, (cycle_id, tester))

    tests = []
    for row in cursor.fetchall():
        # Use workflow_section if set, otherwise fall back to category
        section = row[2] if row[2] else row[4]

        tests.append({
            "test_id": row[0],
            "title": row[1],
            "workflow_section": section or "OTHER",
            "workflow_order": row[3] or 0,
            "category": row[4],
            "test_type": row[5] or "happy_path",
            "test_steps": row[6] or "",
            "expected_results": row[7] or "",
            "prerequisites": row[8] or "",
            "priority": row[9] or "Should Have",
            "compliance_framework": row[10],
            "assignment_type": row[11],
            "profile_id": row[12],
            "platform": row[13],
            "persona": row[14],
            "target_rule": row[15],
            "patient_conditions": row[16],
            "context_hint": "",
            "test_status": "Not Run"
        })

    return tests


def get_workflow_sections(cursor, cycle_id: str, tester: str) -> list:
    """
    PURPOSE:
        Get workflow sections that have tests for this tester.

    PARAMETERS:
        cursor: SQLite cursor
        cycle_id (str): The cycle identifier
        tester (str): Tester email address

    RETURNS:
        list: List of section dictionaries with metadata
    """
    cursor.execute("""
        SELECT DISTINCT
            COALESCE(tc.workflow_section, tc.category) as section,
            ws.section_name,
            ws.section_description,
            ws.guidance_text,
            ws.display_order
        FROM uat_test_cases tc
        LEFT JOIN uat_workflow_sections ws
            ON ws.section_code = COALESCE(tc.workflow_section, tc.category)
        WHERE tc.uat_cycle_id = ?
        AND tc.assigned_to = ?
        ORDER BY COALESCE(ws.display_order, 99)
    """, (cycle_id, tester))

    sections = []
    seen = set()

    for row in cursor.fetchall():
        code = row[0]
        if not code or code in seen:
            continue
        seen.add(code)

        sections.append({
            "code": code,
            "name": row[1] or code,
            "description": row[2] or f"Tests in {code} category",
            "guidance": row[3] or "Complete these tests in order.",
            "icon": get_section_icon(code)
        })

    return sections


def get_section_icon(code: str) -> str:
    """
    PURPOSE:
        Get emoji icon for a workflow section.

    PARAMETERS:
        code (str): Section code (e.g., "P4M", "NCCN")

    RETURNS:
        str: Emoji icon
    """
    icons = {
        # Feature UAT sections
        "P4M": "🩺",
        "PR4M": "🔬",
        "GRX": "🧬",
        "DRAFT": "💾",
        "EDGE": "🔍",
        "AUTH": "🔐",
        "DASH": "📊",
        # NCCN validation sections
        "NCCN": "📋",
        "POS": "✅",
        "NEG": "❌",
        "DEP": "⚠️",
        # Generic
        "OTHER": "📝"
    }
    return icons.get(code, "📝")


def escape_js_string(s: str) -> str:
    """
    PURPOSE:
        Escape a string for safe inclusion in JavaScript.

    PARAMETERS:
        s (str): String to escape

    RETURNS:
        str: Escaped string safe for JS
    """
    if not s:
        return ""
    # Escape backslashes first, then quotes and newlines
    s = s.replace("\\", "\\\\")
    s = s.replace("'", "\\'")
    s = s.replace('"', '\\"')
    s = s.replace("\n", "\\n")
    s = s.replace("\r", "")
    return s


def generate_tracker_html(cycle_info: dict, tester: str, tests: list,
                          sections: list, formspree_id: str = None) -> str:
    """
    PURPOSE:
        Generate the complete HTML tracker file for one tester.

    PARAMETERS:
        cycle_info (dict): UAT cycle metadata
        tester (str): Tester email address
        tests (list): List of test cases assigned to this tester
        sections (list): Workflow sections for this tester's tests
        formspree_id (str): Optional Formspree form ID for submission

    RETURNS:
        str: Complete HTML content for the tracker

    WHY THIS APPROACH:
        We read the template file and inject the tester-specific
        configuration and test data. This keeps the React/JS logic
        in one place (the template) while customizing the data.
    """
    # Parse tester name from email
    tester_name = tester.split('@')[0].replace('.', ' ').title()
    tester_slug = slugify(tester_name)

    # Build JavaScript configuration
    config_js = f"""const UAT_CONFIG = {{
      id: '{escape_js_string(cycle_info["cycle_id"])}-{tester_slug}',
      name: '{escape_js_string(cycle_info["cycle_name"])}',
      target_date: '{escape_js_string(cycle_info["target_date"])}',
      tester_default: '{escape_js_string(tester_name)}',
      tester_email: '{escape_js_string(tester)}',
      formspree_id: {f"'{formspree_id}'" if formspree_id else 'null'},
      localStorage_key: 'uat_{slugify(cycle_info["cycle_id"])}_{tester_slug}'
    }};"""

    # Build sections JavaScript
    sections_js = "const WORKFLOW_SECTIONS = " + json.dumps(sections, indent=2) + ";"

    # Build tests JavaScript
    tests_js = "const TEST_CASES_DATA = " + json.dumps(tests, indent=2) + ";"

    # Read template
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Template not found: {TEMPLATE_PATH}")

    with open(TEMPLATE_PATH, 'r') as f:
        template = f.read()

    # Replace placeholders using regex
    # Replace UAT_CONFIG block
    template = re.sub(
        r'const UAT_CONFIG = \{[^}]+\};',
        config_js,
        template
    )

    # Replace WORKFLOW_SECTIONS block (handles multiline)
    template = re.sub(
        r'const WORKFLOW_SECTIONS = \[[\s\S]*?\n    \];',
        sections_js,
        template
    )

    # Replace TEST_CASES_DATA block (handles multiline)
    template = re.sub(
        r'const TEST_CASES_DATA = \[[\s\S]*?\n    \];',
        tests_js,
        template
    )

    # Update the page title
    template = template.replace(
        '<title>UAT Tracker Template</title>',
        f'<title>{cycle_info["cycle_name"]} - {tester_name}</title>'
    )

    return template


def generate_index_html(cycle_info: dict, testers: list,
                        tester_test_counts: dict) -> str:
    """
    PURPOSE:
        Generate the tester selection index page for a cycle.

    PARAMETERS:
        cycle_info (dict): UAT cycle metadata
        testers (list): List of tester email addresses
        tester_test_counts (dict): Map of tester -> test count

    RETURNS:
        str: HTML content for the index page
    """
    # Calculate total tests
    total_tests = sum(tester_test_counts.values())

    # Build tester links
    tester_links = ""
    for tester in testers:
        tester_name = tester.split('@')[0].replace('.', ' ').title()
        tester_slug = slugify(tester_name)
        test_count = tester_test_counts.get(tester, 0)

        tester_links += f"""
            <a href="tracker-{tester_slug}.html"
               class="block bg-white rounded-lg shadow p-4 hover:shadow-lg transition-shadow mb-3">
                <div class="flex items-center justify-between">
                    <div>
                        <h3 class="text-lg font-semibold text-gray-800">{tester_name}</h3>
                        <p class="text-sm text-gray-500">{test_count} tests assigned</p>
                    </div>
                    <span class="text-blue-500 text-xl">→</span>
                </div>
            </a>
"""

    # Build dashboard link (links to cycle dashboard in parent folder)
    dashboard_slug = slugify(cycle_info['cycle_id'])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{cycle_info['cycle_name']} - Tester Selection</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 min-h-screen py-8">
    <div class="max-w-2xl mx-auto px-4">
        <div class="text-center mb-8">
            <a href="../index.html" class="text-blue-500 text-sm hover:underline">← Back to All UATs</a>
            <h1 class="text-3xl font-bold text-gray-800 mt-2">{cycle_info['cycle_name']}</h1>
            <p class="text-gray-600">Target: {cycle_info['target_date']}</p>
            <p class="text-sm text-gray-500 mt-1">Select your name to open your tracker</p>
        </div>

        <!-- Dashboard Link -->
        <div class="mb-6">
            <a href="../dashboard-{dashboard_slug}.html"
               class="flex items-center justify-center gap-2 bg-blue-600 text-white rounded-lg p-4 hover:bg-blue-700 transition-colors">
                <span class="text-xl">📊</span>
                <div>
                    <span class="font-semibold">View Progress Dashboard</span>
                    <span class="text-blue-200 ml-2 text-sm">{len(testers)} testers | {total_tests} tests</span>
                </div>
            </a>
        </div>

        <div class="text-sm text-gray-500 text-center mb-4">
            Select your tracker below:
        </div>

        <div class="space-y-3">
            {tester_links}
        </div>

        <div class="mt-8 text-center text-gray-400 text-sm">
            <p>Clinical PM: {cycle_info['clinical_pm'] or 'TBD'}</p>
            <p class="mt-4">Propel Health UAT Toolkit</p>
        </div>
    </div>
</body>
</html>
"""


def get_status_color(status: str) -> str:
    """Get Tailwind CSS classes for a status badge."""
    colors = {
        "planning": "bg-gray-100 text-gray-600",
        "validation": "bg-yellow-100 text-yellow-700",
        "kickoff": "bg-blue-100 text-blue-700",
        "testing": "bg-green-100 text-green-700",
        "review": "bg-purple-100 text-purple-700",
        "retesting": "bg-orange-100 text-orange-700",
        "decision": "bg-pink-100 text-pink-700",
        "complete": "bg-green-200 text-green-800",
        "cancelled": "bg-red-100 text-red-700"
    }
    return colors.get(status.lower() if status else "", "bg-gray-100 text-gray-600")


def update_main_index(cursor) -> str:
    """
    PURPOSE:
        Generate updated main index.html listing all UAT cycles.

    PARAMETERS:
        cursor: SQLite cursor

    RETURNS:
        str: HTML content for the main landing page
    """
    # Get all cycles with tester and test counts
    cursor.execute("""
        SELECT
            c.cycle_id, c.name, c.target_launch_date, c.status,
            COUNT(DISTINCT tc.assigned_to) as tester_count,
            COUNT(tc.test_id) as test_count
        FROM uat_cycles c
        LEFT JOIN uat_test_cases tc ON c.cycle_id = tc.uat_cycle_id
            AND tc.assigned_to IS NOT NULL AND tc.assigned_to != ''
        GROUP BY c.cycle_id
        ORDER BY c.created_date DESC
    """)

    # Build cycle cards
    cycle_links = ""
    for row in cursor.fetchall():
        cycle_id, name, target_date, status, tester_count, test_count = row
        folder = slugify(cycle_id)
        status_class = get_status_color(status)

        # Only link to folder if it has testers assigned
        if tester_count > 0:
            cycle_links += f"""
            <a href="{folder}/index.html"
               class="block bg-white rounded-lg shadow p-6 hover:shadow-lg transition-shadow border-l-4 border-green-500">
                <div class="flex items-center justify-between">
                    <div>
                        <div class="flex items-center gap-2 mb-1">
                            <span class="text-xs px-2 py-1 rounded {status_class}">{status or 'planning'}</span>
                        </div>
                        <h2 class="text-xl font-semibold text-gray-800">{name}</h2>
                        <p class="text-gray-600">{tester_count} testers | {test_count} tests</p>
                        <p class="text-sm text-gray-500 mt-1">Target: {target_date or 'TBD'}</p>
                    </div>
                    <span class="text-blue-500 text-2xl">→</span>
                </div>
            </a>
"""
        else:
            cycle_links += f"""
            <div class="block bg-white rounded-lg shadow p-6 border-l-4 border-gray-300 opacity-60">
                <div class="flex items-center justify-between">
                    <div>
                        <div class="flex items-center gap-2 mb-1">
                            <span class="text-xs px-2 py-1 rounded {status_class}">{status or 'planning'}</span>
                            <span class="text-xs px-2 py-1 rounded bg-gray-100 text-gray-500">No testers assigned</span>
                        </div>
                        <h2 class="text-xl font-semibold text-gray-700">{name}</h2>
                        <p class="text-gray-500">{test_count} tests defined</p>
                        <p class="text-sm text-gray-400 mt-1">Target: {target_date or 'TBD'}</p>
                    </div>
                    <span class="text-gray-300 text-2xl">→</span>
                </div>
            </div>
"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Propel Health UAT Toolkit</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 min-h-screen py-8">
    <div class="max-w-3xl mx-auto px-4">
        <div class="text-center mb-8">
            <h1 class="text-3xl font-bold text-gray-800">Propel Health UAT Toolkit</h1>
            <p class="text-gray-600 mt-2">User Acceptance Testing Trackers</p>
        </div>

        <div class="space-y-4">
            {cycle_links}
        </div>

        <div class="mt-12 text-center text-gray-400 text-sm">
            <p>Propel Health</p>
            <p class="mt-1">
                <a href="https://github.com/glewis05/uat_toolkit"
                   class="text-blue-500 hover:underline">GitHub Repository</a>
            </p>
        </div>
    </div>
</body>
</html>
"""


def main(cycle_id: str, formspree_id: str = None):
    """
    PURPOSE:
        Main entry point - generate tracker files for a UAT cycle.

    PARAMETERS:
        cycle_id (str): The UAT cycle identifier
        formspree_id (str): Optional Formspree form ID for submission
    """
    print(f"Generating trackers for cycle: {cycle_id}")

    # Verify database exists
    if not DB_PATH.exists():
        print(f"Error: Database not found: {DB_PATH}")
        print("Make sure the data/ symlink is configured correctly.")
        sys.exit(1)

    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get cycle info
    cycle_info = get_cycle_info(cursor, cycle_id)
    if not cycle_info:
        print(f"Error: Cycle not found: {cycle_id}")
        print("\nAvailable cycles:")
        cursor.execute("SELECT cycle_id, name FROM uat_cycles ORDER BY created_date DESC LIMIT 10")
        for row in cursor.fetchall():
            print(f"  - {row[0]}: {row[1]}")
        conn.close()
        sys.exit(1)

    print(f"   Cycle: {cycle_info['cycle_name']}")
    print(f"   Target: {cycle_info['target_date']}")

    # Get testers
    testers = get_testers_for_cycle(cursor, cycle_id)
    if not testers:
        print("Error: No testers assigned to this cycle")
        print("   Assign testers first using:")
        print(f"   UPDATE uat_test_cases SET assigned_to = 'email@example.com' WHERE uat_cycle_id = '{cycle_id}'")
        conn.close()
        sys.exit(1)

    print(f"   Testers: {len(testers)}")

    # Create cycle folder
    cycle_folder = DOCS_PATH / slugify(cycle_id)
    cycle_folder.mkdir(exist_ok=True)
    print(f"   Output: docs/{slugify(cycle_id)}/")

    # Generate tracker for each tester
    tester_test_counts = {}
    for tester in testers:
        tester_name = tester.split('@')[0].replace('.', ' ').title()
        tester_slug = slugify(tester_name)

        # Get tests and sections for this tester
        tests = get_tests_for_tester(cursor, cycle_id, tester)
        sections = get_workflow_sections(cursor, cycle_id, tester)

        tester_test_counts[tester] = len(tests)

        # Generate HTML
        html = generate_tracker_html(cycle_info, tester, tests, sections, formspree_id)

        # Write file
        output_path = cycle_folder / f"tracker-{tester_slug}.html"
        with open(output_path, 'w') as f:
            f.write(html)

        print(f"   Created: tracker-{tester_slug}.html ({len(tests)} tests)")

    # Generate cycle index page
    index_html = generate_index_html(cycle_info, testers, tester_test_counts)
    with open(cycle_folder / "index.html", 'w') as f:
        f.write(index_html)
    print(f"   Created: index.html (tester selection page)")

    # Update main index with all cycles
    main_index = update_main_index(cursor)
    with open(DOCS_PATH / "index.html", 'w') as f:
        f.write(main_index)
    print(f"   Updated: ../index.html (main landing page)")

    conn.close()

    # Print tester URLs
    print(f"\nGeneration complete!")
    print(f"\nTester URLs:")
    base_url = "https://glewis05.github.io/uat_toolkit"
    for tester in testers:
        tester_name = tester.split('@')[0].replace('.', ' ').title()
        tester_slug = slugify(tester_name)
        print(f"   {tester_name}: {base_url}/{slugify(cycle_id)}/tracker-{tester_slug}.html")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate_tester_trackers.py <cycle_id> [formspree_id]")
        print("")
        print("Generate personalized UAT tracker HTML files for each tester")
        print("assigned to a UAT cycle.")
        print("")
        print("Arguments:")
        print("  cycle_id      UAT cycle identifier (e.g., UAT-NCCN-Q4-2025)")
        print("  formspree_id  Optional Formspree form ID for email submission")
        print("")
        print("Example:")
        print("  python generate_tester_trackers.py UAT-NCCN-Q4-2025 mqeekjjz")
        sys.exit(1)

    cycle_id = sys.argv[1]
    formspree_id = sys.argv[2] if len(sys.argv) > 2 else None

    main(cycle_id, formspree_id)
