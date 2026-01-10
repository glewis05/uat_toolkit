# database/queries.py
# ============================================================================
# UAT TOOLKIT QUERY FUNCTIONS
# ============================================================================
# PURPOSE: Standalone query functions for UAT operations.
#          These complement the UATDatabase class methods and provide
#          formatted output suitable for CLI and MCP tool responses.
#
# USAGE:
#   from database.queries import get_cycle_summary, list_active_cycles
#
# ============================================================================

from typing import Optional, Dict, List
from .db_manager import UATDatabase, get_database_path


def get_cycle_summary(cycle_id: str, db_path: str = None) -> str:
    """
    PURPOSE:
        Get a comprehensive text summary of a UAT cycle.
        Suitable for CLI output or MCP tool response.

    PARAMETERS:
        cycle_id (str): Cycle ID to look up
        db_path (str): Optional database path override

    RETURNS:
        str: Formatted summary text

    R EQUIVALENT:
        Like glue::glue() with embedded data, producing formatted text output.
    """
    with UATDatabase(db_path) as db:
        cycle = db.get_cycle(cycle_id)
        if not cycle:
            return f"Error: Cycle not found: {cycle_id}"

        gate_status = db.get_gate_status(cycle_id)
        tester_progress = db.get_tester_progress(cycle_id)

        # Build summary
        result = f"""
UAT Cycle Summary
{'=' * 50}

Cycle ID: {cycle['cycle_id']}
Name: {cycle['name']}
Type: {cycle['uat_type']}
Status: {cycle['status'].upper()}
Program: {cycle.get('program_name', 'N/A')} [{cycle.get('program_prefix', 'N/A')}]
"""
        if cycle.get('target_launch_date'):
            days = cycle.get('days_to_launch')
            if days is not None:
                if days > 0:
                    result += f"Target Launch: {cycle['target_launch_date']} ({days} days away)\n"
                elif days == 0:
                    result += f"Target Launch: {cycle['target_launch_date']} (TODAY)\n"
                else:
                    result += f"Target Launch: {cycle['target_launch_date']} ({abs(days)} days OVERDUE)\n"

        if cycle.get('clinical_pm'):
            result += f"Clinical PM: {cycle['clinical_pm']}\n"

        # Test Progress
        total = cycle.get('total_tests') or 0
        if total > 0:
            passed = cycle.get('passed') or 0
            failed = cycle.get('failed') or 0
            blocked = cycle.get('blocked') or 0
            not_run = cycle.get('not_run') or 0

            result += f"""
Test Progress
─────────────────────────────────────────
Total Tests: {total}
  Passed:  {passed:>4} ({round(100 * passed / total)}%)
  Failed:  {failed:>4} ({round(100 * failed / total)}%)
  Blocked: {blocked:>4} ({round(100 * blocked / total)}%)
  Not Run: {not_run:>4} ({round(100 * not_run / total)}%)

Execution: {cycle.get('execution_pct') or 0}%
Pass Rate: {cycle.get('pass_rate') or 0}%
"""

        # Gate Status
        result += f"""
Pre-UAT Gate
─────────────────────────────────────────
Items Complete: {gate_status.get('completed') or 0}/{gate_status.get('total') or 0}
Required Pending: {gate_status.get('required_pending') or 0}
Gate Passed: {'Yes' if cycle.get('pre_uat_gate_passed') else 'No'}
"""

        # Tester Progress
        if tester_progress:
            result += """
Tester Progress
─────────────────────────────────────────
"""
            for tp in tester_progress:
                pct = tp.get('completion_pct') or 0
                result += f"  {tp['assigned_to']}: {pct}% ({tp.get('passed', 0)}/{tp.get('total_tests', 0)})\n"

        # Go/No-Go
        if cycle.get('go_nogo_decision'):
            result += f"""
Go/No-Go Decision: {cycle['go_nogo_decision'].upper()}
  Signed by: {cycle.get('go_nogo_signed_by')}
"""

        return result


def list_active_cycles(program_prefix: str = None, db_path: str = None) -> str:
    """
    PURPOSE:
        List all active (non-complete, non-cancelled) UAT cycles.

    PARAMETERS:
        program_prefix: Optional filter by program
        db_path: Optional database path override

    RETURNS:
        str: Formatted list of cycles
    """
    with UATDatabase(db_path) as db:
        # Get all non-terminal cycles
        all_cycles = db.list_cycles(program_prefix=program_prefix)
        active = [c for c in all_cycles if c['status'] not in ('complete', 'cancelled')]

        if not active:
            return "No active UAT cycles found."

        result = f"Active UAT Cycles ({len(active)})\n"
        result += "=" * 50 + "\n\n"

        for cycle in active:
            status_icon = {
                'planning': '[plan]',
                'validation': '[val]',
                'kickoff': '[kick]',
                'testing': '[test]',
                'review': '[rev]',
                'retesting': '[re]',
                'decision': '[dec]'
            }.get(cycle['status'], '[?]')

            result += f"{status_icon} {cycle['cycle_id']}\n"
            result += f"    {cycle['name']}\n"
            result += f"    Type: {cycle['uat_type']}"
            if cycle.get('program_prefix'):
                result += f" | Program: {cycle['program_prefix']}"
            if cycle.get('days_to_launch') is not None:
                result += f" | {cycle['days_to_launch']}d to launch"
            result += "\n"

            if cycle.get('total_tests'):
                pct = cycle.get('execution_pct') or 0
                result += f"    Progress: {pct}% ({cycle.get('passed', 0)}/{cycle['total_tests']})\n"

            result += "\n"

        return result


def get_failing_tests(cycle_id: str, db_path: str = None) -> str:
    """
    PURPOSE:
        Get list of failing tests for a cycle.

    RETURNS:
        str: Formatted list of failed tests
    """
    with UATDatabase(db_path) as db:
        retest_queue = db.get_retest_queue(cycle_id)

        if not retest_queue:
            return f"No failing tests in cycle {cycle_id}"

        result = f"Failing Tests - Retest Queue ({len(retest_queue)})\n"
        result += "=" * 50 + "\n\n"

        for test in retest_queue:
            result += f"[{test['test_id']}]\n"
            result += f"  {test.get('title', 'Untitled')[:60]}\n"
            if test.get('defect_id'):
                result += f"  Defect: {test['defect_id']}\n"
            if test.get('dev_status'):
                result += f"  Dev Status: {test['dev_status']}\n"
            if test.get('retest_status'):
                result += f"  Retest: {test['retest_status']}\n"
            result += "\n"

        return result


def get_gate_checklist(cycle_id: str, db_path: str = None) -> str:
    """
    PURPOSE:
        Get formatted pre-UAT gate checklist.

    RETURNS:
        str: Formatted checklist with completion status
    """
    with UATDatabase(db_path) as db:
        items = db.get_gate_items(cycle_id)
        status = db.get_gate_status(cycle_id)

        if not items:
            return f"No gate items found for cycle {cycle_id}"

        result = f"Pre-UAT Gate Checklist\n"
        result += "=" * 50 + "\n"
        result += f"Status: {status.get('completed', 0)}/{status.get('total', 0)} complete\n"
        result += f"Ready for sign-off: {'Yes' if status.get('ready_for_signoff') else 'No'}\n\n"

        current_category = None
        for item in items:
            if item['category'] != current_category:
                current_category = item['category']
                result += f"\n{current_category.upper().replace('_', ' ')}:\n"

            # Icon: ✓ for complete, * for required incomplete, ○ for optional incomplete
            if item['is_complete']:
                icon = '✓'
            elif item['is_required']:
                icon = '*'
            else:
                icon = '○'

            result += f"  [{icon}] {item['item_text']}"
            if item['is_complete'] and item.get('completed_by'):
                result += f" (by {item['completed_by']})"
            result += "\n"

        result += "\nLegend: ✓ = complete, * = required pending, ○ = optional pending\n"

        return result
