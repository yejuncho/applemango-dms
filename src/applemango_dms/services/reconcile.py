from __future__ import annotations

import os
import stat
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Callable, Optional

from applemango_dms.services.file_operations import (
    FileOperationsService,
)

ProgressCallback = Callable[[dict], None]


class WorkspaceReconciliationService:
    """
    Workspace inventory and database reconciliation service.

    Scanning is read-only. Database writes occur only through the
    explicit apply methods.
    """

    WORKFLOW_PREVIEW = "preview"
    WORKFLOW_APPLIED = "applied"
    WORKFLOW_COMPLETED_WITH_ERRORS = (
        "completed_with_errors"
    )

    MANAGED_TRASH_DIRNAME = (
        FileOperationsService.WORKSPACE_TRASH_DIRNAME
    )
    UPLOAD_STAGING_PREFIX = ".__applemango_upload_"
    UPLOAD_STAGING_SUFFIX = ".part"

    def __init__(self, database):
        if database is None:
            raise ValueError("database is required.")

        required_methods = (
            "get_workspace_file_index",
            "insert_discovered_file_record",
            "reconcile_file_statuses",
        )

        missing_methods = [
            method_name
            for method_name in required_methods
            if not callable(
                getattr(
                    database,
                    method_name,
                    None,
                )
            )
        ]

        if missing_methods:
            missing_text = ", ".join(
                f"{name}()"
                for name in missing_methods
            )

            raise TypeError(
                "database must provide "
                f"{missing_text}."
            )

        self.database = database

    def reconcile_workspace(
        self,
        workspace_id,
        workspace_root,
        *,
        apply_changes=False,
        acting_user=None,
        progress_callback: Optional[
            ProgressCallback
        ] = None,
    ):
        """
        Run a complete workspace reconciliation workflow.

        When apply_changes is False, return a read-only preview.

        When apply_changes is True:
            1. scan the workspace;
            2. insert discovered records;
            3. scan again to verify the resulting state.

        Mutating reconciliation (apply_changes=True) requires an
        explicit acting_user for ownership assignment.
        """
        normalized_workspace_id = (
            self._normalize_workspace_id(
                workspace_id
            )
        )

        root_path = self._normalize_workspace_root(
            workspace_root
        )

        if not isinstance(apply_changes, bool):
            raise TypeError(
                "apply_changes must be a boolean."
            )

        normalized_acting_user = None
        if apply_changes:
            normalized_acting_user = (
                self._normalize_acting_user(
                    acting_user
                )
            )

        workflow = {
            "workspace_id":
                normalized_workspace_id,
            "workspace_root": str(root_path),
            "started_at":
                self._current_timestamp(),
            "completed_at": None,
            "apply_changes": apply_changes,
            "status": "running",
            "initial_scan": None,
            "apply_result": None,
            "verification_scan": None,
            "summary": {
                "files_scanned": 0,
                "database_records_checked": 0,
                "initial_matched_count": 0,
                "initial_unindexed_count": 0,
                "initial_missing_count": 0,
                "inserted_count": 0,
                "skipped_count": 0,
                "failed_count": 0,
                "marked_missing_count": 0,
                "restored_active_count": 0,
                "remaining_unindexed_count": 0,
                "remaining_missing_count": 0,
                "scan_error_count": 0,
                "verification_error_count": 0,
            },
        }

        self._emit_progress(
            progress_callback,
            {
                "event": "workflow_started",
                "workspace_id":
                    normalized_workspace_id,
                "workspace_root":
                    str(root_path),
                "apply_changes":
                    apply_changes,
            },
        )

        initial_scan = self.scan_workspace(
            normalized_workspace_id,
            root_path,
            progress_callback=progress_callback,
        )

        workflow["initial_scan"] = initial_scan

        workflow["summary"].update(
            {
                "files_scanned":
                    initial_scan["files_scanned"],
                "database_records_checked":
                    initial_scan[
                        "database_records_checked"
                    ],
                "initial_matched_count": len(
                    initial_scan["matched_files"]
                ),
                "initial_unindexed_count": len(
                    initial_scan["unindexed_files"]
                ),
                "initial_missing_count": len(
                    initial_scan[
                        "missing_from_storage"
                    ]
                ),
                "scan_error_count": len(
                    initial_scan["errors"]
                ),
            }
        )

        if not apply_changes:
            workflow["completed_at"] = (
                self._current_timestamp()
            )

            workflow["status"] = (
                self.WORKFLOW_COMPLETED_WITH_ERRORS
                if initial_scan["errors"]
                else self.WORKFLOW_PREVIEW
            )

            workflow["summary"][
                "remaining_unindexed_count"
            ] = len(
                initial_scan["unindexed_files"]
            )

            workflow["summary"][
                "remaining_missing_count"
            ] = len(
                initial_scan["missing_from_storage"]
            )

            self._emit_progress(
                progress_callback,
                {
                    "event": "workflow_completed",
                    "workspace_id":
                        normalized_workspace_id,
                    "apply_changes": False,
                    "status":
                        workflow["status"],
                    **workflow["summary"],
                },
            )

            return workflow

        apply_result = self.apply_unindexed_files(
            normalized_workspace_id,
            root_path,
            initial_scan,
            acting_user=normalized_acting_user,
            progress_callback=progress_callback,
        )

        workflow["apply_result"] = apply_result

        workflow["summary"].update(
            {
                "inserted_count":
                    apply_result["inserted_count"],
                "skipped_count":
                    apply_result["skipped_count"],
                "failed_count":
                    apply_result["failed_count"],
            }
        )

        status_reconciliation_result = (
            self.database.reconcile_file_statuses(
                normalized_workspace_id
            )
        )

        workflow[
            "status_reconciliation"
        ] = status_reconciliation_result

        workflow["summary"].update(
            {
                "marked_missing_count": int(
                    status_reconciliation_result.get(
                        "marked_missing",
                        0,
                    )
                ),
                "restored_active_count": int(
                    status_reconciliation_result.get(
                        "restored_active",
                        0,
                    )
                ),
            }
        )

        self._emit_progress(
            progress_callback,
            {
                "event": "status_reconciled",
                "workspace_id": normalized_workspace_id,
                "marked_missing": workflow["summary"][
                    "marked_missing_count"
                ],
                "restored_active": workflow["summary"][
                    "restored_active_count"
                ],
                "checked": int(
                    status_reconciliation_result.get(
                        "checked",
                        0,
                    )
                ),
            },
        )

        verification_scan = self.scan_workspace(
            normalized_workspace_id,
            root_path,
            progress_callback=progress_callback,
        )

        workflow[
            "verification_scan"
        ] = verification_scan

        workflow["summary"].update(
            {
                "remaining_unindexed_count": len(
                    verification_scan[
                        "unindexed_files"
                    ]
                ),
                "remaining_missing_count": len(
                    verification_scan[
                        "missing_from_storage"
                    ]
                ),
                "verification_error_count": len(
                    verification_scan["errors"]
                ),
            }
        )

        has_errors = any(
            (
                initial_scan["errors"],
                apply_result["failed_count"],
                verification_scan["errors"],
                int(
                    status_reconciliation_result.get(
                        "error_count",
                        0,
                    )
                    or 0
                ),
            )
        )

        workflow["status"] = (
            self.WORKFLOW_COMPLETED_WITH_ERRORS
            if has_errors
            else self.WORKFLOW_APPLIED
        )

        workflow["completed_at"] = (
            self._current_timestamp()
        )

        self._emit_progress(
            progress_callback,
            {
                "event": "workflow_completed",
                "workspace_id":
                    normalized_workspace_id,
                "apply_changes": True,
                "status": workflow["status"],
                **workflow["summary"],
            },
        )

        return workflow

    def scan_workspace(
        self,
        workspace_id,
        workspace_root,
        *,
        progress_callback: Optional[ProgressCallback] = None,
    ):
        normalized_workspace_id = self._normalize_workspace_id(workspace_id)
        root_path = self._normalize_workspace_root(workspace_root)

        report = {
            "workspace_id": normalized_workspace_id,
            "workspace_root": str(root_path),
            "started_at": self._current_timestamp(),
            "completed_at": None,
            "status": "running",
            "files_scanned": 0,
            "directories_scanned": 0,
            "total_size": 0,
            "database_records_checked": 0,
            "files": [],
            "matched_files": [],
            "unindexed_files": [],
            "missing_from_storage": [],
            "errors": [],
            "unreadable_directories": [],
            "unreadable_files": [],
        }

        database_index = self.database.get_workspace_file_index(
            normalized_workspace_id
        )

        report["database_records_checked"] = len(database_index)

        unmatched_database_paths = set(database_index)
        unreadable_scope_paths = set()
        unreadable_file_paths = set()
        root_scan_failed = False

        directory_stack = [root_path]

        while directory_stack:
            current_directory = directory_stack.pop()

            try:
                with os.scandir(current_directory) as entries:
                    report["directories_scanned"] += 1

                    for entry in entries:
                        normalized_entry_path = self._normalize_scanned_relative_path(
                            root_path,
                            entry.path,
                        )

                        try:
                            is_directory = entry.is_dir(
                                follow_symlinks=False
                            )
                            is_file = (
                                False
                                if is_directory
                                else entry.is_file(
                                    follow_symlinks=False
                                )
                            )
                        except OSError as exc:
                            if normalized_entry_path is not None:
                                unreadable_scope_paths.add(
                                    normalized_entry_path
                                )

                            error = self._build_error(
                                entry.path,
                                exc,
                            )
                            report["errors"].append(error)

                            self._emit_progress(
                                progress_callback,
                                {
                                    "event": "file_error",
                                    "workspace_id": normalized_workspace_id,
                                    "path": str(entry.path),
                                    "error": str(exc),
                                },
                            )
                            continue

                        if is_directory:
                            if self._is_excluded_directory_name(
                                entry.name
                            ):
                                continue

                            directory_stack.append(Path(entry.path))
                            continue

                        if not is_file:
                            continue

                        try:
                            if self._is_excluded_file_name(
                                entry.name
                            ):
                                continue

                            file_record = self._build_file_record(
                                root_path,
                                entry,
                            )

                            normalized_relative_path = (
                                self._normalize_relative_path(
                                    file_record["relative_path"]
                                )
                            )

                        except (OSError, ValueError) as exc:
                            if normalized_entry_path is not None:
                                unreadable_file_paths.add(
                                    normalized_entry_path
                                )

                            error = self._build_error(
                                entry.path,
                                exc,
                            )
                            report["errors"].append(error)

                            self._emit_progress(
                                progress_callback,
                                {
                                    "event": "file_error",
                                    "workspace_id": normalized_workspace_id,
                                    "path": str(entry.path),
                                    "error": str(exc),
                                },
                            )
                            continue

                        report["files"].append(file_record)
                        report["files_scanned"] += 1
                        report["total_size"] += file_record["file_size"]

                        database_record = database_index.get(
                            normalized_relative_path
                        )

                        if database_record is None:
                            report["unindexed_files"].append(
                                dict(file_record)
                            )

                            comparison_event = "unindexed_file"

                        else:
                            unmatched_database_paths.discard(
                                normalized_relative_path
                            )

                            report["matched_files"].append(
                                {
                                    "file": dict(file_record),
                                    "database_record": dict(
                                        database_record
                                    ),
                                }
                            )

                            comparison_event = "matched_file"

                        self._emit_progress(
                            progress_callback,
                            {
                                "event": comparison_event,
                                "workspace_id": normalized_workspace_id,
                                "relative_path": file_record["relative_path"],
                                "matched_count": len(
                                    report["matched_files"]
                                ),
                                "unindexed_count": len(
                                    report["unindexed_files"]
                                ),
                            },
                        )

                        self._emit_progress(
                            progress_callback,
                            {
                                "event": "file_scanned",
                                "workspace_id": normalized_workspace_id,
                                "files_scanned": report["files_scanned"],
                                "directories_scanned": report[
                                    "directories_scanned"
                                ],
                                "current_path": file_record["relative_path"],
                            },
                        )

            except OSError as exc:
                normalized_directory_path = self._normalize_scanned_relative_path(
                    root_path,
                    current_directory,
                )

                if normalized_directory_path is not None:
                    unreadable_scope_paths.add(
                        normalized_directory_path
                    )

                    if normalized_directory_path == "":
                        root_scan_failed = True

                error = self._build_error(
                    current_directory,
                    exc,
                )
                report["errors"].append(error)

                self._emit_progress(
                    progress_callback,
                    {
                        "event": "directory_error",
                        "workspace_id": normalized_workspace_id,
                        "path": str(current_directory),
                        "error": str(exc),
                    },
                )

        report["unreadable_directories"] = sorted(
            path or "."
            for path in unreadable_scope_paths
        )
        report["unreadable_files"] = sorted(
            unreadable_file_paths
        )

        for normalized_path in sorted(unmatched_database_paths):
            database_record = database_index[
                normalized_path
            ]

            if root_scan_failed:
                continue

            if self._is_path_covered_by_unreadable_scope(
                normalized_path,
                unreadable_scope_paths,
            ):
                continue

            if normalized_path in unreadable_file_paths:
                continue

            report["missing_from_storage"].append(
                dict(database_record)
            )

        report["completed_at"] = self._current_timestamp()
        report["status"] = (
            "completed_with_errors" if report["errors"] else "completed"
        )

        self._emit_progress(
            progress_callback,
            {
                "event": "scan_completed",
                "workspace_id": normalized_workspace_id,
                "files_scanned": report["files_scanned"],
                "directories_scanned": report["directories_scanned"],
                "total_size": report["total_size"],
                "database_records_checked": report[
                    "database_records_checked"
                ],
                "matched_count": len(report["matched_files"]),
                "unindexed_count": len(report["unindexed_files"]),
                "missing_from_storage_count": len(
                    report["missing_from_storage"]
                ),
                "error_count": len(report["errors"]),
                "status": report["status"],
            },
        )

        return report

    def apply_unindexed_files(
        self,
        workspace_id,
        workspace_root,
        scan_report,
        *,
        acting_user,
        progress_callback: Optional[
            ProgressCallback
        ] = None,
    ):
        """
        Insert unindexed filesystem records from a completed scan.

        Individual file failures are collected and do not stop the
        remaining records from being processed.
        """
        normalized_workspace_id = (
            self._normalize_workspace_id(
                workspace_id
            )
        )
        normalized_acting_user = (
            self._normalize_acting_user(
                acting_user
            )
        )
        root_path = self._normalize_workspace_root(
            workspace_root
        )

        if not isinstance(scan_report, dict):
            raise TypeError(
                "scan_report must be a dictionary."
            )

        report_workspace_id = (
            scan_report.get("workspace_id")
        )

        if report_workspace_id is None:
            raise ValueError(
                "scan_report is missing workspace_id."
            )

        normalized_report_workspace_id = (
            self._normalize_workspace_id(
                report_workspace_id
            )
        )

        if (
            normalized_report_workspace_id
            != normalized_workspace_id
        ):
            raise ValueError(
                "scan_report belongs to a different "
                "workspace."
            )

        self._require_matching_scan_report_root(
            scan_report,
            root_path,
        )

        scan_status = str(
            scan_report.get("status") or ""
        ).strip().lower()

        if scan_status not in {
            "completed",
            "completed_with_errors",
        }:
            raise ValueError(
                "Only a completed scan report can be "
                "applied."
            )

        unindexed_files = scan_report.get(
            "unindexed_files"
        )

        if not isinstance(unindexed_files, list):
            raise TypeError(
                "scan_report unindexed_files must be "
                "a list."
            )

        result = {
            "workspace_id":
                normalized_workspace_id,
            "started_at":
                self._current_timestamp(),
            "completed_at": None,
            "status": "running",
            "requested": len(unindexed_files),
            "inserted_count": 0,
            "skipped_count": 0,
            "failed_count": 0,
            "inserted": [],
            "skipped": [],
            "failed": [],
        }

        for index, file_record in enumerate(
            unindexed_files,
            start=1,
        ):
            relative_path = ""

            if isinstance(file_record, dict):
                relative_path = str(
                    file_record.get(
                        "relative_path"
                    )
                    or ""
                ).strip()

            self._emit_progress(
                progress_callback,
                {
                    "event": "apply_file_started",
                    "workspace_id":
                        normalized_workspace_id,
                    "index": index,
                    "total": len(
                        unindexed_files
                    ),
                    "relative_path":
                        relative_path,
                },
            )

            try:
                validated_candidate = (
                    self._validate_unindexed_candidate(
                        root_path,
                        file_record,
                    )
                )

                refreshed_file_record = (
                    validated_candidate[
                        "file_record"
                    ]
                )

                relative_path = str(
                    refreshed_file_record.get(
                        "relative_path"
                    )
                    or relative_path
                )

                database_result = (
                    self.database
                    .insert_discovered_file_record(
                        normalized_workspace_id,
                        refreshed_file_record,
                        acting_user=normalized_acting_user,
                    )
                )

                applied_record = {
                    "file_id": int(
                        database_result["file_id"]
                    ),
                    "relative_path": str(
                        database_result[
                            "relative_path"
                        ]
                    ),
                }

                if database_result["inserted"]:
                    result["inserted"].append(
                        applied_record
                    )
                    result["inserted_count"] += 1
                    event_name = "apply_file_inserted"

                else:
                    result["skipped"].append(
                        applied_record
                    )
                    result["skipped_count"] += 1
                    event_name = "apply_file_skipped"

                self._emit_progress(
                    progress_callback,
                    {
                        "event": event_name,
                        "workspace_id":
                            normalized_workspace_id,
                        "index": index,
                        "total": len(
                            unindexed_files
                        ),
                        "file_id":
                            applied_record["file_id"],
                        "relative_path":
                            applied_record[
                                "relative_path"
                            ],
                        "inserted_count":
                            result[
                                "inserted_count"
                            ],
                        "skipped_count":
                            result[
                                "skipped_count"
                            ],
                        "failed_count":
                            result[
                                "failed_count"
                            ],
                    },
                )

            except Exception as exc:
                failure = {
                    "relative_path":
                        relative_path,
                    "error_type":
                        type(exc).__name__,
                    "message": str(exc),
                }

                result["failed"].append(failure)
                result["failed_count"] += 1

                self._emit_progress(
                    progress_callback,
                    {
                        "event": "apply_file_failed",
                        "workspace_id":
                            normalized_workspace_id,
                        "index": index,
                        "total": len(
                            unindexed_files
                        ),
                        "relative_path":
                            relative_path,
                        "error_type":
                            failure["error_type"],
                        "message":
                            failure["message"],
                        "inserted_count":
                            result[
                                "inserted_count"
                            ],
                        "skipped_count":
                            result[
                                "skipped_count"
                            ],
                        "failed_count":
                            result[
                                "failed_count"
                            ],
                    },
                )

        result["completed_at"] = (
            self._current_timestamp()
        )

        result["status"] = (
            "completed_with_errors"
            if result["failed_count"]
            else "completed"
        )

        self._emit_progress(
            progress_callback,
            {
                "event": "apply_completed",
                "workspace_id":
                    normalized_workspace_id,
                "requested":
                    result["requested"],
                "inserted_count":
                    result["inserted_count"],
                "skipped_count":
                    result["skipped_count"],
                "failed_count":
                    result["failed_count"],
                "status": result["status"],
            },
        )

        return result

    def apply_from_scan_report(
        self,
        workspace_id,
        workspace_root,
        scan_report,
        *,
        acting_user,
        progress_callback: Optional[
            ProgressCallback
        ] = None,
    ):
        """
        Apply reconciliation using a previously completed scan report.

        This avoids re-scanning before apply and keeps apply semantics
        aligned with the reviewed preview result.
        """
        normalized_workspace_id = (
            self._normalize_workspace_id(
                workspace_id
            )
        )
        normalized_acting_user = (
            self._normalize_acting_user(
                acting_user
            )
        )

        root_path = self._normalize_workspace_root(
            workspace_root
        )

        if not isinstance(scan_report, dict):
            raise TypeError(
                "scan_report must be a dictionary."
            )

        report_workspace_id = (
            scan_report.get("workspace_id")
        )

        if report_workspace_id is None:
            raise ValueError(
                "scan_report is missing workspace_id."
            )

        normalized_report_workspace_id = (
            self._normalize_workspace_id(
                report_workspace_id
            )
        )

        if (
            normalized_report_workspace_id
            != normalized_workspace_id
        ):
            raise ValueError(
                "scan_report belongs to a different "
                "workspace."
            )

        self._require_matching_scan_report_root(
            scan_report,
            root_path,
        )

        scan_status = str(
            scan_report.get("status") or ""
        ).strip().lower()

        if scan_status not in {
            "completed",
            "completed_with_errors",
        }:
            raise ValueError(
                "Only a completed scan report can be "
                "applied."
            )

        workflow = {
            "workspace_id":
                normalized_workspace_id,
            "workspace_root": str(root_path),
            "started_at":
                self._current_timestamp(),
            "completed_at": None,
            "apply_changes": True,
            "status": "running",
            "initial_scan": dict(scan_report),
            "apply_result": None,
            "verification_scan": None,
            "summary": {
                "files_scanned": int(
                    scan_report.get("files_scanned")
                    or 0
                ),
                "database_records_checked": int(
                    scan_report.get(
                        "database_records_checked"
                    )
                    or 0
                ),
                "initial_matched_count": len(
                    scan_report.get("matched_files")
                    or []
                ),
                "initial_unindexed_count": len(
                    scan_report.get("unindexed_files")
                    or []
                ),
                "initial_missing_count": len(
                    scan_report.get(
                        "missing_from_storage"
                    )
                    or []
                ),
                "inserted_count": 0,
                "skipped_count": 0,
                "failed_count": 0,
                "marked_missing_count": 0,
                "restored_active_count": 0,
                "remaining_unindexed_count": 0,
                "remaining_missing_count": 0,
                "scan_error_count": len(
                    scan_report.get("errors")
                    or []
                ),
                "verification_error_count": 0,
            },
        }

        self._emit_progress(
            progress_callback,
            {
                "event": "workflow_started",
                "workspace_id":
                    normalized_workspace_id,
                "workspace_root":
                    str(root_path),
                "apply_changes": True,
                "source": "existing_scan",
            },
        )

        apply_result = self.apply_unindexed_files(
            normalized_workspace_id,
            root_path,
            scan_report,
            acting_user=normalized_acting_user,
            progress_callback=progress_callback,
        )

        workflow["apply_result"] = apply_result

        workflow["summary"].update(
            {
                "inserted_count":
                    apply_result["inserted_count"],
                "skipped_count":
                    apply_result["skipped_count"],
                "failed_count":
                    apply_result["failed_count"],
            }
        )

        status_reconciliation_result = (
            self.database.reconcile_file_statuses(
                normalized_workspace_id
            )
        )

        workflow[
            "status_reconciliation"
        ] = status_reconciliation_result

        workflow["summary"].update(
            {
                "marked_missing_count": int(
                    status_reconciliation_result.get(
                        "marked_missing",
                        0,
                    )
                ),
                "restored_active_count": int(
                    status_reconciliation_result.get(
                        "restored_active",
                        0,
                    )
                ),
            }
        )

        self._emit_progress(
            progress_callback,
            {
                "event": "status_reconciled",
                "workspace_id": normalized_workspace_id,
                "marked_missing": workflow["summary"][
                    "marked_missing_count"
                ],
                "restored_active": workflow["summary"][
                    "restored_active_count"
                ],
                "checked": int(
                    status_reconciliation_result.get(
                        "checked",
                        0,
                    )
                ),
            },
        )

        verification_scan = self.scan_workspace(
            normalized_workspace_id,
            root_path,
            progress_callback=progress_callback,
        )

        workflow[
            "verification_scan"
        ] = verification_scan

        workflow["summary"].update(
            {
                "remaining_unindexed_count": len(
                    verification_scan[
                        "unindexed_files"
                    ]
                ),
                "remaining_missing_count": len(
                    verification_scan[
                        "missing_from_storage"
                    ]
                ),
                "verification_error_count": len(
                    verification_scan["errors"]
                ),
            }
        )

        has_errors = any(
            (
                scan_report.get("errors"),
                apply_result["failed_count"],
                verification_scan["errors"],
                int(
                    status_reconciliation_result.get(
                        "error_count",
                        0,
                    )
                    or 0
                ),
            )
        )

        workflow["status"] = (
            self.WORKFLOW_COMPLETED_WITH_ERRORS
            if has_errors
            else self.WORKFLOW_APPLIED
        )

        workflow["completed_at"] = (
            self._current_timestamp()
        )

        self._emit_progress(
            progress_callback,
            {
                "event": "workflow_completed",
                "workspace_id":
                    normalized_workspace_id,
                "apply_changes": True,
                "status": workflow["status"],
                **workflow["summary"],
            },
        )

        return workflow

    def register_nas_only_item(
        self,
        workspace_id,
        workspace_root,
        file_record,
        *,
        acting_user,
        progress_callback: Optional[
            ProgressCallback
        ] = None,
    ):
        """
        Register one NAS-only item in a safe, idempotent way.

        This method validates that the candidate still exists on
        storage, then delegates record creation to the database
        insertion API used by bulk reconciliation apply.
        Newly inserted records are owned by acting_user.
        """
        normalized_workspace_id = (
            self._normalize_workspace_id(
                workspace_id
            )
        )
        normalized_acting_user = (
            self._normalize_acting_user(
                acting_user
            )
        )

        root_path = self._normalize_workspace_root(
            workspace_root
        )

        if not isinstance(file_record, dict):
            raise TypeError(
                "file_record must be a dictionary."
            )

        relative_path = str(
            file_record.get("relative_path")
            or ""
        ).strip()

        if not relative_path:
            raise ValueError(
                "file_record is missing relative_path."
            )

        normalized_relative_path = (
            self._normalize_relative_path(
                relative_path
            )
        )

        result = {
            "workspace_id": normalized_workspace_id,
            "workspace_root": str(root_path),
            "relative_path": relative_path,
            "normalized_relative_path": normalized_relative_path,
            "started_at": self._current_timestamp(),
            "completed_at": None,
            "status": "running",
            "inserted": False,
            "skipped": False,
            "file_id": None,
            "error": None,
        }

        self._emit_progress(
            progress_callback,
            {
                "event": "register_item_started",
                "workspace_id": normalized_workspace_id,
                "relative_path": relative_path,
            },
        )

        try:
            validated_candidate = (
                self._validate_unindexed_candidate(
                    root_path,
                    file_record,
                )
            )

            refreshed_file_record = (
                validated_candidate[
                    "file_record"
                ]
            )

            result["relative_path"] = str(
                refreshed_file_record[
                    "relative_path"
                ]
            )
            result["normalized_relative_path"] = str(
                validated_candidate[
                    "normalized_relative_path"
                ]
            )

            database_result = (
                self.database.insert_discovered_file_record(
                    normalized_workspace_id,
                    refreshed_file_record,
                    acting_user=normalized_acting_user,
                )
            )

            result["inserted"] = bool(
                database_result.get("inserted")
            )
            result["skipped"] = not result["inserted"]

            file_id_value = database_result.get("file_id")
            if file_id_value is not None:
                result["file_id"] = int(file_id_value)

            result["status"] = "completed"

            self._emit_progress(
                progress_callback,
                {
                    "event": "register_item_completed",
                    "workspace_id": normalized_workspace_id,
                    "relative_path": result["relative_path"],
                    "inserted": result["inserted"],
                    "skipped": result["skipped"],
                    "file_id": result["file_id"],
                },
            )

        except Exception as exc:
            result["status"] = "completed_with_errors"
            result["error"] = {
                "error_type": type(exc).__name__,
                "message": str(exc),
            }

            self._emit_progress(
                progress_callback,
                {
                    "event": "register_item_failed",
                    "workspace_id": normalized_workspace_id,
                    "relative_path": result["relative_path"],
                    "error_type": result["error"]["error_type"],
                    "message": result["error"]["message"],
                },
            )

        result["completed_at"] = self._current_timestamp()
        return result

    @classmethod
    def _build_file_record_from_path(
        cls,
        root_path,
        full_path,
        stat_result,
    ):
        relative_path = full_path.relative_to(
            root_path
        )

        return {
            "original_filename": full_path.name,
            "archived_filename": full_path.name,
            "relative_path": str(relative_path),
            "file_ext": full_path.suffix.lower(),
            "file_size": int(stat_result.st_size),
            "source_created_at": cls._timestamp_from_epoch(
                stat_result.st_ctime
            ),
            "source_modified_at": cls._timestamp_from_epoch(
                stat_result.st_mtime
            ),
        }

    @classmethod
    def _validate_unindexed_candidate(
        cls,
        workspace_root,
        file_record,
    ):
        if not isinstance(file_record, dict):
            raise TypeError(
                "file_record must be a dictionary."
            )

        relative_path = str(
            file_record.get("relative_path")
            or ""
        ).strip()

        if not relative_path:
            raise ValueError(
                "file_record is missing relative_path."
            )

        normalized_relative_path = (
            cls._normalize_relative_path(
                relative_path
            )
        )

        storage_path = (
            workspace_root
            / Path(relative_path)
        )

        try:
            stat_result = storage_path.lstat()
        except (FileNotFoundError, NotADirectoryError) as exc:
            raise FileNotFoundError(
                "Storage file is no longer available "
                "for registration."
            ) from exc

        if not stat.S_ISREG(stat_result.st_mode):
            raise ValueError(
                "Storage path is not a regular file "
                "for registration."
            )

        refreshed_file_record = cls._build_file_record_from_path(
            workspace_root,
            storage_path,
            stat_result,
        )

        return {
            "normalized_relative_path": normalized_relative_path,
            "file_record": refreshed_file_record,
        }

    @staticmethod
    def _build_file_record(root_path, directory_entry):
        stat_result = directory_entry.stat(follow_symlinks=False)

        full_path = Path(directory_entry.path)
        return WorkspaceReconciliationService._build_file_record_from_path(
            root_path,
            full_path,
            stat_result,
        )

    @classmethod
    def _is_excluded_directory_name(
        cls,
        directory_name,
    ):
        normalized_name = str(
            directory_name or ""
        ).strip().casefold()

        if not normalized_name:
            return False

        return (
            normalized_name
            == cls.MANAGED_TRASH_DIRNAME.casefold()
        )

    @classmethod
    def _is_excluded_file_name(
        cls,
        file_name,
    ):
        normalized_name = str(
            file_name or ""
        ).strip()

        if not normalized_name:
            return False

        return (
            normalized_name.startswith(
                cls.UPLOAD_STAGING_PREFIX
            )
            and normalized_name.endswith(
                cls.UPLOAD_STAGING_SUFFIX
            )
        )

    @staticmethod
    def _normalize_workspace_id(workspace_id):
        try:
            normalized = int(workspace_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("workspace_id must be an integer.") from exc

        if normalized <= 0:
            raise ValueError("workspace_id must be greater than zero.")

        return normalized

    @staticmethod
    def _normalize_workspace_root(workspace_root):
        if workspace_root is None:
            raise ValueError("workspace_root is required.")

        root_path = Path(workspace_root)

        if not root_path.exists():
            raise FileNotFoundError(f"Workspace path does not exist: {root_path}")

        if not root_path.is_dir():
            raise NotADirectoryError(
                f"Workspace path is not a directory: {root_path}"
            )

        return root_path

    @classmethod
    def _require_matching_scan_report_root(
        cls,
        scan_report,
        workspace_root,
    ):
        report_root = scan_report.get(
            "workspace_root"
        )

        if not str(report_root or "").strip():
            raise ValueError(
                "scan_report is missing workspace_root."
            )

        report_root_path = cls._normalize_workspace_root(
            report_root
        )

        if not cls._workspace_roots_match(
            workspace_root,
            report_root_path,
        ):
            raise ValueError(
                "scan_report belongs to a different "
                "workspace root."
            )

    @staticmethod
    def _workspace_root_identity(root_path):
        return os.path.normcase(
            os.path.normpath(
                os.path.abspath(
                    str(root_path)
                )
            )
        )

    @classmethod
    def _workspace_roots_match(
        cls,
        left_root,
        right_root,
    ):
        return (
            cls._workspace_root_identity(
                left_root
            )
            == cls._workspace_root_identity(
                right_root
            )
        )

    @staticmethod
    def _normalize_acting_user(acting_user):
        normalized = str(acting_user or "").strip()

        if not normalized:
            raise ValueError(
                "acting_user is required for "
                "reconciliation mutations."
            )

        return normalized

    @staticmethod
    def _normalize_relative_path(relative_path):
        normalized = str(relative_path or "").strip()

        if not normalized:
            raise ValueError("relative_path is required.")

        path = Path(normalized)

        if (
            path.is_absolute()
            or path.anchor
            or path.drive
            or path.root
            or ".." in path.parts
        ):
            raise ValueError(
                "relative_path must remain inside "
                "the workspace."
            )

        return path.as_posix().casefold()

    @classmethod
    def _normalize_scanned_relative_path(
        cls,
        root_path,
        path,
    ):
        try:
            relative_path = Path(path).relative_to(
                root_path
            )
        except ValueError:
            return None

        if str(relative_path) in {"", "."}:
            return ""

        try:
            return cls._normalize_relative_path(
                str(relative_path)
            )
        except ValueError:
            return None

    @staticmethod
    def _is_path_covered_by_unreadable_scope(
        normalized_relative_path,
        unreadable_directory_prefixes,
    ):
        if not unreadable_directory_prefixes:
            return False

        path_parts = PurePosixPath(
            normalized_relative_path
        ).parts

        for prefix in unreadable_directory_prefixes:
            if prefix == "":
                return True

            prefix_parts = PurePosixPath(prefix).parts

            if (
                len(prefix_parts)
                <= len(path_parts)
                and path_parts[: len(prefix_parts)]
                == prefix_parts
            ):
                return True

        return False

    @staticmethod
    def _timestamp_from_epoch(epoch_value):
        return datetime.fromtimestamp(epoch_value).isoformat(
            sep=" ",
            timespec="seconds",
        )

    @staticmethod
    def _current_timestamp():
        return datetime.now().isoformat(
            sep=" ",
            timespec="seconds",
        )

    @staticmethod
    def _build_error(path, exception):
        return {
            "path": str(path),
            "error_type": type(exception).__name__,
            "message": str(exception),
        }

    @staticmethod
    def _emit_progress(callback, event):
        if callback is None:
            return

        try:
            callback(dict(event))
        except Exception:
            # UI progress callbacks must never stop the scan.
            pass