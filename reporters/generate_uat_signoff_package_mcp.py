"""
generate_uat_signoff_package - MCP Tool Integration

Add this to your propel_mcp server.py file.

STORY: PLAT-RPT-001 - Generate UAT Sign-Off Package
"""

import os
import subprocess
import json
from datetime import datetime
from pathlib import Path


async def generate_uat_signoff_package(
    cycle_id: str,
    client_name: str,
    client_title: str,
    output_format: str = "docx",
    output_dir: str = None
) -> str:
    """
    Generate a formal UAT Sign-Off Package document for client approval.

    Creates a comprehensive Word document containing:
    - Cover page with program/cycle information
    - Executive summary with test statistics and Go/No-Go recommendation
    - Per-story sign-off sections with linked test case results
    - Appendix A: Defect log
    - Appendix B: Compliance matrix (Part11/HIPAA/SOC2 tagged tests)
    - Final sign-off page with signature blocks

    Args:
        cycle_id: UAT cycle ID (e.g., "UAT-ONB-12345678")
        client_name: Client/reviewer name for sign-off lines
        client_title: Client's title (e.g., "Clinical Program Manager")
        output_format: Output format - "docx" or "pdf" (default: "docx")
        output_dir: Directory to save file (default: ~/Downloads)

    Returns:
        Path to generated file and summary statistics

    Example:
        generate_uat_signoff_package(
            cycle_id="UAT-ONB-12345678",
            client_name="Kim Childers",
            client_title="Clinical Program Manager"
        )
    """

    # Default output directory
    if not output_dir:
        output_dir = str(Path.home() / "Downloads")

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # =========================================================================
    # QUERY DATABASE FOR CYCLE DATA
    # =========================================================================

    conn = get_db_connection()  # Your existing connection function
    cursor = conn.cursor()

    # Get cycle info
    cursor.execute("""
        SELECT cycle_id, name, program_prefix, uat_type, status,
               target_launch_date, kickoff_date, testing_start_date,
               clinical_pm, clinical_pm_email
        FROM uat_cycles
        WHERE cycle_id = ?
    """, (cycle_id,))

    cycle_row = cursor.fetchone()
    if not cycle_row:
        return f"Error: UAT cycle '{cycle_id}' not found"

    cycle = dict(cycle_row)

    # Get program name
    cursor.execute("""
        SELECT program_name FROM programs WHERE prefix = ?
    """, (cycle['program_prefix'],))
    program_row = cursor.fetchone()
    cycle['program_name'] = program_row['program_name'] if program_row else cycle['program_prefix']

    # Get test assignments with execution results
    cursor.execute("""
        SELECT
            ua.test_id,
            ua.assigned_to,
            ua.status as execution_status,
            ua.execution_notes,
            ua.defect_id,
            ua.defect_description,
            ua.dev_status,
            ua.dev_notes,
            ua.executed_at,
            tc.title,
            tc.story_id,
            tc.test_type,
            tc.compliance_framework
        FROM uat_assignments ua
        JOIN test_cases tc ON ua.test_id = tc.test_id
        WHERE ua.cycle_id = ?
        ORDER BY tc.story_id, tc.test_id
    """, (cycle_id,))

    test_assignments = [dict(row) for row in cursor.fetchall()]

    # Get unique story IDs from test assignments
    story_ids = list(set(ta['story_id'] for ta in test_assignments))

    if story_ids:
        placeholders = ','.join('?' * len(story_ids))
        cursor.execute(f"""
            SELECT story_id, title, user_story, acceptance_criteria, priority, status
            FROM user_stories
            WHERE story_id IN ({placeholders})
            ORDER BY story_id
        """, story_ids)
        stories = [dict(row) for row in cursor.fetchall()]
    else:
        stories = []

    # Build test cases list with execution data
    test_cases = []
    for ta in test_assignments:
        test_cases.append({
            'test_id': ta['test_id'],
            'story_id': ta['story_id'],
            'title': ta['title'],
            'status': ta['execution_status'] or 'Not Run',
            'tested_by': ta['assigned_to'],
            'compliance_framework': ta['compliance_framework'],
            'execution_notes': ta['execution_notes']
        })

    # Build defects list
    defects = []
    for ta in test_assignments:
        if ta['defect_id']:
            defects.append({
                'defect_id': ta['defect_id'],
                'test_id': ta['test_id'],
                'description': ta['defect_description'],
                'dev_status': ta['dev_status'],
                'dev_notes': ta['dev_notes']
            })

    conn.close()

    # =========================================================================
    # PREPARE DATA FOR DOCUMENT GENERATOR
    # =========================================================================

    data = {
        'cycle': cycle,
        'stories': stories,
        'testCases': test_cases,
        'defects': defects
    }

    # Calculate stats
    total_tests = len(test_cases)
    passed = len([tc for tc in test_cases if tc['status'] == 'Pass'])
    failed = len([tc for tc in test_cases if tc['status'] == 'Fail'])
    blocked = len([tc for tc in test_cases if tc['status'] == 'Blocked'])
    not_run = len([tc for tc in test_cases if tc['status'] in ('Not Run', 'Skipped', None)])

    pass_rate = (passed / (passed + failed + blocked) * 100) if (passed + failed + blocked) > 0 else 0

    # Determine recommendation
    if failed > 0:
        recommendation = "NO-GO"
    elif blocked > 0 or not_run > 0:
        recommendation = "CONDITIONAL GO"
    else:
        recommendation = "GO"

    # =========================================================================
    # GENERATE DOCUMENT VIA NODE.JS SCRIPT
    # =========================================================================

    # Write data to temp file for Node script
    temp_data_path = f"/tmp/uat_signoff_data_{cycle_id}.json"
    with open(temp_data_path, 'w') as f:
        json.dump(data, f)

    # Generate filename
    timestamp = datetime.now().strftime('%Y-%m-%d')
    safe_client_name = ''.join(c if c.isalnum() else '_' for c in client_name)
    filename = f"UAT_SignOff_{cycle['program_prefix']}_{safe_client_name}_{timestamp}.docx"
    output_path = os.path.join(output_dir, filename)

    # Call Node.js generator (assumes script is in same directory or in PATH)
    # You may need to adjust the path to the script
    script_path = os.path.join(os.path.dirname(__file__), 'generate_uat_signoff_package.js')

    try:
        result = subprocess.run(
            ['node', script_path, cycle_id, client_name, client_title, output_dir],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            return f"Error generating document: {result.stderr}"

    except subprocess.TimeoutExpired:
        return "Error: Document generation timed out"
    except FileNotFoundError:
        return "Error: Node.js or generator script not found"

    # Clean up temp file
    if os.path.exists(temp_data_path):
        os.remove(temp_data_path)

    # =========================================================================
    # RETURN SUMMARY
    # =========================================================================

    compliance_count = len([tc for tc in test_cases if tc['compliance_framework']])

    return f"""
UAT Sign-Off Package Generated
==============================

Cycle: {cycle['name']} ({cycle_id})
Program: {cycle['program_name']}
Client: {client_name}, {client_title}

Test Summary:
  Total Stories: {len(stories)}
  Total Test Cases: {total_tests}
  ✓ Passed: {passed}
  ✗ Failed: {failed}
  ⊘ Blocked: {blocked}
  ○ Not Run: {not_run}
  Pass Rate: {pass_rate:.1f}%

Recommendation: {recommendation}

Document Contents:
  - Cover page
  - Executive summary
  - {len(stories)} user story sign-off sections
  - Appendix A: Defect log ({len(defects)} defects)
  - Appendix B: Compliance matrix ({compliance_count} tagged tests)
  - Final sign-off page

File: {output_path}
"""


# ============================================================================
# MCP TOOL REGISTRATION
# ============================================================================

# Add this to your tool registration in server.py:

"""
@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:

    # ... existing tool handlers ...

    elif name == "generate_uat_signoff_package":
        result = await generate_uat_signoff_package(
            cycle_id=arguments.get("cycle_id"),
            client_name=arguments.get("client_name"),
            client_title=arguments.get("client_title"),
            output_format=arguments.get("output_format", "docx"),
            output_dir=arguments.get("output_dir")
        )
        return [types.TextContent(type="text", text=result)]
"""

# Add this to your tool definitions:

"""
types.Tool(
    name="generate_uat_signoff_package",
    description='''
Generate a formal UAT Sign-Off Package document for client approval.

Creates a comprehensive Word document containing:
- Cover page with program/cycle information
- Executive summary with test statistics and Go/No-Go recommendation
- Per-story sign-off sections with linked test case results
- Appendix A: Defect log
- Appendix B: Compliance matrix (Part11/HIPAA/SOC2 tagged tests)
- Final sign-off page with signature blocks

Args:
    cycle_id: UAT cycle ID (e.g., "UAT-ONB-12345678")
    client_name: Client/reviewer name for sign-off lines
    client_title: Client's title (e.g., "Clinical Program Manager")
    output_format: Output format - "docx" or "pdf" (default: "docx")
    output_dir: Directory to save file (default: ~/Downloads)

Returns:
    Path to generated file and summary statistics

Example:
    generate_uat_signoff_package(
        cycle_id="UAT-ONB-12345678",
        client_name="Kim Childers",
        client_title="Clinical Program Manager"
    )
''',
    inputSchema={
        "type": "object",
        "properties": {
            "cycle_id": {
                "type": "string",
                "description": "UAT cycle ID (e.g., 'UAT-ONB-12345678')"
            },
            "client_name": {
                "type": "string",
                "description": "Client/reviewer name for sign-off lines"
            },
            "client_title": {
                "type": "string",
                "description": "Client's title (e.g., 'Clinical Program Manager')"
            },
            "output_format": {
                "type": "string",
                "default": "docx",
                "description": "Output format - 'docx' or 'pdf'"
            },
            "output_dir": {
                "type": "string",
                "default": None,
                "description": "Directory to save file (default: ~/Downloads)"
            }
        },
        "required": ["cycle_id", "client_name", "client_title"]
    }
)
"""
