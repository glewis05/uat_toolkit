# Formspree Setup for UAT Trackers

## Quick Setup

1. Create account at https://formspree.io (free tier: 50 submissions/month)
2. Create new form, name it for the UAT cycle
3. Copy form ID (e.g., `xyzabc123`)
4. Add to tracker: `formspree_id: 'xyzabc123'`

## Current Configuration

| Tracker | Form ID | Status |
|---------|---------|--------|
| ONB Questionnaire v1 | `mqeekjjz` | Active |

## Email Format

When a tester submits, you'll receive an email with:

**Subject:** UAT Results: [UAT Name] - [Tester Name]

**Body (JSON):**
```json
{
  "tester": "Glen Lewis",
  "submitted_at": "2025-05-01T14:30:00.000Z",
  "summary": {
    "total": 66,
    "executed": 60,
    "passed": 55,
    "failed": 3,
    "blocked": 1,
    "skipped": 1
  },
  "results": [
    {
      "test_id": "ONB-STEP-001-TC01",
      "title": "Verify program options display correctly",
      "section": "P4M",
      "status": "Pass",
      "notes": ""
    },
    {
      "test_id": "ONB-FORM-003-TC02",
      "title": "Verify required field prevents navigation when empty",
      "section": "P4M",
      "status": "Fail",
      "notes": "Error message not displaying correctly"
    }
  ]
}
```

## Importing Results to Database

After receiving email, save the JSON attachment and use:

```bash
python importers/import_uat_results.py path/to/results.json
```

This will:
- Update test_status for each test in the database
- Record the tester name and timestamp
- Append any notes to execution_notes
- Log the import to audit_history

## Free Tier Limits

Formspree free tier includes:
- 50 submissions/month
- 1 email recipient
- JSON data supported
- No file attachments

This is sufficient for UAT where you have a few testers submitting results periodically.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Form not found" | Check form ID is correct in UAT_CONFIG |
| "Rate limited" | Wait or upgrade Formspree plan |
| No email received | Check spam folder, verify Formspree account |
| CORS error | Formspree handles CORS automatically |
| Submit button missing | Verify formspree_id is set (not null) |

## Multiple Testers

For multiple testers:

- **Option A:** Each tester submits separately, you receive separate emails
- **Option B:** Create one Formspree form per tester for tracking
- **Option C:** Testers use Export JSON, email manually, you import

## Adding Formspree to New Trackers

1. Create a new form at Formspree for the UAT cycle
2. Copy the form ID
3. Update the tracker's UAT_CONFIG:

```javascript
const UAT_CONFIG = {
  id: 'your-uat-id',
  name: 'Your UAT Name',
  target_date: '2025-XX-XX',
  tester_default: '',
  formspree_id: 'YOUR_NEW_FORM_ID',  // Add here
  localStorage_key: 'your_uat_tracker'
};
```

## Security Notes

- Formspree form IDs are public (in the HTML source)
- Anyone with the form ID could submit, but they'd need to match the expected JSON structure
- For sensitive UATs, consider using Export JSON + manual email instead
- Results don't contain PHI/PII - only test IDs, statuses, and tester notes
