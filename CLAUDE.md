# UAT Toolkit

## Project Purpose
This toolkit manages UAT (User Acceptance Testing) execution cycles, including test assignment, progress tracking, and compliance documentation.

**Relationship to Other Toolkits:**
- **Requirements Toolkit** generates test cases → UAT Toolkit manages their execution
- Uses Requirements DB via symlink (NOT the Config DB)
- Does NOT generate test cases - only manages execution of existing tests

## Owner Context
- Solo developer (no separate front-end/back-end team)
- Familiar with R, learning Python — explain Python concepts with R comparisons
- Aviation background — aviation analogies work well (retired Marine Cobra pilot)
- Prefers detailed explanations with heavy inline comments

## Code Standards

```python
def example_function(param: str, optional: str = None) -> dict:
    """
    PURPOSE:
        What this function does

    R EQUIVALENT:
        Comparable R function/approach (when applicable)

    PARAMETERS:
        param (str): Description with example
        optional (str): Optional param with default

    RETURNS:
        dict: Description with example structure

    WHY THIS APPROACH:
        Reasoning behind implementation choices
    """
    # Heavy inline comments explaining WHY, not just WHAT
    pass
```

**Key Standards:**
- Use type hints for function signatures
- Prefer explicit over clever — readability beats brevity
- Every change logged to audit_history for FDA 21 CFR Part 11 compliance
- Aviation analogies work well for complex concepts
- Column naming: `created_date`/`updated_date` (NOT `created_at`/`updated_at`)
- Heavy inline comments in all code

## File Organization
```
inputs/          → Drop UAT package Excel files here
outputs/         → Generated reports land here
config/          → UAT settings
database/        → Database operations
importers/       → Excel import modules
reporters/       → Progress reports and exports
data/            → Symlink to shared database
```

## Key Commands
- `python run.py create-cycle` — Create new UAT cycle
- `python run.py import-nccn` — Import NCCN profiles from Excel
- `python run.py status` — Show cycle progress
- `python run.py export` — Export results to Excel

## Two UAT Types

### Feature UAT
Tests user workflows across three personas:
- provider_screening — Review patients, send invites
- patient — Complete assessment, opt-out flows
- provider_dashboard — Review results, clinical summary

Test types: happy_path, negative, validation, edge_case

### NCCN Rule Validation
Tests rule engine trigger logic:
- POS (positive) — Scenario SHOULD trigger the rule
- NEG (negative) — Scenario should NOT trigger the rule
- DEP (deprecated) — Rule was removed, verify it no longer appears

Platforms: P4M (Prevention4ME), Px4M (Precision4ME)

## Database Architecture

### Unified Database Design
All Propel Health toolkits share a **single unified database**:

| Location | Purpose |
|----------|---------|
| `~/projects/data/client_product_database.db` | Requirements, configurations, UAT, access management |

This toolkit accesses the database via **symlink**:
```
~/projects/uat_toolkit/data/client_product_database.db → ~/projects/data/client_product_database.db
```

**Why unified?**
- Programs are the central entity connecting requirements AND configurations
- UAT tests software requirements (user stories) and tracks execution
- All data shares a single audit trail for compliance

### Tables Owned by This Toolkit
- `uat_cycles` — UAT cycle definitions (planning, testing, decision)
- `pre_uat_gate_items` — Pre-flight checklist items

### Tables Extended by This Toolkit
- `uat_test_cases` — Adds: uat_cycle_id, assigned_to, persona, NCCN fields, retest tracking, dev_status

### Tables Read from Requirements Toolkit
- `programs`, `clients` — Software programs being tested
- `user_stories` — Stories that generated the test cases
- `audit_history` — Shared audit trail

### Tables Available (configurations_toolkit manages)
- `clinics`, `locations` — Clinic hierarchy (for clinic-based programs)
- `config_values` — Program/clinic configurations
- `users`, `user_access` — Access management

## Do NOT
- Generate test cases (that's requirements_toolkit's job)
- Modify program or client records
- Skip audit logging
