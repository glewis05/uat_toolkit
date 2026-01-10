-- ============================================================================
-- UAT TOOLKIT SCHEMA
-- ============================================================================
-- PURPOSE: Documents UAT-specific tables and extensions to the shared database.
--
-- IMPORTANT: These tables ALREADY EXIST in the shared database!
-- This file serves as DOCUMENTATION and uses IF NOT EXISTS for safety.
-- The tables were created by requirements_toolkit during initial setup.
--
-- SHARED DATABASE: client_product_database.db
-- Located at: ~/projects/requirements_toolkit/data/client_product_database.db
--
-- AVIATION ANALOGY:
--   Think of the shared database as your squadron's master operations log.
--   Each toolkit (Configuration, Requirements, UAT) is like a different
--   department (Maintenance, Operations, Safety) - all accessing the same
--   aircraft records but focusing on different aspects.
--
--   Requirements Toolkit = Mission Planning (define objectives, create flight plans)
--   UAT Toolkit = Mission Execution (preflight checklist, launch authority, tracking)
-- ============================================================================


-- ============================================================================
-- UAT CYCLES TABLE
-- ============================================================================
-- Tracks UAT packages/releases with phase dates and gate sign-offs.
-- Each cycle groups test cases for a specific release validation.
--
-- AVIATION ANALOGY:
--   This is your mission package - defines the objectives, timeline,
--   checkpoints, and go/no-go criteria for a specific deployment.
--   The Pre-UAT Gate is your preflight checklist - must pass before wheels up.
--
-- STATUS WORKFLOW:
--   planning → validation → kickoff → testing → review → retesting → decision → complete
--                                                                           ↘ cancelled

CREATE TABLE IF NOT EXISTS uat_cycles (
    cycle_id TEXT PRIMARY KEY,      -- UUID format: UAT-{PREFIX}-{8chars}
    program_id TEXT,                -- Optional - can be cross-program (e.g., NCCN)
    name TEXT NOT NULL,             -- "NCCN Q4 2025", "GenoRx e-Consent v1"
    description TEXT,
    uat_type TEXT NOT NULL,         -- 'feature', 'rule_validation', 'regression'
    target_launch_date DATE,
    status TEXT DEFAULT 'planning',
    -- Status values: planning, validation, kickoff, testing, review,
    --                retesting, decision, complete, cancelled

    -- Ownership
    clinical_pm TEXT,               -- Who owns validation
    clinical_pm_email TEXT,

    -- Phase dates (all nullable, filled as phases progress)
    -- AVIATION: Think of these as your mission timeline checkpoints
    validation_start DATE,          -- Pre-UAT validation begins
    validation_end DATE,            -- Gate sign-off target
    kickoff_date DATE,              -- Kickoff meeting
    testing_start DATE,             -- Testing window opens
    testing_end DATE,               -- Testing window closes
    review_date DATE,               -- Issue review meeting
    retest_start DATE,              -- Retesting begins
    retest_end DATE,                -- Retesting ends
    go_nogo_date DATE,              -- Decision meeting

    -- Pre-UAT Gate (must pass before engaging testers)
    -- AVIATION: Your preflight checklist - no takeoff without sign-off
    pre_uat_gate_passed INTEGER DEFAULT 0,  -- Boolean: 0 or 1
    pre_uat_gate_signed_by TEXT,
    pre_uat_gate_signed_date DATE,
    pre_uat_gate_notes TEXT,

    -- Go/No-Go Decision
    -- AVIATION: Launch authority - final approval to proceed to production
    go_nogo_decision TEXT,          -- 'go', 'conditional_go', 'no_go', NULL
    go_nogo_signed_by TEXT,
    go_nogo_signed_date DATE,
    go_nogo_notes TEXT,

    -- Timestamps (NOTE: using created_date/updated_date convention)
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT DEFAULT 'system',

    FOREIGN KEY (program_id) REFERENCES programs(program_id)
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_uat_cycles_program ON uat_cycles(program_id);
CREATE INDEX IF NOT EXISTS idx_uat_cycles_status ON uat_cycles(status);
CREATE INDEX IF NOT EXISTS idx_uat_cycles_launch ON uat_cycles(target_launch_date);
CREATE INDEX IF NOT EXISTS idx_uat_cycles_type ON uat_cycles(uat_type);


-- ============================================================================
-- PRE-UAT GATE ITEMS TABLE
-- ============================================================================
-- Tracks individual validation checklist items for the Pre-UAT Gate.
-- Required for Part 11 compliance - documents who verified what and when.
--
-- AVIATION ANALOGY:
--   This is your preflight checklist broken into individual items.
--   Each item must be verified and signed off before the mission can proceed.
--   Just like checking fuel, oil, flight controls - each has a checkbox.

CREATE TABLE IF NOT EXISTS pre_uat_gate_items (
    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id TEXT NOT NULL,
    category TEXT NOT NULL,
    -- Categories:
    --   'feature_deployment' - Is the code deployed to QA?
    --   'critical_path' - Are core flows working?
    --   'environment' - Is the test environment stable?
    --   'blocker_check' - Any blocking defects?
    --   'sign_off' - Management approval
    sequence INTEGER DEFAULT 0,     -- Order within category
    item_text TEXT NOT NULL,        -- What to verify
    is_required INTEGER DEFAULT 1,  -- Boolean: 1 = must pass for gate
    is_complete INTEGER DEFAULT 0,  -- Boolean: 1 = verified
    completed_by TEXT,              -- Who verified
    completed_date DATE,            -- When verified
    notes TEXT,                     -- Verification notes
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (cycle_id) REFERENCES uat_cycles(cycle_id)
);

CREATE INDEX IF NOT EXISTS idx_gate_items_cycle ON pre_uat_gate_items(cycle_id);
CREATE INDEX IF NOT EXISTS idx_gate_items_category ON pre_uat_gate_items(category);


-- ============================================================================
-- UAT TEST CASES EXTENSIONS
-- ============================================================================
-- The uat_test_cases table is created by requirements_toolkit.
-- These ALTER statements add UAT execution columns.
-- Safe to run multiple times - SQLite silently ignores duplicate columns.
--
-- NOTE: These columns have ALREADY been added to the shared database.
-- This section documents what was added for reference.

-- UAT Cycle association
-- Links test cases to a specific UAT cycle for execution tracking
-- ALTER TABLE uat_test_cases ADD COLUMN uat_cycle_id TEXT;

-- Tester assignment
-- AVIATION: Like assigning a specific pilot to a specific mission
-- ALTER TABLE uat_test_cases ADD COLUMN assigned_to TEXT;
-- ALTER TABLE uat_test_cases ADD COLUMN assignment_type TEXT;
-- assignment_type values: 'primary', 'secondary', 'cross_check'

-- Feature UAT: Persona-based testing
-- Different user types test different aspects of the feature
-- ALTER TABLE uat_test_cases ADD COLUMN persona TEXT;
-- persona values: 'provider_screening', 'patient', 'provider_dashboard', NULL

-- NCCN Rule Validation fields (nullable for feature tests)
-- These track the specific rule validation parameters
-- ALTER TABLE uat_test_cases ADD COLUMN profile_id TEXT;        -- TP-PROS007-POS-01-P4M
-- ALTER TABLE uat_test_cases ADD COLUMN platform TEXT;          -- 'P4M', 'Px4M'
-- ALTER TABLE uat_test_cases ADD COLUMN change_id TEXT;         -- 25Q4R-01 format
-- ALTER TABLE uat_test_cases ADD COLUMN target_rule TEXT;       -- NCCN-PROS-007
-- ALTER TABLE uat_test_cases ADD COLUMN change_type TEXT;       -- 'NEW', 'MODIFIED', 'DEPRECATED'
-- ALTER TABLE uat_test_cases ADD COLUMN patient_conditions TEXT;
-- ALTER TABLE uat_test_cases ADD COLUMN cross_trigger_check TEXT;

-- Retest tracking
-- Keeps initial test separate from retest for audit trail
-- ALTER TABLE uat_test_cases ADD COLUMN retest_status TEXT;
-- ALTER TABLE uat_test_cases ADD COLUMN retest_date TIMESTAMP;
-- ALTER TABLE uat_test_cases ADD COLUMN retest_by TEXT;
-- ALTER TABLE uat_test_cases ADD COLUMN retest_notes TEXT;

-- Developer feedback
-- Tracks dev response to failed tests
-- ALTER TABLE uat_test_cases ADD COLUMN dev_notes TEXT;
-- ALTER TABLE uat_test_cases ADD COLUMN dev_status TEXT;
-- dev_status values: 'pending', 'investigating', 'fixed', 'wont_fix', 'not_a_bug'

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_tests_cycle ON uat_test_cases(uat_cycle_id);
CREATE INDEX IF NOT EXISTS idx_tests_platform ON uat_test_cases(platform);
CREATE INDEX IF NOT EXISTS idx_tests_assigned ON uat_test_cases(assigned_to);
CREATE INDEX IF NOT EXISTS idx_tests_change ON uat_test_cases(change_id);
CREATE INDEX IF NOT EXISTS idx_tests_persona ON uat_test_cases(persona);


-- ============================================================================
-- VIEWS
-- ============================================================================
-- Pre-built views for common reporting needs.
-- These aggregate test data for dashboards and exports.

-- UAT CYCLE SUMMARY VIEW
-- Provides at-a-glance metrics for each cycle
-- AVIATION: Like a mission status board showing completion percentage
CREATE VIEW IF NOT EXISTS v_uat_cycle_summary AS
SELECT
    c.cycle_id,
    c.name,
    c.uat_type,
    c.status,
    c.target_launch_date,
    c.clinical_pm,
    c.pre_uat_gate_passed,
    c.go_nogo_decision,
    p.prefix AS program_prefix,
    p.name AS program_name,
    COUNT(t.test_id) AS total_tests,
    SUM(CASE WHEN t.test_status = 'Pass' THEN 1 ELSE 0 END) AS passed,
    SUM(CASE WHEN t.test_status = 'Fail' THEN 1 ELSE 0 END) AS failed,
    SUM(CASE WHEN t.test_status = 'Blocked' THEN 1 ELSE 0 END) AS blocked,
    SUM(CASE WHEN t.test_status = 'Skipped' THEN 1 ELSE 0 END) AS skipped,
    SUM(CASE WHEN t.test_status = 'Not Run' THEN 1 ELSE 0 END) AS not_run,
    ROUND(100.0 * SUM(CASE WHEN t.test_status != 'Not Run' THEN 1 ELSE 0 END)
          / NULLIF(COUNT(t.test_id), 0), 1) AS execution_pct,
    ROUND(100.0 * SUM(CASE WHEN t.test_status = 'Pass' THEN 1 ELSE 0 END)
          / NULLIF(SUM(CASE WHEN t.test_status IN ('Pass', 'Fail') THEN 1 ELSE 0 END), 0), 1) AS pass_rate,
    CAST(julianday(c.target_launch_date) - julianday('now') AS INTEGER) AS days_to_launch
FROM uat_cycles c
LEFT JOIN programs p ON c.program_id = p.program_id
LEFT JOIN uat_test_cases t ON c.cycle_id = t.uat_cycle_id
GROUP BY c.cycle_id;


-- UAT TESTER PROGRESS VIEW
-- Tracks individual tester completion rates
-- AVIATION: Like tracking each pilot's mission completion status
CREATE VIEW IF NOT EXISTS v_uat_tester_progress AS
SELECT
    c.cycle_id,
    c.name AS cycle_name,
    t.assigned_to,
    t.assignment_type,
    COUNT(t.test_id) AS total_tests,
    SUM(CASE WHEN t.test_status != 'Not Run' THEN 1 ELSE 0 END) AS completed,
    SUM(CASE WHEN t.test_status = 'Pass' THEN 1 ELSE 0 END) AS passed,
    SUM(CASE WHEN t.test_status = 'Fail' THEN 1 ELSE 0 END) AS failed,
    SUM(CASE WHEN t.test_status = 'Blocked' THEN 1 ELSE 0 END) AS blocked,
    SUM(CASE WHEN t.test_status = 'Not Run' THEN 1 ELSE 0 END) AS not_run,
    ROUND(100.0 * SUM(CASE WHEN t.test_status != 'Not Run' THEN 1 ELSE 0 END)
          / NULLIF(COUNT(t.test_id), 0), 1) AS completion_pct
FROM uat_cycles c
JOIN uat_test_cases t ON c.cycle_id = t.uat_cycle_id
WHERE t.assigned_to IS NOT NULL
GROUP BY c.cycle_id, t.assigned_to, t.assignment_type;


-- NCCN RULE COVERAGE VIEW
-- Tracks test coverage by NCCN rule and change
-- Specific to rule_validation UAT type
CREATE VIEW IF NOT EXISTS v_nccn_rule_coverage AS
SELECT
    c.cycle_id,
    c.name AS cycle_name,
    t.change_id,
    t.target_rule,
    t.change_type,
    t.platform,
    COUNT(t.test_id) AS total_profiles,
    SUM(CASE WHEN t.test_type = 'positive' THEN 1 ELSE 0 END) AS pos_tests,
    SUM(CASE WHEN t.test_type = 'negative' THEN 1 ELSE 0 END) AS neg_tests,
    SUM(CASE WHEN t.test_type = 'deprecated' THEN 1 ELSE 0 END) AS dep_tests,
    SUM(CASE WHEN t.test_status = 'Pass' THEN 1 ELSE 0 END) AS passed,
    SUM(CASE WHEN t.test_status = 'Fail' THEN 1 ELSE 0 END) AS failed,
    SUM(CASE WHEN t.test_status = 'Not Run' THEN 1 ELSE 0 END) AS not_run
FROM uat_cycles c
JOIN uat_test_cases t ON c.cycle_id = t.uat_cycle_id
WHERE t.change_id IS NOT NULL
GROUP BY c.cycle_id, t.change_id, t.target_rule, t.change_type, t.platform;


-- RETEST QUEUE VIEW
-- Shows all failed tests that need retesting
-- AVIATION: Like a squawk list - known issues requiring follow-up
CREATE VIEW IF NOT EXISTS v_retest_queue AS
SELECT
    c.cycle_id,
    c.name AS cycle_name,
    t.test_id,
    t.profile_id,
    t.title,
    t.platform,
    t.target_rule,
    t.assigned_to,
    t.test_status AS initial_status,
    t.tested_by AS initial_tester,
    t.tested_date AS initial_test_date,
    t.execution_notes,
    t.defect_id,
    t.dev_status,
    t.dev_notes,
    t.retest_status,
    t.retest_by,
    t.retest_date
FROM uat_cycles c
JOIN uat_test_cases t ON c.cycle_id = t.uat_cycle_id
WHERE t.test_status = 'Fail'
ORDER BY c.cycle_id, t.dev_status, t.test_id;


-- ============================================================================
-- DEFAULT GATE ITEMS
-- ============================================================================
-- Template for pre-UAT gate items by UAT type.
-- Used by create_uat_cycle() to populate initial checklist.

-- FEATURE UAT GATE ITEMS:
-- 1. feature_deployment: Feature deployed to QA environment
-- 2. feature_deployment: Feature flags configured correctly
-- 3. critical_path: Core happy path verified
-- 4. environment: QA environment stable and accessible
-- 5. blocker_check: No critical defects blocking feature
-- 6. sign_off: Product Owner approval for test start

-- RULE_VALIDATION UAT GATE ITEMS:
-- 1. feature_deployment: NCCN rules deployed to QA environment
-- 2. feature_deployment: All rule IDs verified in system
-- 3. critical_path: Patient registration flow tested
-- 4. critical_path: Test profiles created and validated
-- 5. environment: QA environment stable and accessible
-- 6. blocker_check: No critical defects in backlog
-- 7. sign_off: Clinical PM approval for test start

-- REGRESSION UAT GATE ITEMS:
-- 1. feature_deployment: Release candidate deployed to QA
-- 2. critical_path: Smoke tests passing
-- 3. environment: QA environment mirrors production
-- 4. blocker_check: No P0/P1 defects open
-- 5. sign_off: Release Manager approval
