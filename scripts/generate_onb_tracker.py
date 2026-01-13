#!/usr/bin/env python3
"""
PURPOSE:
    Generate the ONB tracker HTML file from exported JSON data.

    Converts the workflow-based JSON export to a complete HTML tracker
    with embedded JavaScript test data and context hints.

R EQUIVALENT:
    Similar to using jsonlite::fromJSON() then glue::glue() for templating.

WHY THIS APPROACH:
    Keeps test data synchronized between database and tracker.
    Context hints help non-technical testers know when to check each test.
"""

import json
from pathlib import Path


def generate_context_hint(test: dict) -> str:
    """
    PURPOSE:
        Generate a contextual hint for each test case based on its content.

    PARAMETERS:
        test (dict): Test case data with title, steps, etc.

    RETURNS:
        str: A brief contextual hint for the tester
    """
    title = test.get('title', '').lower()
    test_id = test.get('test_id', '')
    steps = test.get('test_steps', '').lower()

    # Generate hints based on test content
    if 'program' in title and 'selection' in title:
        return "Check this when you first open the form"
    elif 'clinic' in title and ('phone' in title or 'information' in title):
        return "While filling out Step 2 - Clinic Information"
    elif 'helpdesk' in title or 'helpline' in title:
        return "Look for the patient helpline checkbox in Clinic Info"
    elif 'email' in title:
        return "When entering any email field"
    elif 'zip' in title:
        return "When entering address ZIP codes"
    elif 'phone' in title and 'format' in title:
        return "When entering phone numbers"
    elif 'npi' in title:
        return "When entering provider NPI numbers"
    elif 'required field' in title:
        return "Check asterisks and validation errors on form fields"
    elif 'repeatable' in title or 'add button' in title:
        return "When adding multiple items (locations, providers, etc.)"
    elif 'composite' in title or 'address' in title:
        return "Check grouped field sections (address, contact info)"
    elif 'genetic counselor' in title:
        return "In Step 4 - Contacts section"
    elif 'champion' in title or 'stakeholder' in title:
        return "In Step 5 - Key Stakeholders"
    elif 'lab' in title:
        return "In Step 6 - Lab Configuration"
    elif 'test product' in title:
        return "In Step 7 - Test Products"
    elif 'provider' in title and ('entry' in title or 'npi' in title):
        return "In Step 8 - Ordering Providers"
    elif 'filter' in title:
        return "In Step 9 - Extract Filtering"
    elif 'review' in title:
        return "On the final Review step"
    elif 'word' in title or 'document' in title:
        return "Test the Word document download on Review step"
    elif 'json' in title and 'export' in title:
        return "Test the JSON export on Review step"
    elif 'progress' in title:
        return "Watch the progress indicator as you navigate"
    elif 'navigation' in title or 'previous' in title or 'next' in title:
        return "Test the Previous/Next buttons throughout the form"
    elif 'branding' in title:
        return "Check visual consistency on every step"
    elif 'gene selector' in title or 'gene' in title:
        return "Select CustomNext-Cancer in Test Products to see gene selector"
    elif 'auto-save' in title:
        return "Wait a moment after entering data and check the status bar"
    elif 'resume' in title or 'restore' in title:
        return "Close and reopen the form to test resume"
    elif 'save draft' in title or 'download' in title:
        return "Click Save Draft button in the status bar"
    elif 'load draft' in title:
        return "Click Load Draft button in the status bar"
    elif 'clear' in title or 'start over' in title:
        return "Click Start Over button in the status bar"
    elif 'help' in title:
        return "Click the (?) help icon in the status bar"
    else:
        return ""


def generate_tracker_html(json_path: str, output_path: str):
    """
    PURPOSE:
        Generate the complete ONB tracker HTML from JSON data.

    PARAMETERS:
        json_path (str): Path to the workflow JSON export
        output_path (str): Path for the output HTML file
    """
    # Load the JSON data
    with open(json_path, 'r') as f:
        data = json.load(f)

    # Build workflow sections JavaScript
    sections_js = []
    for section in data['sections']:
        sections_js.append(f"""      {{
        code: '{section["code"]}',
        name: '{section["name"]}',
        description: '{section["description"]}',
        guidance: '{section["guidance"]}',
        icon: '{get_section_icon(section["code"])}'
      }}""")

    # Add PR4M section (no tests yet, but in the reference table)
    sections_js.insert(1, """      {
        code: 'PR4M',
        name: 'Precision4ME Walkthrough',
        description: 'Test program-specific differences',
        guidance: 'Clear the form and start fresh with Precision4ME selected. Watch for fields that appear or disappear. Verify the same validations still work.',
        icon: '🔬'
      }""")

    workflow_sections_js = "const WORKFLOW_SECTIONS = [\n" + ",\n".join(sections_js) + "\n    ];"

    # Build test cases JavaScript
    tests_js = []
    for section in data['sections']:
        section_code = section['code']
        for test in section['tests']:
            context_hint = generate_context_hint(test)
            # Escape single quotes in strings
            title = test['title'].replace("'", "\\'")
            steps = test['test_steps'].replace("'", "\\'").replace('\n', '\\n')
            expected = test['expected_results'].replace("'", "\\'").replace('\n', '\\n')
            hint = context_hint.replace("'", "\\'")

            tests_js.append(f"""      {{
        test_id: '{test["test_id"]}',
        title: '{title}',
        workflow_section: '{section_code}',
        workflow_order: {test["workflow_order"]},
        test_type: '{test["test_type"]}',
        test_steps: '{steps}',
        expected_results: '{expected}',
        context_hint: '{hint}',
        priority: '{test.get("priority", "Should Have")}'
      }}""")

    test_cases_js = "const TEST_CASES_DATA = [\n" + ",\n".join(tests_js) + "\n    ];"

    # Generate the full HTML
    html_content = generate_html_template(workflow_sections_js, test_cases_js)

    # Write output
    with open(output_path, 'w') as f:
        f.write(html_content)

    print(f"Generated: {output_path}")
    print(f"Sections: {len(data['sections']) + 1} (including PR4M)")
    print(f"Tests: {data['total_tests']}")


def get_section_icon(code: str) -> str:
    """Return emoji icon for section code."""
    icons = {
        'P4M': '🩺',
        'PR4M': '🔬',
        'GRX': '🧬',
        'DRAFT': '💾',
        'EDGE': '🔍'
    }
    return icons.get(code, '📋')


def generate_html_template(workflow_sections_js: str, test_cases_js: str) -> str:
    """Generate the complete HTML template with embedded data."""
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ONB Questionnaire v1 - UAT Tracker</title>
    <script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
    <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
    <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50">
    <div id="root"></div>

    <script type="text/babel">
    const {{ useState, useEffect }} = React;

    // =====================================================
    // CONFIGURATION - ONB Questionnaire v1
    // =====================================================
    const UAT_CONFIG = {{
      id: 'onb-v1',
      name: 'ONB Questionnaire v1',
      target_date: '2025-05-02',
      tester_default: 'Glen Lewis',
      formspree_id: null,  // Add your Formspree ID to enable email submission
      localStorage_key: 'onb_uat_tracker'
    }};

    // =====================================================
    // WORKFLOW SECTIONS - Guided Testing Flow
    // =====================================================
    {workflow_sections_js}

    // =====================================================
    // TEST CASES DATA - 66 Tests Organized by Workflow
    // =====================================================
    {test_cases_js}

    // =====================================================
    // COMPONENT: Section Header with Guidance
    // =====================================================
    const SectionHeader = ({{ section, tests, isExpanded, onToggle }}) => {{
      const sectionTests = tests.filter(t => t.workflow_section === section.code);
      const completed = sectionTests.filter(t => t.test_status !== 'Not Run').length;
      const passed = sectionTests.filter(t => t.test_status === 'Pass').length;
      const failed = sectionTests.filter(t => t.test_status === 'Fail').length;
      const total = sectionTests.length;
      const pct = total > 0 ? Math.round((completed / total) * 100) : 0;

      // Don't render sections with no tests
      if (total === 0) return null;

      return (
        <div className="bg-white rounded-lg shadow mb-4">
          <button
            onClick={{onToggle}}
            className="w-full p-4 text-left flex items-center justify-between hover:bg-gray-50"
          >
            <div className="flex items-center gap-3">
              <span className="text-2xl">{{section.icon}}</span>
              <div>
                <h2 className="text-lg font-semibold text-gray-800">{{section.name}}</h2>
                <p className="text-sm text-gray-500">{{section.description}}</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-right">
                <div className="text-sm font-medium">
                  <span className="text-green-600">{{passed}}✓</span>
                  {{failed > 0 && <span className="text-red-600 ml-2">{{failed}}✗</span>}}
                  <span className="text-gray-400 ml-2">{{completed}}/{{total}}</span>
                </div>
                <div className="w-24 h-2 bg-gray-200 rounded-full mt-1">
                  <div
                    className={{`h-2 rounded-full ${{pct === 100 ? 'bg-green-500' : 'bg-blue-500'}}`}}
                    style={{{{ width: `${{pct}}%` }}}}
                  />
                </div>
              </div>
              <span className={{`transform transition-transform ${{isExpanded ? 'rotate-180' : ''}}`}}>
                ▼
              </span>
            </div>
          </button>

          {{isExpanded && (
            <div className="px-4 pb-4">
              <div className="bg-blue-50 border-l-4 border-blue-400 p-3 mb-4">
                <p className="text-sm text-blue-800 font-medium">How to test this section:</p>
                <p className="text-sm text-blue-700 mt-1">{{section.guidance}}</p>
              </div>
            </div>
          )}}
        </div>
      );
    }};

    // =====================================================
    // COMPONENT: Test Case Row
    // =====================================================
    const TestCaseRow = ({{ test, notes, onStatusChange, onNotesChange }}) => {{
      const [expanded, setExpanded] = useState(false);

      const typeColors = {{
        'happy_path': 'bg-green-100 text-green-700',
        'negative': 'bg-red-100 text-red-700',
        'validation': 'bg-blue-100 text-blue-700',
        'edge_case': 'bg-purple-100 text-purple-700'
      }};

      return (
        <div className={{`border rounded-lg mb-2 ${{test.test_status === 'Fail' ? 'border-red-300' : 'border-gray-200'}}`}}>
          <div className="p-3 flex items-center gap-3">
            {{/* Status indicator */}}
            <div className={{`w-3 h-3 rounded-full ${{
              test.test_status === 'Pass' ? 'bg-green-500' :
              test.test_status === 'Fail' ? 'bg-red-500' :
              test.test_status === 'Blocked' ? 'bg-amber-500' :
              test.test_status === 'Skipped' ? 'bg-blue-500' : 'bg-gray-300'
            }}`}} />

            {{/* Test info */}}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <code className="text-xs text-gray-500">{{test.test_id}}</code>
                <span className={{`text-xs px-2 py-0.5 rounded ${{typeColors[test.test_type] || 'bg-gray-100'}}`}}>
                  {{test.test_type.replace('_', ' ')}}
                </span>
              </div>
              <p className="text-sm font-medium text-gray-800 mt-1">{{test.title}}</p>
              {{test.context_hint && (
                <p className="text-xs text-gray-500 italic mt-1">💡 {{test.context_hint}}</p>
              )}}
            </div>

            {{/* Quick action buttons */}}
            <div className="flex gap-1">
              <button
                onClick={{() => onStatusChange(test.test_id, 'Pass')}}
                className={{`w-8 h-8 rounded ${{test.test_status === 'Pass' ? 'bg-green-500 text-white' : 'bg-gray-100 hover:bg-green-100'}}`}}
                title="Pass"
              >✓</button>
              <button
                onClick={{() => onStatusChange(test.test_id, 'Fail')}}
                className={{`w-8 h-8 rounded ${{test.test_status === 'Fail' ? 'bg-red-500 text-white' : 'bg-gray-100 hover:bg-red-100'}}`}}
                title="Fail"
              >✗</button>
              <button
                onClick={{() => onStatusChange(test.test_id, 'Blocked')}}
                className={{`w-8 h-8 rounded ${{test.test_status === 'Blocked' ? 'bg-amber-500 text-white' : 'bg-gray-100 hover:bg-amber-100'}}`}}
                title="Blocked"
              >!</button>
              <button
                onClick={{() => onStatusChange(test.test_id, 'Skipped')}}
                className={{`w-8 h-8 rounded ${{test.test_status === 'Skipped' ? 'bg-blue-500 text-white' : 'bg-gray-100 hover:bg-blue-100'}}`}}
                title="Skip"
              >−</button>
            </div>

            {{/* Expand button */}}
            <button
              onClick={{() => setExpanded(!expanded)}}
              className="text-gray-400 hover:text-gray-600 px-2"
            >
              {{expanded ? '▲' : '▼'}}
            </button>
          </div>

          {{/* Expanded details */}}
          {{expanded && (
            <div className="px-3 pb-3 border-t bg-gray-50">
              <div className="grid md:grid-cols-2 gap-4 mt-3">
                <div>
                  <p className="text-xs font-medium text-gray-500 uppercase mb-1">Test Steps</p>
                  <pre className="text-sm text-gray-700 whitespace-pre-wrap bg-white p-2 rounded border">
                    {{test.test_steps}}
                  </pre>
                </div>
                <div>
                  <p className="text-xs font-medium text-gray-500 uppercase mb-1">Expected Results</p>
                  <pre className="text-sm text-gray-700 whitespace-pre-wrap bg-white p-2 rounded border">
                    {{test.expected_results}}
                  </pre>
                </div>
              </div>
              <div className="mt-3">
                <p className="text-xs font-medium text-gray-500 uppercase mb-1">Your Notes</p>
                <textarea
                  value={{notes[test.test_id] || ''}}
                  onChange={{(e) => onNotesChange(test.test_id, e.target.value)}}
                  placeholder="Add observations, issues found, or questions..."
                  className="w-full p-2 border rounded text-sm"
                  rows={{2}}
                />
              </div>
              {{test.tested_date && (
                <p className="text-xs text-gray-400 mt-2">
                  Tested: {{new Date(test.tested_date).toLocaleString()}}
                </p>
              )}}
            </div>
          )}}
        </div>
      );
    }};

    // =====================================================
    // COMPONENT: Progress Dashboard
    // =====================================================
    const ProgressDashboard = ({{ tests }}) => {{
      const stats = {{
        total: tests.length,
        passed: tests.filter(t => t.test_status === 'Pass').length,
        failed: tests.filter(t => t.test_status === 'Fail').length,
        blocked: tests.filter(t => t.test_status === 'Blocked').length,
        skipped: tests.filter(t => t.test_status === 'Skipped').length,
        notRun: tests.filter(t => t.test_status === 'Not Run').length
      }};
      stats.executed = stats.total - stats.notRun;
      stats.pct = Math.round((stats.executed / stats.total) * 100);

      return (
        <div className="bg-white rounded-lg shadow p-4 mb-6">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm font-medium text-gray-600">Overall Progress</span>
            <span className="text-lg font-bold text-gray-800">{{stats.pct}}%</span>
          </div>

          {{/* Progress bar */}}
          <div className="h-4 bg-gray-200 rounded-full overflow-hidden flex">
            {{stats.passed > 0 && (
              <div className="bg-green-500 h-full" style={{{{ width: `${{(stats.passed/stats.total)*100}}%` }}}} />
            )}}
            {{stats.failed > 0 && (
              <div className="bg-red-500 h-full" style={{{{ width: `${{(stats.failed/stats.total)*100}}%` }}}} />
            )}}
            {{stats.blocked > 0 && (
              <div className="bg-amber-500 h-full" style={{{{ width: `${{(stats.blocked/stats.total)*100}}%` }}}} />
            )}}
            {{stats.skipped > 0 && (
              <div className="bg-blue-500 h-full" style={{{{ width: `${{(stats.skipped/stats.total)*100}}%` }}}} />
            )}}
          </div>

          {{/* Stats */}}
          <div className="flex justify-between mt-3 text-sm">
            <span className="text-green-600">✓ {{stats.passed}} Pass</span>
            <span className="text-red-600">✗ {{stats.failed}} Fail</span>
            <span className="text-amber-600">! {{stats.blocked}} Blocked</span>
            <span className="text-blue-600">− {{stats.skipped}} Skipped</span>
            <span className="text-gray-400">○ {{stats.notRun}} Not Run</span>
          </div>
        </div>
      );
    }};

    // =====================================================
    // MAIN APP COMPONENT
    // =====================================================
    const App = () => {{
      // State
      const [testCases, setTestCases] = useState(() => {{
        const saved = localStorage.getItem(UAT_CONFIG.localStorage_key);
        if (saved) {{
          const parsed = JSON.parse(saved);
          return parsed.testCases || TEST_CASES_DATA.map(t => ({{ ...t, test_status: 'Not Run' }}));
        }}
        return TEST_CASES_DATA.map(t => ({{ ...t, test_status: 'Not Run' }}));
      }});

      const [notes, setNotes] = useState(() => {{
        const saved = localStorage.getItem(UAT_CONFIG.localStorage_key);
        return saved ? JSON.parse(saved).notes || {{}} : {{}};
      }});

      const [testerName, setTesterName] = useState(() => {{
        const saved = localStorage.getItem(UAT_CONFIG.localStorage_key);
        return saved ? JSON.parse(saved).testerName || UAT_CONFIG.tester_default : UAT_CONFIG.tester_default;
      }});

      const [expandedSections, setExpandedSections] = useState(
        WORKFLOW_SECTIONS.reduce((acc, s) => ({{ ...acc, [s.code]: true }}), {{}})
      );

      const [submitting, setSubmitting] = useState(false);
      const [submitted, setSubmitted] = useState(false);

      // Save to localStorage
      useEffect(() => {{
        localStorage.setItem(UAT_CONFIG.localStorage_key, JSON.stringify({{
          testCases, notes, testerName, lastUpdated: new Date().toISOString()
        }}));
      }}, [testCases, notes, testerName]);

      // Handlers
      const handleStatusChange = (testId, status) => {{
        setTestCases(prev => prev.map(t =>
          t.test_id === testId
            ? {{ ...t, test_status: status, tested_date: new Date().toISOString() }}
            : t
        ));
      }};

      const handleNotesChange = (testId, note) => {{
        setNotes(prev => ({{ ...prev, [testId]: note }}));
      }};

      const toggleSection = (code) => {{
        setExpandedSections(prev => ({{ ...prev, [code]: !prev[code] }}));
      }};

      const handleExport = () => {{
        const data = {{
          uat_config: UAT_CONFIG,
          tester: testerName,
          exported_at: new Date().toISOString(),
          summary: {{
            total: testCases.length,
            executed: testCases.filter(t => t.test_status !== 'Not Run').length,
            passed: testCases.filter(t => t.test_status === 'Pass').length,
            failed: testCases.filter(t => t.test_status === 'Fail').length,
            blocked: testCases.filter(t => t.test_status === 'Blocked').length,
            skipped: testCases.filter(t => t.test_status === 'Skipped').length
          }},
          results: testCases.map(t => ({{
            test_id: t.test_id,
            title: t.title,
            workflow_section: t.workflow_section,
            test_status: t.test_status,
            tested_date: t.tested_date,
            notes: notes[t.test_id] || ''
          }}))
        }};

        const blob = new Blob([JSON.stringify(data, null, 2)], {{ type: 'application/json' }});
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${{UAT_CONFIG.id}}_results_${{new Date().toISOString().split('T')[0]}}.json`;
        a.click();
      }};

      const handleSubmit = async () => {{
        if (!UAT_CONFIG.formspree_id) {{
          alert('Email submission not configured. Use Export to download results.');
          return;
        }}
        if (!testerName.trim()) {{
          alert('Please enter your name before submitting.');
          return;
        }}

        const executed = testCases.filter(t => t.test_status !== 'Not Run').length;
        if (executed === 0) {{
          alert('No tests have been executed yet.');
          return;
        }}

        if (!confirm(`Submit ${{executed}} test results as ${{testerName}}?\\n\\nThis will email the results.`)) {{
          return;
        }}

        setSubmitting(true);

        const payload = {{
          _subject: `UAT Results: ${{UAT_CONFIG.name}} - ${{testerName}}`,
          tester: testerName,
          submitted_at: new Date().toISOString(),
          summary: {{
            total: testCases.length,
            executed: executed,
            passed: testCases.filter(t => t.test_status === 'Pass').length,
            failed: testCases.filter(t => t.test_status === 'Fail').length,
            blocked: testCases.filter(t => t.test_status === 'Blocked').length,
            skipped: testCases.filter(t => t.test_status === 'Skipped').length
          }},
          results: testCases.filter(t => t.test_status !== 'Not Run').map(t => ({{
            test_id: t.test_id,
            title: t.title,
            section: t.workflow_section,
            status: t.test_status,
            notes: notes[t.test_id] || ''
          }}))
        }};

        try {{
          const response = await fetch(`https://formspree.io/f/${{UAT_CONFIG.formspree_id}}`, {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify(payload)
          }});

          if (response.ok) {{
            setSubmitted(true);
            alert('Results submitted successfully!');
          }} else {{
            alert('Submission failed. Please use Export instead.');
          }}
        }} catch (error) {{
          alert('Network error. Please use Export instead.');
        }} finally {{
          setSubmitting(false);
        }}
      }};

      const handleReset = () => {{
        if (confirm('Reset all progress? This cannot be undone.')) {{
          setTestCases(TEST_CASES_DATA.map(t => ({{ ...t, test_status: 'Not Run' }})));
          setNotes({{}});
          setSubmitted(false);
        }}
      }};

      return (
        <div className="max-w-4xl mx-auto py-6 px-4">
          {{/* Header */}}
          <div className="bg-white rounded-lg shadow p-4 mb-6">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <a href="index.html" className="text-blue-500 text-sm hover:underline">← Back to UAT List</a>
                <h1 className="text-2xl font-bold text-gray-800">{{UAT_CONFIG.name}}</h1>
                <p className="text-sm text-gray-500">Target: {{UAT_CONFIG.target_date}} | 5 sections | 66 tests</p>
              </div>

              <div className="flex items-center gap-3">
                <input
                  type="text"
                  value={{testerName}}
                  onChange={{(e) => setTesterName(e.target.value)}}
                  placeholder="Your name"
                  className="border rounded px-3 py-2 text-sm w-40"
                />
                <button onClick={{handleExport}} className="bg-gray-600 text-white px-3 py-2 rounded text-sm hover:bg-gray-700">
                  Export
                </button>
                {{UAT_CONFIG.formspree_id && (
                  <button
                    onClick={{handleSubmit}}
                    disabled={{submitting || submitted}}
                    className={{`px-3 py-2 rounded text-sm ${{
                      submitted ? 'bg-green-100 text-green-700' :
                      submitting ? 'bg-gray-300' : 'bg-green-600 text-white hover:bg-green-700'
                    }}`}}
                  >
                    {{submitted ? '✓ Submitted' : submitting ? 'Sending...' : 'Submit'}}
                  </button>
                )}}
                <button onClick={{handleReset}} className="text-red-500 text-sm hover:underline">
                  Reset
                </button>
              </div>
            </div>
          </div>

          {{/* Progress Dashboard */}}
          <ProgressDashboard tests={{testCases}} />

          {{/* Workflow Sections */}}
          {{WORKFLOW_SECTIONS.map(section => (
            <div key={{section.code}}>
              <SectionHeader
                section={{section}}
                tests={{testCases}}
                isExpanded={{expandedSections[section.code]}}
                onToggle={{() => toggleSection(section.code)}}
              />

              {{expandedSections[section.code] && (
                <div className="ml-4 mb-6">
                  {{testCases
                    .filter(t => t.workflow_section === section.code)
                    .sort((a, b) => a.workflow_order - b.workflow_order)
                    .map(test => (
                      <TestCaseRow
                        key={{test.test_id}}
                        test={{test}}
                        notes={{notes}}
                        onStatusChange={{handleStatusChange}}
                        onNotesChange={{handleNotesChange}}
                      />
                    ))
                  }}
                </div>
              )}}
            </div>
          ))}}

          {{/* Footer */}}
          <div className="text-center text-gray-400 text-sm mt-8">
            <p>Propel Health UAT Toolkit</p>
            <p className="text-xs mt-1">Progress auto-saved to browser</p>
          </div>
        </div>
      );
    }};

    ReactDOM.render(<App />, document.getElementById('root'));
    </script>
</body>
</html>
'''


if __name__ == "__main__":
    project_root = Path(__file__).parent.parent
    json_path = project_root / "outputs" / "onb_test_cases_workflow.json"
    output_path = project_root / "docs" / "onb-tracker.html"

    generate_tracker_html(str(json_path), str(output_path))
