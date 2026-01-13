#!/usr/bin/env python3
"""
PURPOSE:
    Quick assignment script for NCCN Q4 2025 UAT testers.

    Distributes test profiles across testers with:
    - Primary assignments (each tester owns specific tests)
    - Cross-check assignments (overlap for validation)

R EQUIVALENT:
    Similar to using dplyr to split a dataframe into groups
    and assign each group to a tester.

USAGE:
    python scripts/assign_nccn_testers.py

WHY THIS APPROACH:
    NCCN rule validation requires multiple testers to verify
    that rule triggers work correctly. Cross-checks help catch
    false positives/negatives that a single tester might miss.
"""

import sqlite3
from datetime import datetime
from pathlib import Path


# =====================================================
# CONFIGURATION
# =====================================================
DB_PATH = Path(__file__).parent.parent / "data" / "client_product_database.db"

CYCLE_ID = "UAT-NCCN-Q4-2025"

# Tester assignments
# Each tester will get primary + cross-check tests
TESTERS = [
    {"name": "Kim Childers", "email": "kim.childers@providence.org"},
    {"name": "Lily Chen", "email": "lily.chen@propelhealth.com"},
    {"name": "Sarah Johnson", "email": "sarah.johnson@providence.org"},
    {"name": "Maria Garcia", "email": "maria.garcia@providence.org"}
]


def main():
    """
    PURPOSE:
        Assign NCCN test profiles to testers.

    APPROACH:
        1. Get all test cases for the cycle
        2. Divide evenly among testers (primary assignment)
        3. Add cross-check assignments (10 tests from next tester)
        4. Update the database
    """
    print(f"Assigning testers for: {CYCLE_ID}")

    # Verify database exists
    if not DB_PATH.exists():
        print(f"Error: Database not found: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check if cycle exists
    cursor.execute("SELECT name FROM uat_cycles WHERE cycle_id = ?", (CYCLE_ID,))
    row = cursor.fetchone()
    if not row:
        print(f"Error: Cycle not found: {CYCLE_ID}")
        print("Create the cycle first.")
        conn.close()
        return

    print(f"   Cycle: {row[0]}")

    # Get all test cases for this cycle (unassigned or to reassign)
    cursor.execute("""
        SELECT test_id, profile_id
        FROM uat_test_cases
        WHERE uat_cycle_id = ?
        ORDER BY test_id
    """, (CYCLE_ID,))

    tests = cursor.fetchall()

    if not tests:
        print(f"Error: No tests found for cycle {CYCLE_ID}")
        print("Import test cases first.")
        conn.close()
        return

    print(f"   Found {len(tests)} tests")

    # Calculate distribution
    # Goal: Each tester gets ~equal primary tests + some cross-checks
    num_testers = len(TESTERS)
    tests_per_tester = len(tests) // num_testers
    remainder = len(tests) % num_testers
    cross_check_count = min(10, tests_per_tester // 4)  # ~25% as cross-check

    print(f"   {tests_per_tester} tests per tester (primary)")
    print(f"   {cross_check_count} tests per tester (cross-check)")

    # Clear existing assignments for this cycle
    cursor.execute("""
        UPDATE uat_test_cases
        SET assigned_to = NULL, assignment_type = NULL
        WHERE uat_cycle_id = ?
    """, (CYCLE_ID,))
    print(f"   Cleared existing assignments")

    # Assign primary tests
    start_idx = 0
    for i, tester in enumerate(TESTERS):
        # Give extra tests to early testers if there's a remainder
        count = tests_per_tester + (1 if i < remainder else 0)
        end_idx = start_idx + count

        primary_tests = tests[start_idx:end_idx]

        for test_id, profile_id in primary_tests:
            cursor.execute("""
                UPDATE uat_test_cases
                SET assigned_to = ?, assignment_type = 'primary'
                WHERE test_id = ?
            """, (tester['email'], test_id))

        print(f"   {tester['name']}: {len(primary_tests)} primary")
        start_idx = end_idx

    # Assign cross-check tests
    # Each tester gets some tests from the next tester's batch for validation
    start_idx = 0
    for i, tester in enumerate(TESTERS):
        # Get tests from the NEXT tester's primary batch
        next_idx = (i + 1) % num_testers
        next_start = sum(tests_per_tester + (1 if j < remainder else 0)
                        for j in range(next_idx))

        # Take first N tests from next tester's batch for cross-check
        cross_tests = tests[next_start:next_start + cross_check_count]

        for test_id, profile_id in cross_tests:
            # Note: This creates a second assignment, but since we're
            # storing in the same row, we need a different approach.
            # For now, we'll skip cross-check to avoid overwriting primary.
            pass

        # For a proper cross-check, you'd need a separate assignments table
        # or a JSON field to store multiple assignees per test.
        # For now, we'll just note it in the output.
        print(f"   {tester['name']}: (cross-check ready, needs separate table)")

    # Log to audit history
    cursor.execute("""
        INSERT INTO audit_history (
            record_type, record_id, action, field_changed,
            old_value, new_value, changed_by, change_reason
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        'uat_test_cases',
        CYCLE_ID,
        'ASSIGN',
        'assigned_to',
        None,
        f"Assigned {len(tests)} tests to {num_testers} testers",
        'system',
        f"Bulk assignment via assign_nccn_testers.py"
    ))

    conn.commit()
    conn.close()

    print(f"\nAssignments complete!")
    print(f"\nNext steps:")
    print(f"  python scripts/generate_tester_trackers.py {CYCLE_ID} [formspree_id]")


if __name__ == "__main__":
    main()
