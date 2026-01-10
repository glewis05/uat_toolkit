#!/usr/bin/env python3
# run.py
# ============================================================================
# UAT TOOLKIT CLI
# ============================================================================
# PURPOSE: Command-line interface for UAT cycle management.
#
# USAGE:
#   python run.py create-cycle "NCCN Q4 2025" rule_validation
#   python run.py status UAT-NCCN-12345678
#   python run.py import-nccn package.xlsx UAT-NCCN-12345678
#   python run.py export UAT-NCCN-12345678
#
# ============================================================================

import argparse
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.db_manager import UATDatabase, get_database_path
from database.queries import get_cycle_summary, list_active_cycles, get_gate_checklist
from importers.nccn_importer import import_nccn_profiles, import_nccn_assignments
from reporters.cycle_summary import get_dashboard_report, get_progress_report
from reporters.excel_export import export_uat_results


def cmd_create_cycle(args):
    """Create a new UAT cycle."""
    with UATDatabase() as db:
        cycle_id = db.create_cycle(
            name=args.name,
            uat_type=args.uat_type,
            target_launch_date=args.launch_date,
            program_prefix=args.program,
            clinical_pm=args.pm,
            clinical_pm_email=args.pm_email,
            description=args.description,
            created_by='cli:run.py'
        )

        print(f"\n✓ UAT Cycle created successfully!")
        print(f"\nCycle ID: {cycle_id}")
        print(f"Name: {args.name}")
        print(f"Type: {args.uat_type}")

        if args.program:
            print(f"Program: {args.program}")
        if args.launch_date:
            print(f"Target Launch: {args.launch_date}")
        if args.pm:
            print(f"Clinical PM: {args.pm}")

        gate_status = db.get_gate_status(cycle_id)
        print(f"\nPre-UAT Gate: {gate_status['total']} items created")

        print(f"\nNext steps:")
        print(f"  python run.py status {cycle_id}")
        print(f"  python run.py import-nccn <file.xlsx> {cycle_id}")


def cmd_status(args):
    """Show cycle status."""
    if args.cycle_id:
        print(get_dashboard_report(args.cycle_id))
    else:
        print(list_active_cycles(program_prefix=args.program))


def cmd_list(args):
    """List UAT cycles."""
    print(get_progress_report(
        program_prefix=args.program,
        status_filter=args.status
    ))


def cmd_gate(args):
    """Show or update pre-UAT gate."""
    if args.complete:
        # Mark item complete
        with UATDatabase() as db:
            success = db.update_gate_item(
                item_id=int(args.complete),
                is_complete=True,
                completed_by=args.by or 'cli:run.py',
                notes=args.notes
            )
            if success:
                print(f"✓ Gate item {args.complete} marked complete")
            else:
                print(f"Error: Gate item {args.complete} not found")
    elif args.signoff:
        # Sign off on gate
        with UATDatabase() as db:
            success, message = db.sign_off_gate(
                cycle_id=args.cycle_id,
                signed_by=args.signoff,
                notes=args.notes
            )
            if success:
                print(f"✓ {message}")
            else:
                print(f"Error: {message}")
    else:
        # Show gate status
        print(get_gate_checklist(args.cycle_id))


def cmd_import_nccn(args):
    """Import NCCN profiles from Excel."""
    result = import_nccn_profiles(
        file_path=args.file,
        cycle_id=args.cycle_id,
        sheet_name=args.sheet,
        preview_only=args.preview
    )

    if result.get('error'):
        print(f"Error: {result['error']}")
        return

    print(f"\n{'PREVIEW - ' if args.preview else ''}NCCN Profile Import")
    print(f"{'=' * 50}")
    print(f"Profiles Found: {result['profiles_found']}")

    if result.get('by_platform'):
        print(f"\nBy Platform:")
        for platform, count in result['by_platform'].items():
            print(f"  {platform}: {count}")

    if result.get('by_test_type'):
        print(f"\nBy Test Type:")
        for test_type, count in result['by_test_type'].items():
            print(f"  {test_type}: {count}")

    if result.get('by_change_type'):
        print(f"\nBy Change Type:")
        for change_type, count in result['by_change_type'].items():
            print(f"  {change_type}: {count}")

    if not args.preview:
        print(f"\nCreated: {result.get('profiles_created', 0)}")
        print(f"Updated: {result.get('profiles_updated', 0)}")
    else:
        print(f"\nRun with --no-preview to import")


def cmd_assign(args):
    """Assign tests from tester sheet."""
    result = import_nccn_assignments(
        file_path=args.file,
        cycle_id=args.cycle_id,
        tester_sheet=args.sheet,
        tester_email=args.tester,
        assignment_type=args.type,
        preview_only=args.preview
    )

    if result.get('error'):
        print(f"Error: {result['error']}")
        return

    print(f"\n{'PREVIEW - ' if args.preview else ''}Test Assignment")
    print(f"{'=' * 50}")
    print(f"Tester: {result['tester']}")
    print(f"Profiles Found: {result['profiles_found']}")
    print(f"Assignment Type: {result['assignment_type']}")

    if not args.preview:
        print(f"Assignments Made: {result.get('assignments_made', 0)}")
    else:
        print(f"\nRun with --no-preview to assign")


def cmd_export(args):
    """Export results to Excel."""
    result = export_uat_results(
        cycle_id=args.cycle_id,
        output_dir=args.output_dir
    )

    if not result.get('success'):
        print(f"Error: {result.get('error', 'Unknown error')}")
        return

    print(f"\n✓ Export successful!")
    print(f"\nFile: {result['file_path']}")
    print(f"Sheets: {', '.join(result['sheets'])}")
    print(f"Tests: {result['test_count']}")
    print(f"Failed: {result.get('failed_count', 0)}")
    print(f"Retest Queue: {result.get('retest_count', 0)}")


def cmd_update_status(args):
    """Update cycle status."""
    with UATDatabase() as db:
        success = db.update_cycle_status(
            cycle_id=args.cycle_id,
            new_status=args.status,
            phase_date=args.date,
            changed_by='cli:run.py',
            notes=args.notes
        )

        if success:
            print(f"✓ Cycle {args.cycle_id} status updated to {args.status}")
        else:
            print(f"Error: Cycle {args.cycle_id} not found")


def cmd_decision(args):
    """Record go/no-go decision."""
    with UATDatabase() as db:
        success, message = db.record_go_nogo_decision(
            cycle_id=args.cycle_id,
            decision=args.decision,
            signed_by=args.signed_by,
            notes=args.notes
        )

        if success:
            print(f"\n✓ {message}")
            print(f"\nCycle: {args.cycle_id}")
            print(f"Decision: {args.decision.upper()}")
            print(f"Signed by: {args.signed_by}")
        else:
            print(f"Error: {message}")


def main():
    parser = argparse.ArgumentParser(
        description='UAT Toolkit - Manage UAT cycles and test execution',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s create-cycle "NCCN Q4 2025" rule_validation --launch-date 2025-03-15
  %(prog)s status UAT-NCCN-12345678
  %(prog)s import-nccn package.xlsx UAT-NCCN-12345678 --preview
  %(prog)s assign package.xlsx UAT-NCCN-12345678 --sheet "Tester 1" --tester jane@example.com
  %(prog)s export UAT-NCCN-12345678
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # create-cycle command
    p_create = subparsers.add_parser('create-cycle', help='Create a new UAT cycle')
    p_create.add_argument('name', help='Cycle name (e.g., "NCCN Q4 2025")')
    p_create.add_argument('uat_type', choices=['feature', 'rule_validation', 'regression'],
                          help='Type of UAT')
    p_create.add_argument('--launch-date', dest='launch_date', help='Target launch date (YYYY-MM-DD)')
    p_create.add_argument('--program', '-p', help='Program prefix (e.g., PROP)')
    p_create.add_argument('--pm', help='Clinical PM name')
    p_create.add_argument('--pm-email', help='Clinical PM email')
    p_create.add_argument('--description', '-d', help='Cycle description')
    p_create.set_defaults(func=cmd_create_cycle)

    # status command
    p_status = subparsers.add_parser('status', help='Show cycle status')
    p_status.add_argument('cycle_id', nargs='?', help='Cycle ID (or show all active)')
    p_status.add_argument('--program', '-p', help='Filter by program prefix')
    p_status.set_defaults(func=cmd_status)

    # list command
    p_list = subparsers.add_parser('list', help='List UAT cycles')
    p_list.add_argument('--program', '-p', help='Filter by program prefix')
    p_list.add_argument('--status', '-s', help='Filter by status')
    p_list.set_defaults(func=cmd_list)

    # gate command
    p_gate = subparsers.add_parser('gate', help='View or update pre-UAT gate')
    p_gate.add_argument('cycle_id', help='Cycle ID')
    p_gate.add_argument('--complete', '-c', help='Mark item ID as complete')
    p_gate.add_argument('--signoff', help='Sign off on gate (provide signer name)')
    p_gate.add_argument('--by', help='Who completed the item')
    p_gate.add_argument('--notes', '-n', help='Notes')
    p_gate.set_defaults(func=cmd_gate)

    # import-nccn command
    p_import = subparsers.add_parser('import-nccn', help='Import NCCN profiles from Excel')
    p_import.add_argument('file', help='Path to Excel file')
    p_import.add_argument('cycle_id', help='Cycle ID to associate profiles with')
    p_import.add_argument('--sheet', default='Test Profile Catalog', help='Sheet name to import')
    p_import.add_argument('--preview', action='store_true', default=True, help='Preview only (default)')
    p_import.add_argument('--no-preview', dest='preview', action='store_false', help='Actually import')
    p_import.set_defaults(func=cmd_import_nccn)

    # assign command
    p_assign = subparsers.add_parser('assign', help='Assign tests from tester sheet')
    p_assign.add_argument('file', help='Path to Excel file')
    p_assign.add_argument('cycle_id', help='Cycle ID')
    p_assign.add_argument('--sheet', required=True, help='Tester sheet name (e.g., "Tester 1")')
    p_assign.add_argument('--tester', required=True, help='Tester email')
    p_assign.add_argument('--type', default='primary', choices=['primary', 'secondary', 'cross_check'],
                          help='Assignment type')
    p_assign.add_argument('--preview', action='store_true', default=True, help='Preview only (default)')
    p_assign.add_argument('--no-preview', dest='preview', action='store_false', help='Actually assign')
    p_assign.set_defaults(func=cmd_assign)

    # export command
    p_export = subparsers.add_parser('export', help='Export results to Excel')
    p_export.add_argument('cycle_id', help='Cycle ID to export')
    p_export.add_argument('--output-dir', '-o', help='Output directory (default: outputs/)')
    p_export.set_defaults(func=cmd_export)

    # update-status command
    p_update = subparsers.add_parser('update-status', help='Update cycle status')
    p_update.add_argument('cycle_id', help='Cycle ID')
    p_update.add_argument('status', choices=['planning', 'validation', 'kickoff', 'testing',
                                              'review', 'retesting', 'decision', 'complete', 'cancelled'],
                          help='New status')
    p_update.add_argument('--date', help='Phase date (YYYY-MM-DD, defaults to today)')
    p_update.add_argument('--notes', '-n', help='Notes')
    p_update.set_defaults(func=cmd_update_status)

    # decision command
    p_decision = subparsers.add_parser('decision', help='Record go/no-go decision')
    p_decision.add_argument('cycle_id', help='Cycle ID')
    p_decision.add_argument('decision', choices=['go', 'conditional_go', 'no_go'],
                            help='Decision')
    p_decision.add_argument('--signed-by', required=True, help='Who is signing off')
    p_decision.add_argument('--notes', '-n', help='Decision notes/conditions')
    p_decision.set_defaults(func=cmd_decision)

    # Parse and execute
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Check database connection
    db_path = get_database_path()
    if not db_path.exists():
        print(f"Warning: Database not found at {db_path}")
        print("Creating database connection anyway...")

    # Run command
    args.func(args)


if __name__ == '__main__':
    main()
