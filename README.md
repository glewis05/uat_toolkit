# UAT Toolkit

Python toolkit for managing UAT execution cycles, test assignment, progress tracking, and compliance documentation.

## Overview

This toolkit:
- Manages UAT (User Acceptance Testing) execution cycles
- Tracks test assignment and progress
- Supports both Feature UAT and NCCN Rule Validation testing
- Generates compliance documentation for FDA 21 CFR Part 11
- Imports test results from various sources (Excel, Notion)

**Note:** This toolkit manages test *execution* — it does not generate test cases. Test cases come from the [requirements_toolkit](https://github.com/glewis05/requirements_toolkit).

## Installation

```bash
# Clone the repository
git clone https://github.com/glewis05/uat_toolkit.git
cd uat_toolkit

# Install dependencies
pip install -r requirements.txt

# Set up database symlink (connects to unified Propel Health database)
ln -s ~/projects/data/client_product_database.db data/client_product_database.db
```

## Quick Start

```bash
# Create a new UAT cycle
python run.py create-cycle --program P4M --name "Q1 2026 Release" --type feature

# Import NCCN profiles from Excel
python run.py import-nccn --file "nccn_profiles.xlsx"

# Show cycle progress
python run.py status --cycle-id 1

# Export results to Excel
python run.py export --cycle-id 1 --output "uat_results.xlsx"
```

## Project Structure

```
uat_toolkit/
├── run.py                  # CLI entry point
├── CLAUDE.md               # AI assistant context
├── database/               # Database operations
│   ├── schema.sql          # UAT-specific tables
│   └── uat_manager.py      # CRUD operations
├── importers/              # Data import modules
│   ├── excel_importer.py   # Import from Excel
│   └── notion_importer.py  # Import from Notion exports
├── reporters/              # Progress reports
│   └── cycle_reporter.py   # Cycle status and metrics
├── config/                 # Configuration files
├── scripts/                # Utility scripts
├── templates/              # Report templates
├── inputs/                 # Drop files to import
├── outputs/                # Generated reports
└── data/                   # Database (symlink to unified DB)
```

## UAT Types

### Feature UAT
Tests user workflows across three personas:
- `provider_screening` — Review patients, send invites
- `patient` — Complete assessment, opt-out flows
- `provider_dashboard` — Review results, clinical summary

Test types: `happy_path`, `negative`, `validation`, `edge_case`

### NCCN Rule Validation
Tests rule engine trigger logic:
- `POS` (positive) — Scenario SHOULD trigger the rule
- `NEG` (negative) — Scenario should NOT trigger the rule
- `DEP` (deprecated) — Rule was removed, verify it no longer appears

Platforms: P4M (Prevention4ME), Px4M (Precision4ME)

## Database Architecture

Part of the unified Propel Health database ecosystem:

| Location | Purpose |
|----------|---------|
| `~/projects/data/client_product_database.db` | Shared database for all toolkits |

### Tables Owned by This Toolkit
- `uat_cycles` — UAT cycle definitions (planning, testing, decision)
- `pre_uat_gate_items` — Pre-flight checklist items

### Tables Extended by This Toolkit
- `uat_test_cases` — Adds: uat_cycle_id, assigned_to, persona, NCCN fields, retest tracking

### Tables Read from Requirements Toolkit
- `programs`, `clients` — Software programs being tested
- `user_stories` — Stories that generated the test cases
- `audit_history` — Shared audit trail

## CLI Commands

| Command | Description |
|---------|-------------|
| `create-cycle` | Create new UAT cycle |
| `import-nccn` | Import NCCN profiles from Excel |
| `import-results` | Import test execution results |
| `status` | Show cycle progress |
| `assign` | Assign tests to testers |
| `export` | Export results to Excel |
| `report` | Generate compliance report |

## Related Projects

- **[requirements_toolkit](https://github.com/glewis05/requirements_toolkit)** - Generates test cases
- **[configurations_toolkit](https://github.com/glewis05/configurations_toolkit)** - Manages clinic configurations
- **[propel_mcp](https://github.com/glewis05/propel_mcp)** - MCP server connecting all toolkits

## License

Proprietary - Propel Health
