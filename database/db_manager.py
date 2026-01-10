# database/db_manager.py
# ============================================================================
# UAT DATABASE MANAGER
# ============================================================================
# PURPOSE: Central database manager for UAT cycle operations.
#          Connects to the shared client_product_database.db.
#
# This toolkit READS from:
#   - programs, clients (from config toolkit)
#   - uat_test_cases (base table from requirements toolkit)
#   - audit_history (shared audit trail)
#
# This toolkit OWNS:
#   - uat_cycles (created by requirements_toolkit schema)
#   - pre_uat_gate_items (created by requirements_toolkit schema)
#
# This toolkit EXTENDS:
#   - uat_test_cases (adds cycle_id, assignment, NCCN fields)
#
# AVIATION ANALOGY:
#   Think of this as your mission operations database access layer.
#   Requirements Toolkit creates the flight plans (test cases),
#   UAT Toolkit manages the mission execution (cycles, assignments, results).
#
# ============================================================================

import os
import sqlite3
import uuid
from datetime import datetime, date
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple


def get_database_path() -> Path:
    """
    PURPOSE:
        Locate the shared database file.
        Checks multiple locations for flexibility.

    R EQUIVALENT:
        Like file.exists() with multiple path checks in a vector.

    RETURNS:
        Path: Path to client_product_database.db

    WHY THIS APPROACH:
        - Supports both local dev and production paths
        - Environment variable override for flexibility
        - Falls back through common locations
    """
    # Check environment variable first - highest priority
    if os.environ.get('PROPEL_DB_PATH'):
        db_path = Path(os.environ['PROPEL_DB_PATH'])
        if db_path.exists():
            return db_path

    # Check environment variable for requirements toolkit DB
    if os.environ.get('REQUIREMENTS_DB_PATH'):
        db_path = Path(os.environ['REQUIREMENTS_DB_PATH'])
        if db_path.exists():
            return db_path

    # Check common locations in order of preference
    locations = [
        # Local data symlink (preferred for this toolkit)
        Path(__file__).parent.parent / 'data' / 'client_product_database.db',
        # Requirements toolkit location (canonical source)
        Path.home() / 'projects' / 'requirements_toolkit' / 'data' / 'client_product_database.db',
        # Generic project location
        Path.home() / 'projects' / 'data' / 'client_product_database.db',
    ]

    for loc in locations:
        if loc.exists():
            return loc

    # If no database found, return the requirements toolkit path
    # (it will be created if needed)
    default_path = Path.home() / 'projects' / 'requirements_toolkit' / 'data' / 'client_product_database.db'
    return default_path


class UATDatabase:
    """
    PURPOSE:
        Central database manager for UAT cycle operations.
        Handles all CRUD operations with full audit logging.

    KEY FEATURES:
        - UAT cycle lifecycle management
        - Pre-UAT gate tracking
        - Test assignment and execution
        - Full audit trail for FDA 21 CFR Part 11 compliance

    USAGE:
        db = UATDatabase()
        cycle_id = db.create_cycle("NCCN Q4 2025", "rule_validation")
        db.close()

    R EQUIVALENT:
        Like a DBI connection with helper methods:
        con <- dbConnect(RSQLite::SQLite(), "database.db")
        dbExecute(con, "INSERT INTO uat_cycles ...")

    AVIATION ANALOGY:
        This is your mission operations database - tracks all UAT
        "missions" from planning through go/no-go decision.
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        PURPOSE:
            Initialize database connection.

        PARAMETERS:
            db_path (str, optional): Path to database file.
                                    Default: auto-detect shared database

        WHY THIS APPROACH:
            Lazy connection - database is only opened when first accessed.
            Supports both explicit path and auto-detection.
        """
        self.db_path = Path(db_path) if db_path else get_database_path()
        self._connection = None
        self._session_id = str(uuid.uuid4())[:8]  # For grouping audit entries

    def get_connection(self) -> sqlite3.Connection:
        """
        PURPOSE:
            Get database connection (creates if needed).

        RETURNS:
            sqlite3.Connection: Database connection object

        WHY THIS APPROACH:
            Single connection per instance for consistency.
            Row factory enables dict-like access to results.
        """
        if self._connection is None:
            self._connection = sqlite3.connect(str(self.db_path))
            self._connection.row_factory = sqlite3.Row
            # Enable foreign keys for referential integrity
            self._connection.execute("PRAGMA foreign_keys = ON")

        return self._connection

    def close(self):
        """Close database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close connection."""
        self.close()

    # ========================================================================
    # AUDIT LOGGING
    # ========================================================================

    def log_audit(
        self,
        record_type: str,
        record_id: str,
        action: str,
        field: Optional[str] = None,
        old_val: Optional[str] = None,
        new_val: Optional[str] = None,
        changed_by: str = 'system',
        reason: Optional[str] = None
    ):
        """
        PURPOSE:
            Log a change to the shared audit_history table.

        PARAMETERS:
            record_type: 'uat_cycle', 'gate_item', 'test_case', etc.
            record_id: ID of the record changed
            action: 'Created', 'Updated', 'Deleted', 'Status Changed', etc.
            field: Which field was changed (for updates)
            old_val: Previous value
            new_val: New value
            changed_by: Who made the change
            reason: Why the change was made (for compliance)

        WHY THIS APPROACH:
            Comprehensive audit trail required for FDA 21 CFR Part 11.
            Every change must be logged with who, what, when, and why.

        AVIATION ANALOGY:
            Like a flight data recorder - captures every significant event
            for post-mission review and regulatory compliance.
        """
        conn = self.get_connection()
        conn.execute("""
            INSERT INTO audit_history
            (record_type, record_id, action, field_changed, old_value,
             new_value, changed_by, change_reason, session_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (record_type, record_id, action, field, old_val, new_val,
              changed_by, reason, self._session_id))
        conn.commit()

    # ========================================================================
    # UAT CYCLE OPERATIONS
    # ========================================================================

    def create_cycle(
        self,
        name: str,
        uat_type: str,
        target_launch_date: Optional[str] = None,
        program_prefix: Optional[str] = None,
        clinical_pm: Optional[str] = None,
        clinical_pm_email: Optional[str] = None,
        description: Optional[str] = None,
        created_by: str = 'system'
    ) -> str:
        """
        PURPOSE:
            Create a new UAT cycle to group test cases for a specific release.

        R EQUIVALENT:
            Like tibble::add_row() with UUID generation and schema validation.

        PARAMETERS:
            name (str): Cycle name, e.g., "NCCN Q4 2025"
            uat_type (str): 'feature', 'rule_validation', 'regression'
            target_launch_date (str): YYYY-MM-DD format
            program_prefix (str): Optional program link (e.g., "NCCN")
            clinical_pm (str): PM name
            clinical_pm_email (str): PM email
            description (str): What's being tested
            created_by (str): Who created this cycle

        RETURNS:
            str: Generated cycle_id (UUID format)

        WHY THIS APPROACH:
            - UUID ensures unique IDs across all cycles
            - Status starts at 'planning' and progresses through workflow
            - Auto-creates default gate items based on uat_type
            - Audit logged for Part 11 compliance

        AVIATION ANALOGY:
            Like creating a new mission package - assigns a unique ID,
            sets initial status to "planning", and creates the preflight
            checklist based on mission type.
        """
        conn = self.get_connection()

        # Resolve program_id from prefix if provided
        program_id = None
        if program_prefix:
            cursor = conn.execute(
                "SELECT program_id FROM programs WHERE UPPER(prefix) = UPPER(?)",
                (program_prefix,)
            )
            row = cursor.fetchone()
            if row:
                program_id = row['program_id']

        # Generate cycle_id with prefix for readability
        prefix = program_prefix.upper() if program_prefix else 'UAT'
        cycle_id = f"UAT-{prefix}-{str(uuid.uuid4())[:8].upper()}"

        # Insert the cycle
        conn.execute("""
            INSERT INTO uat_cycles (
                cycle_id, program_id, name, description, uat_type,
                target_launch_date, clinical_pm, clinical_pm_email,
                status, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'planning', ?)
        """, (
            cycle_id, program_id, name, description, uat_type,
            target_launch_date, clinical_pm, clinical_pm_email, created_by
        ))

        # Create default gate items based on uat_type
        self._create_default_gate_items(cycle_id, uat_type)

        conn.commit()

        # Audit log
        self.log_audit(
            'uat_cycle', cycle_id, 'Created',
            new_val=f"{name} ({uat_type})",
            changed_by=created_by,
            reason=f"New UAT cycle created for {name}"
        )

        return cycle_id

    def _create_default_gate_items(self, cycle_id: str, uat_type: str):
        """
        PURPOSE:
            Create default pre-UAT gate checklist items based on UAT type.

        PARAMETERS:
            cycle_id: The cycle to create items for
            uat_type: 'feature', 'rule_validation', or 'regression'

        WHY THIS APPROACH:
            Different UAT types have different validation requirements.
            Pre-populating the checklist ensures nothing is missed.

        AVIATION ANALOGY:
            Like having mission-specific preflight checklists -
            a cargo mission has different checks than a combat mission.
        """
        conn = self.get_connection()

        # Define gate items by type
        # Format: (category, sequence, item_text, is_required)
        gate_items = []

        if uat_type == 'rule_validation':
            gate_items = [
                ('feature_deployment', 1, 'NCCN rules deployed to QA environment', 1),
                ('feature_deployment', 2, 'All rule IDs verified in system', 1),
                ('critical_path', 1, 'Patient registration flow tested', 1),
                ('critical_path', 2, 'Test profiles created and validated', 1),
                ('environment', 1, 'QA environment stable and accessible', 1),
                ('blocker_check', 1, 'No critical defects in backlog', 1),
                ('sign_off', 1, 'Clinical PM approval for test start', 1),
            ]
        elif uat_type == 'feature':
            gate_items = [
                ('feature_deployment', 1, 'Feature deployed to QA environment', 1),
                ('feature_deployment', 2, 'Feature flags configured correctly', 1),
                ('critical_path', 1, 'Core happy path verified', 1),
                ('environment', 1, 'QA environment stable and accessible', 1),
                ('blocker_check', 1, 'No critical defects blocking feature', 1),
                ('sign_off', 1, 'Product Owner approval for test start', 1),
            ]
        else:  # regression
            gate_items = [
                ('feature_deployment', 1, 'Release candidate deployed to QA', 1),
                ('critical_path', 1, 'Smoke tests passing', 1),
                ('environment', 1, 'QA environment mirrors production', 1),
                ('blocker_check', 1, 'No P0/P1 defects open', 1),
                ('sign_off', 1, 'Release Manager approval', 1),
            ]

        # Insert all gate items
        for category, seq, item_text, is_required in gate_items:
            conn.execute("""
                INSERT INTO pre_uat_gate_items
                (cycle_id, category, sequence, item_text, is_required)
                VALUES (?, ?, ?, ?, ?)
            """, (cycle_id, category, seq, item_text, is_required))

    def get_cycle(self, cycle_id: str) -> Optional[Dict]:
        """
        PURPOSE:
            Retrieve UAT cycle details with progress metrics.

        PARAMETERS:
            cycle_id (str): Cycle ID to look up

        RETURNS:
            dict: Cycle details with metrics, or None if not found

        WHY THIS APPROACH:
            Uses the v_uat_cycle_summary view for computed metrics.
        """
        conn = self.get_connection()
        cursor = conn.execute("""
            SELECT * FROM v_uat_cycle_summary WHERE cycle_id = ?
        """, (cycle_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_cycle_by_name(self, name: str) -> Optional[Dict]:
        """
        PURPOSE:
            Find cycle by name (case-insensitive partial match).

        PARAMETERS:
            name (str): Partial name to search for

        RETURNS:
            dict: First matching cycle, or None
        """
        conn = self.get_connection()
        cursor = conn.execute("""
            SELECT * FROM v_uat_cycle_summary
            WHERE LOWER(name) LIKE LOWER(?)
        """, (f'%{name}%',))
        row = cursor.fetchone()
        return dict(row) if row else None

    def list_cycles(
        self,
        program_prefix: Optional[str] = None,
        status: Optional[str] = None,
        uat_type: Optional[str] = None
    ) -> List[Dict]:
        """
        PURPOSE:
            List UAT cycles with optional filters.

        PARAMETERS:
            program_prefix: Filter by program prefix
            status: Filter by status
            uat_type: Filter by UAT type

        RETURNS:
            list: List of cycle summary dicts
        """
        conn = self.get_connection()

        query = "SELECT * FROM v_uat_cycle_summary WHERE 1=1"
        params = []

        if program_prefix:
            query += " AND UPPER(program_prefix) = UPPER(?)"
            params.append(program_prefix)
        if status:
            query += " AND status = ?"
            params.append(status)
        if uat_type:
            query += " AND uat_type = ?"
            params.append(uat_type)

        query += " ORDER BY target_launch_date DESC, name"

        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def update_cycle(
        self,
        cycle_id: str,
        updates: Dict[str, Any],
        changed_by: str = 'system',
        change_reason: Optional[str] = None
    ) -> bool:
        """
        PURPOSE:
            Update cycle fields with audit logging.
            Only provided fields are updated (sparse update).

        PARAMETERS:
            cycle_id: Cycle to update
            updates: Dict of field:value pairs to update
            changed_by: Who made the change
            change_reason: Why (for compliance)

        RETURNS:
            bool: True if updated, False if cycle not found

        WHY THIS APPROACH:
            Sparse updates prevent accidental overwrites.
            Each field change is individually logged for audit.
        """
        conn = self.get_connection()

        # Get current values
        cursor = conn.execute(
            "SELECT * FROM uat_cycles WHERE cycle_id = ?",
            (cycle_id,)
        )
        current = cursor.fetchone()
        if not current:
            return False

        current = dict(current)

        # Protected fields that shouldn't be updated directly
        protected = {'cycle_id', 'created_date', 'created_by'}

        # Build update query
        set_parts = []
        values = []
        for field, new_val in updates.items():
            if field not in protected:
                set_parts.append(f"{field} = ?")
                values.append(new_val)

                # Log each field change
                old_val = current.get(field)
                if str(old_val) != str(new_val):
                    self.log_audit(
                        'uat_cycle', cycle_id, 'Updated',
                        field=field,
                        old_val=str(old_val) if old_val else None,
                        new_val=str(new_val) if new_val else None,
                        changed_by=changed_by,
                        reason=change_reason
                    )

        if set_parts:
            set_parts.append("updated_date = CURRENT_TIMESTAMP")
            values.append(cycle_id)

            query = f"UPDATE uat_cycles SET {', '.join(set_parts)} WHERE cycle_id = ?"
            conn.execute(query, values)
            conn.commit()

        return True

    def update_cycle_status(
        self,
        cycle_id: str,
        new_status: str,
        phase_date: Optional[str] = None,
        changed_by: str = 'system',
        notes: Optional[str] = None
    ) -> bool:
        """
        PURPOSE:
            Update cycle status and automatically set phase date.

        PARAMETERS:
            cycle_id: Cycle to update
            new_status: New status value
            phase_date: Date for the phase (defaults to today)
            changed_by: Who made the change
            notes: Optional notes

        RETURNS:
            bool: True if updated

        WHY THIS APPROACH:
            Status changes often have associated dates.
            This helper sets the appropriate date column automatically.
        """
        # Map status to phase date column
        date_column_map = {
            'validation': 'validation_start',
            'kickoff': 'kickoff_date',
            'testing': 'testing_start',
            'review': 'review_date',
            'retesting': 'retest_start',
            'decision': 'go_nogo_date',
        }

        updates = {'status': new_status}

        # Set phase date if applicable
        if new_status in date_column_map:
            date_col = date_column_map[new_status]
            updates[date_col] = phase_date or date.today().isoformat()

        return self.update_cycle(
            cycle_id, updates,
            changed_by=changed_by,
            change_reason=notes or f"Status changed to {new_status}"
        )

    # ========================================================================
    # PRE-UAT GATE OPERATIONS
    # ========================================================================

    def get_gate_items(self, cycle_id: str) -> List[Dict]:
        """
        PURPOSE:
            Get all pre-UAT gate items for a cycle.

        RETURNS:
            list: Gate items ordered by category and sequence
        """
        conn = self.get_connection()
        cursor = conn.execute("""
            SELECT * FROM pre_uat_gate_items
            WHERE cycle_id = ?
            ORDER BY category, sequence
        """, (cycle_id,))
        return [dict(row) for row in cursor.fetchall()]

    def get_gate_status(self, cycle_id: str) -> Dict:
        """
        PURPOSE:
            Get gate completion status summary.

        RETURNS:
            dict: {total, completed, required_pending, ready_for_signoff}
        """
        conn = self.get_connection()
        cursor = conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(is_complete) as completed,
                SUM(CASE WHEN is_required = 1 AND is_complete = 0 THEN 1 ELSE 0 END) as required_pending
            FROM pre_uat_gate_items
            WHERE cycle_id = ?
        """, (cycle_id,))
        row = dict(cursor.fetchone())
        row['ready_for_signoff'] = (row['required_pending'] or 0) == 0
        return row

    def update_gate_item(
        self,
        item_id: int,
        is_complete: bool,
        completed_by: Optional[str] = None,
        notes: Optional[str] = None
    ) -> bool:
        """
        PURPOSE:
            Update a single gate item.

        PARAMETERS:
            item_id: Gate item ID
            is_complete: Whether item is complete
            completed_by: Who completed it
            notes: Completion notes

        RETURNS:
            bool: True if updated
        """
        conn = self.get_connection()

        completed_date = date.today().isoformat() if is_complete else None

        cursor = conn.execute("""
            UPDATE pre_uat_gate_items SET
                is_complete = ?,
                completed_by = ?,
                completed_date = ?,
                notes = COALESCE(?, notes)
            WHERE item_id = ?
        """, (1 if is_complete else 0, completed_by, completed_date, notes, item_id))

        conn.commit()
        return cursor.rowcount > 0

    def sign_off_gate(
        self,
        cycle_id: str,
        signed_by: str,
        notes: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        PURPOSE:
            Sign off on the pre-UAT gate for a cycle.

        PARAMETERS:
            cycle_id: Cycle to sign off
            signed_by: Who is signing
            notes: Sign-off notes

        RETURNS:
            tuple: (success: bool, message: str)

        WHY THIS APPROACH:
            Gate sign-off is a critical checkpoint - validates all
            required items are complete before proceeding.

        AVIATION ANALOGY:
            Like signing the aircraft logbook before flight -
            confirms all preflight checks are complete.
        """
        # Check if all required items are complete
        status = self.get_gate_status(cycle_id)
        if not status['ready_for_signoff']:
            return (False, f"{status['required_pending']} required item(s) still pending")

        # Update cycle with gate sign-off
        conn = self.get_connection()
        conn.execute("""
            UPDATE uat_cycles SET
                pre_uat_gate_passed = 1,
                pre_uat_gate_signed_by = ?,
                pre_uat_gate_signed_date = DATE('now'),
                pre_uat_gate_notes = ?,
                updated_date = CURRENT_TIMESTAMP
            WHERE cycle_id = ?
        """, (signed_by, notes, cycle_id))
        conn.commit()

        # Audit log
        self.log_audit(
            'uat_cycle', cycle_id, 'Gate Signed Off',
            field='pre_uat_gate_passed',
            old_val='0',
            new_val='1',
            changed_by=signed_by,
            reason=notes or 'Pre-UAT gate signed off'
        )

        return (True, "Gate signed off successfully")

    # ========================================================================
    # TEST CASE OPERATIONS
    # ========================================================================

    def assign_test_to_cycle(
        self,
        test_id: str,
        cycle_id: str,
        assigned_to: Optional[str] = None,
        assignment_type: str = 'primary'
    ) -> bool:
        """
        PURPOSE:
            Assign a test case to a UAT cycle.

        PARAMETERS:
            test_id: Test case ID
            cycle_id: Cycle to assign to
            assigned_to: Tester email/name
            assignment_type: 'primary', 'secondary', 'cross_check'

        RETURNS:
            bool: True if assigned
        """
        conn = self.get_connection()
        cursor = conn.execute("""
            UPDATE uat_test_cases SET
                uat_cycle_id = ?,
                assigned_to = COALESCE(?, assigned_to),
                assignment_type = COALESCE(?, assignment_type),
                updated_date = CURRENT_TIMESTAMP
            WHERE test_id = ?
        """, (cycle_id, assigned_to, assignment_type, test_id))
        conn.commit()
        return cursor.rowcount > 0

    def update_test_result(
        self,
        test_id: str,
        status: str,
        tested_by: str,
        notes: Optional[str] = None,
        defect_id: Optional[str] = None,
        defect_description: Optional[str] = None
    ) -> bool:
        """
        PURPOSE:
            Record test execution result.

        PARAMETERS:
            test_id: Test case ID
            status: 'Pass', 'Fail', 'Blocked', 'Skipped'
            tested_by: Who executed the test
            notes: Execution notes
            defect_id: Bug/defect ID if failed
            defect_description: Description of the defect

        RETURNS:
            bool: True if updated

        WHY THIS APPROACH:
            Separates initial test from retest results for full audit trail.
        """
        conn = self.get_connection()

        # Get current status for audit
        cursor = conn.execute(
            "SELECT test_status FROM uat_test_cases WHERE test_id = ?",
            (test_id,)
        )
        row = cursor.fetchone()
        if not row:
            return False

        old_status = row['test_status']

        cursor = conn.execute("""
            UPDATE uat_test_cases SET
                test_status = ?,
                tested_by = ?,
                tested_date = CURRENT_TIMESTAMP,
                execution_notes = COALESCE(?, execution_notes),
                defect_id = COALESCE(?, defect_id),
                defect_description = COALESCE(?, defect_description),
                updated_date = CURRENT_TIMESTAMP
            WHERE test_id = ?
        """, (status, tested_by, notes, defect_id, defect_description, test_id))
        conn.commit()

        # Audit log
        self.log_audit(
            'uat_test_case', test_id, 'Test Executed',
            field='test_status',
            old_val=old_status,
            new_val=status,
            changed_by=tested_by,
            reason=notes
        )

        return cursor.rowcount > 0

    def update_retest_result(
        self,
        test_id: str,
        retest_status: str,
        retest_by: str,
        retest_notes: Optional[str] = None
    ) -> bool:
        """
        PURPOSE:
            Record retest result separately from initial test.
            Preserves initial result for audit trail.

        PARAMETERS:
            test_id: Test case ID
            retest_status: 'Pass', 'Fail', 'Blocked', 'Skipped'
            retest_by: Who performed the retest
            retest_notes: Retest notes

        RETURNS:
            bool: True if updated

        WHY THIS APPROACH:
            Keeps initial test result intact while recording retest.
            Important for defect verification workflows.
        """
        conn = self.get_connection()
        cursor = conn.execute("""
            UPDATE uat_test_cases SET
                retest_status = ?,
                retest_by = ?,
                retest_date = CURRENT_TIMESTAMP,
                retest_notes = ?,
                updated_date = CURRENT_TIMESTAMP
            WHERE test_id = ?
        """, (retest_status, retest_by, retest_notes, test_id))
        conn.commit()

        # Audit log
        self.log_audit(
            'uat_test_case', test_id, 'Retested',
            field='retest_status',
            new_val=retest_status,
            changed_by=retest_by,
            reason=retest_notes
        )

        return cursor.rowcount > 0

    def get_tester_progress(self, cycle_id: str) -> List[Dict]:
        """
        PURPOSE:
            Get progress for all testers in a cycle.

        RETURNS:
            list: Tester progress dicts from v_uat_tester_progress
        """
        conn = self.get_connection()
        cursor = conn.execute("""
            SELECT * FROM v_uat_tester_progress
            WHERE cycle_id = ?
            ORDER BY completion_pct DESC
        """, (cycle_id,))
        return [dict(row) for row in cursor.fetchall()]

    def get_retest_queue(self, cycle_id: str) -> List[Dict]:
        """
        PURPOSE:
            Get all tests needing retest in a cycle.

        RETURNS:
            list: Failed tests from v_retest_queue
        """
        conn = self.get_connection()
        cursor = conn.execute("""
            SELECT * FROM v_retest_queue WHERE cycle_id = ?
        """, (cycle_id,))
        return [dict(row) for row in cursor.fetchall()]

    # ========================================================================
    # GO/NO-GO DECISION
    # ========================================================================

    def record_go_nogo_decision(
        self,
        cycle_id: str,
        decision: str,
        signed_by: str,
        notes: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        PURPOSE:
            Record the Go/No-Go decision for a UAT cycle.

        PARAMETERS:
            cycle_id: Cycle ID
            decision: 'go', 'conditional_go', 'no_go'
            signed_by: Who made the decision
            notes: Decision notes/conditions

        RETURNS:
            tuple: (success: bool, message: str)

        AVIATION ANALOGY:
            Like the mission commander's final launch authority.
            "GO" means proceed to production, "NO-GO" means hold.
        """
        valid_decisions = ['go', 'conditional_go', 'no_go']
        if decision not in valid_decisions:
            return (False, f"Invalid decision. Must be one of: {', '.join(valid_decisions)}")

        conn = self.get_connection()

        # Update cycle
        new_status = 'complete' if decision == 'go' else None
        update_sql = """
            UPDATE uat_cycles SET
                go_nogo_decision = ?,
                go_nogo_signed_by = ?,
                go_nogo_signed_date = DATE('now'),
                go_nogo_notes = ?,
                updated_date = CURRENT_TIMESTAMP
        """
        params = [decision, signed_by, notes]

        if new_status:
            update_sql += ", status = ?"
            params.append(new_status)

        update_sql += " WHERE cycle_id = ?"
        params.append(cycle_id)

        conn.execute(update_sql, params)
        conn.commit()

        # Audit log
        self.log_audit(
            'uat_cycle', cycle_id, 'Go/No-Go Decision',
            field='go_nogo_decision',
            new_val=decision,
            changed_by=signed_by,
            reason=notes or f"Decision: {decision}"
        )

        decision_text = {
            'go': 'GO - Approved for launch',
            'conditional_go': 'CONDITIONAL GO - Approved with conditions',
            'no_go': 'NO-GO - Launch blocked'
        }

        return (True, decision_text.get(decision, decision))


# ============================================================================
# CONVENIENCE FUNCTION
# ============================================================================

def get_database(db_path: Optional[str] = None) -> UATDatabase:
    """
    PURPOSE:
        Get a UATDatabase instance with default path.

    USAGE:
        db = get_database()
        cycle = db.get_cycle("UAT-NCCN-12345678")
    """
    return UATDatabase(db_path)
