# M&E Intelligence Engine Deployment Guide

This document provides step-by-step instructions on setting up, running, and deploying the Monitoring & Evaluation (M&E) Intelligence Engine both locally and on Render.

---

## 1. Local Setup Guide (Windows)

### Prerequisites
* Python 3.9 or higher installed.
* Git installed.

### Step 1: Create and Activate Virtual Environment
Clone the repository and navigate to the project directory, then run the appropriate command for your terminal:

* **For PowerShell:**
  ```powershell
  python -m venv .venv
  .venv\Scripts\Activate.ps1
  ```

* **For Command Prompt (CMD):**
  ```cmd
  python -m venv .venv
  .venv\Scripts\activate.bat
  ```

* **For Git Bash (Bash on Windows):**
  ```bash
  source .venv/Scripts/activate
  ```

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Configure Environment Variables
Copy `.env.example` to `.env` if you haven't already:
```bash
cp .env.example .env
```
Populate the following variables inside the `.env` file:
* `GOOGLE_SERVICE_ACCOUNT_FILE`: Absolute path to your Google Service Account JSON key.
* `GOOGLE_SHEETS_SPREADSHEET_ID`: Your Google Sheets Workbook ID.
* `GEMINI_API_KEY`: Google Gemini Developer API key.
* `SMTP_USERNAME`/`SMTP_PASSWORD`: Credentials for sending out narrative emails.

### Step 4: Run the Development Server
Start the local server using Uvicorn with hot-reload enabled:
```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
* **Verify Health**: Visit [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health) in your web browser.

---

## 2. Production Deployment on Render

Render is the recommended hosting platform because it supports **Secret Files** (allowing secure uploads of service account credentials) and **Persistent Disks** (allowing SQLite audits and reports to persist across deployments).

### Step 1: Create a Render Web Service
1. Log in to [Render Dashboard](https://dashboard.render.com/) and click **New > Web Service**.
2. Link your private GitHub repository.
3. Configure the following service fields:
   * **Name**: `me-intelligence-engine`
   * **Runtime**: `Python`
   * **Build Command**: `pip install -r requirements.txt`
   * **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### Step 2: Configure Secret Credentials
Because the Google Sheets connector uses a service account key file, you should upload it securely on Render without checking it into your repository:
1. Navigate to the **Environment** tab of your service.
2. Click **Add Secret File**.
3. Name the file: `service_account.json`
4. Paste the entire content of your Google Service Account JSON file into the value box.
5. Save changes. Render will place this file at `/etc/secrets/service_account.json` in the container.

### Step 3: Mount a Persistent Disk
Since Render containers have ephemeral filesystems, write audit runs to a persistent volume:
1. Go to the **Disks** tab of your service.
2. Click **Add Disk**.
3. Name: `me-db`
4. Mount Path: `/opt/render/project/src/db` (Places the disk at a folder named `db` in the repository root).
5. Size: `1 GB`

### Step 4: Add Environment Variables
Under the **Environment** tab, click **Add Environment Variable** and configure the variables matching your `.env` settings:

| Variable | Value | Description |
| :--- | :--- | :--- |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | `/etc/secrets/service_account.json` | Path pointing to your Render secret file mount |
| `GOOGLE_SHEETS_SPREADSHEET_ID` | `YourSpreadsheetIDHere` | Target Google Spreadsheet ID |
| `GEMINI_API_URL` | `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent` | Gemini content API Endpoint |
| `GEMINI_API_KEY` | `YourGeminiAPIKey` | API Key for model requests |
| `SMTP_HOST` | `smtp.gmail.com` | SMTP Server Host |
| `SMTP_PORT` | `465` | SMTP Server Port |
| `SMTP_USERNAME` | `your-email@example.com` | SMTP Username |
| `SMTP_PASSWORD` | `your-smtp-app-password` | SMTP App Password |
| `EMAIL_FROM` | `your-email@example.com` | Sender address |
| `EMAIL_TO` | `recipient1@example.com,recipient2@example.com` | List of report recipients (comma-separated) |
| `LOG_DB_URL` | `sqlite:////opt/render/project/src/db/report_audit.db` | Points database storage to the persistent disk |

*Note: For production, keep the `LOG_DB_URL` exactly as specified to align with the persistent disk volume path.*

---

## 3. Connecting Google Sheets Apps Script Trigger

To execute full M&E analyses in real-time when sheet updates occur, deploy a Google Apps Script trigger on your spreadsheet:

1. In your Google Sheet, click **Extensions > Apps Script**.
2. Replace any default code with the following snippet:

```javascript
function onEdit(e) {
  var range = e.range;
  var sheet = range.getSheet();
  var sheetName = sheet.getName();
  
  // 1. Specify the sheet name containing activity tracker/Gantt tasks
  if (sheetName === "Activity Tracker") {
    var col = range.getColumn();
    var headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
    var changedHeader = headers[col - 1];
    
    // 2. Identify if the change was to a status column
    if (changedHeader && changedHeader.toLowerCase().includes("status")) {
      var oldValue = e.oldValue || "";
      var newValue = range.getValue();
      
      // Update this with your Render deployment URL
      var url = "https://me-intelligence-engine.onrender.com/webhooks/google-sheets/change";
      
      var payload = {
        "changed_sheet_title": sheetName,
        "changed_column": changedHeader,
        "old_value": String(oldValue),
        "new_value": String(newValue),
        "changed_range": range.getA1Notation(),
        "event_timestamp": new Date().toISOString()
      };
      
      var options = {
        "method": "post",
        "contentType": "application/json",
        "payload": JSON.stringify(payload),
        "muteHttpExceptions": true
      };
      
      try {
        var response = UrlFetchApp.fetch(url, options);
        Logger.log("Trigger Status Code: " + response.getResponseCode());
      } catch (err) {
        Logger.log("Webhook delivery error: " + err.toString());
      }
    }
  }
}
```

3. Save the script project.
4. **Important**: Since simple `onEdit(e)` triggers cannot perform network requests without authorization, you must set up an **Installable Trigger**:
   * Click the **Triggers** clock icon in the left-hand menu of Apps Script.
   * Click **Add Trigger** (bottom right).
   * Choose function to run: `onEdit`
   * Select event source: `From spreadsheet`
   * Select event type: `On edit`
   * Click **Save** and authorize permissions when prompted.
