#!/usr/bin/env python3
"""
PURPOSE:
    Import UAT results from JSON (exported from tracker or emailed via Formspree).

    This script takes a JSON file containing test results and updates the
    corresponding test cases in the database with their execution status.

R EQUIVALENT:
    Similar to using jsonlite::fromJSON() to read the file, then DBI::dbExecute()
    to update records in a loop.

USAGE:
    python importers/import_uat_results.py path/to/results.json
    python importers/import_uat_results.py path/to/results.json --partial

WHY THIS APPROACH:
    Formspree emails results as JSON. This script allows you to import those
    results back into the database for reporting and audit purposes.

    The --partial flag is for progress syncs (auto_open, auto_10pm, manual)
    which should only update executed tests. Final submissions update all tests.
"""

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


# Database path - uses symlink to shared database
# Like R's here::here() for project-relative paths
DB_PATH = Path(__file__).parent.parent / "data" / "client_product_database.db"


def import_results(json_path: str, partial: bool = False) -> dict:
    """
    PURPOSE:
        Import UAT results from JSON file to database.

    PARAMETERS:
        json_path (str): Path to the JSON file containing test results
        partial (bool): If True, only import executed tests (skip 'Not Run')
                        Use for progress syncs vs final submissions

    RETURNS:
        dict: Summary of import operation with counts and any errors

    WHY THIS APPROACH:
        We iterate through each result and update individually to:
        1. Track which tests were found vs not found
        2. Append notes rather than overwrite (preserves history)
        3. Log errors per-test for debugging
        4. For partial syncs, skip 'Not Run' tests to preserve previous results
    """

    # Read the JSON file
    # Similar to jsonlite::fromJSON() in R
    with open(json_path, 'r') as f:
        data = json.load(f)

    # Extract metadata from the JSON
    # The structure matches what the tracker exports/Formspree sends
    tester = data.get('tester', 'Unknown')
    sync_type = data.get('sync_type', 'final')  # auto_open, auto_10pm, manual, final
    submitted_at = data.get('submitted_at', data.get('synced_at', datetime.now().isoformat()))

    # Detect partial mode from sync_type if not explicitly set
    # Progress syncs (not final) should only update executed tests
    if sync_type in ('auto_open', 'auto_10pm', 'manual'):
        partial = True

    # Results can be in 'results' key (from export) or directly in data
    results = data.get('results', [])

    if not results:
        return {"error": "No results found in JSON file"}

    # Connect to database
    # Similar to DBI::dbConnect() in R
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Track import statistics
    updated = 0
    skipped = 0  # Tests skipped in partial mode
    not_found = 0
    errors = []

    # Process each test result
    for result in results:
        # Extract fields - handle both export format and Formspree format
        test_id = result.get('test_id')
        status = result.get('status', result.get('test_status'))
        notes = result.get('notes', '')
        tested_date = result.get('tested_date', submitted_at)

        # Validate required fields
        if not test_id or not status:
            errors.append(f"Missing test_id or status: {result}")
            continue

        # In partial mode, skip tests that haven't been executed
        # This preserves any previous results for tests not yet re-executed
        if partial and status in ('Not Run', 'Not_Run', ''):
            skipped += 1
            continue

        try:
            # Update the test case in the database
            # We append notes rather than replace to preserve history
            # COALESCE handles the case where execution_notes is NULL
            cursor.execute("""
                UPDATE uat_test_cases
                SET test_status = ?,
                    tested_by = ?,
                    tested_date = ?,
                    execution_notes = CASE
                        WHEN execution_notes IS NULL OR execution_notes = '' THEN ?
                        WHEN ? = '' THEN execution_notes
                        ELSE execution_notes || char(10) || '[' || ? || '] ' || ?
                    END,
                    updated_date = CURRENT_TIMESTAMP
                WHERE test_id = ?
            """, (
                status,           # test_status
                tester,           # tested_by
                tested_date,      # tested_date
                notes,            # execution_notes (if empty)
                notes,            # check if notes is empty
                tester,           # prefix for appended notes
                notes,            # notes to append
                test_id           # WHERE clause
            ))

            if cursor.rowcount > 0:
                updated += 1
            else:
                not_found += 1
                errors.append(f"Test not found in database: {test_id}")

        except Exception as e:
            errors.append(f"Error updating {test_id}: {str(e)}")

    # Log the import to audit_history for compliance tracking
    # FDA 21 CFR Part 11 requires tracking all changes
    action_type = 'SYNC' if partial else 'IMPORT'
    cursor.execute("""
        INSERT INTO audit_history (
            record_type, record_id, action, field_changed,
            old_value, new_value, changed_by, change_reason
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        'uat_test_cases',
        f"batch-{action_type.lower()}-{len(results)}",
        action_type,
        'test_status',
        None,
        f"{'Synced' if partial else 'Imported'} {updated} results, {skipped} skipped, {not_found} not found",
        tester,
        f"JSON {sync_type} from {Path(json_path).name}"
    ))

    # Commit all changes
    conn.commit()
    conn.close()

    # Return summary
    return {
        "success": True,
        "tester": tester,
        "sync_type": sync_type,
        "partial": partial,
        "submitted_at": submitted_at,
        "total_in_file": len(results),
        "updated": updated,
        "skipped": skipped,
        "not_found": not_found,
        "errors": errors
    }


def main():
    """
    PURPOSE:
        Entry point for command-line usage.

    USAGE:
        python import_uat_results.py <path/to/results.json>
        python import_uat_results.py <path/to/results.json> --partial
    """
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description='Import UAT test results from JSON file into the database.',
        epilog='The JSON file can be exported from the UAT tracker or received via Formspree.'
    )
    parser.add_argument('json_path', help='Path to the JSON results file')
    parser.add_argument(
        '--partial', '-p',
        action='store_true',
        help='Partial sync mode: only update executed tests (skip Not Run). '
             'Use for progress syncs. Automatically detected from sync_type in JSON.'
    )

    args = parser.parse_args()

    # Verify file exists
    if not Path(args.json_path).exists():
        print(f"Error: File not found: {args.json_path}")
        sys.exit(1)

    # Verify database exists
    if not DB_PATH.exists():
        print(f"Error: Database not found: {DB_PATH}")
        print("Make sure the data/ symlink is configured correctly.")
        sys.exit(1)

    # Run the import
    mode_str = " (partial sync mode)" if args.partial else ""
    print(f"Importing results from: {args.json_path}{mode_str}")
    print(f"Database: {DB_PATH}")
    print("")

    result = import_results(args.json_path, partial=args.partial)

    # Handle errors
    if result.get("error"):
        print(f"Error: {result['error']}")
        sys.exit(1)

    # Print summary
    action = "Sync" if result['partial'] else "Import"
    print(f"{action} complete!")
    print(f"  Tester: {result['tester']}")
    print(f"  Sync type: {result['sync_type']}")
    print(f"  Submitted: {result['submitted_at']}")
    print(f"  Total in file: {result['total_in_file']}")
    print(f"  Updated: {result['updated']}")
    if result['skipped'] > 0:
        print(f"  Skipped (not run): {result['skipped']}")
    print(f"  Not found: {result['not_found']}")

    # Print errors if any
    if result['errors']:
        print(f"\nWarnings/Errors ({len(result['errors'])}):")
        # Show first 10 errors
        for err in result['errors'][:10]:
            print(f"  - {err}")
        if len(result['errors']) > 10:
            print(f"  ... and {len(result['errors']) - 10} more")

    # Exit with appropriate code
    if result['updated'] == 0:
        print("\nNo tests were updated. Check test IDs match the database.")
        sys.exit(1)
    else:
        print(f"\nSuccessfully updated {result['updated']} test(s).")
        sys.exit(0)


if __name__ == "__main__":
    main()
