#!/usr/bin/env node
/**
 * generate_uat_signoff_package.js
 *
 * Generates a formal UAT Sign-Off Package document for client approval.
 *
 * STORY: PLAT-RPT-001 - Generate UAT Sign-Off Package
 *
 * Usage:
 *   node generate_uat_signoff_package.js <cycle_id> <client_name> <client_title> [output_dir]
 *
 * Example:
 *   node generate_uat_signoff_package.js "UAT-ONB-12345678" "Kim Childers" "Clinical Program Manager" ~/Downloads
 */

const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, HeadingLevel, BorderStyle, WidthType,
  ShadingType, PageNumber, PageBreak, LevelFormat
} = require('docx');
const fs = require('fs');
const path = require('path');
const os = require('os');

// ============================================================================
// CONFIGURATION
// ============================================================================

// Database path - adjust as needed for your environment
const DB_PATH = process.env.PROPEL_DB_PATH ||
  path.join(os.homedir(), 'propel_data', 'requirements.db');

// Page dimensions (US Letter)
const PAGE_WIDTH = 12240;  // 8.5 inches in DXA
const PAGE_HEIGHT = 15840; // 11 inches in DXA
const MARGIN = 1440;       // 1 inch margins
const CONTENT_WIDTH = PAGE_WIDTH - (2 * MARGIN); // 9360 DXA

// Colors
const COLORS = {
  PRIMARY: "1B4F72",      // Dark blue
  SECONDARY: "2E86AB",    // Medium blue
  HEADER_BG: "D5E8F0",    // Light blue
  PASS: "27AE60",         // Green
  FAIL: "E74C3C",         // Red
  BLOCKED: "F39C12",      // Orange
  NOT_RUN: "95A5A6",      // Gray
  BORDER: "CCCCCC"
};

// ============================================================================
// DATABASE QUERIES
// ============================================================================

/**
 * Mock data structure - replace with actual SQLite queries in MCP integration
 */
async function getCycleData(cycleId) {
  // In the actual MCP tool, this would query the database
  // For now, returning structure that matches expected data

  // Example query pattern:
  // SELECT * FROM uat_cycles WHERE cycle_id = ?
  // SELECT * FROM uat_assignments WHERE cycle_id = ?
  // SELECT * FROM user_stories WHERE story_id IN (SELECT DISTINCT story_id FROM test_cases WHERE test_id IN (...))
  // etc.

  return {
    cycle: {
      cycle_id: cycleId,
      name: "Sample UAT Cycle",
      program_prefix: "ONB",
      program_name: "Onboarding Questionnaire",
      uat_type: "feature",
      status: "testing",
      target_launch_date: "2025-01-20",
      kickoff_date: "2025-01-13",
      testing_start_date: "2025-01-14",
      clinical_pm: "Kim Childers",
      clinical_pm_email: "kim.childers@providence.org"
    },
    stories: [],      // Populated by query
    testCases: [],    // Populated by query
    executions: [],   // Populated by query
    defects: []       // Populated by query
  };
}

// ============================================================================
// DOCUMENT BUILDING HELPERS
// ============================================================================

const border = { style: BorderStyle.SINGLE, size: 1, color: COLORS.BORDER };
const borders = { top: border, bottom: border, left: border, right: border };
const cellMargins = { top: 80, bottom: 80, left: 120, right: 120 };

/**
 * Create a styled heading paragraph
 */
function createHeading(text, level = HeadingLevel.HEADING_1) {
  return new Paragraph({
    heading: level,
    children: [new TextRun({ text, bold: true })]
  });
}

/**
 * Create a basic paragraph
 */
function createParagraph(text, options = {}) {
  return new Paragraph({
    spacing: { before: 120, after: 120 },
    ...options,
    children: [new TextRun({ text, ...options })]
  });
}

/**
 * Create a status badge text run
 */
function getStatusColor(status) {
  const statusMap = {
    'Pass': COLORS.PASS,
    'Fail': COLORS.FAIL,
    'Blocked': COLORS.BLOCKED,
    'Skipped': COLORS.NOT_RUN,
    'Not Run': COLORS.NOT_RUN
  };
  return statusMap[status] || COLORS.NOT_RUN;
}

/**
 * Create a table cell with standard formatting
 */
function createCell(content, options = {}) {
  const children = typeof content === 'string'
    ? [new Paragraph({ children: [new TextRun(content)] })]
    : content;

  return new TableCell({
    borders,
    margins: cellMargins,
    width: options.width ? { size: options.width, type: WidthType.DXA } : undefined,
    shading: options.shading ? { fill: options.shading, type: ShadingType.CLEAR } : undefined,
    children
  });
}

/**
 * Create the sign-off line block
 */
function createSignOffLine() {
  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    columnWidths: [3120, 2340, 3900], // Initial, Date, Notes
    rows: [
      new TableRow({
        children: [
          createCell("Initial", { shading: COLORS.HEADER_BG, width: 3120 }),
          createCell("Date", { shading: COLORS.HEADER_BG, width: 2340 }),
          createCell("Notes", { shading: COLORS.HEADER_BG, width: 3900 })
        ]
      }),
      new TableRow({
        children: [
          createCell([new Paragraph({ children: [new TextRun(" ")] })], { width: 3120 }),
          createCell([new Paragraph({ children: [new TextRun(" ")] })], { width: 2340 }),
          createCell([new Paragraph({ children: [new TextRun(" ")] })], { width: 3900 })
        ]
      })
    ]
  });
}

// ============================================================================
// DOCUMENT SECTIONS
// ============================================================================

/**
 * Create cover page section
 */
function createCoverPage(cycleData, clientName, clientTitle, preparedBy) {
  const { cycle } = cycleData;
  const today = new Date().toLocaleDateString('en-US', {
    year: 'numeric', month: 'long', day: 'numeric'
  });

  return [
    new Paragraph({ spacing: { before: 2400 } }), // Top spacing

    new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({
        text: "USER ACCEPTANCE TESTING",
        bold: true, size: 48, color: COLORS.PRIMARY
      })]
    }),

    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 240 },
      children: [new TextRun({
        text: "SIGN-OFF PACKAGE",
        bold: true, size: 40, color: COLORS.PRIMARY
      })]
    }),

    new Paragraph({ spacing: { before: 720 } }), // Spacing

    new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({
        text: cycle.program_name,
        bold: true, size: 36
      })]
    }),

    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 240 },
      children: [new TextRun({
        text: cycle.name,
        size: 28, italics: true
      })]
    }),

    new Paragraph({ spacing: { before: 1200 } }), // Spacing

    // Info table
    new Table({
      width: { size: 60, type: WidthType.PERCENTAGE },
      alignment: AlignmentType.CENTER,
      columnWidths: [2800, 4680],
      rows: [
        new TableRow({
          children: [
            createCell([new Paragraph({
              children: [new TextRun({ text: "Cycle ID:", bold: true })]
            })], { width: 2800, shading: COLORS.HEADER_BG }),
            createCell(cycle.cycle_id, { width: 4680 })
          ]
        }),
        new TableRow({
          children: [
            createCell([new Paragraph({
              children: [new TextRun({ text: "UAT Type:", bold: true })]
            })], { width: 2800, shading: COLORS.HEADER_BG }),
            createCell(cycle.uat_type.charAt(0).toUpperCase() + cycle.uat_type.slice(1), { width: 4680 })
          ]
        }),
        new TableRow({
          children: [
            createCell([new Paragraph({
              children: [new TextRun({ text: "Testing Period:", bold: true })]
            })], { width: 2800, shading: COLORS.HEADER_BG }),
            createCell(`${cycle.kickoff_date || 'TBD'} - ${cycle.target_launch_date || 'TBD'}`, { width: 4680 })
          ]
        }),
        new TableRow({
          children: [
            createCell([new Paragraph({
              children: [new TextRun({ text: "Document Date:", bold: true })]
            })], { width: 2800, shading: COLORS.HEADER_BG }),
            createCell(today, { width: 4680 })
          ]
        })
      ]
    }),

    new Paragraph({ spacing: { before: 1200 } }), // Spacing

    new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: "Prepared For:", bold: true, size: 24 })]
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: clientName, size: 24 })]
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: clientTitle, size: 22, italics: true })]
    }),

    new Paragraph({ spacing: { before: 480 } }),

    new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: "Prepared By:", bold: true, size: 24 })]
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: preparedBy, size: 24 })]
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: "Propel Health", size: 22, italics: true })]
    }),

    new Paragraph({ children: [new PageBreak()] })
  ];
}

/**
 * Create executive summary section
 */
function createExecutiveSummary(cycleData, stats) {
  const { cycle } = cycleData;

  // Calculate pass rate
  const totalExecuted = stats.pass + stats.fail + stats.blocked;
  const passRate = totalExecuted > 0
    ? ((stats.pass / totalExecuted) * 100).toFixed(1)
    : 0;

  // Determine recommendation
  let recommendation = "GO";
  let recommendationColor = COLORS.PASS;
  if (stats.fail > 0) {
    recommendation = "NO-GO";
    recommendationColor = COLORS.FAIL;
  } else if (stats.blocked > 0 || stats.notRun > 0) {
    recommendation = "CONDITIONAL GO";
    recommendationColor = COLORS.BLOCKED;
  }

  return [
    createHeading("Executive Summary"),

    createParagraph(`This document summarizes the User Acceptance Testing results for ${cycle.name}. The testing was conducted to validate that the implemented functionality meets the approved requirements and is ready for production deployment.`),

    new Paragraph({ spacing: { before: 240 } }),

    // Summary stats table
    new Table({
      width: { size: 100, type: WidthType.PERCENTAGE },
      columnWidths: [4680, 4680],
      rows: [
        new TableRow({
          children: [
            createCell([new Paragraph({
              children: [new TextRun({ text: "Total User Stories", bold: true })]
            })], { width: 4680, shading: COLORS.HEADER_BG }),
            createCell(String(stats.totalStories), { width: 4680 })
          ]
        }),
        new TableRow({
          children: [
            createCell([new Paragraph({
              children: [new TextRun({ text: "Total Test Cases", bold: true })]
            })], { width: 4680, shading: COLORS.HEADER_BG }),
            createCell(String(stats.totalTests), { width: 4680 })
          ]
        }),
        new TableRow({
          children: [
            createCell([new Paragraph({
              children: [new TextRun({ text: "Passed", bold: true })]
            })], { width: 4680, shading: COLORS.HEADER_BG }),
            createCell([new Paragraph({
              children: [new TextRun({ text: String(stats.pass), color: COLORS.PASS, bold: true })]
            })], { width: 4680 })
          ]
        }),
        new TableRow({
          children: [
            createCell([new Paragraph({
              children: [new TextRun({ text: "Failed", bold: true })]
            })], { width: 4680, shading: COLORS.HEADER_BG }),
            createCell([new Paragraph({
              children: [new TextRun({ text: String(stats.fail), color: COLORS.FAIL, bold: true })]
            })], { width: 4680 })
          ]
        }),
        new TableRow({
          children: [
            createCell([new Paragraph({
              children: [new TextRun({ text: "Blocked", bold: true })]
            })], { width: 4680, shading: COLORS.HEADER_BG }),
            createCell([new Paragraph({
              children: [new TextRun({ text: String(stats.blocked), color: COLORS.BLOCKED, bold: true })]
            })], { width: 4680 })
          ]
        }),
        new TableRow({
          children: [
            createCell([new Paragraph({
              children: [new TextRun({ text: "Not Run", bold: true })]
            })], { width: 4680, shading: COLORS.HEADER_BG }),
            createCell(String(stats.notRun), { width: 4680 })
          ]
        }),
        new TableRow({
          children: [
            createCell([new Paragraph({
              children: [new TextRun({ text: "Pass Rate", bold: true })]
            })], { width: 4680, shading: COLORS.HEADER_BG }),
            createCell(`${passRate}%`, { width: 4680 })
          ]
        })
      ]
    }),

    new Paragraph({ spacing: { before: 480 } }),

    // Recommendation box
    new Table({
      width: { size: 100, type: WidthType.PERCENTAGE },
      columnWidths: [CONTENT_WIDTH],
      rows: [
        new TableRow({
          children: [
            new TableCell({
              borders,
              margins: { top: 200, bottom: 200, left: 200, right: 200 },
              shading: { fill: "F8F9FA", type: ShadingType.CLEAR },
              children: [
                new Paragraph({
                  alignment: AlignmentType.CENTER,
                  children: [
                    new TextRun({ text: "RECOMMENDATION: ", bold: true, size: 28 }),
                    new TextRun({ text: recommendation, bold: true, size: 28, color: recommendationColor })
                  ]
                })
              ]
            })
          ]
        })
      ]
    }),

    new Paragraph({ children: [new PageBreak()] })
  ];
}

/**
 * Create story sign-off section for a single story
 */
function createStorySection(story, testCases) {
  const elements = [];

  // Story header
  elements.push(createHeading(`${story.story_id}: ${story.title}`, HeadingLevel.HEADING_2));

  // Story details table
  elements.push(new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    columnWidths: [2340, 7020],
    rows: [
      new TableRow({
        children: [
          createCell([new Paragraph({
            children: [new TextRun({ text: "Priority:", bold: true })]
          })], { width: 2340, shading: COLORS.HEADER_BG }),
          createCell(story.priority || "Should Have", { width: 7020 })
        ]
      }),
      new TableRow({
        children: [
          createCell([new Paragraph({
            children: [new TextRun({ text: "User Story:", bold: true })]
          })], { width: 2340, shading: COLORS.HEADER_BG }),
          createCell(story.user_story || "", { width: 7020 })
        ]
      }),
      new TableRow({
        children: [
          createCell([new Paragraph({
            children: [new TextRun({ text: "Acceptance Criteria:", bold: true })]
          })], { width: 2340, shading: COLORS.HEADER_BG }),
          createCell(story.acceptance_criteria || "", { width: 7020 })
        ]
      })
    ]
  }));

  elements.push(new Paragraph({ spacing: { before: 240 } }));

  // Test cases table
  elements.push(new Paragraph({
    children: [new TextRun({ text: "Test Cases:", bold: true })]
  }));

  if (testCases && testCases.length > 0) {
    const testRows = [
      new TableRow({
        children: [
          createCell([new Paragraph({
            children: [new TextRun({ text: "Test ID", bold: true })]
          })], { width: 2340, shading: COLORS.HEADER_BG }),
          createCell([new Paragraph({
            children: [new TextRun({ text: "Title", bold: true })]
          })], { width: 4680, shading: COLORS.HEADER_BG }),
          createCell([new Paragraph({
            children: [new TextRun({ text: "Result", bold: true })]
          })], { width: 1560, shading: COLORS.HEADER_BG }),
          createCell([new Paragraph({
            children: [new TextRun({ text: "Tester", bold: true })]
          })], { width: 1560, shading: COLORS.HEADER_BG })
        ]
      })
    ];

    for (const tc of testCases) {
      const statusColor = getStatusColor(tc.status || 'Not Run');
      testRows.push(new TableRow({
        children: [
          createCell(tc.test_id, { width: 2340 }),
          createCell(tc.title || "", { width: 4680 }),
          createCell([new Paragraph({
            children: [new TextRun({
              text: tc.status || "Not Run",
              color: statusColor,
              bold: true
            })]
          })], { width: 1560 }),
          createCell(tc.tested_by || "-", { width: 1560 })
        ]
      }));
    }

    elements.push(new Table({
      width: { size: 100, type: WidthType.PERCENTAGE },
      columnWidths: [2340, 4680, 1560, 1560],
      rows: testRows
    }));
  } else {
    elements.push(createParagraph("No test cases linked to this story.", { italics: true }));
  }

  elements.push(new Paragraph({ spacing: { before: 360 } }));

  // Sign-off line
  elements.push(new Paragraph({
    children: [new TextRun({ text: "Story Acceptance:", bold: true })]
  }));
  elements.push(createSignOffLine());

  elements.push(new Paragraph({ spacing: { before: 480 } }));

  return elements;
}

/**
 * Create defect log appendix
 */
function createDefectAppendix(defects) {
  const elements = [
    new Paragraph({ children: [new PageBreak()] }),
    createHeading("Appendix A: Defect Log")
  ];

  if (!defects || defects.length === 0) {
    elements.push(createParagraph("No defects were recorded during this UAT cycle.", { italics: true }));
    return elements;
  }

  const rows = [
    new TableRow({
      children: [
        createCell([new Paragraph({ children: [new TextRun({ text: "Defect ID", bold: true })] })],
          { width: 1560, shading: COLORS.HEADER_BG }),
        createCell([new Paragraph({ children: [new TextRun({ text: "Test Case", bold: true })] })],
          { width: 1872, shading: COLORS.HEADER_BG }),
        createCell([new Paragraph({ children: [new TextRun({ text: "Description", bold: true })] })],
          { width: 3744, shading: COLORS.HEADER_BG }),
        createCell([new Paragraph({ children: [new TextRun({ text: "Status", bold: true })] })],
          { width: 1248, shading: COLORS.HEADER_BG }),
        createCell([new Paragraph({ children: [new TextRun({ text: "Dev Notes", bold: true })] })],
          { width: 1872, shading: COLORS.HEADER_BG })
      ]
    })
  ];

  for (const defect of defects) {
    rows.push(new TableRow({
      children: [
        createCell(defect.defect_id || "-", { width: 1560 }),
        createCell(defect.test_id || "-", { width: 1872 }),
        createCell(defect.description || "", { width: 3744 }),
        createCell(defect.dev_status || "Open", { width: 1248 }),
        createCell(defect.dev_notes || "-", { width: 1872 })
      ]
    }));
  }

  elements.push(new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    columnWidths: [1560, 1872, 3744, 1248, 1872],
    rows
  }));

  return elements;
}

/**
 * Create compliance matrix appendix
 */
function createComplianceAppendix(testCases) {
  const elements = [
    new Paragraph({ children: [new PageBreak()] }),
    createHeading("Appendix B: Compliance Matrix")
  ];

  // Filter to only compliance-tagged tests
  const complianceTests = testCases.filter(tc => tc.compliance_framework);

  if (complianceTests.length === 0) {
    elements.push(createParagraph("No test cases have compliance framework tags.", { italics: true }));
    return elements;
  }

  const rows = [
    new TableRow({
      children: [
        createCell([new Paragraph({ children: [new TextRun({ text: "Test ID", bold: true })] })],
          { width: 2340, shading: COLORS.HEADER_BG }),
        createCell([new Paragraph({ children: [new TextRun({ text: "Title", bold: true })] })],
          { width: 4056, shading: COLORS.HEADER_BG }),
        createCell([new Paragraph({ children: [new TextRun({ text: "Framework", bold: true })] })],
          { width: 1560, shading: COLORS.HEADER_BG }),
        createCell([new Paragraph({ children: [new TextRun({ text: "Result", bold: true })] })],
          { width: 1404, shading: COLORS.HEADER_BG })
      ]
    })
  ];

  for (const tc of complianceTests) {
    const statusColor = getStatusColor(tc.status || 'Not Run');
    rows.push(new TableRow({
      children: [
        createCell(tc.test_id, { width: 2340 }),
        createCell(tc.title || "", { width: 4056 }),
        createCell(tc.compliance_framework || "", { width: 1560 }),
        createCell([new Paragraph({
          children: [new TextRun({ text: tc.status || "Not Run", color: statusColor, bold: true })]
        })], { width: 1404 })
      ]
    }));
  }

  elements.push(new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    columnWidths: [2340, 4056, 1560, 1404],
    rows
  }));

  return elements;
}

/**
 * Create final sign-off page
 */
function createFinalSignOff(clientName, clientTitle, cycleName) {
  return [
    new Paragraph({ children: [new PageBreak()] }),
    createHeading("Final UAT Sign-Off"),

    createParagraph(`By signing below, I acknowledge that I have reviewed the User Acceptance Testing results for ${cycleName} and approve the functionality for production deployment.`),

    new Paragraph({ spacing: { before: 720 } }),

    // Signature block
    new Table({
      width: { size: 80, type: WidthType.PERCENTAGE },
      alignment: AlignmentType.CENTER,
      columnWidths: [3744, 3744],
      rows: [
        new TableRow({
          children: [
            createCell([
              new Paragraph({ spacing: { before: 600 }, children: [new TextRun("_".repeat(40))] }),
              new Paragraph({ children: [new TextRun({ text: clientName, bold: true })] }),
              new Paragraph({ children: [new TextRun({ text: clientTitle, italics: true })] })
            ], { width: 3744 }),
            createCell([
              new Paragraph({ spacing: { before: 600 }, children: [new TextRun("_".repeat(40))] }),
              new Paragraph({ children: [new TextRun({ text: "Date", bold: true })] })
            ], { width: 3744 })
          ]
        })
      ]
    }),

    new Paragraph({ spacing: { before: 960 } }),

    new Table({
      width: { size: 80, type: WidthType.PERCENTAGE },
      alignment: AlignmentType.CENTER,
      columnWidths: [3744, 3744],
      rows: [
        new TableRow({
          children: [
            createCell([
              new Paragraph({ spacing: { before: 600 }, children: [new TextRun("_".repeat(40))] }),
              new Paragraph({ children: [new TextRun({ text: "Propel Health Representative", bold: true })] })
            ], { width: 3744 }),
            createCell([
              new Paragraph({ spacing: { before: 600 }, children: [new TextRun("_".repeat(40))] }),
              new Paragraph({ children: [new TextRun({ text: "Date", bold: true })] })
            ], { width: 3744 })
          ]
        })
      ]
    })
  ];
}

// ============================================================================
// MAIN DOCUMENT GENERATOR
// ============================================================================

/**
 * Generate the complete UAT Sign-Off Package
 *
 * @param {string} cycleId - UAT cycle ID
 * @param {string} clientName - Client reviewer name
 * @param {string} clientTitle - Client reviewer title
 * @param {object} data - Object containing stories, testCases, defects from database
 * @param {string} preparedBy - Name of person preparing document
 * @returns {Document} - docx Document object
 */
function generateDocument(cycleId, clientName, clientTitle, data, preparedBy = "Propel Health") {
  const { cycle, stories, testCases, defects } = data;

  // Calculate stats
  const stats = {
    totalStories: stories.length,
    totalTests: testCases.length,
    pass: testCases.filter(tc => tc.status === 'Pass').length,
    fail: testCases.filter(tc => tc.status === 'Fail').length,
    blocked: testCases.filter(tc => tc.status === 'Blocked').length,
    notRun: testCases.filter(tc => !tc.status || tc.status === 'Not Run' || tc.status === 'Skipped').length
  };

  // Build document sections
  const children = [];

  // Cover page
  children.push(...createCoverPage(data, clientName, clientTitle, preparedBy));

  // Executive summary
  children.push(...createExecutiveSummary(data, stats));

  // Story sign-off sections
  children.push(createHeading("User Story Acceptance"));
  children.push(createParagraph("Please review each user story and its associated test results. Initial each story to indicate acceptance."));
  children.push(new Paragraph({ spacing: { before: 240 } }));

  for (const story of stories) {
    const storyTests = testCases.filter(tc => tc.story_id === story.story_id);
    children.push(...createStorySection(story, storyTests));
  }

  // Appendices
  children.push(...createDefectAppendix(defects));
  children.push(...createComplianceAppendix(testCases));

  // Final sign-off
  children.push(...createFinalSignOff(clientName, clientTitle, cycle.name));

  // Create document
  return new Document({
    styles: {
      default: {
        document: {
          run: { font: "Arial", size: 24 } // 12pt default
        }
      },
      paragraphStyles: [
        {
          id: "Heading1",
          name: "Heading 1",
          basedOn: "Normal",
          next: "Normal",
          quickFormat: true,
          run: { size: 32, bold: true, font: "Arial", color: COLORS.PRIMARY },
          paragraph: { spacing: { before: 360, after: 240 }, outlineLevel: 0 }
        },
        {
          id: "Heading2",
          name: "Heading 2",
          basedOn: "Normal",
          next: "Normal",
          quickFormat: true,
          run: { size: 26, bold: true, font: "Arial", color: COLORS.SECONDARY },
          paragraph: { spacing: { before: 280, after: 180 }, outlineLevel: 1 }
        }
      ]
    },
    sections: [{
      properties: {
        page: {
          size: { width: PAGE_WIDTH, height: PAGE_HEIGHT },
          margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN }
        }
      },
      headers: {
        default: new Header({
          children: [new Paragraph({
            alignment: AlignmentType.RIGHT,
            children: [new TextRun({
              text: `${cycle.program_name} - ${cycle.name}`,
              size: 20,
              color: COLORS.NOT_RUN
            })]
          })]
        })
      },
      footers: {
        default: new Footer({
          children: [new Paragraph({
            alignment: AlignmentType.CENTER,
            children: [
              new TextRun({ text: "Page ", size: 20 }),
              new TextRun({ children: [PageNumber.CURRENT], size: 20 }),
              new TextRun({ text: " | Confidential - Propel Health", size: 20, color: COLORS.NOT_RUN })
            ]
          })]
        })
      },
      children
    }]
  });
}

// ============================================================================
// MCP TOOL INTEGRATION FUNCTION
// ============================================================================

/**
 * This is the function to integrate into the MCP server.
 * Copy this into your tools file and call it from the MCP handler.
 *
 * @param {string} cycleId - UAT cycle ID (e.g., "UAT-ONB-12345678")
 * @param {string} clientName - Client name for sign-off
 * @param {string} clientTitle - Client title
 * @param {string} outputFormat - "docx" or "pdf" (default: "docx")
 * @param {string} outputDir - Output directory (default: ~/Downloads)
 * @returns {string} - Path to generated file and summary
 */
async function generate_uat_signoff_package(cycleId, clientName, clientTitle, outputFormat = 'docx', outputDir = null) {
  // Default output directory
  if (!outputDir) {
    outputDir = path.join(os.homedir(), 'Downloads');
  }

  // Ensure output directory exists
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  // =========================================================================
  // DATABASE QUERIES - Replace with actual SQLite queries in MCP
  // =========================================================================

  // In the actual MCP integration, you would:
  // 1. Query uat_cycles table for cycle info
  // 2. Query uat_assignments for test assignments
  // 3. Query test_cases for test details
  // 4. Query user_stories for story details
  // 5. Query for any defects

  // For now, using mock data to demonstrate structure
  const data = await getCycleData(cycleId);

  // =========================================================================
  // GENERATE DOCUMENT
  // =========================================================================

  const doc = generateDocument(cycleId, clientName, clientTitle, data, "Glen Lewis");

  // Generate filename
  const timestamp = new Date().toISOString().split('T')[0];
  const safeClientName = clientName.replace(/[^a-zA-Z0-9]/g, '_');
  const filename = `UAT_SignOff_${data.cycle.program_prefix}_${safeClientName}_${timestamp}.docx`;
  const outputPath = path.join(outputDir, filename);

  // Write file
  const buffer = await Packer.toBuffer(doc);
  fs.writeFileSync(outputPath, buffer);

  // Summary
  const summary = `
UAT Sign-Off Package Generated
==============================
Cycle: ${data.cycle.name} (${cycleId})
Client: ${clientName}, ${clientTitle}
File: ${outputPath}

Contents:
  - Cover page
  - Executive summary
  - ${data.stories.length} user story sign-off sections
  - Appendix A: Defect log (${data.defects.length} defects)
  - Appendix B: Compliance matrix
  - Final sign-off page
`;

  return summary;
}

// ============================================================================
// CLI EXECUTION
// ============================================================================

if (require.main === module) {
  const args = process.argv.slice(2);

  if (args.length < 3) {
    console.log(`
Usage: node generate_uat_signoff_package.js <cycle_id> <client_name> <client_title> [output_dir]

Example:
  node generate_uat_signoff_package.js "UAT-ONB-12345678" "Kim Childers" "Clinical Program Manager"
`);
    process.exit(1);
  }

  const [cycleId, clientName, clientTitle, outputDir] = args;

  generate_uat_signoff_package(cycleId, clientName, clientTitle, 'docx', outputDir)
    .then(result => console.log(result))
    .catch(err => {
      console.error('Error generating document:', err);
      process.exit(1);
    });
}

// Export for MCP integration
module.exports = {
  generate_uat_signoff_package,
  generateDocument
};
