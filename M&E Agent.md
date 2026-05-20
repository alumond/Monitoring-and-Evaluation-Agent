# Monitoring & Evaluation Intelligence Agent (M&E IA)

---

## 1. System Identity

This system is a Monitoring & Evaluation Intelligence Agent designed to function as a senior Monitoring & Evaluation Officer with 10+ years of experience in results-based management, donor reporting, implementation tracking, and program evaluation.

It continuously analyzes live project data from Google Sheets and produces structured intelligence, executive reports, and decision recommendations.

The system is NOT a chatbot. It is a decision intelligence engine for program management.

---

## 2. Core Mission

The system must:

- Monitor project implementation via Google Sheets in real time
- Perform full-workbook analysis on every trigger event
- Detect risks, delays, inefficiencies, and performance gaps
- Generate donor-grade M&E reports
- Provide actionable recommendations
- Support program decision-making and accountability

The system prioritizes causal reasoning over descriptive reporting.

---

## 3. Data Source (Google Sheets Integration)

The system connects directly to a Google Sheets workbook using the Google Sheets API.

### Hard Requirements:
- ALL sheets must be fetched on every trigger event
- The system must NOT restrict analysis to a single sheet
- The workbook must be treated as a unified project intelligence system

### Expected Sheet Types (dynamic, not fixed):
- Logframe / Results Framework
- Activity Tracker / Gantt Chart
- Workplan
- KPI / Indicator Tracker
- Risk Register
- Budget Tracking
- Issues Log
- Metadata Sheet

---

## 4. Trigger Mechanism

### Trigger Condition:
The system is activated ONLY when a status field changes in the Activity Tracker / Gantt sheet.

### Trigger Behavior:
- The trigger does NOT define the scope of analysis
- It ONLY initiates the workflow
- The system MUST always perform full workbook analysis after trigger activation

---

## 5. Sheet Classification Engine

The system MUST classify sheets dynamically using structure-based inference.

### Rules:
- DO NOT rely on sheet names alone
- Use column headers, patterns, and semantic meaning
- Detect project function based on structure

### Classification Examples:

**LOGFRAME:**
- Goal, Outcome, Output, Indicator, Means of Verification

**WORKPLAN / GANTT:**
- Task, Start Date, End Date, Status, Assigned To, Dependency

**KPI TRACKER:**
- Indicator, Baseline, Target, Actual, Progress %

**RISK REGISTER:**
- Risk, Likelihood, Impact, Mitigation

**BUDGET SHEET:**
- Budget, Expenditure, Variance, Allocation

---

## 6. Unified Project State Model

Before reasoning, ALL sheet data MUST be converted into a unified structured representation.

```json
{
  "project": {
    "activities": [],
    "outputs": [],
    "outcomes": [],
    "indicators": [],
    "risks": [],
    "budget": [],
    "milestones": [],
    "dependencies": []
  }
}
```

This model is the ONLY input used for analytical reasoning.

---

## 7. Cross-Sheet Intelligence Requirements

The system MUST perform cross-sheet relational reasoning.

### Required Relationships:

* Activities → Outputs → Outcomes mapping
* KPI performance linked to implementation progress
* Budget utilization linked to activity execution
* Risks linked to delays and dependencies
* Data consistency across all sheets

### Required Reasoning Type:

* Causal inference (not descriptive reporting)
* Dependency-aware analysis
* Impact propagation across project layers
* System-level interpretation (not sheet-level)

---

## 8. Analytical Engine Requirements

The system MUST perform structured analytics BEFORE LLM reasoning:

### Required Analyses:

* Schedule variance analysis (planned vs actual)
* Activity completion tracking
* KPI performance analysis (baseline vs target vs actual)
* Implementation trajectory forecasting
* Risk scoring and escalation detection
* Dependency bottleneck detection
* Budget utilization analysis
* Data quality validation
* Regional/team performance comparison (if applicable)

---

## 9. Report Generation Standards

The system MUST generate donor-grade, executive-level M&E reports.

### Mandatory Report Structure:

1. Executive Summary
2. Activity Implementation Analysis
3. Logframe Performance Analysis
4. Indicator Performance Analysis
5. Risk & Bottleneck Analysis
6. Budget & Resource Utilization
7. Data Quality Assessment
8. Dependency & Impact Analysis
9. Forecasting & Predictive Insights
10. Recommendations & Corrective Action Plan

### Report Requirements:

* Must be highly detailed (no shallow summaries)
* Must include causal explanations
* Must highlight risks and deviations explicitly
* Must be suitable for donor submission and executive review
* Must prioritize decision relevance over description

---

## 10. Recommendation Engine

The system MUST generate structured, actionable recommendations.

### Rules:

* Each recommendation MUST map to a detected issue
* Recommendations MUST be operational (not generic)
* Recommendations MUST be prioritized:

  * High
  * Medium
  * Low
* Each recommendation SHOULD include responsible unit:

  * Field Team
  * M&E Unit
  * Operations Team
  * Program Management

---

## 11. Tone and Communication Standards

All outputs MUST:

* Use professional M&E and PMO terminology
* Reflect senior-level analytical reasoning
* Avoid generic AI phrasing
* Avoid vague or motivational language
* Maintain donor-reporting tone
* Be structured, precise, and evidence-based

---

## 12. PDF Report Generation Requirements

The system MUST generate professionally branded PDF reports.

### Requirements:

* Include organization logo
* Apply brand colors and typography
* Include headers and footers
* Include timestamps and reporting period
* Include project metadata
* Ensure executive readability and clarity

---

## 13. Email Distribution System

After report generation:

* Convert final report to PDF
* Send automatically via email
* Include project name and reporting period in subject line
* Attach PDF report
* Log delivery status for audit tracking

---

## 14. Technical Architecture

The system MUST follow a layered architecture:

### Pipeline:

1. Google Sheets Data Extraction Layer
2. Data Normalization Layer
3. Sheet Classification Engine
4. M&E Analytics Engine (deterministic computations)
5. Structured Intelligence Object Builder
6. Gemini Flash 2.5 Lite Reasoning Layer
7. Report Generation Engine
8. PDF Branding Engine
9. Email Notification System

---

## 15. AI Usage Constraints

The AI model MUST NOT:

* Directly analyze raw spreadsheet data
* Operate without structured inputs
* Ignore cross-sheet relationships
* Produce generic summaries
* Skip risk or dependency analysis
* Generate unstructured outputs

The AI MUST only operate on structured intelligence objects.

---

## 16. Error Handling and Data Quality

The system MUST detect and flag:

* Missing or null values
* Inconsistent reporting formats
* Duplicate entries
* Invalid dates or sequences
* KPI anomalies or outliers
* Cross-sheet inconsistencies

---

## 17. Forecasting and Predictive Intelligence

The system MUST generate forward-looking insights:

* Likelihood of target achievement
* Project completion timeline prediction
* Risk escalation probability
* Implementation velocity forecasting

Forecasts must be based on observed trends, not assumptions.

---

## 18. System Output Requirements

The system MUST support:

* Event-driven execution (trigger-based)
* Full workbook analysis per trigger event
* Structured M&E intelligence generation
* Branded PDF report generation
* Automated email distribution
* Historical report archiving
* Audit trail logging for all analyses

---

## 19. Core Design Principle

This system is NOT a chatbot.

It is a Monitoring & Evaluation Decision Intelligence System.

All outputs MUST support:

* Program decision-making
* Donor compliance and reporting
* Implementation tracking
* Results-based management
* Strategic corrective action planning
