# Task Organizer

A Windows desktop app for organizing tasks that come at you from everywhere
(email, your manager, Teams messages, your own head) and keeping them all in
one place: a dashboard, an Eisenhower priority matrix, a time tracker, and a
weekly report -- built for **solo** use, at **$0** cost, with **local**
data you control.

This is not a tray icon or a spreadsheet -- it's a full application with
several views, described below.

---

## What's in v1

- **Dashboard** -- today's tasks, upcoming deadlines, overdue tasks.
- **Eisenhower Matrix** -- a real 4-quadrant board (urgent/important) you
  drag tasks between, not just a priority dropdown buried in a form.
- **Time Tracker** -- start/stop a timer per task; time accumulates against
  the task's estimate so you can see estimate vs. actual.
- **Reports** -- a weekly summary: time spent by project, tasks completed
  vs. planned, overdue tasks. Exportable to Excel.
- **Settings** -- configure your OneDrive sync folder, your Ollama model,
  notification preferences, and your Azure AD app client ID.
- **Notifications** -- upcoming-deadline alerts plus daily/weekly digest
  reminders (Windows toast notifications, with an in-app status-bar
  fallback if toasts aren't available).
- **Outlook integration** -- sign in with your Microsoft account (free,
  no admin needed for Outlook.com/personal accounts), pull recent emails,
  and turn one into a task with one click.
- **Teams integration** -- read recent chat messages the same way. Reading
  **channel** messages usually needs your IT admin's consent in a work
  account -- see [Teams limitations](#teams-limitations) below.
- **Excel import/export** -- read a task list from an existing `.xlsx`
  file, or export your tasks / weekly report to a new one. Fully
  self-contained, no sign-in needed.
- **AI features** (optional, free, local) -- summarize an email into
  candidate tasks, suggest an Eisenhower quadrant for a task, and generate
  friendly deadline reminder text -- all powered by a **local** AI model
  running on your own PC via [Ollama](https://ollama.com), so nothing is
  sent to a paid API and nothing costs money.

What's deliberately **not** in v1: Slack, Google Sheets, multi-user/team
features, and any cloud backend. If you want those later, the AI provider
and integration modules are written behind clean interfaces specifically so
more can be added without a rewrite.

---

## 1. Install and run

### Requirements
- Windows 10/11 (the app also runs on macOS/Linux for development, minus
  the Windows-toast notification piece, which just falls back gracefully).
- [Python 3.11+](https://www.python.org/downloads/) -- when installing on
  Windows, tick **"Add python.exe to PATH"**.

### Steps

1. Download/clone this repository to a folder on your PC.
2. Open a terminal (PowerShell) in that folder.
3. Create and activate a virtual environment (keeps this app's Python
   packages separate from everything else on your machine):

   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   ```

4. Install the dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

5. Run the app:

   ```powershell
   python app\main.py
   ```

   (On macOS/Linux: `python3 app/main.py`, with the venv activated via
   `source .venv/bin/activate`.)

That's it -- the app creates its local database automatically on first run,
in `~/.task_organizer/task_organizer.db` (i.e. `C:\Users\<you>\.task_organizer\`
on Windows) unless you point it somewhere else in Settings.

### Running the tests (optional, for the curious/technical)

```powershell
pip install -r requirements.txt
pytest
```

Tests cover the task database (CRUD + time tracking) and the Excel
import/export round-trip without needing any network access, Windows, or a
real Azure/Ollama setup. A few UI "smoke" tests also run if a Qt display (or
the offscreen Qt platform plugin) is available in your environment; they
skip themselves with a clear reason if not, rather than failing.

---

## 2. The "mobile sync" approach (and its limits) -- read this

**Budget for this project is $0**, so there's no cloud server behind this
app, and building a real native mobile app was out of scope. Instead, v1
uses a practical, free workaround:

### How it works
1. In **Settings**, set your **OneDrive sync folder** to a folder inside
   your OneDrive, e.g. `C:\Users\you\OneDrive\TaskOrganizer\`.
2. The app's local database file lives in that folder from then on.
   OneDrive syncs that folder to the cloud (and to any other PC you have
   OneDrive signed into) automatically, the same way it syncs any other
   file -- the app doesn't talk to OneDrive's API directly, it just writes
   to a folder OneDrive is already watching.
3. To actually **view or edit tasks from your phone**, use the toolbar's
   **"Export to Excel"** button (or the same button in Reports) to write an
   `.xlsx` snapshot into that same OneDrive folder. Open it with the
   OneDrive mobile app or the Excel mobile app on your phone -- both are
   free.

### Limits of this approach (please read)
- This is **not** a dedicated native mobile app, and it is **not real-time,
  two-way sync**. It's "your database file happens to live somewhere that
  syncs" plus "you can export a snapshot to look at on your phone."
- Editing the exported `.xlsx` on your phone does **not** write back into
  the app automatically -- you'd need to re-import it (toolbar → "Import
  from Excel") next time you're at your PC.
- Don't run the desktop app on two different PCs pointed at the same synced
  database file **at the same time** -- SQLite doesn't handle that safely
  over a cloud-synced folder, and OneDrive's conflict resolution for a
  binary database file is "last writer wins," which can lose data. Treat it
  as "sync when I'm not actively using the other copy," not simultaneous
  multi-device use.
- If none of this fits how you want to use your phone, you can also just
  leave the sync folder blank (default) and use the app purely on one PC,
  no OneDrive involved at all.

---

## 3. Outlook & Teams setup (Microsoft Graph)

Both integrations use the same **free, no-admin-approval-required** kind of
Azure AD app registration: a "public client" app using **device-code
sign-in** (you get a code, you type it into a Microsoft web page, done --
no client secret, no server, no cost). You only have to do this setup once.

### Step-by-step: register your own free Azure AD app

1. Go to <https://portal.azure.com> and sign in with the Microsoft account
   you want to use with the app (a personal Microsoft account or a work
   account both work for Outlook; Teams channel reading may need a work
   account with admin consent -- see below).
2. Search for **"App registrations"** and click **New registration**.
3. Name it anything, e.g. "Task Organizer Desktop".
4. Under **Supported account types**, choose "Accounts in any
   organizational directory and personal Microsoft accounts" (or narrower,
   if you know what you're doing and prefer that).
5. Leave **Redirect URI** blank for now and click **Register**.
6. On the app's **Overview** page, copy the **Application (client) ID** --
   you'll paste this into the app's **Settings** view (`Azure AD client
   ID` field).
7. Go to **Authentication** (left sidebar) → scroll to **Advanced
   settings** → set **"Allow public client flows"** to **Yes** → **Save**.
   This is required for the device-code flow to work.
8. Go to **API permissions** (left sidebar) → **Add a permission** →
   **Microsoft Graph** → **Delegated permissions**, and add:
   - `Mail.Read` (Outlook)
   - `Chat.Read` (Teams 1:1/group chats)
   - `ChannelMessage.Read.All` (Teams channel messages -- see limitation
     below)
   - `offline_access` and `User.Read` are usually added automatically.
9. Click **Grant admin consent** if you're able to (only relevant/needed
   for work accounts; personal Microsoft accounts don't need this step for
   `Mail.Read`/`Chat.Read`).
10. Paste the client ID from step 6 into **Settings → Azure AD client ID**
    in the app, save, then use the toolbar's **"Import from Outlook"**
    button. A dialog will show you a short code and a URL
    (`https://microsoft.com/devicelogin`) -- open that URL on any device,
    enter the code, sign in, and approve. The app will then fetch your
    recent emails.

This app **never stores a client secret and never runs a server** -- that's
what makes it possible to do this for free as a solo user. The client ID
itself isn't secret (it's fine that it's visible in Settings/config); what
matters is that "public client" apps like this can only act as the signed-in
user, with whatever permissions that user consents to.

### Teams limitations

Reading **channel** messages (`ChannelMessage.Read.All`) is a permission
that Microsoft treats as sensitive, and in most work/school (tenant)
environments it requires **your IT administrator to grant admin consent**
-- an individual user often can't self-approve it. If that hasn't been
granted in your organization, channel reading will fail with a clear
permission-denied message in the app (it won't crash) -- see
`app/integrations/teams_graph.py`'s `TeamsAccessError`.

Reading your own 1:1 and group **chats** (`Chat.Read`) is much more likely
to work without admin help, since it's a permission the signed-in user can
consent to on their own.

If you're on a personal Microsoft account (not a work/school one), Teams
features are unlikely to apply to you at all -- Outlook mail reading is
the integration most relevant to personal accounts.

This is, by design, the roughest integration in v1 -- the core task
engine, matrix, time tracker, and Excel/Outlook integrations are the
parts guaranteed to work well everywhere.

---

## 4. AI features setup (Ollama -- free, local, optional)

The AI features (summarizing emails into candidate tasks, suggesting an
Eisenhower quadrant, writing friendly deadline reminders) run against a
small language model on **your own computer** via
[Ollama](https://ollama.com) -- free, no API key, nothing sent to the
cloud. If you don't install it, the app still works fine; AI buttons will
just show a message like:

> AI features unavailable — install and run Ollama (https://ollama.com)...

### Setup
1. Download and install Ollama from <https://ollama.com/download> (Windows
   installer available).
2. Once installed, Ollama runs a small local server automatically (default
   `http://localhost:11434`). You can check it's running by visiting that
   URL in a browser -- it should say "Ollama is running".
3. Pull a model (this only needs to be done once; it downloads a few GB):

   ```powershell
   ollama pull llama3.2
   ```

   (`qwen2.5` is a good, lighter-weight alternative: `ollama pull qwen2.5`.)
4. In the app's **Settings**, confirm/adjust the **Ollama host** (default
   `http://localhost:11434`) and **Ollama model** (default `llama3.2`) to
   match whatever you pulled.

The AI layer lives entirely behind one small interface,
`app/integrations/ai_provider.py`'s `AIProvider` abstract class, with
`OllamaProvider` as the only implementation in v1. If you ever want to swap
in a paid API (OpenAI, Anthropic, etc.) later, you'd write one new class
implementing the same three methods (`summarize_email`, `suggest_quadrant`,
`smart_reminder_text`) -- nothing else in the app would need to change.

---

## 5. Building a Windows installer (`TaskOrganizer-Setup.exe`)

There are two ways to get an installer:

### Option A -- download the one CI already built (easiest)

Every push to this branch runs
[`.github/workflows/build-windows-installer.yml`](.github/workflows/build-windows-installer.yml)
on a real `windows-latest` GitHub Actions runner. It:

1. Installs the Python dependencies and PyInstaller.
2. Builds `dist/TaskOrganizer/TaskOrganizer.exe` using
   [`packaging/task_organizer.spec`](packaging/task_organizer.spec) (a
   one-folder build -- more reliable for PySide6 apps than `--onefile`).
3. Installs [Inno Setup](https://jrsoftware.org/isinfo.php) and compiles
   [`packaging/installer.iss`](packaging/installer.iss) into a proper Windows
   installer (Start Menu shortcut, optional desktop icon, uninstaller entry
   in "Add or Remove Programs") at `packaging/output/TaskOrganizer-Setup.exe`.
4. Uploads that installer as the workflow run's build artifact.

To get it: open the **Actions** tab on GitHub -> the latest
"Build Windows Installer" run -> download the `TaskOrganizer-Setup` artifact
(a zip containing `TaskOrganizer-Setup.exe`). Run that `.exe` on Windows like
any other installer.

You can also trigger a build on demand from the **Actions** tab via
"Run workflow" (`workflow_dispatch`), without needing a new commit.

### Option B -- build it yourself on a Windows machine

```powershell
pip install -r requirements.txt
pip install pyinstaller
pyinstaller --noconfirm --distpath dist --workpath build packaging\task_organizer.spec
```

This produces `dist\TaskOrganizer\TaskOrganizer.exe` (a folder you can zip and
share as-is, or run directly). To also get a proper installer `.exe`, install
[Inno Setup 6](https://jrsoftware.org/isdl.php), then run:

```powershell
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging\installer.iss
```

which writes `packaging\output\TaskOrganizer-Setup.exe`.

Notes:
- The app's data file (`~/.task_organizer/...` or your configured OneDrive
  folder) lives outside the installed app, so reinstalling/updating never
  touches your task data.
- If a fresh PyInstaller build fails to start, run
  `dist\TaskOrganizer\TaskOrganizer.exe` from a terminal to see the error --
  most failures are a missing `--hidden-import` for a PySide6/APScheduler/
  plyer plugin; add it to `hiddenimports` in `packaging/task_organizer.spec`.

---

## 6. Project structure

```
app/
  main.py                     entrypoint
  db.py                       SQLite schema + task/time-entry CRUD
  models.py                   Task / TimeEntry dataclasses, Eisenhower + status constants
  config.py                   JSON-backed app settings (sync folder, Ollama, Azure client id, notif prefs)
  notifications.py            APScheduler-based reminders/digests, best-effort Windows toasts
  sync.py                     OneDrive-folder-based "mobile sync" helpers
  ui/
    main_window.py            navigation shell + toolbar actions (new task, import/export, Outlook)
    dashboard.py               today / upcoming / overdue
    matrix_view.py             Eisenhower 4-quadrant drag-and-drop board
    task_dialog.py              add/edit task form (+ "Suggest with AI" button)
    time_tracker.py             per-task start/stop timer table
    reports_view.py             weekly report (+ pure build_weekly_report() function)
    settings_view.py            sync folder / Ollama / Azure / notification settings
  integrations/
    outlook_graph.py            MSAL device-code auth + list/convert emails
    teams_graph.py               MSAL-based Teams chat/channel reading, graceful permission errors
    excel_io.py                  .xlsx import/export (tasks + reports)
    ai_provider.py               AIProvider interface + OllamaProvider
tests/
  test_db.py                   task CRUD + time tracking
  test_excel_io.py              Excel round-trip + edge cases
  test_ai_provider.py            AI graceful-failure behavior
  test_ui_smoke.py               UI import + (if possible) construction smoke tests
requirements.txt
.gitignore
launcher.py                    PyInstaller entrypoint (outside the app/ package)
packaging/
  task_organizer.spec          PyInstaller build spec
  installer.iss                Inno Setup installer script
.github/workflows/
  build-windows-installer.yml  CI: builds TaskOrganizer-Setup.exe on windows-latest
```

## 7. Data & privacy

Everything -- your tasks, your database, your exported spreadsheets -- stays
on your own machine (and, if you opt in, in your own OneDrive). The Outlook
and Teams integrations only ever act as *you*, using a token you
personally approved via Microsoft's own sign-in page; this app never sees
your Microsoft password, and the AI features never send anything to a
third-party server since they run against a model on your own PC.
