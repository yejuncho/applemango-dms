# Applemango DMS

**Version 1.0.0**

Applemango DMS is a lightweight Windows desktop Document Management System built for organizations that store operational documents on a Synology NAS.

It provides a structured interface for saving, indexing, searching, managing, and reconciling documents while keeping the physical files on the organization's existing network storage.

The application combines NAS-based file storage with an SQLite metadata index so users can work with documents through meaningful information such as document date, document type, tags, uploader, and filename rather than navigating folders manually.

---

## v1.0.0

Version 1.0.0 is the first production-ready release of Applemango DMS.

The release includes the complete core document workflow:

- authenticated NAS access
- workspace discovery and designation
- network-drive mapping
- structured document upload
- automatic archive naming
- metadata indexing
- document search
- document detail and file operations
- workspace reconciliation
- document-type management
- local Demo Mode
- packaged Windows executable

Applemango DMS v1.0.0 is designed specifically for the organization's current Windows + Synology NAS environment.

---

## Core Features

### File Storage

Users can add individual files or entire folders to an active workspace.

Before a document is stored, the user can assign:

- document date
- document type
- tags

Uploaded documents are:

1. copied through a temporary staging file
2. verified with SHA-256
3. assigned a unique archive filename
4. published to the workspace
5. indexed in SQLite with metadata

The original filename is preserved in the database.

---

### Automatic File Naming

Archived files follow the general convention:

```text
YYYY-MM-DD_DocumentType_Tag_OriginalFilename.ext
```

For example:

```text
2026-07-16_Invoice_HQ_Invoice_348.pdf
```

Name collisions are resolved automatically without overwriting an existing archive file.

---

### File Search

The Search Files screen provides metadata-based document retrieval within the active workspace.

The main search can match user-facing metadata including:

- original filename
- archived filename
- document date
- document type
- tags
- uploaded by
- file extension

Search results are backed by SQLite rather than filesystem-name matching alone.

From a document result, users can inspect its metadata and perform supported file operations.

---

### File Operations

Supported document actions include:

- open file
- open containing folder
- copy file path
- rename archived file
- soft delete
- restore

File records use stable database IDs internally rather than relying on filenames as identity.

Deleted files are managed through the DMS lifecycle instead of being immediately destroyed.

---

### Workspace Sync

Workspace Sync reconciles the physical NAS workspace with the SQLite metadata index.

It can detect situations such as:

- a file exists on the NAS but has no DMS record
- a database record points to a file that is no longer present
- a previously missing file has returned

The synchronization workflow can then:

- register newly discovered NAS files
- mark unavailable records as `missing`
- restore returned files to `active`

The DMS Trash and internal working files are excluded from normal reconciliation.

This allows Applemango DMS to coexist with documents that were stored on the NAS before the DMS was introduced or that were added outside the application.

---

### Document Type Management

Document types are managed independently for each workspace.

Users can:

- add document types
- rename document types
- change their ordering
- deactivate or reactivate types

Document types are stored in SQLite and become part of the metadata assigned to archived documents.

---

### Workspace Management

A workspace represents a designated NAS shared folder.

Each workspace has:

- its own documents
- its own document types
- its own metadata scope
- its own reconciliation state

Available NAS shares can be discovered and designated through Workspace Settings.

The internal NAS share:

```text
database
```

is reserved for Applemango DMS system data and cannot be designated as a user workspace.

---

## Production Storage Architecture

In production, document files remain inside their designated Synology NAS shares.

The central metadata database is stored at:

```text
\\applemango\database\applemango.db
```

The `database` NAS share is reserved for internal Applemango DMS data.

A simplified architecture looks like:

```text
Windows Client
      │
      ▼
Applemango DMS
      │
      ├──── SQLite metadata ────> \\applemango\database\
      │
      └──── Documents ──────────> \\applemango\<workspace>\
```

Applemango DMS does not replace the NAS filesystem. It provides a structured document-management layer on top of it.

---

## Document Lifecycle

File records currently use three principal states:

```text
active
missing
deleted
```

### `active`

The document is registered and available.

### `missing`

The database record exists, but Workspace Sync cannot currently locate the corresponding physical file.

### `deleted`

The document has been soft-deleted through the DMS.

Workspace Sync can transition eligible records between `active` and `missing` when filesystem state changes.

---

## Metadata

Each indexed document may contain information such as:

- original filename
- archived filename
- document date
- document type
- tags
- uploader
- file extension
- MIME type
- file size
- SHA-256 checksum
- source-created timestamp
- source-modified timestamp
- archive timestamp
- relative workspace path
- lifecycle status

SQLite stores the authoritative metadata relationships, while the actual documents remain on the NAS filesystem.

---

## Demo Mode

Applemango DMS includes a local Demo Mode for development, demonstrations, and testing without connecting to the production NAS.

The repository contains bundled demo workspace seeds:

```text
demo/
└── workspaces/
    ├── workspace_A/
    ├── workspace_B/
    └── workspace_C/
```

At runtime, writable demo data is stored separately under:

```text
%LOCALAPPDATA%\ApplemangoDMS\demo
```

The bundled `demo/` directory acts only as initial seed data.

This separation ensures that packaged application resources remain read-only and that Demo Mode data survives application restarts.

---

## Windows Application Data

Writable local application data is stored under:

```text
%LOCALAPPDATA%\ApplemangoDMS
```

Packaged resources such as icons, fonts, logos, and demo seed files remain bundled with the application.

Production document and database storage remain on the NAS.

---

## Technology

Applemango DMS v1.0.0 is built with:

- Python 3.13
- Tkinter
- SQLite
- Pillow
- `resvg_py`
- PyInstaller

The application currently targets **Windows**.

Windows-specific functionality is used for NAS authentication, network-drive mapping, Explorer integration, file opening, and executable packaging.

---

## Repository Structure

```text
applemango-dms/
│
├── assets/
│   ├── fonts/
│   ├── icons/
│   └── logos/
│
├── demo/
│   └── workspaces/
│
├── docs/
│   ├── developer_notes/
│   └── mockups/
│
├── legacy/
│
├── scripts/
│   └── build_windows.ps1
│
├── src/
│   └── applemango_dms/
│       ├── db/
│       ├── debug/
│       ├── services/
│       ├── ui/
│       ├── utils/
│       ├── app.py
│       ├── config.py
│       ├── main.py
│       └── state.py
│
├── tests/
│
├── .gitignore
├── README.md
├── requirements.txt
└── requirements-dev.txt
```

---

## Running From Source

### 1. Create a virtual environment

From the repository root:

```powershell
python -m venv .venv
```

### 2. Activate it

```powershell
.\.venv\Scripts\Activate.ps1
```

### 3. Install runtime dependencies

```powershell
python -m pip install -r requirements.txt
```

For development and executable packaging:

```powershell
python -m pip install -r requirements-dev.txt
```

### 4. Run the application

Because the project uses a `src/` layout:

```powershell
$env:PYTHONPATH = "src"
python -m applemango_dms.main
```

---

## Building the Windows Executable

The repository includes a reproducible PowerShell build script.

First activate the repository virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Then run:

```powershell
.\scripts\build_windows.ps1
```

The script verifies the build environment and produces:

```text
dist\ApplemangoDMS.exe
```

The executable is built with PyInstaller in `onefile` + `windowed` mode and includes the required assets and Demo Mode seed files.

Generated PyInstaller files under `build/`, `dist/`, and `*.spec` are excluded from Git.

---

## Runtime Requirements

The packaged Windows executable does not require the end user to install Python separately.

When running from source, the Python dependencies are defined in:

```text
requirements.txt
```

Packaging/development dependencies are defined separately in:

```text
requirements-dev.txt
```

---

## NAS Requirements

Production operation assumes access to the configured Synology NAS:

```text
\\applemango
```

Users must have appropriate network access and NAS credentials.

The application depends on Windows networking capabilities for authentication and workspace drive mapping.

Demo Mode can be used when production NAS access is unavailable.

---

## v1.0.0 Scope

The first release focuses on dependable core document-management operations.

Included in v1.0.0:

- NAS login and connectivity
- workspace discovery/designation
- workspace drive mapping
- file and folder upload
- metadata capture
- automatic archive naming
- checksum verification
- SQLite indexing
- search
- file detail actions
- rename/delete/restore operations
- workspace reconciliation
- document-type management
- Demo Mode
- Windows onefile executable

Features such as OCR, full-text document-content indexing, document version history, advanced permissions, and comprehensive audit logging are outside the scope of v1.0.0.

---

## Current Platform Scope

Applemango DMS v1.0.0 is an internal Windows application designed around the organization's existing NAS infrastructure.

It is not currently intended as:

- a cross-platform application
- a public cloud DMS
- a multi-tenant service
- a browser-based application

Future versions may expand beyond the current deployment model.

---

## License

Applemango DMS is proprietary software developed for internal organizational document management.

All rights reserved.

---

## Author

Developed by **Yejun (Daniel) Cho**.