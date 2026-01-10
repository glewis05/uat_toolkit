# reporters/cycle_summary.py
# ============================================================================
# UAT CYCLE SUMMARY REPORTS
# ============================================================================
# PURPOSE: Generate progress dashboards and reports for UAT cycles.
#
# AVIATION ANALOGY:
#   Like a mission status board showing completion percentage,
#   crew assignments, and readiness status.
#
# ============================================================================

from typing import Optional, Dict, List
from database.db_manager import UATDatabase


def get_dashboard_report(cycle_id: str, db_path: str = None) -> str:
    """
    PURPOSE:
        Generate a comprehensive dashboard view of UAT cycle progress.
        Designed for display in terminal or as MCP tool response.

    PARAMETERS:
        cycle_id (str): Cycle ID to report on
        db_path (str): Optional database path override

    RETURNS:
        str: Formatted dashboard text with visual progress indicators

    R EQUIVALENT:
        Like cli::cli_h1() with embedded progress bars.

    AVIATION ANALOGY:
        This is your mission status board - shows overall progress,
        crew (tester) status, and any issues requiring attention.
    """
    with UATDatabase(db_path) as db:
        cycle = db.get_cycle(cycle_id)
        if not cycle:
            return f"Error: Cycle not found: {cycle_id}"

        gate_status = db.get_gate_status(cycle_id)
        tester_progress = db.get_tester_progress(cycle_id)
        retest_queue = db.get_retest_queue(cycle_id)

        # Build dashboard
        result = f"""
{'=' * 64}
  UAT CYCLE DASHBOARD
{'=' * 64}
  {cycle['name'][:55]}
  {cycle.get('program_prefix', 'N/A')} | {cycle['uat_type']} | Status: {cycle['status'].upper()}
{'=' * 64}
"""

        # Days to launch warning
        days = cycle.get('days_to_launch')
        if days is not None:
            if days > 7:
                result += f"Target Launch: {cycle.get('target_launch_date')} ({days} days)\n"
            elif days > 0:
                result += f"!!! {days} DAYS TO LAUNCH !!!\n"
            elif days == 0:
                result += "!!! TARGET LAUNCH DATE IS TODAY !!!\n"
            else:
                result += f"*** {abs(days)} DAYS PAST TARGET LAUNCH ***\n"

        # Test Progress Section
        total = cycle.get('total_tests') or 0
        passed = cycle.get('passed') or 0
        failed = cycle.get('failed') or 0
        blocked = cycle.get('blocked') or 0
        not_run = cycle.get('not_run') or 0

        result += f"""
TEST PROGRESS
{'─' * 50}
Total Tests: {total}
"""

        if total > 0:
            # Calculate percentages
            pass_pct = round(100 * passed / total)
            fail_pct = round(100 * failed / total)
            blocked_pct = round(100 * blocked / total)
            not_run_pct = round(100 * not_run / total)

            # Visual progress bar (40 chars wide)
            bar_width = 40
            pass_bar = int(bar_width * passed / total)
            fail_bar = int(bar_width * failed / total)
            blocked_bar = int(bar_width * blocked / total)
            not_run_bar = bar_width - pass_bar - fail_bar - blocked_bar

            bar = '#' * pass_bar + 'X' * fail_bar + '!' * blocked_bar + '.' * not_run_bar
            result += f"[{bar}]\n\n"

            result += f"  Passed:   {passed:>4} ({pass_pct:>3}%) #\n"
            result += f"  Failed:   {failed:>4} ({fail_pct:>3}%) X\n"
            result += f"  Blocked:  {blocked:>4} ({blocked_pct:>3}%) !\n"
            result += f"  Not Run:  {not_run:>4} ({not_run_pct:>3}%) .\n"

            exec_pct = cycle.get('execution_pct') or 0
            pass_rate = cycle.get('pass_rate') or 0
            result += f"\nExecution: {exec_pct}% | Pass Rate: {pass_rate}%\n"

        # Tester Progress Section
        if tester_progress:
            result += f"""
TESTER PROGRESS
{'─' * 50}
"""
            for tp in tester_progress:
                pct = tp.get('completion_pct') or 0
                bar_len = int(20 * pct / 100)
                bar = '#' * bar_len + '.' * (20 - bar_len)

                # Truncate tester name if needed
                tester = tp['assigned_to'][:20] if tp['assigned_to'] else 'Unassigned'
                result += f"  {tester:<20} [{bar}] {pct:>3}%\n"
                result += f"    {tp.get('passed', 0)} pass / {tp.get('failed', 0)} fail / {tp.get('not_run', 0)} pending\n"

        # Retest Queue Section
        if retest_queue:
            result += f"""
RETEST QUEUE ({len(retest_queue)} tests)
{'─' * 50}
"""
            for test in retest_queue[:5]:
                status_icon = {
                    'pending': '[---]',
                    'investigating': '[INV]',
                    'fixed': '[FIX]',
                    'wont_fix': '[WNT]',
                    'not_a_bug': '[NAB]'
                }.get(test.get('dev_status', 'pending'), '[???]')

                result += f"  {status_icon} {test['test_id']}\n"
                if test.get('defect_id'):
                    result += f"         Defect: {test['defect_id']}\n"

            if len(retest_queue) > 5:
                result += f"  ... and {len(retest_queue) - 5} more\n"

        # Gate Status Section
        result += f"""
PRE-UAT GATE
{'─' * 50}
  Items: {gate_status.get('completed', 0)}/{gate_status.get('total', 0)} complete
  Required Pending: {gate_status.get('required_pending', 0)}
  Gate Passed: {'YES' if cycle.get('pre_uat_gate_passed') else 'NO'}
"""

        # Go/No-Go Decision
        if cycle.get('go_nogo_decision'):
            decision_display = {
                'go': 'GO - Approved',
                'conditional_go': 'CONDITIONAL GO',
                'no_go': 'NO-GO - Blocked'
            }.get(cycle['go_nogo_decision'], cycle['go_nogo_decision'])

            result += f"""
GO/NO-GO DECISION
{'─' * 50}
  Decision: {decision_display}
  Signed by: {cycle.get('go_nogo_signed_by', 'N/A')}
  Date: {cycle.get('go_nogo_signed_date', 'N/A')}
"""
            if cycle.get('go_nogo_notes'):
                result += f"  Notes: {cycle['go_nogo_notes'][:60]}\n"

        return result


def get_progress_report(
    program_prefix: str = None,
    status_filter: str = None,
    db_path: str = None
) -> str:
    """
    PURPOSE:
        Generate a summary report across multiple UAT cycles.

    PARAMETERS:
        program_prefix: Filter by program
        status_filter: Filter by status
        db_path: Optional database path

    RETURNS:
        str: Multi-cycle progress summary
    """
    with UATDatabase(db_path) as db:
        cycles = db.list_cycles(
            program_prefix=program_prefix,
            status=status_filter
        )

        if not cycles:
            msg = "No UAT cycles found"
            if program_prefix:
                msg += f" for program {program_prefix}"
            if status_filter:
                msg += f" with status {status_filter}"
            return msg

        result = f"""
UAT PROGRESS REPORT
{'=' * 64}
"""
        if program_prefix:
            result += f"Program: {program_prefix}\n"
        if status_filter:
            result += f"Status: {status_filter}\n"
        result += f"Cycles: {len(cycles)}\n\n"

        # Summary totals
        total_tests = sum(c.get('total_tests') or 0 for c in cycles)
        total_passed = sum(c.get('passed') or 0 for c in cycles)
        total_failed = sum(c.get('failed') or 0 for c in cycles)

        if total_tests > 0:
            result += f"Total Tests: {total_tests}\n"
            result += f"Overall Pass Rate: {round(100 * total_passed / total_tests)}%\n\n"

        # Per-cycle breakdown
        for cycle in cycles:
            status_icon = {
                'planning': '[PLAN]',
                'validation': '[VAL ]',
                'kickoff': '[KICK]',
                'testing': '[TEST]',
                'review': '[REV ]',
                'retesting': '[RTST]',
                'decision': '[DEC ]',
                'complete': '[DONE]',
                'cancelled': '[CANC]'
            }.get(cycle['status'], '[????]')

            result += f"{status_icon} {cycle['cycle_id']}\n"
            result += f"  {cycle['name']}\n"

            tests = cycle.get('total_tests') or 0
            if tests > 0:
                pct = cycle.get('execution_pct') or 0
                passed = cycle.get('passed') or 0
                result += f"  Progress: {pct}% ({passed}/{tests})\n"

            if cycle.get('days_to_launch') is not None:
                days = cycle['days_to_launch']
                if days >= 0:
                    result += f"  Launch: {days} days\n"
                else:
                    result += f"  Launch: {abs(days)} days OVERDUE\n"

            result += "\n"

        return result


def get_rule_coverage_report(cycle_id: str, db_path: str = None) -> str:
    """
    PURPOSE:
        Generate NCCN rule coverage report for a cycle.
        Shows test coverage by rule and change type.

    PARAMETERS:
        cycle_id: Cycle to report on
        db_path: Optional database path

    RETURNS:
        str: Rule coverage summary
    """
    with UATDatabase(db_path) as db:
        conn = db.get_connection()
        cursor = conn.execute("""
            SELECT * FROM v_nccn_rule_coverage
            WHERE cycle_id = ?
            ORDER BY change_id, target_rule
        """, (cycle_id,))
        rules = [dict(row) for row in cursor.fetchall()]

        if not rules:
            return f"No NCCN rule coverage data for cycle {cycle_id}"

        result = f"""
NCCN RULE COVERAGE REPORT
{'=' * 64}
Cycle: {cycle_id}
{'=' * 64}

"""

        current_change = None
        for rule in rules:
            if rule['change_id'] != current_change:
                current_change = rule['change_id']
                result += f"\nChange: {current_change} ({rule.get('change_type', 'Unknown')})\n"
                result += "─" * 40 + "\n"

            total = rule.get('total_profiles') or 0
            passed = rule.get('passed') or 0
            failed = rule.get('failed') or 0
            not_run = rule.get('not_run') or 0

            if total > 0:
                pct = round(100 * passed / total)
            else:
                pct = 0

            result += f"  {rule['target_rule']} [{rule.get('platform', '?')}]: "
            result += f"{passed}/{total} ({pct}%)\n"

            # Show breakdown by test type
            pos = rule.get('pos_tests') or 0
            neg = rule.get('neg_tests') or 0
            dep = rule.get('dep_tests') or 0

            if pos + neg + dep > 0:
                result += f"    POS: {pos} | NEG: {neg} | DEP: {dep}\n"

            if failed > 0:
                result += f"    ** {failed} FAILED **\n"

        return result
