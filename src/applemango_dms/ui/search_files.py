import sqlite3
import subprocess
import sys
import tkinter as tk
import tkinter.font as tkfont
from calendar import monthrange
from datetime import date, datetime, timedelta
from pathlib import Path
import re
from tkinter import TclError, filedialog, messagebox
import applemango_dms.config as config
import applemango_dms.state as state
from applemango_dms.services.file_operations import FileOperationsService
from applemango_dms.ui.workplace_menu import render_workspace_sidebar_nav
from applemango_dms.ui.widgets import RoundedInput

try:
    from PIL import Image, ImageDraw, ImageTk
    _PIL_AVAILABLE = True
except Exception:
    Image = None
    ImageDraw = None
    ImageTk = None
    _PIL_AVAILABLE = False

from applemango_dms.ui import colors
from applemango_dms.utils.images import load_logo_photo, load_svg_photo

SF_SURFACE = colors.SURFACE_ALT
SF_BORDER = colors.BORDER_LIGHT
SF_SEARCH_BOX_BORDER = "#5C667F"
SF_SURFACE_HOVER_SOFT = colors.SURFACE_HOVER_SOFT
SF_RESULT_ROW_HOVER_BG = colors.SURFACE_ALT2
SF_RESULT_ROW_SELECTED_BG = colors.SURFACE_ALT2
SF_STATUS_PROCESSING = colors.PROCESSING
SF_TEXT_DARK = colors.TEXT_NEUTRAL_DARK
SF_TEXT_MAIN = colors.TEXT_EMPHASIS
SF_STATUS_FAILED = colors.FAILED_STRONG
SF_TEXT_PLACEHOLDER = colors.TEXT_PLACEHOLDER
SF_PRIMARY = colors.PRIMARY
SF_INPUT_IDLE_BORDER = colors.BORDER
SF_INPUT_FOCUS_BORDER = colors.PRIMARY_PRESSED
SF_NUMBER_DESIGNATION_BG = getattr(
    colors,
    "NUMBER_DESIGNATION_BG",
    colors.SURFACE_HOVER,
)

SF_RESULTS_PER_PAGE = 7
SF_FILTER_EXPANDED_ROW_REDUCTION = 3
SF_VISIBLE_PAGE_BUTTONS = 5
SF_CALENDAR_WEEKDAYS = (
    "월",
    "화",
    "수",
    "목",
    "금",
    "토",
    "일",
)


def _parse_svg_dimension(raw_text):
    text = str(raw_text or "").strip().lower()

    if not text:
        return None

    if text.endswith("px"):
        text = text[:-2].strip()

    match = re.match(r"^([0-9]+(?:\.[0-9]+)?)", text)
    if not match:
        return None

    try:
        value = float(match.group(1))
    except ValueError:
        return None

    if value <= 0:
        return None

    return max(1, int(round(value)))


def _extract_svg_attr(svg_text, attr_name):
    patterns = (
        rf"\b{attr_name}\s*=\s*\"([^\"]+)\"",
        rf"\b{attr_name}\s*=\s*'([^']+)'",
    )

    for pattern in patterns:
        match = re.search(pattern, svg_text, flags=re.IGNORECASE)
        if match:
            return str(match.group(1)).strip()

    return None


def _read_svg_intrinsic_size(icon_path):
    fallback_width = 24
    fallback_height = 24

    try:
        source = Path(icon_path).read_text(encoding="utf-8")
    except Exception:
        return fallback_width, fallback_height

    width = _parse_svg_dimension(_extract_svg_attr(source, "width"))
    height = _parse_svg_dimension(_extract_svg_attr(source, "height"))

    view_box_text = _extract_svg_attr(source, "viewBox")
    if view_box_text:
        parts = re.split(r"\s+|,", view_box_text.strip())
        if len(parts) == 4:
            try:
                vb_width = float(parts[2])
                vb_height = float(parts[3])
                if vb_width > 0 and width is None:
                    width = int(round(vb_width))
                if vb_height > 0 and height is None:
                    height = int(round(vb_height))
            except ValueError:
                pass

    if width is None and height is None:
        return fallback_width, fallback_height

    if width is None:
        width = height
    if height is None:
        height = width

    return max(1, int(width)), max(1, int(height))

def show_search_files_screen(app):
    shell = app._create_workspace_shell()
    app.root.title("애플망고 DMS - 파일 검색")

    render_workspace_sidebar_nav(app, shell["sidebar"], "search")

    outer = shell["content"]
    app._build_workspace_page_header(outer, "파일 검색", "저장된 필요한 파일을 빠르게 찾고 열람하거나 관리할 수 있어요.")

    board = tk.Frame(outer, bg=SF_SURFACE, highlightthickness=0, bd=0)
    board.pack(fill="both", expand=True, padx=0, pady=0)

    gap = 15

    split = tk.Frame(board, bg=SF_SURFACE)
    split.pack(fill="both", expand=True, padx=gap, pady=0)
    split.grid_columnconfigure(0, weight=39, uniform="search_cols")
    split.grid_columnconfigure(1, weight=11, uniform="search_cols")
    split.grid_rowconfigure(0, weight=1)

    left_col = tk.Frame(split, bg=SF_SURFACE, highlightthickness=0, bd=0)
    left_col.grid(row=0, column=0, sticky="nsew", padx=(0, gap))

    left_top_card = tk.Canvas(left_col, bg=SF_SURFACE, highlightthickness=0, bd=0)

    left_bottom_card = tk.Canvas(left_col, bg=SF_SURFACE, highlightthickness=0, bd=0)
    left_bottom_card.configure(
        takefocus=True,
    )

    right_card = tk.Canvas(split, bg=SF_SURFACE, highlightthickness=0, bd=0)
    right_card.grid(row=0, column=1, sticky="nsew")

    search_placeholder_text = "파일명, 문서 유형, 태그, 업로더 등으로 검색할 수 있어요."
    search_result_count_var = tk.StringVar(value="0건")
    search_var = tk.StringVar(value="")
    search_box_inset = 15
    # Horizontal insets for the two left cards.
    # Increase left_cards_left_inset to grow the gap from the sidebar side.
    left_cards_left_inset = 6
    left_cards_right_inset = 0
    search_box_height = 48
    filter_row_top_gap = 10
    filter_row_height = 30
    filter_content_top_gap = 8
    filter_content_height = 228
    filter_content_bottom_padding = 14

    search_box_holder = tk.Frame(left_top_card, bg=colors.SURFACE_ALT, highlightthickness=0, bd=0)
    search_input_holder = tk.Frame(
        search_box_holder,
        bg=colors.SURFACE_ALT,
        highlightthickness=0,
        bd=0,
    )

    icon_size = 20
    icon_gap = 4
    icon_padding = (7, 7)
    search_icon_photo = load_svg_photo(
        config.PROJECT_ROOT / "assets" / "icons" / "workspace" / "search_files" / "search.svg",
        max_width=icon_size,
        max_height=icon_size,
    )
    clear_icon_photo = load_svg_photo(
        config.PROJECT_ROOT / "assets" / "icons" / "workspace" / "search_files" / "exit.svg",
        max_width=icon_size,
        max_height=icon_size,
    )
    expand_icon_photo = load_svg_photo(
        config.PROJECT_ROOT / "assets" / "icons" / "workspace" / "search_files" / "expand.svg",
        max_width=18,
        max_height=18,
    )
    collapse_icon_photo = load_svg_photo(
        config.PROJECT_ROOT / "assets" / "icons" / "workspace" / "search_files" / "collapse.svg",
        max_width=18,
        max_height=18,
    )
    to_icon_photo = load_svg_photo(
        config.PROJECT_ROOT / "assets" / "icons" / "workspace" / "search_files" / "to.svg",
        max_width=14,
        max_height=14,
    )
    calendar_icon_photo = load_svg_photo(
        config.PROJECT_ROOT / "assets" / "icons" / "workspace" / "search_files" / "calendar.svg",
        max_width=14,
        max_height=14,
    )
    far_before_icon_path = (
        config.PROJECT_ROOT
        / "assets"
        / "icons"
        / "workspace"
        / "search_files"
        / "far_before.svg"
    )
    before_icon_path = (
        config.PROJECT_ROOT
        / "assets"
        / "icons"
        / "workspace"
        / "search_files"
        / "before.svg"
    )
    after_icon_path = (
        config.PROJECT_ROOT
        / "assets"
        / "icons"
        / "workspace"
        / "search_files"
        / "after.svg"
    )
    far_after_icon_path = (
        config.PROJECT_ROOT
        / "assets"
        / "icons"
        / "workspace"
        / "search_files"
        / "far_after.svg"
    )

    far_before_w, far_before_h = _read_svg_intrinsic_size(far_before_icon_path)
    before_w, before_h = _read_svg_intrinsic_size(before_icon_path)
    after_w, after_h = _read_svg_intrinsic_size(after_icon_path)
    far_after_w, far_after_h = _read_svg_intrinsic_size(far_after_icon_path)

    far_before_icon_photo = load_svg_photo(
        far_before_icon_path,
        max_width=far_before_w,
        max_height=far_before_h,
    )
    before_icon_photo = load_svg_photo(
        before_icon_path,
        max_width=before_w,
        max_height=before_h,
    )
    after_icon_photo = load_svg_photo(
        after_icon_path,
        max_width=after_w,
        max_height=after_h,
    )
    far_after_icon_photo = load_svg_photo(
        far_after_icon_path,
        max_width=far_after_w,
        max_height=far_after_h,
    )

    result_reset_icon_photo = load_svg_photo(
        config.PROJECT_ROOT / "assets" / "icons" / "workspace" / "save_files" / "reset.svg",
        max_width=18,
        max_height=18,
        tint=SF_TEXT_DARK,
    )
    toolbar_download_blue_icon_photo = load_svg_photo(
        config.PROJECT_ROOT / "assets" / "icons" / "workspace" / "search_files" / "download_blue.svg",
        max_width=14,
        max_height=14,
    )

    detail_action_icon_size = 16
    open_file_button_icon = load_svg_photo(
        config.PROJECT_ROOT / "assets" / "icons" / "workspace" / "search_files" / "open_file.svg",
        max_width=detail_action_icon_size,
        max_height=detail_action_icon_size,
        tint=colors.TEXT_INVERSE,
    )
    open_folder_button_icon = load_svg_photo(
        config.PROJECT_ROOT / "assets" / "icons" / "workspace" / "search_files" / "open_folder.svg",
        max_width=detail_action_icon_size,
        max_height=detail_action_icon_size,
        tint=SF_PRIMARY,
    )
    download_button_icon = load_svg_photo(
        config.PROJECT_ROOT / "assets" / "icons" / "workspace" / "search_files" / "download.svg",
        max_width=detail_action_icon_size,
        max_height=detail_action_icon_size,
        tint=colors.TEXT_INVERSE,
    )
    copy_path_button_icon = load_svg_photo(
        config.PROJECT_ROOT / "assets" / "icons" / "workspace" / "search_files" / "copy_path.svg",
        max_width=detail_action_icon_size,
        max_height=detail_action_icon_size,
        tint=SF_PRIMARY,
    )

    file_icon_dir = config.PROJECT_ROOT / "assets" / "icons" / "file_formats"
    detail_file_format_icons = {
        "word": load_logo_photo(file_icon_dir / "icons8-word-48.png", max_width=18, max_height=18),
        "txt": load_logo_photo(file_icon_dir / "icons8-txt-48.png", max_width=18, max_height=18),
        "pdf": load_logo_photo(file_icon_dir / "icons8-pdf-48.png", max_width=18, max_height=18),
        "excel": load_logo_photo(file_icon_dir / "icons8-excel-48.png", max_width=18, max_height=18),
        "csv": load_logo_photo(file_icon_dir / "icons8-csv-48.png", max_width=18, max_height=18),
        "powerpoint": load_logo_photo(file_icon_dir / "icons8-powerpoint-48.png", max_width=18, max_height=18),
        "image": load_logo_photo(file_icon_dir / "icons8-image-file-48.png", max_width=18, max_height=18),
        "folder": load_logo_photo(file_icon_dir / "icons8-folder-48.png", max_width=18, max_height=18),
        "archive_folder": load_logo_photo(file_icon_dir / "icons8-archive-folder-48.png", max_width=18, max_height=18),
        "video": load_logo_photo(file_icon_dir / "icons8-video-48.png", max_width=18, max_height=18),
        "audio": load_logo_photo(file_icon_dir / "icons8-audio-48.png", max_width=18, max_height=18),
        "exe": load_logo_photo(file_icon_dir / "icons8-exe-48.png", max_width=18, max_height=18),
        "design": load_logo_photo(file_icon_dir / "icons8-design-48.png", max_width=18, max_height=18),
        "db": load_logo_photo(file_icon_dir / "icons8-db-48.png", max_width=18, max_height=18),
        "html": load_logo_photo(file_icon_dir / "icons8-html-48.png", max_width=18, max_height=18),
        "file": load_logo_photo(file_icon_dir / "icons8-file-48.png", max_width=18, max_height=18),
    }

    filter_row = tk.Frame(left_top_card, bg=colors.SURFACE_ALT, highlightthickness=0, bd=0)
    filter_label = tk.Label(
        filter_row,
        text="상세 필터",
        bg=colors.SURFACE_ALT,
        fg=SF_TEXT_DARK,
        font=app._font(11, "bold"),
        anchor="w",
    )
    filter_content_clip = tk.Frame(left_top_card, bg=colors.SURFACE_ALT, highlightthickness=0, bd=0)
    filter_content_inner = tk.Frame(filter_content_clip, bg=colors.SURFACE_ALT, highlightthickness=0, bd=0)

    filter_column_specs = [
        ("문서 날짜", 18),
        ("문서 유형", 9),
        ("파일 종류", 9),
        ("업로드한 사람", 9),
    ]

    filter_content_inner.grid_rowconfigure(0, weight=1)
    for idx, (_title, weight) in enumerate(filter_column_specs):
        filter_content_inner.grid_columnconfigure(idx, weight=weight, uniform="filter_cols")

    filter_col_frames = []
    for idx, (title, _weight) in enumerate(filter_column_specs):
        col_frame = tk.Frame(filter_content_inner, bg=colors.SURFACE_ALT, highlightthickness=0, bd=0)
        col_frame.grid(row=0, column=idx, sticky="nsew", padx=(0 if idx == 0 else 8, 0), pady=(0, 0))
        col_frame.grid_columnconfigure(0, weight=1)

        header_label = tk.Label(
            col_frame,
            text=title,
            bg=colors.SURFACE_ALT,
            fg=SF_TEXT_DARK,
            font=app._font(10, "bold"),
            anchor="w",
            justify="left",
        )
        header_label.grid(row=0, column=0, sticky="w", padx=(2, 0), pady=(0, 8))
        filter_col_frames.append(col_frame)

    date_from_var = tk.StringVar(value="")
    date_to_var = tk.StringVar(value="")
    doc_type_var = tk.StringVar(value="")
    file_type_var = tk.StringVar(value="")
    uploader_var = tk.StringVar(value="")

    search_state = {
        "results": [],
        "total_count": 0,
        "query": None,
        "database_filters": None,
        "selected_file_id": None,
        "selected_file_ids": set(),
        "is_searching": False,
        "is_loading_page": False,
        "has_searched": False,
        "error": None,
    }

    document_type_records = []
    document_type_name_to_id = {}
    doc_type_options = []

    workspace_id = getattr(state, "active_workspace_id", None)
    file_operations = FileOperationsService(app.db)

    try:
        document_type_records = app.db.get_document_types(
            workspace_id
        )

        document_type_name_to_id = {
            record["name"]: int(record["id"])
            for record in document_type_records
        }

        doc_type_options = [
            record["name"]
            for record in document_type_records
        ]

    except Exception as exc:
        print(
            "Unable to load workspace document types:",
            exc,
        )

    file_type_options = [
        ".doc", ".docx", ".txt", ".pdf", ".xls", ".xlsx", ".xlsm", ".csv", ".ppt", ".pptx", ".pptm",
        ".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff", ".webp", ".svg",
        ".zip", ".7z", ".rar", ".tar", ".gz",
        ".mp4", ".mov", ".avi", ".wmv", ".mkv",
        ".mp3", ".wma", ".m4a",
        ".exe", ".msi", ".bat", ".cmd",
        ".psd", ".ai", ".indd", ".xd",
        ".db", ".sqlite", ".mdb", ".accdb",
        ".html", ".htm",
    ]

    dropdown_state = {
        "doc_type_expanded": False,
        "file_type_expanded": False,
        "doc_type_popup": None,
        "file_type_popup": None,
    }
    calendar_popup_state = {
        "popup": None,
        "field_kind": None,
        "display_year": None,
        "display_month": None,
    }

    filter_panel_state = {
        "expanded": False,
        "target_expanded": False,
        "current_top_height": 0.0,
        "anim_job": None,
        "anim_start_height": 0.0,
        "anim_target_height": 0.0,
        "anim_start_time": 0.0,
        "anim_duration_ms": 220,
    }
    layout_state = {
        "retry_job": None,
        "initial_layout_job": None,
    }
    screen_lifecycle = {
        "destroyed": False,
    }

    result_table_state = {
        "select_all_checked": False,
        "page_index": 0,
        "rows_per_page": SF_RESULTS_PER_PAGE,
        "base_row_height": None,
        "hovered_file_id": None,
    }
    result_sort_state = {
        "key": None,
        "direction": None,
    }

    result_table_icons = {
        "unchecked": load_svg_photo(
            config.PROJECT_ROOT / "assets" / "icons" / "workspace" / "search_files" / "unchecked.svg",
            max_width=14,
            max_height=14,
        ),
        "checked": load_svg_photo(
            config.PROJECT_ROOT / "assets" / "icons" / "workspace" / "search_files" / "checked.svg",
            max_width=14,
            max_height=14,
        ),
    }

    search_action_button = None

    def _is_search_screen_alive():
        if screen_lifecycle["destroyed"]:
            return False

        for widget in (board, split, left_col, left_top_card, left_bottom_card, right_card):
            try:
                if widget is None or not widget.winfo_exists():
                    return False
            except TclError:
                return False

        return True

    def _is_descendant_of(widget, ancestor):
        current = widget
        while current is not None:
            if current is ancestor:
                return True
            current = getattr(current, "master", None)
        return False

    def _on_click_outside_search_box(event):
        if not board.winfo_exists():
            return

        if (
            search_state["selected_file_id"] is not None
            and not _is_result_row_click_event(event)
            and not _is_detail_card_click_event(event)
        ):
            _clear_detail_selection()

        calendar_popup = calendar_popup_state.get(
            "popup"
        )

        if (
            calendar_popup is not None
            and calendar_popup.winfo_exists()
            and _is_descendant_of(
                event.widget,
                calendar_popup,
            )
        ):
            return

        for popup_key in ("doc_type_popup", "file_type_popup"):
            popup = dropdown_state.get(popup_key)
            if popup is not None and popup.winfo_exists() and _is_descendant_of(event.widget, popup):
                return

        input_ancestors = [
            search_box_holder,
            date_from_field["canvas"],
            date_to_field["canvas"],
            doc_type_field["canvas"],
            file_type_field["canvas"],
            uploader_field["canvas"],
            date_quick_row,
        ]
        for ancestor in input_ancestors:
            if _is_descendant_of(event.widget, ancestor):
                return

        focused = app.root.focus_get()
        editable_widgets = {
            search_text_entry,
            date_from_field["entry"],
            date_to_field["entry"],
            doc_type_field["entry"],
            file_type_field["entry"],
            uploader_field["entry"],
        }
        if focused in editable_widgets:
            board.focus_set()

        _close_dropdown_popup("doc_type")
        _close_dropdown_popup("file_type")
        _set_dropdown_icon(
            doc_type_field["toggle"],
            False,
        )
        _set_dropdown_icon(
            file_type_field["toggle"],
            False,
        )
        _close_calendar_popup()

    def _is_result_row_click_event(event):
        widget = getattr(event, "widget", None)
        if widget is not left_bottom_card:
            return False

        try:
            current_items = widget.find_withtag("current")
        except TclError:
            return False

        hit_items = list(current_items)

        # After a row click, the table is re-drawn immediately, so the
        # transient Tk "current" tag may be empty by the time the root-level
        # click handler runs. Fall back to geometry hit-testing at the click
        # coordinates to preserve row selection behavior.
        if not hit_items:
            try:
                click_x = int(getattr(event, "x", -1))
                click_y = int(getattr(event, "y", -1))
                if click_x >= 0 and click_y >= 0:
                    hit_items = list(
                        widget.find_overlapping(
                            click_x,
                            click_y,
                            click_x,
                            click_y,
                        )
                    )
            except (TclError, TypeError, ValueError):
                hit_items = []

        for item_id in hit_items:
            tags = widget.gettags(item_id)
            for tag in tags:
                if tag.startswith("sf_result_row_") or tag.startswith("sf_result_check_"):
                    return True

        return False

    def _is_detail_card_click_event(event):
        widget = getattr(event, "widget", None)
        return widget is right_card

    def _start_search_placeholder():
        search_text_entry.focus_set()

    def _clear_search_text():
        search_var.set("")
        search_text_entry.focus_set()

    def _collect_search_filters():
        return {
            "query": search_var.get().strip(),
            "date_from": date_from_var.get().strip(),
            "date_to": date_to_var.get().strip(),
            "document_type": doc_type_var.get().strip(),
            "file_type": file_type_var.get().strip(),
            "uploaded_by": uploader_var.get().strip(),
        }

    def _normalize_search_filters(raw_filters):
        normalized = dict(raw_filters)

        for key, value in normalized.items():
            if isinstance(value, str):
                normalized[key] = value.strip()

        if normalized["date_from"] == "-":
            normalized["date_from"] = ""

        if normalized["date_to"] == "-":
            normalized["date_to"] = ""

        selected_document_type = normalized.pop(
            "document_type",
            "",
        )

        if selected_document_type == "모든 문서 유형":
            selected_document_type = ""

        normalized["document_type_id"] = (
            document_type_name_to_id.get(
                selected_document_type
            )
            if selected_document_type
            else None
        )

        if normalized["file_type"] == "모든 파일 종류":
            normalized["file_type"] = ""

        return normalized

    def _build_database_filters(filters):
        (
            normalized_date_from,
            normalized_date_to,
        ) = _normalize_search_date_range(
            filters["date_from"],
            filters["date_to"],
        )

        return {
            "document_date_from": (
                normalized_date_from
            ),
            "document_date_to": (
                normalized_date_to
            ),
            "document_type_id": (
                filters["document_type_id"]
            ),
            "uploaded_by": (
                filters["uploaded_by"] or None
            ),
            "file_ext": (
                filters["file_type"] or None
            ),
        }

    def _reset_search_selection():
        search_state["selected_file_id"] = None
        search_state["selected_file_ids"].clear()

        result_table_state["select_all_checked"] = False
        result_table_state["hovered_file_id"] = None
        result_table_state["page_index"] = 0

    def _reset_search_screen():
        search_var.set("")
        date_from_var.set("")
        date_to_var.set("")
        doc_type_var.set("")
        file_type_var.set("")
        uploader_var.set("")

        search_state["results"] = []
        search_state["total_count"] = 0
        search_state["query"] = None
        search_state["database_filters"] = None
        search_state["error"] = None
        search_state["is_searching"] = False
        search_state["is_loading_page"] = False
        search_state["has_searched"] = False

        result_sort_state["key"] = None
        result_sort_state["direction"] = None

        _reset_search_selection()

        _close_dropdown_popup("doc_type")
        _close_dropdown_popup("file_type")
        _close_calendar_popup()

        _set_dropdown_icon(
            doc_type_field["toggle"],
            False,
        )
        _set_dropdown_icon(
            file_type_field["toggle"],
            False,
        )

        _set_quick_button_state(None)

        search_result_count_var.set(
            "0건"
        )

        _draw_results_table()
        _draw_file_details()

        search_text_entry.focus_set()

    def _set_search_busy(is_busy):
        busy = bool(is_busy)

        search_state["is_loading_page"] = busy

        if search_action_button is not None:
            search_action_button.set_enabled(
                not busy
            )

    def _load_search_page(
        page_index,
        *,
        clear_detail=True,
    ):
        normalized_page_index = max(
            0,
            int(page_index),
        )

        rows_per_page = max(
            1,
            int(result_table_state["rows_per_page"]),
        )
        offset = normalized_page_index * rows_per_page

        page = app.db.search_files_page(
            workspace_id,
            search_text=search_state["query"],
            search_field="all",
            filters=search_state["database_filters"],
            statuses=None,
            sort_field=result_sort_state["key"],
            sort_direction=result_sort_state["direction"],
            limit=rows_per_page,
            offset=offset,
        )

        search_state["error"] = None

        search_state["results"] = list(
            page["results"]
        )
        search_state["total_count"] = int(
            page["total_count"]
        )

        result_table_state["page_index"] = (
            normalized_page_index
        )
        result_table_state["hovered_file_id"] = None
        result_table_state["select_all_checked"] = False

        if clear_detail:
            search_state["selected_file_id"] = None

        search_result_count_var.set(
            f"{search_state['total_count']}건"
        )

        _clamp_result_page()

    def _request_search_page(
        page_index,
        *,
        clear_detail=True,
        redraw=True,
    ):
        if search_state["is_loading_page"]:
            return False

        previous_results = list(
            search_state["results"]
        )
        previous_total_count = int(
            search_state["total_count"] or 0
        )
        previous_page_index = int(
            result_table_state["page_index"]
        )
        previous_selected_file_id = (
            search_state["selected_file_id"]
        )

        _set_search_busy(True)

        try:
            _load_search_page(
                page_index,
                clear_detail=clear_detail,
            )

        except (
            ValueError,
            TypeError,
            LookupError,
            sqlite3.Error,
        ) as exc:
            search_state["results"] = previous_results
            search_state["total_count"] = (
                previous_total_count
            )
            result_table_state["page_index"] = (
                previous_page_index
            )
            search_state["selected_file_id"] = (
                previous_selected_file_id
            )
            search_state["error"] = str(exc)

            print("Search page load failed:", exc)
            return False

        except Exception as exc:
            search_state["results"] = previous_results
            search_state["total_count"] = (
                previous_total_count
            )
            result_table_state["page_index"] = (
                previous_page_index
            )
            search_state["selected_file_id"] = (
                previous_selected_file_id
            )
            search_state["error"] = str(exc)

            print(
                "Unexpected search page error:",
                exc,
            )
            return False

        finally:
            _set_search_busy(False)

            if redraw:
                _draw_results_table()
                _draw_file_details()

        return True

    def _run_search(_event=None):
        if search_state["is_searching"]:
            return "break"

        _close_calendar_popup()

        search_state["is_searching"] = True
        search_state["error"] = None

        if search_action_button is not None:
            search_action_button.set_enabled(False)

        try:
            search_state["has_searched"] = True

            raw_filters = _collect_search_filters()
            filters = _normalize_search_filters(
                raw_filters
            )
            database_filters = (
                _build_database_filters(filters)
            )

            search_state["query"] = (
                filters["query"] or None
            )
            search_state["database_filters"] = (
                database_filters
            )

            result_sort_state["key"] = None
            result_sort_state["direction"] = None

            _reset_search_selection()

            _load_search_page(
                0,
                clear_detail=True,
            )

            print(
                "Search request:",
                {
                    "search_text": filters["query"],
                    "filters": database_filters,
                },
            )
            print("Search page loaded.")

        except (
            ValueError,
            TypeError,
            LookupError,
            sqlite3.Error,
        ) as exc:
            search_state["results"] = []
            search_state["total_count"] = 0
            search_state["query"] = None
            search_state["database_filters"] = None

            result_sort_state["key"] = None
            result_sort_state["direction"] = None

            search_state["error"] = str(exc)
            _reset_search_selection()

            search_result_count_var.set("0건")

            print("Search failed:", exc)

        except Exception as exc:
            search_state["results"] = []
            search_state["total_count"] = 0
            search_state["query"] = None
            search_state["database_filters"] = None

            result_sort_state["key"] = None
            result_sort_state["direction"] = None

            search_state["error"] = str(exc)
            _reset_search_selection()

            search_result_count_var.set("0건")

            print("Unexpected search error:", exc)

        finally:
            search_state["is_searching"] = False

            if search_action_button is not None:
                search_action_button.set_enabled(True)

            _draw_results_table()
            _draw_file_details()

        return "break"

    def is_leap_year(year_value):
        return (year_value % 4 == 0 and year_value % 100 != 0) or (year_value % 400 == 0)

    def max_day_for_month(year_value, month_value):
        if month_value in (1, 3, 5, 7, 8, 10, 12):
            return 31
        if month_value in (4, 6, 9, 11):
            return 30
        if month_value == 2:
            return 29 if is_leap_year(year_value) else 28
        return 31

    def _normalize_search_date(
        value,
        *,
        field_name,
        is_end_date,
    ):
        today_value = date.today()

        def _clamp_to_today(iso_text):
            try:
                parsed_date = datetime.strptime(
                    iso_text,
                    "%Y-%m-%d",
                ).date()
            except ValueError:
                return iso_text

            if parsed_date > today_value:
                return today_value.isoformat()

            return iso_text

        text = str(value or "").strip()

        if not text or text == "-":
            return None

        parts = text.split("-")

        try:
            if len(parts) == 1:
                year_value = int(parts[0])

                if not 1 <= year_value <= 9999:
                    raise ValueError

                if is_end_date:
                    return _clamp_to_today(
                        f"{year_value:04d}-12-31"
                    )

                return _clamp_to_today(
                    f"{year_value:04d}-01-01"
                )

            if len(parts) == 2:
                year_value = int(parts[0])
                month_value = int(parts[1])

                if not 1 <= year_value <= 9999:
                    raise ValueError

                if not 1 <= month_value <= 12:
                    raise ValueError

                if is_end_date:
                    final_day = monthrange(
                        year_value,
                        month_value,
                    )[1]

                    return _clamp_to_today(
                        f"{year_value:04d}-"
                        f"{month_value:02d}-"
                        f"{final_day:02d}"
                    )

                return _clamp_to_today(
                    f"{year_value:04d}-"
                    f"{month_value:02d}-01"
                )

            if len(parts) == 3:
                year_value = int(parts[0])
                month_value = int(parts[1])
                day_value = int(parts[2])

                if not 1 <= year_value <= 9999:
                    raise ValueError

                if not 1 <= month_value <= 12:
                    raise ValueError

                final_day = monthrange(
                    year_value,
                    month_value,
                )[1]

                if not 1 <= day_value <= final_day:
                    raise ValueError

                return _clamp_to_today(
                    f"{year_value:04d}-"
                    f"{month_value:02d}-"
                    f"{day_value:02d}"
                )

        except (TypeError, ValueError):
            pass

        raise ValueError(
            f"{field_name} 형식이 올바르지 않아요. "
            "연도, 연도-월 또는 연도-월-일 형식으로 "
            "입력해 주세요."
        )

    def _normalize_search_date_range(
        date_from,
        date_to,
    ):
        normalized_from = _normalize_search_date(
            date_from,
            field_name="시작일",
            is_end_date=False,
        )

        normalized_to = _normalize_search_date(
            date_to,
            field_name="종료일",
            is_end_date=True,
        )

        if (
            normalized_from is not None
            and normalized_to is not None
            and normalized_from > normalized_to
        ):
            raise ValueError(
                "시작일은 종료일보다 늦을 수 없어요."
            )

        return normalized_from, normalized_to

    def normalize_date_input(raw_value):
        today_value = date.today()
        current_year = 9999
        today_iso = today_value.isoformat()
        today_digits = today_value.strftime("%Y%m%d")

        def clamp_if_future(normalized_digits, normalized_text):
            if len(normalized_text) != 10:
                return normalized_digits, normalized_text

            try:
                parsed = datetime.strptime(
                    normalized_text,
                    "%Y-%m-%d",
                ).date()
            except ValueError:
                return normalized_digits, normalized_text

            if parsed > today_value:
                return today_digits, today_iso

            return normalized_digits, normalized_text

        digits = ''.join(ch for ch in str(raw_value or "") if ch.isdigit())[:8]
        if not digits:
            return "", ""

        if len(digits) < 4:
            return digits, digits

        year_digits = digits[:4]
        year_int = max(1, min(current_year, int(year_digits)))
        year_digits = f"{year_int:04d}"

        rest = digits[4:]
        if not rest:
            return year_digits, year_digits

        month_display = ""
        month_digits_for_state = ""
        day_digits_raw = ""

        if len(rest) == 1:
            month_display = rest
            month_digits_for_state = rest
        else:
            month_two = rest[:2]
            month_two_int = int(month_two)

            if 1 <= month_two_int <= 12:
                month_display = f"{month_two_int:02d}"
                month_digits_for_state = month_display
                day_digits_raw = rest[2:4]
            else:
                month_one = rest[0]
                carry_to_day = rest[1:4]
                if month_one == "0":
                    month_display = "0"
                    month_digits_for_state = "0"
                else:
                    month_one_int = max(1, min(9, int(month_one)))
                    month_display = f"{month_one_int:02d}"
                    month_digits_for_state = month_display
                day_digits_raw = carry_to_day

        if not month_display:
            return year_digits, year_digits

        if not day_digits_raw:
            normalized_digits = year_digits + month_digits_for_state
            return normalized_digits, f"{year_digits}-{month_display}"

        if len(day_digits_raw) == 1:
            day_first = int(day_digits_raw)
            if 4 <= day_first <= 9:
                day_digits = f"0{day_first}"
                normalized_digits = year_digits + month_digits_for_state + day_digits
                return clamp_if_future(
                    normalized_digits,
                    f"{year_digits}-{month_display}-{day_digits}",
                )
            normalized_digits = year_digits + month_digits_for_state + day_digits_raw
            return normalized_digits, f"{year_digits}-{month_display}-{day_digits_raw}"

        month_for_day = int(month_digits_for_state if len(month_digits_for_state) == 2 else month_display)
        day_int = int(day_digits_raw[:2])
        max_day = max_day_for_month(year_int, month_for_day)
        day_int = max(1, min(max_day, day_int))
        day_digits = f"{day_int:02d}"

        normalized_digits = year_digits + month_digits_for_state + day_digits
        return clamp_if_future(
            normalized_digits,
            f"{year_digits}-{month_display}-{day_digits}",
        )

    def _create_icon_action(parent, icon_photo, fallback_text, command, *, icon_pad=None):
        local_icon_pad = icon_padding if icon_pad is None else icon_pad
        wrapper = tk.Frame(parent, bg=colors.SURFACE_ALT, highlightthickness=0, bd=0, cursor="hand2")
        label = tk.Label(
            wrapper,
            image=icon_photo,
            text=fallback_text if icon_photo is None else "",
            compound="center",
            bg=colors.SURFACE_ALT,
            fg=SF_TEXT_DARK,
            font=("Segoe UI Emoji", 11),
            cursor="hand2",
        )
        label.pack(padx=local_icon_pad[0], pady=local_icon_pad[1])

        def set_state(bg_color):
            wrapper.configure(bg=bg_color)
            label.configure(bg=bg_color)

        def on_enter(_event):
            set_state(SF_SURFACE_HOVER_SOFT)

        def on_leave(_event):
            set_state(colors.SURFACE_ALT)

        def on_click(_event):
            command()

        for widget in (wrapper, label):
            widget.bind("<Enter>", on_enter, add="+")
            widget.bind("<Leave>", on_leave, add="+")
            widget.bind("<Button-1>", on_click, add="+")

        wrapper.image = icon_photo
        wrapper.icon_label = label
        return wrapper

    def _draw_plain_rounded_rect(canvas, x1, y1, x2, y2, radius, *, fill, outline, border_width=1):
        r = max(2, min(int(radius), int((x2 - x1) / 2), int((y2 - y1) / 2)))

        # Fill (no shadow): center strips + corner pies.
        canvas.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline="")
        canvas.create_rectangle(x1, y1 + r, x2, y2 - r, fill=fill, outline="")
        canvas.create_arc(x1, y1, x1 + 2 * r, y1 + 2 * r, start=90, extent=90, style="pieslice", fill=fill, outline="")
        canvas.create_arc(x2 - 2 * r, y1, x2, y1 + 2 * r, start=0, extent=90, style="pieslice", fill=fill, outline="")
        canvas.create_arc(x2 - 2 * r, y2 - 2 * r, x2, y2, start=270, extent=90, style="pieslice", fill=fill, outline="")
        canvas.create_arc(x1, y2 - 2 * r, x1 + 2 * r, y2, start=180, extent=90, style="pieslice", fill=fill, outline="")

        # Outline.
        canvas.create_arc(x1, y1, x1 + 2 * r, y1 + 2 * r, start=90, extent=90, style="arc", outline=outline, width=border_width)
        canvas.create_arc(x2 - 2 * r, y1, x2, y1 + 2 * r, start=0, extent=90, style="arc", outline=outline, width=border_width)
        canvas.create_arc(x2 - 2 * r, y2 - 2 * r, x2, y2, start=270, extent=90, style="arc", outline=outline, width=border_width)
        canvas.create_arc(x1, y2 - 2 * r, x1 + 2 * r, y2, start=180, extent=90, style="arc", outline=outline, width=border_width)
        canvas.create_line(x1 + r, y1, x2 - r, y1, fill=outline, width=border_width)
        canvas.create_line(x2, y1 + r, x2, y2 - r, fill=outline, width=border_width)
        canvas.create_line(x1 + r, y2, x2 - r, y2, fill=outline, width=border_width)
        canvas.create_line(x1, y1 + r, x1, y2 - r, fill=outline, width=border_width)

    def _draw_count_badge(
        canvas,
        *,
        left,
        center_y,
        text,
    ):
        badge_height = 28
        badge_radius = 10
        badge_font = app._font(12, "bold")
        badge_text = str(text or "")
        badge_text_width = tkfont.Font(font=badge_font).measure(badge_text)
        badge_width = max(44, badge_text_width + 20)

        x1 = int(left)
        y1 = int(center_y - (badge_height / 2))
        x2 = x1 + badge_width
        y2 = y1 + badge_height

        app._smooth_rounded_rect(
            canvas,
            x1,
            y1,
            x2,
            y2,
            badge_radius,
            fill=SF_NUMBER_DESIGNATION_BG,
            outline=SF_NUMBER_DESIGNATION_BG,
            width=1,
        )

        canvas.create_text(
            int((x1 + x2) / 2),
            int(center_y),
            text=badge_text,
            fill=colors.TEXT_SECONDARY,
            font=badge_font,
            anchor="center",
        )

        return x2

    def _create_search_action_button(
        parent,
        *,
        text,
        command,
        width,
        primary=False,
        icon_photo=None,
    ):
        canvas = tk.Canvas(
            parent,
            width=width,
            height=search_box_height,
            bg=colors.SURFACE_ALT,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )

        button_state = {
            "hovered": False,
            "enabled": True,
        }

        def _redraw(_event=None):
            canvas.delete("all")

            canvas_width = max(
                20,
                canvas.winfo_width(),
            )
            canvas_height = max(
                20,
                canvas.winfo_height(),
            )

            hovered = button_state["hovered"]
            enabled = button_state["enabled"]

            if primary:
                fill_color = (
                    colors.PRIMARY_HOVER
                    if hovered and enabled
                    else SF_PRIMARY
                )
                border_color = SF_PRIMARY
                text_color = (
                    colors.TEXT_INVERSE
                    if enabled
                    else SF_TEXT_PLACEHOLDER
                )
            else:
                fill_color = (
                    SF_SURFACE_HOVER_SOFT
                    if hovered and enabled
                    else colors.SURFACE_ALT
                )
                border_color = (
                    SF_INPUT_FOCUS_BORDER
                    if hovered and enabled
                    else SF_INPUT_IDLE_BORDER
                )
                text_color = (
                    SF_TEXT_DARK
                    if enabled
                    else SF_TEXT_PLACEHOLDER
                )

            _draw_plain_rounded_rect(
                canvas,
                1,
                1,
                canvas_width - 1,
                canvas_height - 1,
                10,
                fill=fill_color,
                outline=border_color,
                border_width=1,
            )

            if icon_photo is not None:
                icon_x = (
                    canvas_width / 2.0
                    - 16
                )

                canvas.create_image(
                    icon_x,
                    canvas_height / 2.0,
                    image=icon_photo,
                    anchor="center",
                )

                canvas.create_text(
                    icon_x + 14,
                    canvas_height / 2.0,
                    text=text,
                    fill=text_color,
                    font=app._font(10, "bold"),
                    anchor="w",
                )
            else:
                canvas.create_text(
                    canvas_width / 2.0,
                    canvas_height / 2.0,
                    text=text,
                    fill=text_color,
                    font=app._font(10, "bold"),
                    anchor="center",
                )

            canvas.create_rectangle(
                0,
                0,
                canvas_width,
                canvas_height,
                fill="",
                outline="",
                tags=("action_button",),
            )

        def _on_enter(_event=None):
            if not button_state["enabled"]:
                return

            button_state["hovered"] = True
            _redraw()

        def _on_leave(_event=None):
            button_state["hovered"] = False
            _redraw()

        def _on_click(_event=None):
            if not button_state["enabled"]:
                return "break"

            command()
            return "break"

        def _set_enabled(enabled):
            button_state["enabled"] = bool(enabled)
            button_state["hovered"] = False

            canvas.configure(
                cursor=(
                    "hand2"
                    if button_state["enabled"]
                    else ""
                )
            )
            _redraw()

        canvas.bind(
            "<Configure>",
            _redraw,
            add="+",
        )
        canvas.bind(
            "<Enter>",
            _on_enter,
            add="+",
        )
        canvas.bind(
            "<Leave>",
            _on_leave,
            add="+",
        )
        canvas.bind(
            "<Button-1>",
            _on_click,
            add="+",
        )

        canvas.image = icon_photo
        canvas.set_enabled = _set_enabled

        _redraw()
        return canvas

    def _color_to_rgb(color_value):
        r16, g16, b16 = app.root.winfo_rgb(color_value)
        return (r16 // 256, g16 // 256, b16 // 256)

    def _draw_dropdown_shell(canvas, width, height, *, radius=10, border_width=1):
        canvas.delete("dropdown_shell")
        width = max(2, int(width))
        height = max(2, int(height))

        if _PIL_AVAILABLE:
            scale = 4
            sw = width * scale
            sh = height * scale
            sr = max(0, int(round(radius * scale)))
            sbw = max(1, int(round(border_width * scale)))

            bg_rgb = _color_to_rgb(colors.SURFACE_ALT)
            fill_rgb = _color_to_rgb(colors.SURFACE_ALT)
            border_rgb = _color_to_rgb(SF_INPUT_IDLE_BORDER)

            image = Image.new("RGBA", (sw, sh), (bg_rgb[0], bg_rgb[1], bg_rgb[2], 255))
            draw = ImageDraw.Draw(image)
            draw.rounded_rectangle([0, 0, sw - 1, sh - 1], radius=sr, fill=(border_rgb[0], border_rgb[1], border_rgb[2], 255))
            draw.rounded_rectangle(
                [sbw, sbw, sw - 1 - sbw, sh - 1 - sbw],
                radius=max(0, sr - sbw),
                fill=(fill_rgb[0], fill_rgb[1], fill_rgb[2], 255),
            )

            try:
                resample_mode = Image.Resampling.LANCZOS
            except Exception:
                resample_mode = Image.LANCZOS

            downsampled = image.resize((width, height), resample=resample_mode)
            photo = ImageTk.PhotoImage(downsampled, master=canvas)
            canvas._dropdown_shell_photo = photo
            canvas.create_image(0, 0, anchor="nw", image=photo, tags=("dropdown_shell",))
            return

        # Fallback: smooth rounded rect from app helper.
        app._smooth_rounded_rect(
            canvas,
            1,
            1,
            width - 1,
            height - 1,
            radius,
            fill=colors.SURFACE_ALT,
            outline=SF_INPUT_IDLE_BORDER,
            width=1,
            tags="dropdown_shell",
        )

    def _create_rounded_input(
        parent,
        text_var,
        *,
        placeholder="",
        with_toggle_icon=False,
        toggle_command=None,
        trailing_icon_photo=None,
        trailing_icon_command=None,
    ):
        field_holder = tk.Frame(parent, bg=colors.SURFACE_ALT, highlightthickness=0, bd=0)

        rounded_input = RoundedInput(
            field_holder,
            textvariable=text_var,
            placeholder=placeholder,
            width=120,
            height=34,
            corner_radius=10,
            font=app._font(10),
            foreground=SF_TEXT_DARK,
            placeholder_color=SF_TEXT_PLACEHOLDER,
            fill=colors.SURFACE_ALT,
            border_color=SF_INPUT_IDLE_BORDER,
            focus_fill=colors.SURFACE_ALT,
            focus_border_color=SF_INPUT_FOCUS_BORDER,
            disabled_fill=colors.SURFACE_ALT,
            disabled_foreground=SF_TEXT_PLACEHOLDER,
            state="normal",
        )
        rounded_input.pack(fill="both", expand=True)

        entry = rounded_input.entry
        entry.configure(justify="left", insertbackground=SF_TEXT_DARK)
        entry.grid_configure(padx=(6, 8))

        toggle_widget = None
        trailing_widget = None
        has_right_icon = False

        if with_toggle_icon and callable(toggle_command):
            toggle_widget = _create_icon_action(
                rounded_input,
                expand_icon_photo,
                "▾",
                toggle_command,
                icon_pad=(1, 1),
            )
            toggle_widget.place(relx=1.0, rely=0.5, x=-6, y=0, anchor="e")
            has_right_icon = True

        if trailing_icon_photo is not None:
            trailing_widget = _create_icon_action(
                rounded_input,
                trailing_icon_photo,
                "📅",
                trailing_icon_command if callable(trailing_icon_command) else (lambda: None),
                icon_pad=(1, 1),
            )
            trailing_widget.place(relx=1.0, rely=0.5, x=-6, y=0, anchor="e")
            has_right_icon = True

        if has_right_icon:
            entry.grid_configure(padx=(6, 30))

        return {
            "canvas": field_holder,
            "entry": entry,
            "toggle": toggle_widget,
            "trailing": trailing_widget,
            "rounded": rounded_input,
        }

    def _align_rounded_placeholder(field, left_pad, right_pad):
        rounded = field["rounded"]
        rounded._placeholder_left_pad_override = int(left_pad)
        rounded._placeholder_right_pad_override = int(right_pad)
        rounded._reposition_placeholder()

    def _compute_left_top_targets():
        if not _is_search_screen_alive():
            return 1, 1, 1

        total_height = max(1, left_col.winfo_height())
        available_height = max(1, total_height - gap)

        # Baseline expanded size keeps the previous visual target.
        expanded_height = max(120, int(available_height * 0.40))

        # Default collapsed size is one-third of the baseline expanded size.
        collapsed_min_height = search_box_inset + search_box_height + filter_row_top_gap + filter_row_height + 16
        collapsed_height = max(collapsed_min_height, int(expanded_height / 3.0))

        min_bottom_height = 120
        expanded_height = min(expanded_height, max(collapsed_height, available_height - min_bottom_height))
        collapsed_height = min(collapsed_height, expanded_height)
        return collapsed_height, expanded_height, available_height

    def _has_valid_left_layout_space():
        if not _is_search_screen_alive():
            return False

        min_height = search_box_inset + search_box_height + filter_row_top_gap + filter_row_height + 20
        try:
            return left_col.winfo_width() > 160 and left_col.winfo_height() >= min_height
        except TclError:
            return False

    def _schedule_layout_retry():
        if not _is_search_screen_alive():
            return

        if layout_state["retry_job"] is not None:
            return

        try:
            layout_state["retry_job"] = app.root.after(24, _retry_layout)
        except TclError:
            layout_state["retry_job"] = None

    def _retry_layout():
        layout_state["retry_job"] = None

        if not _is_search_screen_alive():
            return

        _on_layout_change()

    def _place_left_cards(top_height):
        _collapsed, _expanded, available_height = _compute_left_top_targets()
        min_bottom_height = 1
        clamped_top = max(1, min(int(top_height), max(1, available_height - min_bottom_height)))
        bottom_height = max(1, available_height - clamped_top)

        left_top_card.place(x=0, y=0, relwidth=1.0, width=0, height=clamped_top)
        left_bottom_card.place(x=0, y=clamped_top + gap, relwidth=1.0, width=0, height=bottom_height)
        return clamped_top

    def _apply_left_top_height(top_height):
        clamped_top = _place_left_cards(top_height)
        filter_panel_state["current_top_height"] = float(clamped_top)

    def _set_filter_toggle_visuals(expanded):
        filter_label.configure(fg=SF_PRIMARY if expanded else SF_TEXT_DARK)
        icon = collapse_icon_photo if expanded else expand_icon_photo
        fallback = "▴" if expanded else "▾"
        filter_toggle_icon.icon_label.configure(image=icon, text=fallback if icon is None else "")
        filter_toggle_icon.image = icon

    def _set_dropdown_icon(toggle_widget, expanded):
        if toggle_widget is None:
            return

        icon_label = getattr(toggle_widget, "icon_label", None)
        if icon_label is None:
            return

        try:
            if not icon_label.winfo_exists():
                return
        except TclError:
            return

        icon = collapse_icon_photo if expanded else expand_icon_photo
        fallback = "▴" if expanded else "▾"
        try:
            icon_label.configure(image=icon, text=fallback if icon is None else "")
            toggle_widget.image = icon
        except TclError:
            return

    def _close_dropdown_popup(kind):
        popup_key = f"{kind}_popup"
        expanded_key = f"{kind}_expanded"
        popup = dropdown_state.get(popup_key)
        if popup is not None and popup.winfo_exists():
            popup.destroy()
        dropdown_state[popup_key] = None
        dropdown_state[expanded_key] = False

    def _close_calendar_popup():
        popup = calendar_popup_state.get("popup")

        if (
            popup is not None
            and popup.winfo_exists()
        ):
            popup.destroy()

        calendar_popup_state["popup"] = None
        calendar_popup_state["field_kind"] = None

    def _resolve_calendar_start_date(value):
        text = str(value or "").strip()
        today_value = date.today()

        if not text or text == "-":
            return today_value

        for date_format in (
            "%Y-%m-%d",
            "%Y-%m",
            "%Y",
        ):
            try:
                parsed = datetime.strptime(
                    text,
                    date_format,
                )

                resolved = parsed.date()
                if resolved > today_value:
                    return today_value

                return resolved

            except ValueError:
                continue

        return today_value

    def _shift_calendar_month(
        year_value,
        month_value,
        direction,
    ):
        minimum_month_index = 1 * 12
        maximum_month_index = (
            9999 * 12
        ) + 11

        month_index = (
            int(year_value) * 12
            + int(month_value)
            - 1
            + int(direction)
        )

        month_index = max(
            minimum_month_index,
            min(
                maximum_month_index,
                month_index,
            ),
        )

        shifted_year = month_index // 12
        shifted_month = (
            month_index % 12
        ) + 1

        return shifted_year, shifted_month

    def _create_calendar_control(
        parent,
        *,
        text,
        command,
        width=28,
    ):
        control = tk.Label(
            parent,
            text=text,
            width=max(1, int(width / 10)),
            bg=colors.SURFACE_ALT,
            fg=SF_TEXT_DARK,
            font=app._font(10, "bold"),
            cursor="hand2",
            anchor="center",
            padx=4,
            pady=3,
        )

        def _on_enter(_event=None):
            control.configure(
                bg=SF_SURFACE_HOVER_SOFT
            )

        def _on_leave(_event=None):
            control.configure(
                bg=colors.SURFACE_ALT
            )

        def _on_click(_event=None):
            command()
            return "break"

        control.bind("<Enter>", _on_enter)
        control.bind("<Leave>", _on_leave)
        control.bind("<Button-1>", _on_click)

        return control

    def _open_calendar_popup(
        field_kind,
        field,
        value_var,
    ):
        _close_dropdown_popup("doc_type")
        _close_dropdown_popup("file_type")
        _set_dropdown_icon(
            doc_type_field["toggle"],
            False,
        )
        _set_dropdown_icon(
            file_type_field["toggle"],
            False,
        )
        _close_calendar_popup()

        initial_date = _resolve_calendar_start_date(
            value_var.get()
        )

        calendar_popup_state["field_kind"] = (
            field_kind
        )
        calendar_popup_state["display_year"] = (
            initial_date.year
        )
        calendar_popup_state["display_month"] = (
            initial_date.month
        )

        popup_width = 286
        popup_height = 326

        popup_x = field["canvas"].winfo_rootx()
        popup_y = (
            field["canvas"].winfo_rooty()
            + field["canvas"].winfo_height()
            + 2
        )

        popup = tk.Toplevel(app.root)
        popup.overrideredirect(True)
        popup.transient(app.root)
        popup.configure(bg=colors.SURFACE_ALT)
        popup.geometry(
            f"{popup_width}x{popup_height}"
            f"+{popup_x}+{popup_y}"
        )
        popup.lift()
        popup.focus_force()

        calendar_popup_state["popup"] = popup

        shell_canvas = tk.Canvas(
            popup,
            bg=colors.SURFACE_ALT,
            highlightthickness=0,
            bd=0,
        )
        shell_canvas.pack(fill="both", expand=True)

        _draw_dropdown_shell(
            shell_canvas,
            popup_width,
            popup_height,
            radius=12,
            border_width=1,
        )

        body = tk.Frame(
            shell_canvas,
            bg=colors.SURFACE_ALT,
            highlightthickness=0,
            bd=0,
        )
        shell_canvas.create_window(
            8,
            8,
            anchor="nw",
            window=body,
            width=popup_width - 16,
            height=popup_height - 16,
        )

        header = tk.Frame(
            body,
            bg=colors.SURFACE_ALT,
            highlightthickness=0,
            bd=0,
        )
        header.pack(
            fill="x",
            padx=4,
            pady=(2, 8),
        )

        month_title = tk.Label(
            header,
            text="",
            bg=colors.SURFACE_ALT,
            fg=SF_TEXT_MAIN,
            font=app._font(12, "bold"),
            anchor="center",
        )
        month_title.pack(
            side="left",
            fill="x",
            expand=True,
        )

        calendar_grid = tk.Frame(
            body,
            bg=colors.SURFACE_ALT,
            highlightthickness=0,
            bd=0,
        )
        calendar_grid.pack(
            fill="both",
            expand=True,
            padx=4,
        )

        for column_index in range(7):
            calendar_grid.grid_columnconfigure(
                column_index,
                weight=1,
                uniform="calendar_day",
            )

        def _select_calendar_date(day_value):
            year_value = int(
                calendar_popup_state[
                    "display_year"
                ]
            )
            month_value = int(
                calendar_popup_state[
                    "display_month"
                ]
            )

            value_var.set(
                f"{year_value:04d}-"
                f"{month_value:02d}-"
                f"{int(day_value):02d}"
            )

            _set_quick_button_state(None)
            _close_calendar_popup()

        def _draw_calendar_month():
            for child in calendar_grid.winfo_children():
                child.destroy()

            year_value = int(
                calendar_popup_state[
                    "display_year"
                ]
            )
            month_value = int(
                calendar_popup_state[
                    "display_month"
                ]
            )

            month_title.configure(
                text=f"{year_value}년 {month_value}월"
            )

            for weekday_index, weekday_text in enumerate(
                SF_CALENDAR_WEEKDAYS
            ):
                weekday_label = tk.Label(
                    calendar_grid,
                    text=weekday_text,
                    bg=colors.SURFACE_ALT,
                    fg=(
                        SF_STATUS_FAILED
                        if weekday_index == 6
                        else SF_TEXT_PLACEHOLDER
                    ),
                    font=app._font(9, "bold"),
                    anchor="center",
                    pady=5,
                )
                weekday_label.grid(
                    row=0,
                    column=weekday_index,
                    sticky="nsew",
                )

            first_weekday = date(
                year_value,
                month_value,
                1,
            ).weekday()

            final_day = monthrange(
                year_value,
                month_value,
            )[1]

            today_value = date.today()
            selected_text = str(
                value_var.get() or ""
            ).strip()

            for day_value in range(
                1,
                final_day + 1,
            ):
                cell_index = (
                    first_weekday
                    + day_value
                    - 1
                )
                row_index = (
                    cell_index // 7
                ) + 1
                column_index = cell_index % 7

                iso_value = (
                    f"{year_value:04d}-"
                    f"{month_value:02d}-"
                    f"{day_value:02d}"
                )

                cell_date = date(
                    year_value,
                    month_value,
                    day_value,
                )

                is_future = (
                    cell_date > today_value
                )

                is_selected = (
                    selected_text == iso_value
                    and not is_future
                )

                is_today = (
                    today_value.year == year_value
                    and today_value.month == month_value
                    and today_value.day == day_value
                )

                day_label = tk.Label(
                    calendar_grid,
                    text=str(day_value),
                    bg=(
                        SF_PRIMARY
                        if is_selected
                        else colors.SURFACE_ALT
                    ),
                    fg=(
                        colors.TEXT_INVERSE
                        if is_selected
                        else (
                            SF_TEXT_PLACEHOLDER
                            if is_future
                            else (
                            SF_PRIMARY
                            if is_today
                            else (
                                SF_STATUS_FAILED
                                if column_index == 6
                                else SF_TEXT_DARK
                            )
                            )
                        )
                    ),
                    font=app._font(
                        9,
                        "bold"
                        if is_selected or is_today
                        else "normal",
                    ),
                    cursor=(
                        "arrow"
                        if is_future
                        else "hand2"
                    ),
                    anchor="center",
                    padx=4,
                    pady=6,
                )

                day_label.grid(
                    row=row_index,
                    column=column_index,
                    sticky="nsew",
                    padx=1,
                    pady=1,
                )

                def _on_day_enter(
                    _event,
                    widget=day_label,
                    selected=is_selected,
                    future=is_future,
                ):
                    if not selected and not future:
                        widget.configure(
                            bg=SF_SURFACE_HOVER_SOFT
                        )

                def _on_day_leave(
                    _event,
                    widget=day_label,
                    selected=is_selected,
                ):
                    widget.configure(
                        bg=(
                            SF_PRIMARY
                            if selected
                            else colors.SURFACE_ALT
                        )
                    )

                day_label.bind(
                    "<Enter>",
                    _on_day_enter,
                )
                day_label.bind(
                    "<Leave>",
                    _on_day_leave,
                )

                if not is_future:
                    day_label.bind(
                        "<Button-1>",
                        lambda _event, day=day_value:
                            _select_calendar_date(day),
                    )

        def _change_calendar_month(direction):
            current_year = int(
                calendar_popup_state[
                    "display_year"
                ]
            )
            current_month = int(
                calendar_popup_state[
                    "display_month"
                ]
            )

            (
                shifted_year,
                shifted_month,
            ) = _shift_calendar_month(
                current_year,
                current_month,
                direction,
            )

            calendar_popup_state["display_year"] = (
                shifted_year
            )
            calendar_popup_state["display_month"] = (
                shifted_month
            )

            _draw_calendar_month()

        previous_month_control = (
            _create_calendar_control(
                header,
                text="‹",
                command=lambda:
                    _change_calendar_month(-1),
            )
        )
        previous_month_control.pack(side="left")

        # Move the title between navigation controls.
        month_title.pack_forget()
        month_title.pack(
            side="left",
            fill="x",
            expand=True,
        )

        next_month_control = (
            _create_calendar_control(
                header,
                text="›",
                command=lambda:
                    _change_calendar_month(1),
            )
        )
        next_month_control.pack(side="right")

        footer = tk.Frame(
            body,
            bg=colors.SURFACE_ALT,
            highlightthickness=0,
            bd=0,
        )
        footer.pack(
            fill="x",
            padx=4,
            pady=(8, 2),
        )

        def _select_today():
            today_value = date.today()

            value_var.set(today_value.isoformat())
            _set_quick_button_state(None)
            _close_calendar_popup()

        today_control = tk.Label(
            footer,
            text="오늘",
            bg=colors.SURFACE_ALT,
            fg=SF_PRIMARY,
            font=app._font(9, "bold"),
            cursor="hand2",
            padx=8,
            pady=4,
        )
        today_control.pack(side="right")

        today_control.bind(
            "<Button-1>",
            lambda _event: _select_today(),
        )

        popup.bind(
            "<Escape>",
            lambda _event: _close_calendar_popup(),
        )

        _draw_calendar_month()

    def _open_dropdown_popup(kind, field, options, value_var):
        popup_key = f"{kind}_popup"
        expanded_key = f"{kind}_expanded"

        _close_dropdown_popup(kind)

        popup_width = max(120, int(field["canvas"].winfo_width()))
        popup_rows = max(1, min(5, len(options)))
        popup_height = (popup_rows * 28) + 12
        popup_x = field["canvas"].winfo_rootx()
        popup_y = field["canvas"].winfo_rooty() + field["canvas"].winfo_height() + 2

        popup = tk.Toplevel(app.root)
        popup.overrideredirect(True)
        popup.transient(app.root)
        popup.configure(bg=colors.SURFACE_ALT)
        popup.geometry(f"{popup_width}x{popup_height}+{popup_x}+{popup_y}")
        popup.lift()
        popup.focus_force()

        shell_canvas = tk.Canvas(popup, bg=colors.SURFACE_ALT, highlightthickness=0, bd=0)
        shell_canvas.pack(fill="both", expand=True)

        inner_pad = 2
        _draw_dropdown_shell(shell_canvas, popup_width, popup_height, radius=10, border_width=1)

        def _on_shell_resize(event):
            _draw_dropdown_shell(shell_canvas, event.width, event.height, radius=10, border_width=1)

        shell_canvas.bind("<Configure>", _on_shell_resize, add="+")

        body = tk.Frame(
            shell_canvas,
            bg=colors.SURFACE_ALT,
            bd=0,
            highlightthickness=0,
        )
        shell_canvas.create_window(
            inner_pad,
            inner_pad,
            anchor="nw",
            window=body,
            width=max(1, popup_width - (inner_pad * 2)),
            height=max(1, popup_height - (inner_pad * 2)),
        )

        listbox = tk.Listbox(
            body,
            height=popup_rows,
            activestyle="none",
            selectmode="browse",
            bd=0,
            highlightthickness=0,
            relief="flat",
            bg=colors.SURFACE_ALT,
            fg=SF_TEXT_DARK,
            font=app._font(11),
            selectbackground=SF_PRIMARY,
            selectforeground=colors.TEXT_INVERSE,
            exportselection=False,
        )
        listbox.pack(fill="both", expand=True)

        for option in options:
            listbox.insert(tk.END, option)

        current_value = (value_var.get() or "").strip()
        if current_value in options:
            current_index = options.index(current_value)
            listbox.selection_set(current_index)
            listbox.see(current_index)

        def _commit_selection(_event=None):
            selection = listbox.curselection()
            if not selection:
                return "break"
            chosen = listbox.get(selection[0])
            value_var.set(chosen)
            _close_dropdown_popup(kind)
            return "break"

        listbox.bind("<ButtonRelease-1>", _commit_selection)
        listbox.bind("<Double-Button-1>", _commit_selection)
        listbox.bind("<Return>", _commit_selection)
        popup.bind("<Escape>", lambda _event: _close_dropdown_popup(kind))
        popup.after(0, lambda: listbox.focus_set())

        dropdown_state[popup_key] = popup
        dropdown_state[expanded_key] = True

    def _layout_filter_row():
        top_card_width = max(100, left_top_card.winfo_width())
        card_x1 = 1 + left_cards_left_inset
        card_x2 = max(card_x1 + 40, top_card_width - 1 - left_cards_right_inset)
        card_inner_width = max(100, card_x2 - card_x1)
        row_width = max(140, card_inner_width - (search_box_inset * 2))
        row_height = filter_row_height
        row_y = search_box_inset + search_box_height + filter_row_top_gap
        filter_row.place(x=card_x1 + search_box_inset, y=row_y, width=row_width, height=row_height)

    def _layout_filter_content():
        top_card_width = max(100, left_top_card.winfo_width())
        card_x1 = 1 + left_cards_left_inset
        card_x2 = max(card_x1 + 40, top_card_width - 1 - left_cards_right_inset)
        card_inner_width = max(100, card_x2 - card_x1)
        content_x = card_x1 + search_box_inset
        content_y = search_box_inset + search_box_height + filter_row_top_gap + filter_row_height + filter_content_top_gap
        content_width = max(140, card_inner_width - (search_box_inset * 2))
        max_visible_height = max(0, left_top_card.winfo_height() - content_y - filter_content_bottom_padding)
        visible_height = min(filter_content_height, max_visible_height)

        if visible_height <= 0:
            filter_content_clip.place_forget()
            return

        filter_content_clip.place(x=content_x, y=content_y, width=content_width, height=visible_height)
        filter_content_inner.place(x=0, y=0, width=content_width, height=filter_content_height)

    def _toggle_doc_type_dropdown():
        _close_calendar_popup()

        if dropdown_state["doc_type_expanded"]:
            _close_dropdown_popup("doc_type")
        else:
            _close_dropdown_popup("file_type")
            _open_dropdown_popup("doc_type", doc_type_field, doc_type_options, doc_type_var)
        _set_dropdown_icon(doc_type_field["toggle"], dropdown_state["doc_type_expanded"])
        _set_dropdown_icon(file_type_field["toggle"], dropdown_state["file_type_expanded"])

    def _toggle_file_type_dropdown():
        _close_calendar_popup()

        if dropdown_state["file_type_expanded"]:
            _close_dropdown_popup("file_type")
        else:
            _close_dropdown_popup("doc_type")
            _open_dropdown_popup("file_type", file_type_field, file_type_options, file_type_var)
        _set_dropdown_icon(doc_type_field["toggle"], dropdown_state["doc_type_expanded"])
        _set_dropdown_icon(file_type_field["toggle"], dropdown_state["file_type_expanded"])

    def _refresh_layout_drawings():
        if not _is_search_screen_alive():
            return

        _draw_card(left_top_card, bottom_shrink=0)
        _draw_results_table()
        _draw_file_details()
        _draw_search_box()
        _layout_filter_row()
        _layout_filter_content()

    def _finish_filter_animation(expanded):
        filter_panel_state["expanded"] = expanded
        filter_panel_state["target_expanded"] = expanded
        filter_panel_state["anim_job"] = None
        _set_filter_toggle_visuals(expanded)
        _sync_result_rows_per_page_for_layout(
            reload_page=True,
        )
        _refresh_layout_drawings()

    def _animate_filter_height_step():
        filter_panel_state["anim_job"] = None

        if not _is_search_screen_alive():
            return

        try:
            now_ms = int(app.root.tk.call("clock", "milliseconds"))
        except TclError:
            return

        elapsed = now_ms - int(filter_panel_state["anim_start_time"])
        duration = max(1, int(filter_panel_state["anim_duration_ms"]))
        progress = min(1.0, max(0.0, elapsed / float(duration)))
        eased = progress * progress * (3.0 - 2.0 * progress)

        start_h = float(filter_panel_state["anim_start_height"])
        target_h = float(filter_panel_state["anim_target_height"])
        next_h = start_h + ((target_h - start_h) * eased)
        _apply_left_top_height(next_h)
        _refresh_layout_drawings()

        if progress >= 1.0:
            _finish_filter_animation(filter_panel_state["target_expanded"])
            return

        try:
            filter_panel_state["anim_job"] = app.root.after(16, _animate_filter_height_step)
        except TclError:
            filter_panel_state["anim_job"] = None

    def _toggle_filter_panel():
        if not _is_search_screen_alive():
            return

        if filter_panel_state["anim_job"] is not None:
            try:
                app.root.after_cancel(filter_panel_state["anim_job"])
            except TclError:
                pass
            filter_panel_state["anim_job"] = None

        target_expanded = not bool(filter_panel_state["target_expanded"])
        filter_panel_state["target_expanded"] = target_expanded
        _set_filter_toggle_visuals(target_expanded)
        _sync_result_rows_per_page_for_layout(
            reload_page=False,
        )

        collapsed_height, expanded_height, _available = _compute_left_top_targets()
        target_height = expanded_height if target_expanded else collapsed_height
        current_height = float(filter_panel_state["current_top_height"] or collapsed_height)

        filter_panel_state["anim_start_height"] = current_height
        filter_panel_state["anim_target_height"] = float(target_height)
        try:
            filter_panel_state["anim_start_time"] = int(app.root.tk.call("clock", "milliseconds"))
            filter_panel_state["anim_job"] = app.root.after(16, _animate_filter_height_step)
        except TclError:
            filter_panel_state["anim_job"] = None

    search_input = RoundedInput(
        search_input_holder,
        textvariable=search_var,
        placeholder=search_placeholder_text,
        width=260,
        height=search_box_height,
        corner_radius=12,
        font=app._font(11),
        foreground=SF_TEXT_DARK,
        placeholder_color=SF_TEXT_PLACEHOLDER,
        fill=colors.SURFACE_ALT,
        border_color=SF_INPUT_IDLE_BORDER,
        focus_fill=colors.SURFACE_ALT,
        focus_border_color=SF_INPUT_FOCUS_BORDER,
        disabled_fill=colors.SURFACE_ALT,
        disabled_foreground=SF_TEXT_PLACEHOLDER,
        leading_icon=search_icon_photo,
        state="normal",
    )
    search_text_entry = search_input.entry
    search_text_entry.configure(insertbackground=SF_TEXT_DARK)
    search_text_entry.grid_configure(padx=(6, 30))
    search_text_entry.bind("<Return>", _run_search)

    clear_icon_button = _create_icon_action(search_input_holder, clear_icon_photo, "✕", _clear_search_text)

    filter_toggle_icon = _create_icon_action(
        filter_row,
        expand_icon_photo,
        "▾",
        _toggle_filter_panel,
        icon_pad=(1, 1),
    )

    # Filter inputs: date range (2) + document type + file type + uploader.
    date_col = filter_col_frames[0]
    doc_type_col = filter_col_frames[1]
    file_type_col = filter_col_frames[2]
    uploader_col = filter_col_frames[3]

    date_range_row = tk.Frame(date_col, bg=colors.SURFACE_ALT, highlightthickness=0, bd=0)
    date_range_row.grid(row=1, column=0, sticky="ew", padx=(2, 6))
    date_range_row.grid_columnconfigure(0, weight=1)
    date_range_row.grid_columnconfigure(1, weight=0)
    date_range_row.grid_columnconfigure(2, weight=1)

    date_from_field = _create_rounded_input(
        date_range_row,
        date_from_var,
        placeholder="시작일",
        trailing_icon_photo=calendar_icon_photo,
        trailing_icon_command=lambda:
            _open_calendar_popup(
                "date_from",
                date_from_field,
                date_from_var,
            ),
    )
    date_from_field["canvas"].grid(row=0, column=0, sticky="ew")
    _align_rounded_placeholder(date_from_field, left_pad=6, right_pad=30)

    to_label = tk.Label(
        date_range_row,
        image=to_icon_photo,
        text="~" if to_icon_photo is None else "",
        compound="center",
        bg=colors.SURFACE_ALT,
        fg=SF_TEXT_DARK,
        font=app._font(9, "bold"),
    )
    to_label.grid(row=0, column=1, padx=(6, 6))
    to_label.image = to_icon_photo

    date_to_field = _create_rounded_input(
        date_range_row,
        date_to_var,
        placeholder="종료일",
        trailing_icon_photo=calendar_icon_photo,
        trailing_icon_command=lambda:
            _open_calendar_popup(
                "date_to",
                date_to_field,
                date_to_var,
            ),
    )
    date_to_field["canvas"].grid(row=0, column=2, sticky="ew")
    _align_rounded_placeholder(date_to_field, left_pad=6, right_pad=30)

    date_quick_row = tk.Frame(date_col, bg=colors.SURFACE_ALT, highlightthickness=0, bd=0)
    date_quick_row.grid(row=2, column=0, sticky="ew", padx=(2, 6), pady=(6, 0))
    for quick_idx in range(5):
        date_quick_row.grid_columnconfigure(quick_idx, weight=1, uniform="date_quick")

    doc_type_field = _create_rounded_input(
        doc_type_col,
        doc_type_var,
        placeholder="모든 문서 유형",
        with_toggle_icon=True,
        toggle_command=_toggle_doc_type_dropdown,
    )
    doc_type_field["canvas"].grid(row=1, column=0, sticky="ew", padx=(2, 6))
    _align_rounded_placeholder(doc_type_field, left_pad=6, right_pad=30)

    file_type_field = _create_rounded_input(
        file_type_col,
        file_type_var,
        placeholder="모든 파일 종류",
        with_toggle_icon=True,
        toggle_command=_toggle_file_type_dropdown,
    )
    file_type_field["canvas"].grid(row=1, column=0, sticky="ew", padx=(2, 6))
    _align_rounded_placeholder(file_type_field, left_pad=6, right_pad=30)

    uploader_field = _create_rounded_input(
        uploader_col,
        uploader_var,
        placeholder="이름을 입력하세요",
    )
    uploader_field["canvas"].grid(row=1, column=0, sticky="ew", padx=(2, 6))
    _align_rounded_placeholder(uploader_field, left_pad=6, right_pad=8)

    def _bind_date_entry(entry_widget, value_var):
        def on_focus_in(_event):
            return None

        def on_key_release(_event):
            if str(value_var.get() or "").strip() == "-":
                return

            _set_quick_button_state(None)

            _digits, normalized_text = (
                normalize_date_input(
                    value_var.get()
                )
            )

            value_var.set(normalized_text)
            entry_widget.icursor(tk.END)

        entry_widget.bind("<FocusIn>", on_focus_in, add="+")
        entry_widget.bind("<KeyRelease>", on_key_release, add="+")

    _bind_date_entry(date_from_field["entry"], date_from_var)
    _bind_date_entry(date_to_field["entry"], date_to_var)

    for search_entry in (
        date_from_field["entry"],
        date_to_field["entry"],
        doc_type_field["entry"],
        file_type_field["entry"],
        uploader_field["entry"],
    ):
        search_entry.bind(
            "<Return>",
            _run_search,
            add="+",
        )

    quick_date_state = {"active": None}
    quick_date_buttons = {}

    def _set_quick_button_state(active_key):
        quick_date_state["active"] = active_key
        for key, button in quick_date_buttons.items():
            button["set_active"](key == active_key)

    def _set_date_range_by_quick_key(key):
        today = date.today()
        if key == "today":
            iso_today = today.isoformat()
            date_from_var.set(iso_today)
            date_to_var.set(iso_today)
        elif key == "7d":
            date_to_var.set(today.isoformat())
            date_from_var.set((today - timedelta(days=6)).isoformat())
        elif key == "30d":
            date_to_var.set(today.isoformat())
            date_from_var.set((today - timedelta(days=29)).isoformat())
        elif key == "1y":
            date_to_var.set(today.isoformat())
            date_from_var.set((today - timedelta(days=365)).isoformat())
        elif key == "all":
            date_from_var.set("-")
            date_to_var.set("-")
        _set_quick_button_state(key)

    def _create_quick_button(parent, text, key):
        canvas = tk.Canvas(
            parent,
            bg=colors.SURFACE_ALT,
            highlightthickness=0,
            bd=0,
            height=24,
            cursor="hand2",
        )
        state = {"active": False}

        def _redraw(_event=None):
            canvas.delete("all")
            width = max(20, canvas.winfo_width())
            height = max(20, canvas.winfo_height())
            is_active = state["active"]
            fill_color = SF_PRIMARY if is_active else colors.SURFACE_ALT
            border_color = SF_PRIMARY if is_active else SF_INPUT_IDLE_BORDER
            text_color = colors.TEXT_INVERSE if is_active else SF_TEXT_DARK

            _draw_plain_rounded_rect(
                canvas,
                1,
                1,
                width - 1,
                height - 1,
                8,
                fill=fill_color,
                outline=border_color,
                border_width=1,
            )
            canvas.create_text(
                width / 2.0,
                height / 2.0,
                text=text,
                fill=text_color,
                font=app._font(9, "bold"),
                anchor="center",
                tags=("quick_btn",),
            )
            canvas.create_rectangle(0, 0, width, height, fill="", outline="", tags=("quick_btn",))

        def _apply_quick(_event=None):
            _set_date_range_by_quick_key(key)

        def _set_active(enabled):
            state["active"] = bool(enabled)
            _redraw()

        canvas.bind("<Configure>", _redraw, add="+")
        canvas.bind("<Button-1>", _apply_quick, add="+")
        canvas.tag_bind("quick_btn", "<Button-1>", _apply_quick)
        _redraw()
        return {
            "canvas": canvas,
            "set_active": _set_active,
        }

    for idx, (label_text, key) in enumerate([
        ("오늘", "today"),
        ("7일", "7d"),
        ("30일", "30d"),
        ("1년", "1y"),
        ("전체", "all"),
    ]):
        btn = _create_quick_button(date_quick_row, label_text, key)
        btn["canvas"].grid(row=0, column=idx, sticky="ew", padx=(0 if idx == 0 else 4, 0))
        quick_date_buttons[key] = btn

    _set_dropdown_icon(doc_type_field["toggle"], False)
    _set_dropdown_icon(file_type_field["toggle"], False)

    search_input_holder.pack(
        side="left",
        fill="both",
        expand=True,
    )

    search_input.pack(
        fill="both",
        expand=True,
    )

    clear_icon_button.place(relx=1.0, rely=0.5, x=-6, y=0, anchor="e")

    filter_label.pack(side="left", padx=(2, 0))
    filter_toggle_icon.pack(side="left", padx=(1, 0))

    root_click_binding_id = app.root.bind("<Button-1>", _on_click_outside_search_box, add="+")

    def _draw_card(card_canvas, bottom_shrink=12):
        card_canvas.delete("all")
        card_width = max(100, card_canvas.winfo_width())
        full_height = max(100, card_canvas.winfo_height())
        card_height = max(100, full_height - bottom_shrink)
        card_x1 = 1 + left_cards_left_inset
        card_x2 = max(card_x1 + 40, card_width - 1 - left_cards_right_inset)
        app._smooth_rounded_rect(
            card_canvas,
            card_x1,
            1,
            card_x2,
            card_height - 1,
            24,
            fill=colors.SURFACE_ALT,
            outline=SF_BORDER,
            width=1,
        )

    def _format_file_size(file_size):
        if file_size is None:
            return "-"

        try:
            size = float(file_size)
        except (TypeError, ValueError):
            return "-"

        units = ("B", "KB", "MB", "GB", "TB")
        unit_index = 0

        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024.0
            unit_index += 1

        if unit_index == 0:
            return f"{int(size)} {units[unit_index]}"

        if size >= 100:
            return f"{size:.0f} {units[unit_index]}"

        if size >= 10:
            return f"{size:.1f} {units[unit_index]}"

        return f"{size:.2f} {units[unit_index]}"

    def _format_archived_at(value):
        text = str(value or "").strip()

        if not text:
            return "-"

        normalized = text.replace("T", " ")
        if normalized.endswith("Z"):
            normalized = normalized[:-1]

        try:
            parsed = datetime.fromisoformat(normalized)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            pass

        if len(text) >= 10:
            return text[:10]

        return text

    def _normalize_file_type(value):
        text = str(value or "").strip()

        if not text:
            return ""

        if text.startswith("."):
            text = text[1:]

        return text.lower()

    def _format_file_type_label(value):
        normalized = _normalize_file_type(value)

        if not normalized:
            return "-"

        return normalized.upper()

    def _pick_file_format_icon_key(file_type_value):
        normalized = _normalize_file_type(file_type_value)

        if not normalized:
            return "file"

        if normalized in {"zip", "7z", "rar", "tar", "gz"}:
            return "archive_folder"
        if normalized in {"doc", "docx"}:
            return "word"
        if normalized in {"txt"}:
            return "txt"
        if normalized in {"pdf"}:
            return "pdf"
        if normalized in {"xls", "xlsx", "xlsm"}:
            return "excel"
        if normalized in {"csv"}:
            return "csv"
        if normalized in {"ppt", "pptx", "pptm"}:
            return "powerpoint"
        if normalized in {"jpg", "jpeg", "png", "gif", "tmp", "tif", "tiff", "webp", "svg"}:
            return "image"
        if normalized in {"mp4", "mov", "avi", "wmv", "mkv"}:
            return "video"
        if normalized in {"mp3", "wma", "m4a"}:
            return "audio"
        if normalized in {"exe", "msi", "bat", "cmd"}:
            return "exe"
        if normalized in {"psd", "ai", "indd", "xd"}:
            return "design"
        if normalized in {"db", "sqlite", "mdb", "accdb"}:
            return "db"
        if normalized in {"html", "htm"}:
            return "html"

        return "file"

    def _resolve_file_type_colors(value):
        normalized = _normalize_file_type(value)
        return colors.FILE_TYPE_COLORS.get(
            normalized,
            colors.DEFAULT_FILE_TYPE_COLOR,
        )

    def _format_document_type_label(value):
        text = str(value or "").strip()
        return text if text else "-"

    def _resolve_document_type_colors(value):
        label = _format_document_type_label(value)
        return colors.DOCUMENT_TYPE_COLORS.get(
            label,
            colors.DEFAULT_DOCUMENT_TYPE_COLOR,
        )

    def _draw_document_type_badge(
        canvas,
        *,
        center_x,
        center_y,
        document_type_value,
        max_width,
        tag=None,
    ):
        badge_font = app._font(9, "bold")
        label = _format_document_type_label(document_type_value)
        label = _truncate_canvas_text(
            canvas,
            label,
            max(20, int(max_width) - 16),
            badge_font,
            truncate_suffix="...",
        )

        text_color, bg_color = _resolve_document_type_colors(document_type_value)
        text_width = tkfont.Font(font=badge_font).measure(label)

        badge_height = 24
        badge_width = max(36, text_width + 16)
        badge_width = min(badge_width, max(20, int(max_width)))

        x1 = center_x - (badge_width / 2.0)
        y1 = center_y - (badge_height / 2.0)
        x2 = center_x + (badge_width / 2.0)
        y2 = center_y + (badge_height / 2.0)

        _draw_plain_rounded_rect(
            canvas,
            x1,
            y1,
            x2,
            y2,
            10,
            fill=bg_color,
            outline=bg_color,
            border_width=1,
        )

        text_id = canvas.create_text(
            center_x,
            center_y,
            text=label,
            fill=text_color,
            font=badge_font,
            anchor="center",
            tags=((tag,) if tag else ()),
        )

        if tag:
            bbox = canvas.bbox(text_id)
            if bbox is not None:
                pad_x = 8
                pad_y = 6
                canvas.create_rectangle(
                    bbox[0] - pad_x,
                    bbox[1] - pad_y,
                    bbox[2] + pad_x,
                    bbox[3] + pad_y,
                    fill="",
                    outline="",
                    tags=(tag,),
                )

    def _draw_file_type_badge(
        canvas,
        *,
        center_x,
        center_y,
        file_type_value,
        max_width,
        tag=None,
    ):
        label = _format_file_type_label(file_type_value)
        text_color, bg_color = _resolve_file_type_colors(file_type_value)
        badge_font = app._font(9, "bold")
        text_width = tkfont.Font(font=badge_font).measure(label)

        badge_height = 24
        badge_width = max(36, text_width + 16)
        badge_width = min(badge_width, max(20, int(max_width)))

        x1 = center_x - (badge_width / 2.0)
        y1 = center_y - (badge_height / 2.0)
        x2 = center_x + (badge_width / 2.0)
        y2 = center_y + (badge_height / 2.0)

        _draw_plain_rounded_rect(
            canvas,
            x1,
            y1,
            x2,
            y2,
            10,
            fill=bg_color,
            outline=bg_color,
            border_width=1,
        )

        text_id = canvas.create_text(
            center_x,
            center_y,
            text=label,
            fill=text_color,
            font=badge_font,
            anchor="center",
            tags=((tag,) if tag else ()),
        )

        if tag:
            bbox = canvas.bbox(text_id)
            if bbox is not None:
                pad_x = 8
                pad_y = 6
                canvas.create_rectangle(
                    bbox[0] - pad_x,
                    bbox[1] - pad_y,
                    bbox[2] + pad_x,
                    bbox[3] + pad_y,
                    fill="",
                    outline="",
                    tags=(tag,),
                )

    def _format_detail_value(value, fallback="-"):
        if value is None:
            return fallback

        if isinstance(value, (list, tuple, set)):
            values = [
                str(item).strip()
                for item in value
                if str(item or "").strip()
            ]
            return ", ".join(values) if values else fallback

        text = str(value).strip()
        return text or fallback

    def _truncate_canvas_text(
        canvas,
        text,
        max_width,
        font,
        truncate_suffix="…",
    ):
        value = str(text or "")

        if max_width <= 10:
            return ""

        test_id = canvas.create_text(
            -10000,
            -10000,
            text=value,
            font=font,
            anchor="nw",
        )

        bbox = canvas.bbox(test_id)
        canvas.delete(test_id)

        if bbox is None or bbox[2] - bbox[0] <= max_width:
            return value

        suffix = str(truncate_suffix or "…")
        low = 0
        high = len(value)

        while low < high:
            middle = (low + high + 1) // 2
            candidate = value[:middle] + suffix

            test_id = canvas.create_text(
                -10000,
                -10000,
                text=candidate,
                font=font,
                anchor="nw",
            )
            bbox = canvas.bbox(test_id)
            canvas.delete(test_id)

            candidate_width = (
                bbox[2] - bbox[0]
                if bbox is not None
                else 0
            )

            if candidate_width <= max_width:
                low = middle
            else:
                high = middle - 1

        return value[:low] + suffix

    def _truncate_canvas_multiline_text(
        canvas,
        text,
        max_width,
        max_height,
        font,
        truncate_suffix="...",
    ):
        value = str(text or "")

        if max_width <= 10 or max_height <= 10:
            return ""

        def _fits(candidate):
            test_id = canvas.create_text(
                -10000,
                -10000,
                text=candidate,
                font=font,
                anchor="nw",
                width=max_width,
                justify="left",
            )
            bbox = canvas.bbox(test_id)
            canvas.delete(test_id)

            if bbox is None:
                return True

            return (bbox[3] - bbox[1]) <= max_height

        if _fits(value):
            return value

        suffix = str(truncate_suffix or "...")
        low = 0
        high = len(value)
        best = suffix

        while low < high:
            middle = (low + high + 1) // 2
            candidate = value[:middle].rstrip() + suffix

            if _fits(candidate):
                low = middle
                best = candidate
            else:
                high = middle - 1

        return best

    def _toggle_result_sort(sort_key):
        if not search_state["has_searched"]:
            return

        allowed_sort_keys = {
            "original_filename",
            "document_type",
            "document_date",
            "uploaded_by",
            "archived_at",
            "file_size",
            "file_ext",
        }

        if sort_key not in allowed_sort_keys:
            return

        current_key = result_sort_state["key"]
        current_direction = (
            result_sort_state["direction"]
        )

        if current_key != sort_key:
            next_direction = "asc"

        elif current_direction == "asc":
            next_direction = "desc"

        elif current_direction == "desc":
            next_direction = None

        else:
            next_direction = "asc"

        result_sort_state["key"] = (
            sort_key
            if next_direction is not None
            else None
        )
        result_sort_state["direction"] = (
            next_direction
        )

        sort_succeeded = _request_search_page(
            0,
            clear_detail=True,
        )

        if not sort_succeeded:
            result_sort_state["key"] = current_key
            result_sort_state["direction"] = (
                current_direction
            )

            _draw_results_table()
            _draw_file_details()

    def _get_page_count():
        total_count = int(
            search_state["total_count"] or 0
        )

        rows_per_page = max(
            1,
            int(result_table_state["rows_per_page"]),
        )

        if total_count == 0:
            return 1

        return (
            total_count + rows_per_page - 1
        ) // rows_per_page

    def _get_target_rows_per_page_for_layout():
        if filter_panel_state["target_expanded"]:
            return max(
                1,
                SF_RESULTS_PER_PAGE - SF_FILTER_EXPANDED_ROW_REDUCTION,
            )

        return SF_RESULTS_PER_PAGE

    def _sync_result_rows_per_page_for_layout(
        *,
        reload_page,
    ):
        target_rows_per_page = (
            _get_target_rows_per_page_for_layout()
        )

        if int(result_table_state["rows_per_page"]) == int(target_rows_per_page):
            return

        result_table_state["rows_per_page"] = int(
            target_rows_per_page
        )
        _clamp_result_page()

        if (
            reload_page
            and search_state["has_searched"]
            and not search_state["is_loading_page"]
        ):
            _request_search_page(
                result_table_state["page_index"],
                clear_detail=True,
            )

    def _clamp_result_page():
        page_count = _get_page_count()
        current_page = int(
            result_table_state["page_index"]
        )

        result_table_state["page_index"] = max(
            0,
            min(current_page, page_count - 1),
        )

    def _get_visible_page_indexes():
        page_count = _get_page_count()

        if page_count <= SF_VISIBLE_PAGE_BUTTONS:
            return list(range(page_count))

        current_page = int(
            result_table_state["page_index"]
        )

        half_window = (
            SF_VISIBLE_PAGE_BUTTONS // 2
        )

        window_start = current_page - half_window
        window_end = (
            window_start
            + SF_VISIBLE_PAGE_BUTTONS
        )

        if window_start < 0:
            window_start = 0
            window_end = SF_VISIBLE_PAGE_BUTTONS

        if window_end > page_count:
            window_end = page_count
            window_start = (
                page_count
                - SF_VISIBLE_PAGE_BUTTONS
            )

        return list(
            range(window_start, window_end)
        )

    def _change_result_page(direction):
        if search_state["is_loading_page"]:
            return

        page_count = _get_page_count()
        current_page = int(
            result_table_state["page_index"]
        )
        next_page = max(
            0,
            min(
                current_page + int(direction),
                page_count - 1,
            ),
        )

        if next_page == current_page:
            return

        _request_search_page(
            next_page,
            clear_detail=True,
        )

    def _go_to_result_page(page_index):
        if search_state["is_loading_page"]:
            return

        page_count = _get_page_count()

        normalized_page_index = max(
            0,
            min(
                int(page_index),
                page_count - 1,
            ),
        )

        if (
            normalized_page_index
            == result_table_state["page_index"]
        ):
            return

        _request_search_page(
            normalized_page_index,
            clear_detail=True,
        )

    def _go_to_first_result_page():
        _go_to_result_page(0)

    def _go_to_last_result_page():
        _go_to_result_page(
            _get_page_count() - 1
        )

    def _get_selected_result():
        selected_file_id = search_state["selected_file_id"]

        if selected_file_id is None:
            return None

        for result in search_state["results"]:
            if int(result["file_id"]) == int(selected_file_id):
                return result

        return None

    def _refresh_search_results_after_open_failure():
        if not search_state["has_searched"]:
            _draw_results_table()
            _draw_file_details()
            return

        current_page = int(
            result_table_state["page_index"]
        )

        loaded = _request_search_page(
            current_page,
            clear_detail=True,
            redraw=False,
        )

        if loaded:
            clamped_page = int(
                result_table_state["page_index"]
            )

            if clamped_page != current_page:
                _request_search_page(
                    clamped_page,
                    clear_detail=True,
                    redraw=False,
                )

            if (
                int(search_state["total_count"] or 0) > 0
                and not search_state["results"]
                and int(result_table_state["page_index"]) > 0
            ):
                _request_search_page(
                    int(result_table_state["page_index"]) - 1,
                    clear_detail=True,
                    redraw=False,
                )

        _draw_results_table()
        _draw_file_details()

    def _refresh_search_results_screen():
        if search_state["is_searching"] or search_state["is_loading_page"]:
            return

        search_state["selected_file_ids"].clear()
        result_table_state["select_all_checked"] = False

        if search_state["has_searched"]:
            _refresh_search_results_after_open_failure()
            return

        _run_search()

    def _resolve_unique_download_destination(base_directory, filename, used_names):
        safe_name = str(filename or "").strip()
        if not safe_name:
            safe_name = "downloaded_file"

        base_directory_path = Path(base_directory)
        initial_path = base_directory_path / safe_name
        candidate_name = initial_path.name
        stem = initial_path.stem
        suffix = initial_path.suffix

        counter = 2

        while True:
            normalized_name = candidate_name.casefold()
            candidate_path = base_directory_path / candidate_name

            if normalized_name not in used_names and not candidate_path.exists():
                used_names.add(normalized_name)
                return candidate_path

            candidate_name = f"{stem} ({counter}){suffix}"
            counter += 1

    def _download_selected_checkbox_files():
        selected_ids = set(
            int(file_id)
            for file_id in search_state["selected_file_ids"]
        )

        if not selected_ids:
            messagebox.showinfo(
                "선택 파일 모두 다운로드",
                "다운로드할 체크박스 선택 파일이 없습니다.",
                parent=app.root,
            )
            return

        current_page_file_ids = _get_current_page_file_ids()
        target_file_ids = [
            int(result["file_id"])
            for result in search_state["results"]
            if int(result["file_id"]) in selected_ids
            and int(result["file_id"]) in current_page_file_ids
        ]

        if not target_file_ids:
            messagebox.showinfo(
                "선택 파일 모두 다운로드",
                "현재 화면에서 체크된 파일이 없습니다.",
                parent=app.root,
            )
            return

        destination_directory = filedialog.askdirectory(
            parent=app.root,
            title="선택 파일 저장 위치",
        )

        if not destination_directory:
            return

        destination_path = Path(destination_directory)

        if not destination_path.exists() or not destination_path.is_dir():
            messagebox.showerror(
                "선택 파일 모두 다운로드",
                "선택한 저장 위치를 찾을 수 없습니다.",
                parent=app.root,
            )
            return

        try:
            current_workspace_id = int(workspace_id)
        except (TypeError, ValueError):
            messagebox.showerror(
                "선택 파일 모두 다운로드",
                "워크스페이스 정보를 확인할 수 없습니다.",
                parent=app.root,
            )
            return

        result_by_file_id = {
            int(result["file_id"]): result
            for result in search_state["results"]
        }

        used_names = {
            path.name.casefold()
            for path in destination_path.iterdir()
            if path.is_file()
        }

        downloaded_count = 0
        failed_messages = []
        needs_refresh = False

        for file_id in target_file_ids:
            result = result_by_file_id.get(file_id) or {}
            preferred_name = (
                str(result.get("original_filename") or "").strip()
                or str(result.get("archived_filename") or "").strip()
                or f"file_{file_id}"
            )

            destination_file = _resolve_unique_download_destination(
                destination_path,
                preferred_name,
                used_names,
            )

            try:
                file_operations.copy_file_to(
                    current_workspace_id,
                    file_id,
                    destination_file,
                    overwrite=False,
                )
                downloaded_count += 1

            except (FileNotFoundError, LookupError) as exc:
                failed_messages.append(
                    f"- {preferred_name}: {exc}"
                )
                needs_refresh = True

            except ConnectionError as exc:
                failed_messages.append(
                    f"- {preferred_name}: {exc}"
                )

            except Exception as exc:
                failed_messages.append(
                    f"- {preferred_name}: {type(exc).__name__}: {exc}"
                )

        if needs_refresh:
            _refresh_search_results_after_open_failure()

        if failed_messages:
            summary_lines = [
                f"성공: {downloaded_count}개",
                f"실패: {len(failed_messages)}개",
                "",
                "실패 상세:",
            ]
            summary_lines.extend(failed_messages[:10])

            if len(failed_messages) > 10:
                summary_lines.append(
                    f"... 외 {len(failed_messages) - 10}개"
                )

            messagebox.showerror(
                "선택 파일 모두 다운로드",
                "\n".join(summary_lines),
                parent=app.root,
            )
            return

        messagebox.showinfo(
            "선택 파일 모두 다운로드",
            f"총 {downloaded_count}개 파일을 다운로드했습니다.",
            parent=app.root,
        )

    def _open_selected_file():
        selected_result = _get_selected_result()

        if selected_result is None:
            return

        try:
            current_workspace_id = int(workspace_id)
            selected_file_id = int(
                selected_result["file_id"]
            )

            file_operations.open_file(
                current_workspace_id,
                selected_file_id,
            )

        except FileNotFoundError as exc:
            messagebox.showerror(
                "파일 열기",
                "파일을 NAS에서 찾을 수 없습니다. 파일 상태가 갱신되었습니다.\n\n"
                f"{exc}",
                parent=app.root,
            )
            _refresh_search_results_after_open_failure()

        except ConnectionError as exc:
            messagebox.showerror(
                "파일 열기",
                "워크스페이스/NAS에 연결할 수 없습니다. 연결 상태를 확인해 주세요.\n\n"
                f"{exc}",
                parent=app.root,
            )

        except LookupError as exc:
            messagebox.showerror(
                "파일 열기",
                "선택한 파일 정보를 찾을 수 없거나 더 이상 활성 상태가 아닙니다.\n"
                "검색 결과를 새로고침합니다.\n\n"
                f"{exc}",
                parent=app.root,
            )
            _refresh_search_results_after_open_failure()

        except NotImplementedError as exc:
            messagebox.showerror(
                "파일 열기",
                "현재 환경에서는 파일 열기를 지원하지 않습니다.\n\n"
                f"{exc}",
                parent=app.root,
            )

        except OSError as exc:
            messagebox.showerror(
                "파일 열기",
                "파일을 여는 데 실패했습니다. 기본 연결 프로그램 설정을 확인해 주세요.\n\n"
                f"{exc}",
                parent=app.root,
            )

        except Exception as exc:
            messagebox.showerror(
                "파일 열기",
                "파일 열기 중 오류가 발생했습니다.\n\n"
                f"{type(exc).__name__}: {exc}",
                parent=app.root,
            )

    def _resolve_selected_file_path(action_title):
        selected_result = _get_selected_result()

        if selected_result is None:
            return None

        try:
            current_workspace_id = int(workspace_id)
            selected_file_id = int(selected_result["file_id"])

            return file_operations.get_openable_path(
                current_workspace_id,
                selected_file_id,
            )

        except FileNotFoundError as exc:
            messagebox.showerror(
                action_title,
                "파일을 NAS에서 찾을 수 없습니다. 파일 상태가 갱신되었습니다.\n\n"
                f"{exc}",
                parent=app.root,
            )
            _refresh_search_results_after_open_failure()

        except ConnectionError as exc:
            messagebox.showerror(
                action_title,
                "워크스페이스/NAS에 연결할 수 없습니다. 연결 상태를 확인해 주세요.\n\n"
                f"{exc}",
                parent=app.root,
            )

        except LookupError as exc:
            messagebox.showerror(
                action_title,
                "선택한 파일 정보를 찾을 수 없거나 더 이상 활성 상태가 아닙니다.\n"
                "검색 결과를 새로고침합니다.\n\n"
                f"{exc}",
                parent=app.root,
            )
            _refresh_search_results_after_open_failure()

        except Exception as exc:
            messagebox.showerror(
                action_title,
                "경로 확인 중 오류가 발생했습니다.\n\n"
                f"{type(exc).__name__}: {exc}",
                parent=app.root,
            )

        return None

    def _open_selected_file_folder():
        selected_path = _resolve_selected_file_path("폴더 열기")

        if selected_path is None:
            return

        if sys.platform != "win32":
            messagebox.showerror(
                "폴더 열기",
                "현재 환경에서는 폴더 열기를 지원하지 않습니다.",
                parent=app.root,
            )
            return

        try:
            subprocess.Popen(
                [
                    "explorer",
                    "/select,",
                    str(selected_path),
                ]
            )
            return

        except OSError:
            pass

        try:
            subprocess.Popen(
                [
                    "explorer",
                    str(selected_path.parent),
                ]
            )

        except OSError as exc:
            messagebox.showerror(
                "폴더 열기",
                "폴더를 여는 중 운영체제 오류가 발생했습니다.\n\n"
                f"{exc}",
                parent=app.root,
            )

        except Exception as exc:
            messagebox.showerror(
                "폴더 열기",
                "폴더 열기 중 오류가 발생했습니다.\n\n"
                f"{type(exc).__name__}: {exc}",
                parent=app.root,
            )

    def _copy_selected_file_path():
        selected_path = _resolve_selected_file_path("경로 복사")

        if selected_path is None:
            return

        try:
            app.root.clipboard_clear()
            app.root.clipboard_append(str(selected_path))
            app.root.update_idletasks()
            messagebox.showinfo(
                "경로 복사",
                "파일 경로를 클립보드에 복사했습니다.",
                parent=app.root,
            )

        except TclError as exc:
            messagebox.showerror(
                "경로 복사",
                "클립보드에 경로를 복사하지 못했습니다.\n\n"
                f"{exc}",
                parent=app.root,
            )

        except Exception as exc:
            messagebox.showerror(
                "경로 복사",
                "경로 복사 중 오류가 발생했습니다.\n\n"
                f"{type(exc).__name__}: {exc}",
                parent=app.root,
            )

    def _download_selected_file():
        selected_result = _get_selected_result()

        if selected_result is None:
            return

        selected_path = _resolve_selected_file_path("다운로드")

        if selected_path is None:
            return

        try:
            current_workspace_id = int(workspace_id)
            selected_file_id = int(selected_result["file_id"])

            preferred_filename = str(
                selected_result.get("original_filename")
                or selected_path.name
                or ""
            ).strip()

            if not preferred_filename:
                preferred_filename = str(selected_path.name)

            default_extension = Path(preferred_filename).suffix or ""

            destination = filedialog.asksaveasfilename(
                parent=app.root,
                title="다운로드 위치 선택",
                initialfile=preferred_filename,
                defaultextension=default_extension,
                filetypes=[("모든 파일", "*.*")],
                confirmoverwrite=False,
            )

            if not destination:
                return

            destination_path = Path(destination)
            should_overwrite = False

            if destination_path.exists():
                should_overwrite = messagebox.askyesno(
                    "다운로드",
                    "같은 이름의 파일이 이미 존재합니다. 덮어쓰시겠어요?",
                    parent=app.root,
                )

                if not should_overwrite:
                    return

            downloaded_path = file_operations.copy_file_to(
                current_workspace_id,
                selected_file_id,
                destination_path,
                overwrite=should_overwrite,
            )

            messagebox.showinfo(
                "다운로드",
                "파일 다운로드가 완료되었습니다.\n\n"
                f"{downloaded_path}",
                parent=app.root,
            )

        except FileNotFoundError as exc:
            messagebox.showerror(
                "다운로드",
                "파일을 NAS에서 찾을 수 없습니다. 파일 상태가 갱신되었습니다.\n\n"
                f"{exc}",
                parent=app.root,
            )
            _refresh_search_results_after_open_failure()

        except ConnectionError as exc:
            messagebox.showerror(
                "다운로드",
                "워크스페이스/NAS에 연결할 수 없습니다. 연결 상태를 확인해 주세요.\n\n"
                f"{exc}",
                parent=app.root,
            )

        except LookupError as exc:
            messagebox.showerror(
                "다운로드",
                "선택한 파일 정보를 찾을 수 없거나 더 이상 활성 상태가 아닙니다.\n"
                "검색 결과를 새로고침합니다.\n\n"
                f"{exc}",
                parent=app.root,
            )
            _refresh_search_results_after_open_failure()

        except PermissionError as exc:
            messagebox.showerror(
                "다운로드",
                "선택한 위치에 파일을 저장할 권한이 없습니다.\n\n"
                f"{exc}",
                parent=app.root,
            )

        except FileExistsError as exc:
            messagebox.showerror(
                "다운로드",
                "대상 위치에 같은 파일이 이미 존재합니다.\n\n"
                f"{exc}",
                parent=app.root,
            )

        except NotADirectoryError as exc:
            messagebox.showerror(
                "다운로드",
                "선택한 저장 위치가 올바른 폴더가 아닙니다.\n\n"
                f"{exc}",
                parent=app.root,
            )

        except OSError as exc:
            messagebox.showerror(
                "다운로드",
                "파일 저장 중 운영체제 오류가 발생했습니다.\n\n"
                f"{exc}",
                parent=app.root,
            )

        except Exception as exc:
            messagebox.showerror(
                "다운로드",
                "다운로드 중 오류가 발생했습니다.\n\n"
                f"{type(exc).__name__}: {exc}",
                parent=app.root,
            )

    def _get_selected_result_index():
        selected_file_id = search_state[
            "selected_file_id"
        ]

        if selected_file_id is None:
            return None

        for index, result in enumerate(
            search_state["results"]
        ):
            if (
                int(result["file_id"])
                == int(selected_file_id)
            ):
                return index

        return None

    def _select_result_row(file_id):
        left_bottom_card.focus_set()

        search_state["selected_file_id"] = int(
            file_id
        )

        _draw_results_table()
        _draw_file_details()

    def _open_result_row(file_id):
        _select_result_row(file_id)
        _open_selected_file()
        return "break"

    def _select_result_by_index(result_index):
        results = search_state["results"]

        if not results:
            return

        normalized_index = max(
            0,
            min(
                int(result_index),
                len(results) - 1,
            ),
        )

        selected_result = results[
            normalized_index
        ]

        search_state["selected_file_id"] = int(
            selected_result["file_id"]
        )

        _draw_results_table()
        _draw_file_details()

    def _move_result_selection(direction):
        results = search_state["results"]

        if not results:
            return "break"

        selected_index = (
            _get_selected_result_index()
        )

        if selected_index is None:
            target_index = (
                0
                if int(direction) >= 0
                else len(results) - 1
            )

        else:
            target_index = (
                selected_index + int(direction)
            )

        if target_index < 0:
            current_page = int(
                result_table_state["page_index"]
            )

            if current_page > 0:
                loaded = _request_search_page(
                    current_page - 1,
                    clear_detail=True,
                    redraw=False,
                )

                if loaded and search_state["results"]:
                    _select_result_by_index(
                        len(search_state["results"]) - 1
                    )

                if not loaded:
                    _draw_results_table()
                    _draw_file_details()

            return "break"

        if target_index >= len(results):
            current_page = int(
                result_table_state["page_index"]
            )

            if current_page < _get_page_count() - 1:
                loaded = _request_search_page(
                    current_page + 1,
                    clear_detail=True,
                    redraw=False,
                )

                if loaded and search_state["results"]:
                    _select_result_by_index(0)

                if not loaded:
                    _draw_results_table()
                    _draw_file_details()

            return "break"

        _select_result_by_index(target_index)
        return "break"

    def _move_result_page(direction):
        current_page = int(
            result_table_state["page_index"]
        )

        target_page = max(
            0,
            min(
                current_page + int(direction),
                _get_page_count() - 1,
            ),
        )

        if target_page == current_page:
            return "break"

        selected_index = (
            _get_selected_result_index()
        )
        if selected_index is None:
            selected_index = 0

        loaded = _request_search_page(
            target_page,
            clear_detail=True,
            redraw=False,
        )

        if not loaded:
            _draw_results_table()
            _draw_file_details()
            return "break"

        if search_state["results"]:
            _select_result_by_index(
                min(
                    selected_index,
                    len(search_state["results"]) - 1,
                )
            )

        return "break"

    def _select_first_result(_event=None):
        if search_state["total_count"]:
            loaded = _request_search_page(
                0,
                clear_detail=True,
                redraw=False,
            )

            if loaded and search_state["results"]:
                _select_result_by_index(0)
            elif not loaded:
                _draw_results_table()
                _draw_file_details()

        return "break"

    def _select_last_result(_event=None):
        if search_state["total_count"]:
            last_page = _get_page_count() - 1

            loaded = _request_search_page(
                last_page,
                clear_detail=True,
                redraw=False,
            )

            if loaded and search_state["results"]:
                _select_result_by_index(
                    len(search_state["results"]) - 1
                )
            elif not loaded:
                _draw_results_table()
                _draw_file_details()

        return "break"

    def _toggle_keyboard_selected_result(
        _event=None,
    ):
        selected_file_id = search_state[
            "selected_file_id"
        ]

        if selected_file_id is not None:
            _toggle_result_checkbox(
                selected_file_id
            )

        return "break"

    def _clear_detail_selection(_event=None):
        search_state["selected_file_id"] = None

        _draw_results_table()
        _draw_file_details()

        return "break"

    def _toggle_result_checkbox(file_id):
        left_bottom_card.focus_set()

        normalized_file_id = int(file_id)
        selected_ids = search_state["selected_file_ids"]

        if normalized_file_id in selected_ids:
            selected_ids.remove(normalized_file_id)
        else:
            selected_ids.add(normalized_file_id)

        _draw_results_table()

    def _get_current_page_file_ids():
        rows_per_page = max(
            1,
            int(result_table_state["rows_per_page"]),
        )

        return {
            int(result["file_id"])
            for result in search_state["results"][:rows_per_page]
        }

    def _clear_result_selection():
        search_state["selected_file_ids"].clear()

        result_table_state["select_all_checked"] = False

        _draw_results_table()

    def _select_current_result_page():
        page_file_ids = _get_current_page_file_ids()

        search_state["selected_file_ids"].update(
            page_file_ids
        )

        _draw_results_table()

    def _draw_pagination_button(
        canvas,
        *,
        center_x,
        center_y,
        width,
        height,
        tag,
        text=None,
        icon=None,
        active=False,
        enabled=True,
        command=None,
    ):
        x1 = center_x - (width / 2.0)
        y1 = center_y - (height / 2.0)
        x2 = center_x + (width / 2.0)
        y2 = center_y + (height / 2.0)

        fill_color = (
            SF_PRIMARY
            if active
            else colors.SURFACE_ALT
        )

        border_color = (
            SF_PRIMARY
            if active
            else (
                SF_BORDER
                if enabled
                else colors.SURFACE_ALT
            )
        )

        text_color = (
            colors.TEXT_INVERSE
            if active
            else (
                SF_TEXT_DARK
                if enabled
                else SF_TEXT_PLACEHOLDER
            )
        )

        _draw_plain_rounded_rect(
            canvas,
            x1,
            y1,
            x2,
            y2,
            8,
            fill=fill_color,
            outline=border_color,
            border_width=1,
        )

        if icon is not None:
            canvas.create_image(
                center_x,
                center_y,
                image=icon,
                anchor="center",
                tags=(tag,),
            )

        elif text is not None:
            canvas.create_text(
                center_x,
                center_y,
                text=text,
                fill=text_color,
                font=app._font(9, "bold"),
                anchor="center",
                tags=(tag,),
            )

        canvas.create_rectangle(
            x1,
            y1,
            x2,
            y2,
            fill="",
            outline="",
            tags=(tag,),
        )

        if enabled and callable(command):
            canvas.tag_bind(
                tag,
                "<Button-1>",
                lambda _event: command(),
            )

    def _draw_selection_toolbar_button(
        canvas,
        *,
        x,
        center_y,
        text,
        tag,
        command,
        icon=None,
        fill=colors.SURFACE_ALT,
        outline=SF_BORDER,
        text_color=SF_TEXT_DARK,
        hover_fill=SF_SURFACE_HOVER_SOFT,
        hover_outline=SF_BORDER,
    ):
        text_font = app._font(9, "bold")

        text_id = canvas.create_text(
            -10000,
            -10000,
            text=text,
            font=text_font,
            anchor="nw",
        )
        bbox = canvas.bbox(text_id)
        canvas.delete(text_id)

        text_width = (
            bbox[2] - bbox[0]
            if bbox is not None
            else 60
        )

        icon_width = icon.width() if icon is not None else 0
        icon_gap = 6 if icon is not None else 0

        button_width = text_width + icon_width + icon_gap + 24
        button_height = 28

        x1 = x
        y1 = center_y - button_height / 2.0
        x2 = x1 + button_width
        y2 = center_y + button_height / 2.0

        background_shape = app._smooth_rounded_rect(
            canvas,
            x1,
            y1,
            x2,
            y2,
            8,
            fill=fill,
            outline=outline,
            width=1,
            tags=(tag, f"{tag}_bg"),
        )

        content_center_x = (x1 + x2) / 2.0
        content_left = content_center_x - ((text_width + icon_width + icon_gap) / 2.0)

        if icon is not None:
            canvas.create_image(
                content_left,
                center_y,
                image=icon,
                anchor="w",
                tags=(tag,),
            )

        canvas.create_text(
            content_left + icon_width + icon_gap,
            center_y,
            text=text,
            fill=text_color,
            font=text_font,
            anchor="w",
            tags=(tag,),
        )

        canvas.create_rectangle(
            x1,
            y1,
            x2,
            y2,
            fill="",
            outline="",
            tags=(tag,),
        )

        canvas.tag_bind(
            tag,
            "<Button-1>",
            lambda _event: command(),
        )
        canvas.tag_bind(
            tag,
            "<Enter>",
            lambda _event: (
                canvas.itemconfigure(background_shape, fill=hover_fill, outline=hover_outline),
                canvas.configure(cursor="hand2"),
            ),
        )
        canvas.tag_bind(
            tag,
            "<Leave>",
            lambda _event: (
                canvas.itemconfigure(background_shape, fill=fill, outline=outline),
                canvas.configure(cursor=""),
            ),
        )

        return x2

    def _draw_results_table():
        card_canvas = left_bottom_card
        card_canvas.delete("all")

        card_width = max(
            100,
            card_canvas.winfo_width(),
        )
        full_height = max(
            100,
            card_canvas.winfo_height(),
        )
        card_height = max(
            100,
            full_height - 12,
        )

        card_x1 = 1 + left_cards_left_inset
        card_x2 = max(
            card_x1 + 40,
            card_width - 1 - left_cards_right_inset,
        )

        app._smooth_rounded_rect(
            card_canvas,
            card_x1,
            1,
            card_x2,
            card_height - 1,
            24,
            fill=colors.SURFACE_ALT,
            outline=SF_BORDER,
            width=1,
        )

        inner_padding = 8
        inner_x1 = card_x1 + inner_padding
        inner_y1 = inner_padding
        inner_x2 = card_x2 - inner_padding
        inner_y2 = card_height - inner_padding
        inner_height = max(1, inner_y2 - inner_y1)

        title_height = 48
        header_height = 36
        footer_height = 46

        body_top = inner_y1 + title_height + header_height
        body_bottom = inner_y2 - footer_height
        body_height = max(1, body_bottom - body_top)

        card_canvas.create_rectangle(
            inner_x1,
            inner_y1,
            inner_x2,
            inner_y1 + title_height,
            fill=colors.SURFACE_ALT,
            outline="",
        )
        card_canvas.create_rectangle(
            inner_x1,
            inner_y1 + title_height,
            inner_x2,
            body_top,
            fill=colors.SURFACE_ACCENT_SOFT,
            outline="",
        )
        card_canvas.create_rectangle(
            inner_x1,
            body_top,
            inner_x2,
            body_bottom,
            fill=colors.SURFACE_ALT,
            outline="",
        )
        card_canvas.create_rectangle(
            inner_x1,
            body_bottom,
            inner_x2,
            inner_y2,
            fill=colors.SURFACE_ALT,
            outline="",
        )

        for divider_y in (
            inner_y1 + title_height,
            body_top,
            body_bottom,
        ):
            card_canvas.create_line(
                inner_x1,
                divider_y,
                inner_x2,
                divider_y,
                fill=SF_BORDER,
                width=1,
            )

        title_center_y = (
            inner_y1 + title_height / 2.0
        )

        selected_count = len(
            search_state["selected_file_ids"]
        )

        title_left = inner_x1 + 10
        title_label_text = "검색 결과"
        title_font = app._font(14, "bold")

        card_canvas.create_text(
            title_left,
            title_center_y,
            text=title_label_text,
            fill=SF_TEXT_MAIN,
            font=title_font,
            anchor="w",
        )

        title_label_width = tkfont.Font(font=title_font).measure(
            title_label_text
        )
        show_result_count_badge = int(
            search_state["total_count"] or 0
        ) > 0
        title_tail_x = (
            title_left + title_label_width
        )

        if show_result_count_badge:
            badge_right = _draw_count_badge(
                card_canvas,
                left=title_tail_x + 8,
                center_y=title_center_y,
                text=search_result_count_var.get(),
            )
            title_tail_x = badge_right

        if show_result_count_badge:
            reset_tag = "sf_results_reset_button"
            reset_hit_size = 24
            reset_center_x = title_tail_x + 8 + (reset_hit_size / 2.0)
            reset_left = reset_center_x - (reset_hit_size / 2.0)
            reset_top = title_center_y - (reset_hit_size / 2.0)
            reset_right = reset_center_x + (reset_hit_size / 2.0)
            reset_bottom = title_center_y + (reset_hit_size / 2.0)

            reset_hover_id = card_canvas.create_rectangle(
                reset_left,
                reset_top,
                reset_right,
                reset_bottom,
                fill=colors.SURFACE_ALT,
                outline="",
                tags=(f"{reset_tag}_hover",),
            )

            if result_reset_icon_photo is not None:
                card_canvas.create_image(
                    reset_center_x,
                    title_center_y,
                    image=result_reset_icon_photo,
                    anchor="center",
                    tags=(reset_tag,),
                )
            else:
                card_canvas.create_text(
                    reset_center_x,
                    title_center_y,
                    text="R",
                    fill=SF_TEXT_DARK,
                    font=app._font(10, "bold"),
                    anchor="center",
                    tags=(reset_tag,),
                )

            card_canvas.create_rectangle(
                reset_left,
                reset_top,
                reset_right,
                reset_bottom,
                fill="",
                outline="",
                tags=(reset_tag,),
            )

            card_canvas.tag_bind(
                reset_tag,
                "<Enter>",
                lambda _event: (
                    card_canvas.itemconfigure(
                        reset_hover_id,
                        fill=SF_SURFACE_HOVER_SOFT,
                    ),
                    card_canvas.configure(cursor="hand2"),
                ),
            )
            card_canvas.tag_bind(
                reset_tag,
                "<Leave>",
                lambda _event: (
                    card_canvas.itemconfigure(
                        reset_hover_id,
                        fill=colors.SURFACE_ALT,
                    ),
                    card_canvas.configure(cursor=""),
                ),
            )
            card_canvas.tag_bind(
                reset_tag,
                "<Button-1>",
                lambda _event: _refresh_search_results_screen(),
            )

            card_canvas.tag_raise(reset_tag)

        if search_state["is_loading_page"]:
            card_canvas.create_text(
                inner_x2 - 12,
                title_center_y,
                text="불러오는 중…",
                fill=SF_STATUS_PROCESSING,
                font=app._font(9, "bold"),
                anchor="e",
            )

        available_toolbar_width = (
            inner_x2 - inner_x1
        )

        if selected_count and available_toolbar_width >= 620:
            toolbar_gap = 6
            toolbar_right = inner_x2 - 10

            toolbar_specs = [
                (
                    "선택 파일 모두 다운로드",
                    "sf_download_selected",
                    _download_selected_checkbox_files,
                    toolbar_download_blue_icon_photo,
                ),
            ]

            page_file_ids_for_toolbar = (
                _get_current_page_file_ids()
            )

            if (
                page_file_ids_for_toolbar
                and not page_file_ids_for_toolbar.issubset(
                    search_state["selected_file_ids"]
                )
            ):
                toolbar_specs.insert(
                    0,
                    (
                        "현재 페이지 선택",
                        "sf_select_page",
                        _select_current_result_page,
                        None,
                    ),
                )

            button_measurements = []

            for text, tag, command, icon in toolbar_specs:
                measure_id = card_canvas.create_text(
                    -10000,
                    -10000,
                    text=text,
                    font=app._font(9, "bold"),
                    anchor="nw",
                )
                bbox = card_canvas.bbox(measure_id)
                card_canvas.delete(measure_id)

                text_width = (
                    bbox[2] - bbox[0]
                    if bbox is not None
                    else 60
                )

                icon_width = icon.width() if icon is not None else 0
                icon_gap = 6 if icon is not None else 0

                button_measurements.append(
                    text_width + icon_width + icon_gap + 24
                )

            toolbar_width = sum(button_measurements)
            toolbar_width += toolbar_gap * max(
                0,
                len(toolbar_specs) - 1,
            )

            toolbar_x = toolbar_right - toolbar_width

            for text, tag, command, icon in toolbar_specs:
                is_download_button = tag == "sf_download_selected"
                toolbar_x = _draw_selection_toolbar_button(
                    card_canvas,
                    x=toolbar_x,
                    center_y=title_center_y,
                    text=text,
                    tag=tag,
                    command=command,
                    icon=icon,
                    fill=(
                        colors.SURFACE_ALT
                        if is_download_button
                        else colors.SURFACE_ALT
                    ),
                    outline=(
                        SF_PRIMARY
                        if is_download_button
                        else SF_BORDER
                    ),
                    text_color=(
                        SF_PRIMARY
                        if is_download_button
                        else SF_TEXT_DARK
                    ),
                    hover_fill=(
                        colors.SURFACE_ACCENT_SOFT
                        if is_download_button
                        else SF_SURFACE_HOVER_SOFT
                    ),
                    hover_outline=(
                        SF_PRIMARY
                        if is_download_button
                        else SF_BORDER
                    ),
                )
                toolbar_x += toolbar_gap

        table_col_widths_pct = [
            5.0,
            35.0,
            10.0,
            14.0,
            7.0,
            14.0,
            5.0,
            10.0,
        ]
        header_definitions = [
            {
                "text": "",
                "sort_key": None,
            },
            {
                "text": "문서명",
                "sort_key": "original_filename",
            },
            {
                "text": "문서 유형",
                "sort_key": "document_type",
            },
            {
                "text": "문서 날짜",
                "sort_key": "document_date",
            },
            {
                "text": "업로더",
                "sort_key": "uploaded_by",
            },
            {
                "text": "업로드 날짜",
                "sort_key": "archived_at",
            },
            {
                "text": "크기",
                "sort_key": "file_size",
            },
            {
                "text": "파일 종류",
                "sort_key": "file_ext",
            },
        ]

        table_x1 = inner_x1 + 2
        table_x2 = inner_x2 - 2
        table_width = max(1, table_x2 - table_x1)

        column_widths = [
            int(table_width * (pct / 100.0))
            for pct in table_col_widths_pct
        ]
        column_widths[-1] += (
            table_width - sum(column_widths)
        )

        column_starts = []
        column_centers = []

        x_cursor = table_x1
        for column_width in column_widths:
            column_starts.append(x_cursor)
            column_centers.append(
                x_cursor + (column_width / 2.0)
            )
            x_cursor += column_width

        header_center_y = (
            inner_y1
            + title_height
            + (header_height / 2.0)
        )

        for column_index, definition in enumerate(
            header_definitions
        ):
            header_text = definition["text"]
            sort_key = definition["sort_key"]

            if not header_text:
                continue

            displayed_header = header_text

            if result_sort_state["key"] == sort_key:
                if result_sort_state["direction"] == "asc":
                    displayed_header += " ▲"
                elif result_sort_state["direction"] == "desc":
                    displayed_header += " ▼"

            header_tag = (
                f"sf_result_header_{column_index}"
            )

            card_canvas.create_text(
                column_centers[column_index],
                header_center_y,
                text=displayed_header,
                fill=(
                    SF_PRIMARY
                    if result_sort_state["key"] == sort_key
                    else SF_TEXT_DARK
                ),
                font=app._font(11),
                anchor="center",
                tags=(header_tag,),
            )

            if sort_key is not None:
                card_canvas.create_rectangle(
                    column_starts[column_index],
                    inner_y1 + title_height,
                    column_starts[column_index]
                    + column_widths[column_index],
                    body_top,
                    fill="",
                    outline="",
                    tags=(header_tag,),
                )

                card_canvas.tag_bind(
                    header_tag,
                    "<Button-1>",
                    lambda _event, key=sort_key:
                        _toggle_result_sort(key),
                )
                card_canvas.tag_bind(
                    header_tag,
                    "<Enter>",
                    lambda _event:
                        card_canvas.configure(cursor="hand2"),
                )
                card_canvas.tag_bind(
                    header_tag,
                    "<Leave>",
                    lambda _event:
                        card_canvas.configure(cursor=""),
                )

        results = search_state["results"]

        rows_per_page = max(
            1,
            int(result_table_state["rows_per_page"]),
        )

        # Keep result row spacing stable across filter expand/collapse.
        if not filter_panel_state["target_expanded"]:
            result_table_state["base_row_height"] = max(
                32,
                int(
                    body_height
                    / max(1, SF_RESULTS_PER_PAGE)
                ),
            )

        row_height = max(
            32,
            int(
                result_table_state["base_row_height"]
                or (
                    body_height
                    / max(1, SF_RESULTS_PER_PAGE)
                )
            ),
        )

        _clamp_result_page()

        page_index = int(
            result_table_state["page_index"]
        )
        page_loading = search_state[
            "is_loading_page"
        ]
        row_slots = []

        for slot_index in range(rows_per_page):
            row_top = body_top + (slot_index * row_height)
            row_bottom = row_top + row_height

            if row_bottom > body_bottom:
                break

            row_slots.append(
                (
                    row_top,
                    row_bottom,
                )
            )

        if not row_slots and body_bottom > body_top:
            row_slots.append(
                (
                    body_top,
                    body_bottom,
                )
            )

        page_results = results[: len(row_slots)]

        page_file_ids = {
            int(result["file_id"])
            for result in page_results
        }

        selected_ids = search_state["selected_file_ids"]

        all_page_selected = (
            bool(page_file_ids)
            and page_file_ids.issubset(selected_ids)
        )
        result_table_state["select_all_checked"] = (
            all_page_selected
        )

        unchecked_icon = result_table_icons.get("unchecked")
        checked_icon = result_table_icons.get("checked")

        select_all_tag = "sf_result_select_all"
        select_all_icon = (
            checked_icon
            if all_page_selected
            else unchecked_icon
        )

        if select_all_icon is not None:
            card_canvas.create_image(
                column_centers[0],
                header_center_y,
                image=select_all_icon,
                anchor="center",
                tags=(select_all_tag,),
            )
        else:
            card_canvas.create_text(
                column_centers[0],
                header_center_y,
                text="☑" if all_page_selected else "□",
                fill=SF_TEXT_DARK,
                font=app._font(12, "bold"),
                anchor="center",
                tags=(select_all_tag,),
            )

        card_canvas.create_rectangle(
            column_starts[0],
            inner_y1 + title_height,
            column_starts[0] + column_widths[0],
            body_top,
            fill="",
            outline="",
            tags=(select_all_tag,),
        )

        def _toggle_select_all(_event=None):
            if not page_file_ids:
                return "break"

            if page_file_ids.issubset(selected_ids):
                selected_ids.difference_update(page_file_ids)
            else:
                selected_ids.update(page_file_ids)

            _draw_results_table()
            return "break"

        card_canvas.tag_bind(
            select_all_tag,
            "<Button-1>",
            _toggle_select_all,
        )

        if search_state["error"]:
            card_canvas.create_text(
                (inner_x1 + inner_x2) / 2.0,
                (body_top + body_bottom) / 2.0,
                text=search_state["error"],
                fill=SF_STATUS_FAILED,
                font=app._font(11),
                width=max(
                    100,
                    inner_x2 - inner_x1 - 80,
                ),
                justify="center",
                anchor="center",
            )

        elif not search_state["has_searched"]:
            card_canvas.create_text(
                (inner_x1 + inner_x2) / 2.0,
                (body_top + body_bottom) / 2.0,
                text=(
                    "검색어나 상세 조건을 입력한 뒤\n"
                    "Enter 키를 눌러 주세요"
                ),
                fill=SF_TEXT_PLACEHOLDER,
                font=app._font(11),
                justify="center",
                anchor="center",
            )

        elif not results:
            card_canvas.create_text(
                (inner_x1 + inner_x2) / 2.0,
                (body_top + body_bottom) / 2.0,
                text=(
                    "조건에 맞는 파일이 없어요.\n"
                    "검색어나 필터를 변경해 보세요."
                ),
                fill=SF_TEXT_PLACEHOLDER,
                font=app._font(11),
                justify="center",
                anchor="center",
            )

        else:
            row_font = app._font(10)
            filename_font = app._font(10, "bold")

            for local_index, result in enumerate(page_results):
                row_top, row_bottom = row_slots[
                    local_index
                ]
                row_center = (
                    row_top + row_bottom
                ) / 2.0

                file_id = int(result["file_id"])
                is_selected_row = (
                    search_state["selected_file_id"]
                    == file_id
                )
                is_checked = file_id in selected_ids
                is_hovered = (
                    result_table_state[
                        "hovered_file_id"
                    ]
                    == file_id
                )

                if is_selected_row:
                    row_fill = (
                        SF_RESULT_ROW_SELECTED_BG
                    )
                elif is_hovered:
                    row_fill = SF_RESULT_ROW_HOVER_BG
                else:
                    row_fill = colors.SURFACE_ALT

                row_tag = f"sf_result_row_{file_id}"
                row_background_tag = (
                    f"sf_result_row_background_{file_id}"
                )
                check_tag = f"sf_result_check_{file_id}"

                card_canvas.create_rectangle(
                    table_x1,
                    row_top,
                    table_x2,
                    row_bottom,
                    fill=row_fill,
                    outline="",
                    tags=(
                        row_tag,
                        row_background_tag,
                    ),
                )

                checkbox_icon = (
                    checked_icon
                    if is_checked
                    else unchecked_icon
                )

                if checkbox_icon is not None:
                    card_canvas.create_image(
                        column_centers[0],
                        row_center,
                        image=checkbox_icon,
                        anchor="center",
                        tags=(check_tag,),
                    )
                else:
                    card_canvas.create_text(
                        column_centers[0],
                        row_center,
                        text="☑" if is_checked else "□",
                        fill=SF_TEXT_DARK,
                        font=app._font(12, "bold"),
                        anchor="center",
                        tags=(check_tag,),
                    )

                card_canvas.create_rectangle(
                    column_starts[0],
                    row_top,
                    column_starts[0] + column_widths[0],
                    row_bottom,
                    fill="",
                    outline="",
                    tags=(check_tag,),
                )

                filename = _truncate_canvas_text(
                    card_canvas,
                    str(
                        result.get(
                            "original_filename",
                            "",
                        )
                        or ""
                    ).lower(),
                    column_widths[1] - 14,
                    filename_font,
                )

                document_type = result.get("document_type", "")

                uploaded_by = _truncate_canvas_text(
                    card_canvas,
                    result.get("uploaded_by", ""),
                    column_widths[4] - 10,
                    row_font,
                    truncate_suffix="...",
                )

                row_values = [
                    None,
                    filename,
                    document_type,
                    result.get("document_date") or "-",
                    uploaded_by,
                    _format_archived_at(
                        result.get("archived_at")
                    ),
                    _format_file_size(
                        result.get("file_size")
                    ),
                    result.get("file_ext"),
                ]

                for column_index, value in enumerate(row_values):
                    if column_index == 0 or value is None:
                        continue

                    if column_index == 2:
                        _draw_document_type_badge(
                            card_canvas,
                            center_x=column_centers[column_index],
                            center_y=row_center,
                            document_type_value=value,
                            max_width=column_widths[column_index] - 10,
                            tag=row_tag,
                        )
                        continue

                    if column_index == 7:
                        _draw_file_type_badge(
                            card_canvas,
                            center_x=column_centers[column_index],
                            center_y=row_center,
                            file_type_value=value,
                            max_width=column_widths[column_index] - 10,
                            tag=row_tag,
                        )
                        continue

                    anchor = (
                        "w"
                        if column_index == 1
                        else "center"
                    )
                    text_x = (
                        column_starts[column_index] + 7
                        if column_index == 1
                        else column_centers[column_index]
                    )

                    card_canvas.create_text(
                        text_x,
                        row_center,
                        text=value,
                        fill=SF_TEXT_DARK,
                        font=(
                            filename_font
                            if column_index == 1
                            else row_font
                        ),
                        anchor=anchor,
                        tags=(row_tag,),
                    )

                card_canvas.tag_bind(
                    row_tag,
                    "<Button-1>",
                    lambda _event, fid=file_id:
                        _select_result_row(fid),
                )
                card_canvas.tag_bind(
                    row_tag,
                    "<Double-Button-1>",
                    lambda _event, fid=file_id:
                        _open_result_row(fid),
                )
                def _on_row_enter(
                    _event,
                    hovered_id=file_id,
                    background_tag=row_background_tag,
                ):
                    result_table_state[
                        "hovered_file_id"
                    ] = hovered_id

                    card_canvas.configure(cursor="hand2")

                    if (
                        search_state["selected_file_id"]
                        != hovered_id
                    ):
                        card_canvas.itemconfigure(
                            background_tag,
                            fill=SF_RESULT_ROW_HOVER_BG,
                        )

                def _on_row_leave(
                    _event,
                    hovered_id=file_id,
                    background_tag=row_background_tag,
                ):
                    if (
                        result_table_state[
                            "hovered_file_id"
                        ]
                        == hovered_id
                    ):
                        result_table_state[
                            "hovered_file_id"
                        ] = None

                    card_canvas.configure(cursor="")

                    if (
                        search_state["selected_file_id"]
                        != hovered_id
                    ):
                        card_canvas.itemconfigure(
                            background_tag,
                            fill=colors.SURFACE_ALT,
                        )

                card_canvas.tag_bind(
                    row_tag,
                    "<Enter>",
                    _on_row_enter,
                )
                card_canvas.tag_bind(
                    row_tag,
                    "<Leave>",
                    _on_row_leave,
                )
                card_canvas.tag_bind(
                    check_tag,
                    "<Button-1>",
                    lambda _event, fid=file_id:
                        _toggle_result_checkbox(fid),
                )

        # Draw separators only for rendered rows, ending at the last result.
        for slot_index in range(len(page_results)):
            slot_bottom = row_slots[slot_index][1]

            card_canvas.create_line(
                table_x1,
                slot_bottom,
                table_x2,
                slot_bottom,
                fill=SF_BORDER,
                width=1,
            )

        if not search_state["error"]:
            page_count = _get_page_count()
            current_page = int(
                result_table_state["page_index"]
            )

            footer_center_y = (
                body_bottom
                + ((inner_y2 - body_bottom) / 2.0)
                + 2
            )

            page_button_width = 30
            page_button_height = 28
            label_text = f"{current_page + 1} / {page_count}"
            label_font = app._font(12)
            label_width = tkfont.Font(font=label_font).measure(label_text)

            # Mirror workspace_sync pagination spacing:
            # far_before, before, page label, after, far_after
            # with gaps of 6, 8, 8, and 6.
            first_gap = 6
            second_gap = 8
            third_gap = 8
            fourth_gap = 6

            total_controls_width = (
                page_button_width
                + first_gap
                + page_button_width
                + second_gap
                + label_width
                + third_gap
                + page_button_width
                + fourth_gap
                + page_button_width
            )

            controls_x = (
                (inner_x1 + inner_x2) / 2.0
                - (total_controls_width / 2.0)
            )

            can_go_prev = (
                current_page > 0
                and not page_loading
            )
            can_go_next = (
                current_page < page_count - 1
                and not page_loading
            )

            first_center_x = controls_x + (page_button_width / 2.0)
            _draw_pagination_button(
                card_canvas,
                center_x=first_center_x,
                center_y=footer_center_y,
                width=page_button_width,
                height=page_button_height,
                tag="sf_page_control_first",
                icon=far_before_icon_photo,
                enabled=can_go_prev,
                command=_go_to_first_result_page,
            )
            controls_x += page_button_width + first_gap

            prev_center_x = controls_x + (page_button_width / 2.0)
            _draw_pagination_button(
                card_canvas,
                center_x=prev_center_x,
                center_y=footer_center_y,
                width=page_button_width,
                height=page_button_height,
                tag="sf_page_control_prev",
                icon=before_icon_photo,
                enabled=can_go_prev,
                command=lambda: _change_result_page(-1),
            )
            controls_x += page_button_width + second_gap

            label_center_x = controls_x + (label_width / 2.0)
            card_canvas.create_text(
                label_center_x,
                footer_center_y,
                text=label_text,
                fill=SF_TEXT_MAIN,
                font=label_font,
                anchor="center",
            )
            controls_x += label_width + third_gap

            next_center_x = controls_x + (page_button_width / 2.0)
            _draw_pagination_button(
                card_canvas,
                center_x=next_center_x,
                center_y=footer_center_y,
                width=page_button_width,
                height=page_button_height,
                tag="sf_page_control_next",
                icon=after_icon_photo,
                enabled=can_go_next,
                command=lambda: _change_result_page(1),
            )
            controls_x += page_button_width + fourth_gap

            last_center_x = controls_x + (page_button_width / 2.0)
            _draw_pagination_button(
                card_canvas,
                center_x=last_center_x,
                center_y=footer_center_y,
                width=page_button_width,
                height=page_button_height,
                tag="sf_page_control_last",
                icon=far_after_icon_photo,
                enabled=can_go_next,
                command=_go_to_last_result_page,
            )

        card_canvas.result_table_icons_ref = {
            **result_table_icons,
            "far_before": far_before_icon_photo,
            "before": before_icon_photo,
            "after": after_icon_photo,
            "far_after": far_after_icon_photo,
        }

    def _draw_detail_field(
        canvas,
        *,
        x,
        y,
        width,
        label,
        value,
        value_font=None,
    ):
        label_font = app._font(9, "bold")
        resolved_value_font = value_font or app._font(10)

        canvas.create_text(
            x,
            y,
            text=label,
            fill=SF_TEXT_PLACEHOLDER,
            font=label_font,
            anchor="nw",
        )

        value_y = y + 22

        value_id = canvas.create_text(
            x,
            value_y,
            text=_format_detail_value(value),
            fill=SF_TEXT_DARK,
            font=resolved_value_font,
            anchor="nw",
            width=max(20, width),
            justify="left",
        )

        bbox = canvas.bbox(value_id)

        if bbox is None:
            return value_y + 22

        return bbox[3] + 16

    def _draw_file_details():
        canvas = right_card
        canvas.delete("all")

        detail_title_font = app._font(13, "bold")

        canvas_width = max(
            100,
            canvas.winfo_width(),
        )
        full_height = max(
            100,
            canvas.winfo_height(),
        )
        card_height = max(
            100,
            full_height - 12,
        )

        card_x1 = 1
        card_y1 = 1
        card_x2 = max(60, canvas_width - 1)
        card_y2 = card_height - 1

        app._smooth_rounded_rect(
            canvas,
            card_x1,
            card_y1,
            card_x2,
            card_y2,
            24,
            fill=colors.SURFACE_ALT,
            outline=SF_BORDER,
            width=1,
        )

        inner_x = card_x1 + 20
        inner_width = max(
            40,
            card_x2 - inner_x - 20,
        )

        selected_result = _get_selected_result()

        if selected_result is None:
            canvas.create_text(
                inner_x,
                card_y1 + 22,
                text="파일 상세 정보",
                fill=SF_TEXT_MAIN,
                font=detail_title_font,
                anchor="nw",
            )

            canvas.create_text(
                (card_x1 + card_x2) / 2.0,
                (card_y1 + card_y2) / 2.0,
                text=(
                    "검색 결과에서 파일을 선택하면 상세 정보가 여기에 표시돼요"
                ),
                fill=SF_TEXT_PLACEHOLDER,
                font=app._font(10),
                justify="center",
                anchor="center",
                width=max(80, inner_width),
            )
            return

        y_cursor = card_y1 + 22

        canvas.create_text(
            inner_x,
            y_cursor,
            text="파일 상세 정보",
            fill=SF_TEXT_MAIN,
            font=detail_title_font,
            anchor="nw",
        )
        y_cursor += 34

        canvas.create_line(
            inner_x,
            y_cursor,
            card_x2 - 20,
            y_cursor,
            fill=SF_BORDER,
            width=1,
        )
        y_cursor += 14

        header_icon_size = 18
        header_icon_gap = 10
        header_text_x = inner_x + header_icon_size + header_icon_gap
        header_text_width = max(
            20,
            (card_x2 - 20) - header_text_x,
        )
        header_text_font = app._font(12, "bold")
        header_line_height = tkfont.Font(font=header_text_font).metrics("linespace")
        header_max_height = max(header_line_height, (header_line_height * 2) + 2)

        original_filename_text = _truncate_canvas_multiline_text(
            canvas,
            _format_detail_value(
                selected_result.get("original_filename")
            ),
            header_text_width,
            header_max_height,
            header_text_font,
            truncate_suffix="...",
        )

        header_file_type_key = _pick_file_format_icon_key(
            selected_result.get("file_ext")
        )
        header_icon = detail_file_format_icons.get(
            header_file_type_key
        ) or detail_file_format_icons.get("file")

        if header_icon is not None:
            canvas.create_image(
                inner_x,
                y_cursor + 1,
                image=header_icon,
                anchor="nw",
            )

        original_filename_id = canvas.create_text(
            header_text_x,
            y_cursor,
            text=original_filename_text,
            fill=SF_TEXT_MAIN,
            font=header_text_font,
            anchor="nw",
            width=header_text_width,
            justify="left",
        )

        original_filename_bbox = canvas.bbox(original_filename_id)
        icon_bottom = y_cursor + header_icon_size
        text_bottom = y_cursor

        if original_filename_bbox is not None:
            text_bottom = original_filename_bbox[3]

        y_cursor = max(icon_bottom, text_bottom) + 18

        # Keep label/value keys explicit for future pill-style rendering upgrades.
        metadata_rows = [
            {
                "label": "문서 유형",
                "value": _format_detail_value(selected_result.get("document_type")),
                "wrap_lines": 1,
            },
            {
                "label": "문서 날짜",
                "value": _format_detail_value(selected_result.get("document_date")),
                "wrap_lines": 1,
            },
            {
                "label": "파일 종류",
                "value": _format_file_type_label(selected_result.get("file_ext")),
                "wrap_lines": 1,
            },
            {
                "label": "업로더",
                "value": _format_detail_value(selected_result.get("uploaded_by")),
                "wrap_lines": 1,
            },
            {
                "label": "업로드 날짜",
                "value": _format_archived_at(selected_result.get("archived_at")),
                "wrap_lines": 1,
            },
            {
                "label": "크기",
                "value": _format_file_size(selected_result.get("file_size")),
                "wrap_lines": 1,
            },
            {
                "label": "저장 파일명",
                "value": _format_detail_value(selected_result.get("archived_filename")),
                "wrap_lines": 2,
            },
            {
                "label": "저장 경로",
                "value": _format_detail_value(selected_result.get("relative_path")),
                "wrap_lines": 3,
            },
            {
                "label": "태그",
                "value": _format_detail_value(selected_result.get("tags")),
                "wrap_lines": 2,
            },
        ]

        label_font = app._font(9, "bold")
        value_font = app._font(10)
        label_col_width = 80
        row_gap = 7

        label_x = inner_x
        value_x = inner_x + label_col_width
        right_edge_x = card_x2 - 20
        value_col_width = max(40, right_edge_x - value_x)
        line_height = tkfont.Font(font=value_font).metrics("linespace")

        for row in metadata_rows:
            label_id = canvas.create_text(
                label_x,
                y_cursor,
                text=row["label"],
                fill=SF_TEXT_PLACEHOLDER,
                font=label_font,
                anchor="nw",
            )

            wrap_lines = int(row.get("wrap_lines", 1) or 1)
            raw_value_text = _format_detail_value(row.get("value"))

            if wrap_lines <= 1:
                value_text = _truncate_canvas_text(
                    canvas,
                    raw_value_text,
                    value_col_width,
                    value_font,
                    truncate_suffix="...",
                )
                value_id = canvas.create_text(
                    value_x,
                    y_cursor,
                    text=value_text,
                    fill=SF_TEXT_DARK,
                    font=value_font,
                    anchor="nw",
                    justify="left",
                )
            else:
                max_height = max(line_height, (line_height * wrap_lines) + 2)
                value_text = _truncate_canvas_multiline_text(
                    canvas,
                    raw_value_text,
                    value_col_width,
                    max_height,
                    value_font,
                    truncate_suffix="...",
                )
                value_id = canvas.create_text(
                    value_x,
                    y_cursor,
                    text=value_text,
                    fill=SF_TEXT_DARK,
                    font=value_font,
                    anchor="nw",
                    width=value_col_width,
                    justify="left",
                )

            label_bbox = canvas.bbox(label_id)
            value_bbox = canvas.bbox(value_id)

            label_bottom = y_cursor
            value_bottom = y_cursor

            if label_bbox is not None:
                label_bottom = label_bbox[3]
            if value_bbox is not None:
                value_bottom = value_bbox[3]

            y_cursor = max(label_bottom, value_bottom) + row_gap

        base_button_width = max(80, card_x2 - inner_x - 20)
        button_side_margin = 8
        max_button_width = max(
            80,
            int((card_x2 - card_x1) - (button_side_margin * 2)),
        )
        button_width = min(
            max_button_width,
            max(80, int(round(base_button_width * 1.045))),
        )
        button_height = 32
        button_gap = 10
        button_radius = 10
        button_label_font = app._font(10, "bold")

        action_buttons = [
            {
                "tag": "sf_detail_open_button",
                "label": "파일 열기",
                "icon": open_file_button_icon,
                "fill": SF_PRIMARY,
                "outline": SF_PRIMARY,
                "text_color": colors.TEXT_INVERSE,
                "hover_fill": colors.PRIMARY_HOVER,
                "hover_outline": colors.PRIMARY_HOVER,
                "command": _open_selected_file,
            },
            {
                "tag": "sf_detail_download_button",
                "label": "다운로드",
                "icon": download_button_icon,
                "fill": SF_PRIMARY,
                "outline": SF_PRIMARY,
                "text_color": colors.TEXT_INVERSE,
                "hover_fill": colors.PRIMARY_HOVER,
                "hover_outline": colors.PRIMARY_HOVER,
                "command": _download_selected_file,
            },
            {
                "tag": "sf_detail_open_folder_button",
                "label": "폴더 열기",
                "icon": open_folder_button_icon,
                "fill": colors.SURFACE_ALT,
                "outline": SF_PRIMARY,
                "text_color": SF_PRIMARY,
                "hover_fill": colors.SURFACE_ACCENT_SOFT,
                "hover_outline": SF_PRIMARY,
                "command": _open_selected_file_folder,
            },
            {
                "tag": "sf_detail_copy_path_button",
                "label": "경로 복사",
                "icon": copy_path_button_icon,
                "fill": colors.SURFACE_ALT,
                "outline": SF_PRIMARY,
                "text_color": SF_PRIMARY,
                "hover_fill": colors.SURFACE_ACCENT_SOFT,
                "hover_outline": SF_PRIMARY,
                "command": _copy_selected_file_path,
            },
        ]

        stack_height = (
            (button_height * len(action_buttons))
            + (button_gap * (len(action_buttons) - 1))
        )

        stack_y1 = max(
            y_cursor + 12,
            card_y2 - 20 - stack_height,
        )
        stack_y2 = stack_y1 + stack_height

        if stack_y2 > card_y2 - 8:
            stack_y2 = card_y2 - 8
            stack_y1 = stack_y2 - stack_height

        button_x1 = card_x1 + ((card_x2 - card_x1) - button_width) / 2.0
        button_x2 = button_x1 + button_width

        def _draw_detail_action_button(
            *,
            tag,
            x1,
            y1,
            x2,
            y2,
            label,
            icon,
            fill,
            outline,
            text_color,
            hover_fill,
            hover_outline,
            command,
        ):
            button_shape = app._smooth_rounded_rect(
                canvas,
                x1,
                y1,
                x2,
                y2,
                button_radius,
                fill=fill,
                outline=outline,
                width=1,
                tags=(tag,),
            )

            center_x = (x1 + x2) / 2.0
            center_y = (y1 + y2) / 2.0
            text_width = tkfont.Font(font=button_label_font).measure(label)
            icon_width = icon.width() if icon is not None else 0
            icon_gap = 8 if icon is not None else 0
            content_width = icon_width + icon_gap + text_width
            content_left = center_x - (content_width / 2.0)

            if icon is not None:
                canvas.create_image(
                    content_left,
                    center_y,
                    image=icon,
                    anchor="w",
                    tags=(tag,),
                )

            canvas.create_text(
                content_left + icon_width + icon_gap,
                center_y,
                text=label,
                fill=text_color,
                font=button_label_font,
                anchor="w",
                tags=(tag,),
            )

            canvas.create_rectangle(
                x1,
                y1,
                x2,
                y2,
                fill="",
                outline="",
                tags=(tag,),
            )

            def _on_enter(_event=None):
                canvas.itemconfigure(
                    button_shape,
                    fill=hover_fill,
                    outline=hover_outline,
                )
                canvas.configure(cursor="hand2")

            def _on_leave(_event=None):
                canvas.itemconfigure(
                    button_shape,
                    fill=fill,
                    outline=outline,
                )
                canvas.configure(cursor="")

            canvas.tag_bind(tag, "<Enter>", _on_enter)
            canvas.tag_bind(tag, "<Leave>", _on_leave)
            canvas.tag_bind(
                tag,
                "<Button-1>",
                lambda _event: command(),
            )

        for index, spec in enumerate(action_buttons):
            current_y1 = stack_y1 + (index * (button_height + button_gap))
            current_y2 = current_y1 + button_height

            _draw_detail_action_button(
                tag=spec["tag"],
                x1=button_x1,
                y1=current_y1,
                x2=button_x2,
                y2=current_y2,
                label=spec["label"],
                icon=spec["icon"],
                fill=spec["fill"],
                outline=spec["outline"],
                text_color=spec["text_color"],
                hover_fill=spec["hover_fill"],
                hover_outline=spec["hover_outline"],
                command=spec["command"],
            )

    def _draw_search_box():
        top_card_width = max(100, left_top_card.winfo_width())
        card_x1 = 1 + left_cards_left_inset
        card_x2 = max(card_x1 + 40, top_card_width - 1 - left_cards_right_inset)
        card_inner_width = max(100, card_x2 - card_x1)
        bar_width = max(220, card_inner_width - (search_box_inset * 2))
        search_box_holder.place(
            x=card_x1 + search_box_inset,
            y=search_box_inset,
            width=bar_width,
            height=search_box_height,
        )

    def _on_layout_change(_event=None):
        if not _is_search_screen_alive():
            return

        if not _has_valid_left_layout_space():
            _schedule_layout_retry()
            return

        if filter_panel_state["anim_job"] is None:
            collapsed_height, expanded_height, _available = _compute_left_top_targets()
            target_height = expanded_height if filter_panel_state["expanded"] else collapsed_height
            _apply_left_top_height(target_height)

        _refresh_layout_drawings()

    left_bottom_card.bind(
        "<Up>",
        lambda _event:
            _move_result_selection(-1),
    )

    left_bottom_card.bind(
        "<Down>",
        lambda _event:
            _move_result_selection(1),
    )

    left_bottom_card.bind(
        "<Prior>",
        lambda _event:
            _move_result_page(-1),
    )

    left_bottom_card.bind(
        "<Next>",
        lambda _event:
            _move_result_page(1),
    )

    left_bottom_card.bind(
        "<Home>",
        _select_first_result,
    )

    left_bottom_card.bind(
        "<End>",
        _select_last_result,
    )

    left_bottom_card.bind(
        "<space>",
        _toggle_keyboard_selected_result,
    )

    left_bottom_card.bind(
        "<Escape>",
        _clear_detail_selection,
    )

    left_top_card.bind("<Configure>", _on_layout_change)
    left_bottom_card.bind("<Configure>", _on_layout_change)
    split.bind("<Configure>", _on_layout_change)
    right_card.bind("<Configure>", _on_layout_change)
    left_col.bind("<Configure>", _on_layout_change)

    def _on_screen_destroy(_event=None):
        screen_lifecycle["destroyed"] = True

        if root_click_binding_id:
            try:
                app.root.unbind("<Button-1>", root_click_binding_id)
            except Exception:
                pass

        if layout_state["retry_job"] is not None:
            try:
                app.root.after_cancel(layout_state["retry_job"])
            except Exception:
                pass
            layout_state["retry_job"] = None

        if layout_state["initial_layout_job"] is not None:
            try:
                app.root.after_cancel(layout_state["initial_layout_job"])
            except Exception:
                pass
            layout_state["initial_layout_job"] = None

        if filter_panel_state["anim_job"] is not None:
            try:
                app.root.after_cancel(filter_panel_state["anim_job"])
            except Exception:
                pass
            filter_panel_state["anim_job"] = None

        _close_dropdown_popup("doc_type")
        _close_dropdown_popup("file_type")
        _close_calendar_popup()

    left_top_card.bind("<Destroy>", _on_screen_destroy, add="+")

    _set_filter_toggle_visuals(False)
    layout_state["initial_layout_job"] = app.root.after_idle(_on_layout_change)