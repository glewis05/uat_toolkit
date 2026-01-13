#!/usr/bin/env python3
"""
PURPOSE:
    Generate a UAT progress dashboard HTML page that aggregates progress
    from all testers in a cycle.

R EQUIVALENT:
    Similar to using Shiny or R Markdown to create an interactive dashboard
    that displays summary statistics from a data source.

USAGE:
    python scripts/generate_dashboard.py UAT-NCCN-Q4-2025

WHY THIS APPROACH:
    Progress syncs from testers come via Formspree (or manual export).
    This script reads the database to generate a static HTML dashboard
    showing overall cycle progress, per-tester progress, and section
    breakdowns. The dashboard is regenerated as new results are imported.
"""

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


# =====================================================
# CONFIGURATION
# =====================================================
# Database path - uses symlink to shared database
# Like R's here::here() for project-relative paths
REPO_ROOT = Path(__file__).parent.parent
DB_PATH = REPO_ROOT / "data" / "client_product_database.db"
OUTPUT_DIR = REPO_ROOT / "docs"


def get_cycle_info(cursor, cycle_id: str) -> dict:
    """
    PURPOSE:
        Get cycle metadata from the database.

    PARAMETERS:
        cursor: SQLite cursor
        cycle_id (str): The cycle identifier (e.g., "UAT-NCCN-Q4-2025")

    RETURNS:
        dict: Cycle information or None if not found
    """
    cursor.execute("""
        SELECT cycle_id, name, target_date, status
        FROM uat_cycles
        WHERE cycle_id = ?
    """, (cycle_id,))

    row = cursor.fetchone()
    if row:
        return {
            'cycle_id': row[0],
            'name': row[1],
            'target_date': row[2],
            'status': row[3]
        }
    return None


def get_tester_progress(cursor, cycle_id: str) -> list:
    """
    PURPOSE:
        Get progress summary for each tester in the cycle.

    PARAMETERS:
        cursor: SQLite cursor
        cycle_id (str): The cycle identifier

    RETURNS:
        list: List of dicts with tester progress stats

    WHY THIS APPROACH:
        We group by assigned_to to get per-tester statistics,
        similar to dplyr::group_by() + summarise() in R.
    """
    cursor.execute("""
        SELECT
            assigned_to,
            COUNT(*) as total,
            SUM(CASE WHEN test_status = 'Pass' THEN 1 ELSE 0 END) as passed,
            SUM(CASE WHEN test_status = 'Fail' THEN 1 ELSE 0 END) as failed,
            SUM(CASE WHEN test_status = 'Blocked' THEN 1 ELSE 0 END) as blocked,
            SUM(CASE WHEN test_status = 'Skipped' THEN 1 ELSE 0 END) as skipped,
            SUM(CASE WHEN test_status NOT IN ('Not Run', '') OR test_status IS NULL THEN 0 ELSE 1 END) as not_run,
            MAX(tested_date) as last_tested
        FROM uat_test_cases
        WHERE uat_cycle_id = ?
        AND assigned_to IS NOT NULL
        GROUP BY assigned_to
        ORDER BY assigned_to
    """, (cycle_id,))

    testers = []
    for row in cursor.fetchall():
        total = row[1]
        executed = row[2] + row[3] + row[4] + row[5]  # pass + fail + blocked + skipped
        pct = round((executed / total) * 100) if total > 0 else 0

        testers.append({
            'email': row[0],
            'name': row[0].split('@')[0].replace('.', ' ').title() if row[0] else 'Unassigned',
            'total': total,
            'passed': row[2],
            'failed': row[3],
            'blocked': row[4],
            'skipped': row[5],
            'not_run': total - executed,
            'executed': executed,
            'percent_complete': pct,
            'last_tested': row[7]
        })

    return testers


def get_overall_stats(cursor, cycle_id: str) -> dict:
    """
    PURPOSE:
        Get overall cycle statistics.

    PARAMETERS:
        cursor: SQLite cursor
        cycle_id (str): The cycle identifier

    RETURNS:
        dict: Overall cycle statistics
    """
    cursor.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN test_status = 'Pass' THEN 1 ELSE 0 END) as passed,
            SUM(CASE WHEN test_status = 'Fail' THEN 1 ELSE 0 END) as failed,
            SUM(CASE WHEN test_status = 'Blocked' THEN 1 ELSE 0 END) as blocked,
            SUM(CASE WHEN test_status = 'Skipped' THEN 1 ELSE 0 END) as skipped
        FROM uat_test_cases
        WHERE uat_cycle_id = ?
    """, (cycle_id,))

    row = cursor.fetchone()
    total = row[0]
    executed = row[1] + row[2] + row[3] + row[4]
    pct = round((executed / total) * 100) if total > 0 else 0

    return {
        'total': total,
        'passed': row[1],
        'failed': row[2],
        'blocked': row[3],
        'skipped': row[4],
        'not_run': total - executed,
        'executed': executed,
        'percent_complete': pct
    }


def generate_dashboard_html(cycle_info: dict, overall: dict, testers: list) -> str:
    """
    PURPOSE:
        Generate the dashboard HTML content.

    PARAMETERS:
        cycle_info (dict): Cycle metadata
        overall (dict): Overall statistics
        testers (list): Per-tester statistics

    RETURNS:
        str: Complete HTML content for the dashboard

    WHY THIS APPROACH:
        Using React + Tailwind for consistency with the tracker templates.
        The dashboard is a static page that can be regenerated on demand.
    """
    # Build tester rows HTML
    tester_rows = []
    for t in testers:
        # Determine row color based on completion
        row_class = ''
        if t['percent_complete'] == 100:
            row_class = 'bg-green-50'
        elif t['failed'] > 0:
            row_class = 'bg-red-50'

        tester_rows.append(f"""
            <tr className="{row_class}">
              <td className="px-4 py-3 whitespace-nowrap">
                <div className="font-medium text-gray-900">{t['name']}</div>
                <div className="text-xs text-gray-500">{t['email']}</div>
              </td>
              <td className="px-4 py-3 text-center">
                <div className="flex items-center justify-center gap-1">
                  <div className="w-16 h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div className="bg-blue-500 h-full" style={{{{ width: '{t['percent_complete']}%' }}}} />
                  </div>
                  <span className="text-sm font-medium">{t['percent_complete']}%</span>
                </div>
              </td>
              <td className="px-4 py-3 text-center text-green-600 font-medium">{t['passed']}</td>
              <td className="px-4 py-3 text-center text-red-600 font-medium">{t['failed']}</td>
              <td className="px-4 py-3 text-center text-amber-600">{t['blocked']}</td>
              <td className="px-4 py-3 text-center text-gray-400">{t['not_run']}</td>
              <td className="px-4 py-3 text-center text-xs text-gray-500">
                {t['last_tested'][:10] if t['last_tested'] else '-'}
              </td>
            </tr>""")

    tester_rows_html = '\n'.join(tester_rows)

    # Calculate pass rate
    pass_rate = round((overall['passed'] / overall['executed']) * 100) if overall['executed'] > 0 else 0

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{cycle_info['name']} - UAT Dashboard</title>
    <script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
    <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
    <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100">
    <div id="root"></div>

    <script type="text/babel">
    const Dashboard = () => {{
      // Data embedded at generation time
      const cycle = {json.dumps(cycle_info)};
      const overall = {json.dumps(overall)};
      const testers = {json.dumps(testers)};
      const generatedAt = "{datetime.now().isoformat()}";

      return (
        <div className="max-w-6xl mx-auto py-8 px-4">
          {{/* Header */}}
          <div className="bg-white rounded-lg shadow p-6 mb-6">
            <div className="flex items-center justify-between">
              <div>
                <a href="index.html" className="text-blue-500 text-sm hover:underline">← Back to UAT List</a>
                <h1 className="text-2xl font-bold text-gray-800">{{cycle.name}}</h1>
                <p className="text-sm text-gray-500">
                  Target: {{cycle.target_date}} | Status: {{cycle.status}}
                </p>
              </div>
              <div className="text-right">
                <p className="text-xs text-gray-400">Dashboard generated</p>
                <p className="text-sm text-gray-600">{{new Date(generatedAt).toLocaleString()}}</p>
              </div>
            </div>
          </div>

          {{/* Overall Progress Cards */}}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-white rounded-lg shadow p-4">
              <div className="text-3xl font-bold text-blue-600">{{overall.percent_complete}}%</div>
              <div className="text-sm text-gray-500">Complete</div>
              <div className="text-xs text-gray-400 mt-1">{{overall.executed}} of {{overall.total}} tests</div>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <div className="text-3xl font-bold text-green-600">{{overall.passed}}</div>
              <div className="text-sm text-gray-500">Passed</div>
              <div className="text-xs text-gray-400 mt-1">
                {{{pass_rate}}}% pass rate
              </div>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <div className="text-3xl font-bold text-red-600">{{overall.failed}}</div>
              <div className="text-sm text-gray-500">Failed</div>
              <div className="text-xs text-gray-400 mt-1">Requires attention</div>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <div className="text-3xl font-bold text-gray-400">{{overall.not_run}}</div>
              <div className="text-sm text-gray-500">Remaining</div>
              <div className="text-xs text-gray-400 mt-1">Not yet executed</div>
            </div>
          </div>

          {{/* Overall Progress Bar */}}
          <div className="bg-white rounded-lg shadow p-4 mb-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-gray-600">Overall Progress</span>
              <span className="text-sm text-gray-500">
                {{overall.executed}} / {{overall.total}} tests executed
              </span>
            </div>
            <div className="h-6 bg-gray-200 rounded-full overflow-hidden flex">
              {{overall.passed > 0 && (
                <div
                  className="bg-green-500 h-full flex items-center justify-center text-white text-xs font-medium"
                  style={{{{ width: `${{(overall.passed/overall.total)*100}}%` }}}}
                >
                  {{overall.passed > 3 && overall.passed}}
                </div>
              )}}
              {{overall.failed > 0 && (
                <div
                  className="bg-red-500 h-full flex items-center justify-center text-white text-xs font-medium"
                  style={{{{ width: `${{(overall.failed/overall.total)*100}}%` }}}}
                >
                  {{overall.failed > 3 && overall.failed}}
                </div>
              )}}
              {{overall.blocked > 0 && (
                <div
                  className="bg-amber-500 h-full"
                  style={{{{ width: `${{(overall.blocked/overall.total)*100}}%` }}}}
                />
              )}}
              {{overall.skipped > 0 && (
                <div
                  className="bg-blue-400 h-full"
                  style={{{{ width: `${{(overall.skipped/overall.total)*100}}%` }}}}
                />
              )}}
            </div>
            <div className="flex justify-between mt-2 text-xs text-gray-500">
              <span className="text-green-600">Pass: {{overall.passed}}</span>
              <span className="text-red-600">Fail: {{overall.failed}}</span>
              <span className="text-amber-600">Blocked: {{overall.blocked}}</span>
              <span className="text-blue-500">Skipped: {{overall.skipped}}</span>
            </div>
          </div>

          {{/* Tester Progress Table */}}
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <div className="px-6 py-4 border-b">
              <h2 className="text-lg font-semibold text-gray-800">Tester Progress</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Tester
                    </th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Progress
                    </th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Pass
                    </th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Fail
                    </th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Blocked
                    </th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Remaining
                    </th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Last Active
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {tester_rows_html}
                </tbody>
              </table>
            </div>
          </div>

          {{/* Footer */}}
          <div className="text-center text-gray-400 text-sm mt-8">
            <p>Propel Health UAT Toolkit</p>
            <p className="text-xs mt-1">
              Run <code className="bg-gray-100 px-1">python scripts/generate_dashboard.py {cycle_info['cycle_id']}</code> to refresh
            </p>
          </div>
        </div>
      );
    }};

    ReactDOM.render(<Dashboard />, document.getElementById('root'));
    </script>
</body>
</html>
"""
    return html


def main():
    """
    PURPOSE:
        Entry point for dashboard generation.

    USAGE:
        python scripts/generate_dashboard.py UAT-NCCN-Q4-2025
    """
    if len(sys.argv) < 2:
        print("Usage: python scripts/generate_dashboard.py <cycle_id>")
        print("")
        print("Generate a UAT progress dashboard for the specified cycle.")
        print("")
        print("Example:")
        print("  python scripts/generate_dashboard.py UAT-NCCN-Q4-2025")
        sys.exit(1)

    cycle_id = sys.argv[1]

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
        conn.close()
        sys.exit(1)

    print(f"Generating dashboard for: {cycle_info['name']}")

    # Get statistics
    overall = get_overall_stats(cursor, cycle_id)
    testers = get_tester_progress(cursor, cycle_id)

    conn.close()

    print(f"   Total tests: {overall['total']}")
    print(f"   Executed: {overall['executed']} ({overall['percent_complete']}%)")
    print(f"   Testers: {len(testers)}")

    # Generate HTML
    html = generate_dashboard_html(cycle_info, overall, testers)

    # Write to output file
    # Use cycle_id slug for the filename
    slug = cycle_id.lower().replace('_', '-')
    output_file = OUTPUT_DIR / f"dashboard-{slug}.html"

    with open(output_file, 'w') as f:
        f.write(html)

    print(f"\nDashboard generated: {output_file}")
    print(f"\nView at: https://glewis05.github.io/uat_toolkit/dashboard-{slug}.html")


if __name__ == "__main__":
    main()
