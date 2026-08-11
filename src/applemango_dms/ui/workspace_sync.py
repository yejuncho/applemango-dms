import tkinter as tk
import tkinter.font as tkfont
from datetime import datetime
from pathlib import Path
import re

import applemango_dms.config as config
import applemango_dms.state as state
from applemango_dms.ui import colors
from applemango_dms.ui.workplace_menu import render_workspace_sidebar_nav
from applemango_dms.services.workspace_stats import collect_workspace_filesystem_stats
from applemango_dms.utils.images import load_svg_photo

SYNC_PAGE_BG = colors.SURFACE_ALT
SYNC_CARD_BG = colors.SURFACE_ALT
SYNC_CARD_BORDER = colors.BORDER_LIGHT

SYNC_TEXT_TITLE = colors.TEXT_EMPHASIS
SYNC_TEXT_BODY = colors.TEXT_SUBTLE
SYNC_TEXT_LABEL = colors.TEXT_SECONDARY
SYNC_TEXT_VALUE = colors.TEXT_TINT

SYNC_BADGE_BG = colors.SURFACE_HOVER
SYNC_BADGE_BORDER = colors.BORDER

SYNC_HOVER_BG = colors.SURFACE_HOVER_SOFT

SYNC_BUTTON_PRIMARY_BG = colors.PRIMARY
SYNC_BUTTON_PRIMARY_HOVER = colors.PRIMARY_HOVER
SYNC_BUTTON_PRIMARY_TEXT = colors.TEXT_INVERSE
SYNC_BUTTON_OUTLINE_BG = colors.SURFACE_ALT
SYNC_BUTTON_OUTLINE_HOVER = getattr(colors, "PRIMARY_ACTION_HOVER", colors.SURFACE_HOVER_SOFT)
SYNC_BUTTON_OUTLINE_BORDER = colors.PRIMARY
SYNC_BUTTON_OUTLINE_TEXT = colors.PRIMARY

SYNC_BUTTON_DISABLED_BG = colors.SURFACE_HOVER
SYNC_BUTTON_DISABLED_BORDER = colors.BORDER
SYNC_BUTTON_DISABLED_TEXT = colors.TEXT_PLACEHOLDER

SYNC_PROGRESS_TRACK_BG = colors.SURFACE_HOVER
SYNC_PROGRESS_FILL_BG = colors.PROCESSING

SYNC_STATUS_OK = colors.SUCCESS
SYNC_STATUS_INFO = colors.PROCESSING
# Reuse the warm orange already present in the app's status accents.
SYNC_STATUS_WARN = colors.ALERT
SYNC_STATUS_ERROR = colors.FAILED

SYNC_STATUS_ICON_DIR = (
    config.PROJECT_ROOT
    / "assets"
    / "icons"
    / "workspace"
    / "workplace_sync"
)

# Card No. 2 demo-mode safety switch. This patch intentionally avoids
# NAS access and SQLite reconciliation writes while polishing UI/UX.
SYNC_UI_DEMO_MODE = True

SYNC_CARD_STATE_INITIAL = "initial"
SYNC_CARD_STATE_SCANNING = "scanning"
SYNC_CARD_STATE_RESULT = "result"
SYNC_CARD_STATE_SYNCING = "syncing"
SYNC_CARD_STATE_COMPLETE = "complete"

SYNC_WORKFLOW_PRIMARY = "#3447AA"
SYNC_WORKFLOW_PRIMARY_HOVER = getattr(colors, "PRIMARY_HOVER", "#2d3f98")

SYNC_SUMMARY_COLOR_NORMAL = colors.SUCCESS
SYNC_SUMMARY_COLOR_NEW = colors.PRIMARY
SYNC_SUMMARY_COLOR_ALERT = colors.ALERT
SYNC_SUMMARY_COLOR_ERROR = colors.FAILED_STRONG

SYNC_DEMO_SCAN_TOTAL_FILES = 18442
SYNC_DEMO_SCAN_TICK_MS = 110
SYNC_DEMO_SYNC_TICK_MS = 110

SYNC_DEMO_SUMMARY_AFTER_SCAN = {
    "normal": 18421,
    "registration_required": 15,
    "review_required": 4,
    "error": 2,
}

SYNC_DEMO_SUMMARY_AFTER_SYNC = {
    "normal": 18436,
    "registration_required": 0,
    "review_required": 4,
    "error": 2,
}


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


def _format_sync_timestamp(value):
    text = str(value or "").strip()

    if not text:
        return "-"

    normalized = text.replace("T", " ")
    if normalized.endswith("Z"):
        normalized = normalized[:-1]

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return text

    return parsed.strftime("%Y-%m-%d %H:%M:%S")


def _format_sync_count(value, fallback="-"):
    if value is None:
        return fallback

    try:
        return str(int(value))
    except (TypeError, ValueError):
        return fallback


def _format_grouped_number(value, fallback="-"):
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return fallback


def _resolve_workspace_context(app):
    workspace_id = getattr(state, "active_workspace_id", None)
    workspace_name = str(getattr(state, "active_workspace", "") or "").strip()
    share_path = None

    if getattr(app, "db", None) is None:
        return workspace_id, workspace_name, share_path

    workspace_row = None

    if workspace_id is not None:
        try:
            workspace_row = app.db.get_workspace_by_id(workspace_id)
        except Exception:
            workspace_row = None

    if workspace_row is None and workspace_name:
        try:
            workspace_row = app.db.get_workspace_by_name(workspace_name)
        except Exception:
            workspace_row = None

    if workspace_row is not None:
        workspace_id = int(workspace_row["id"])
        workspace_name = str(workspace_row.get("name") or workspace_name)
        share_path = workspace_row.get("share_path")

    return workspace_id, workspace_name, share_path


def _collect_sync_status_snapshot(app):
    workspace_id, workspace_name, share_path = _resolve_workspace_context(app)

    db_file_count = None
    if getattr(app, "db", None) is not None and workspace_id is not None:
        try:
            db_file_count = app.db.count_files_by_workspace(workspace_id)
        except Exception:
            db_file_count = None

    nas_file_count = None
    if share_path:
        try:
            stats = collect_workspace_filesystem_stats(Path(str(share_path)))
            nas_file_count = int(stats.get("fs_file_count", 0))
        except Exception:
            nas_file_count = None

    last_check_raw = getattr(app, "sync_last_check_at", None)

    if (
        not last_check_raw
        and getattr(app, "db", None) is not None
        and workspace_id is not None
        and callable(getattr(app.db, "get_workspace_last_check_timestamp", None))
    ):
        try:
            last_check_raw = app.db.get_workspace_last_check_timestamp(workspace_id)
        except Exception:
            last_check_raw = None

    last_sync_raw = getattr(app, "sync_last_sync_at", None)

    is_synced = (
        nas_file_count is not None
        and db_file_count is not None
        and int(nas_file_count) == int(db_file_count)
    )

    if is_synced and not last_sync_raw:
        last_sync_raw = last_check_raw

    return {
        "workspace_name": workspace_name or "-",
        "status_key": "sync_pass" if is_synced else "sync_alert",
        "status_text": "정상" if is_synced else "확인 필요",
        "last_check_text": _format_sync_timestamp(last_check_raw),
        "last_sync_text": _format_sync_timestamp(last_sync_raw),
        "nas_files_text": _format_sync_count(nas_file_count, fallback="접근 불가"),
        "db_files_text": _format_sync_count(db_file_count),
    }


def _create_workspace_status_cell(
    app,
    parent,
    *,
    icon_photo,
    title,
    value,
    title_color=None,
    value_color=None,
):
    cell = tk.Frame(parent, bg=SYNC_CARD_BG, highlightthickness=0, bd=0)
    cell.grid_columnconfigure(0, weight=0)
    cell.grid_columnconfigure(1, weight=1)

    icon_label = tk.Label(
        cell,
        image=icon_photo,
        bg=SYNC_CARD_BG,
        anchor="w",
    )
    icon_label.image = icon_photo
    icon_label.grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 8), pady=(1, 0))

    title_label = tk.Label(
        cell,
        text=title,
        font=app._font(10),
        fg=title_color or SYNC_TEXT_TITLE,
        bg=SYNC_CARD_BG,
        anchor="w",
        justify="left",
    )
    title_label.grid(row=0, column=1, sticky="sw")

    value_label = tk.Label(
        cell,
        text=value,
        font=app._font(11, "bold"),
        fg=value_color or SYNC_TEXT_TITLE,
        bg=SYNC_CARD_BG,
        anchor="w",
        justify="left",
    )
    value_label.grid(row=1, column=1, sticky="nw", pady=(1, 0))

    return cell


def _build_workspace_status_grid(app, parent):
    snapshot = _collect_sync_status_snapshot(app)

    icon_names = {
        "workspace": "workspace.svg",
        "status": f"{snapshot['status_key']}.svg",
        "last_check": "last_check.svg",
        "last_sync": "last_sync.svg",
        "nas_files": "nas_files.svg",
        "db_files": "db_files.svg",
    }

    icon_photos = {}
    for key, filename in icon_names.items():
        icon_path = SYNC_STATUS_ICON_DIR / filename
        icon_width, icon_height = _read_svg_intrinsic_size(icon_path)
        icon_photos[key] = load_svg_photo(
            icon_path,
            max_width=icon_width,
            max_height=icon_height,
        )

    app.workspace_sync_status_icons = icon_photos

    table = tk.Frame(parent, bg=SYNC_CARD_BG, highlightthickness=0, bd=0)
    table.pack(fill="both", expand=True, pady=(14, 0))

    for row in range(3):
        table.grid_rowconfigure(row, weight=1, uniform="sync_status_rows")
    for col in range(2):
        table.grid_columnconfigure(col, weight=1, uniform="sync_status_cols")

    status_value_color = (
        colors.SUCCESS_STRONG
        if snapshot["status_text"] == "정상"
        else colors.ALERT
    )

    cell_specs = [
        (
            "workspace",
            "워크스페이스",
            snapshot["workspace_name"],
            SYNC_TEXT_TITLE,
            SYNC_TEXT_TITLE,
        ),
        (
            "status",
            "상태",
            snapshot["status_text"],
            SYNC_TEXT_TITLE,
            status_value_color,
        ),
        (
            "last_check",
            "마지막 검사",
            snapshot["last_check_text"],
            SYNC_TEXT_TITLE,
            colors.PRIMARY,
        ),
        (
            "last_sync",
            "마지막 동기화",
            snapshot["last_sync_text"],
            SYNC_TEXT_TITLE,
            colors.PRIMARY,
        ),
        (
            "nas_files",
            "NAS 파일 수",
            snapshot["nas_files_text"],
            SYNC_TEXT_TITLE,
            SYNC_TEXT_TITLE,
        ),
        (
            "db_files",
            "DMS 파일 수",
            snapshot["db_files_text"],
            SYNC_TEXT_TITLE,
            SYNC_TEXT_TITLE,
        ),
    ]

    for idx, (key, title, value, title_color, value_color) in enumerate(cell_specs):
        row = idx // 2
        col = idx % 2
        cell = _create_workspace_status_cell(
            app,
            table,
            icon_photo=icon_photos.get(key),
            title=title,
            value=value,
            title_color=title_color,
            value_color=value_color,
        )
        cell.grid(
            row=row,
            column=col,
            sticky="nsew",
            padx=(0, 14) if col == 0 else (0, 0),
            pady=(0, 10) if row < 2 else (0, 0),
        )


def _create_rounded_card(app, parent, *, radius=16, height=None):
    canvas = tk.Canvas(parent, bg=parent.cget("bg"), highlightthickness=0, bd=0)
    if height is not None:
        canvas.configure(height=height)

    body = tk.Frame(canvas, bg=SYNC_CARD_BG, highlightthickness=0, bd=0)
    body_id = canvas.create_window(0, 0, window=body, anchor="nw")

    def redraw(_event=None):
        canvas.delete("card")

        width = max(120, int(canvas.winfo_width()))
        full_height = max(80, int(canvas.winfo_height()))

        x1, y1 = 2, 2
        x2, y2 = width - 4, full_height - 4
        app._smooth_rounded_rect(
            canvas,
            x1,
            y1,
            x2,
            y2,
            radius,
            fill=SYNC_CARD_BG,
            outline=SYNC_CARD_BORDER,
            width=1,
            tags="card",
        )

        inset = 16
        canvas.coords(body_id, inset, inset)
        canvas.itemconfigure(body_id, width=max(10, width - (inset * 2)), height=max(10, full_height - (inset * 2)))
        canvas.tag_lower("card")

    canvas.bind("<Configure>", redraw, add="+")
    canvas.after_idle(redraw)
    return canvas, body


def _create_status_badge(app, parent, text):
    badge = tk.Canvas(parent, width=96, height=32, bg=parent.cget("bg"), highlightthickness=0, bd=0)

    def redraw(_event=None):
        badge.delete("all")
        width = max(80, badge.winfo_width())
        height = max(24, badge.winfo_height())
        app._smooth_rounded_rect(
            badge,
            1,
            1,
            width - 1,
            height - 1,
            14,
            fill=SYNC_BADGE_BG,
            outline=SYNC_BADGE_BORDER,
            width=1,
        )
        badge.create_text(
            width / 2.0,
            height / 2.0,
            text=text,
            fill=SYNC_TEXT_LABEL,
            font=app._font(10, "bold"),
            anchor="center",
        )

    badge.bind("<Configure>", redraw, add="+")
    badge.after_idle(redraw)
    return badge


def _create_action_button(app, parent, text, command, *, enabled=True, primary=False, width=220, height=56):
    button = tk.Canvas(parent, width=width, height=height, bg=parent.cget("bg"), highlightthickness=0, bd=0, cursor="hand2" if enabled else "")
    state = {"enabled": bool(enabled), "hovered": False}

    def redraw():
        button.delete("all")
        btn_w = max(width, button.winfo_width())
        btn_h = max(height, button.winfo_height())

        if state["enabled"]:
            if primary:
                fill = SYNC_BUTTON_PRIMARY_HOVER if state["hovered"] else SYNC_BUTTON_PRIMARY_BG
                border = fill
                text_color = SYNC_BUTTON_PRIMARY_TEXT
            else:
                fill = SYNC_CARD_BG
                border = colors.BORDER
                text_color = SYNC_TEXT_VALUE
        else:
            fill = SYNC_BUTTON_DISABLED_BG
            border = SYNC_BUTTON_DISABLED_BORDER
            text_color = SYNC_BUTTON_DISABLED_TEXT

        app._smooth_rounded_rect(
            button,
            1,
            1,
            btn_w - 1,
            btn_h - 1,
            14,
            fill=fill,
            outline=border,
            width=1,
        )

        button.create_text(
            btn_w / 2.0,
            btn_h / 2.0,
            text=text,
            fill=text_color,
            font=app._font(12, "bold"),
            anchor="center",
        )

    def on_enter(_event=None):
        if not state["enabled"]:
            return
        state["hovered"] = True
        redraw()

    def on_leave(_event=None):
        if not state["enabled"]:
            return
        state["hovered"] = False
        redraw()

    def on_click(_event=None):
        if not state["enabled"]:
            return "break"
        command()
        return "break"

    button.bind("<Configure>", lambda _event: redraw(), add="+")
    button.bind("<Enter>", on_enter, add="+")
    button.bind("<Leave>", on_leave, add="+")
    button.bind("<Button-1>", on_click, add="+")

    button.after_idle(redraw)
    return button


def _create_sync_icon_button(
    app,
    parent,
    *,
    text,
    icon_name,
    command,
    primary=True,
    enabled=True,
    width=260,
    height=48,
):
    button = tk.Canvas(
        parent,
        width=width,
        height=height,
        bg=parent.cget("bg"),
        highlightthickness=0,
        bd=0,
        cursor="hand2" if enabled else "",
    )

    icon_photo = None
    if icon_name:
        icon_path = SYNC_STATUS_ICON_DIR / icon_name
        icon_w, icon_h = _read_svg_intrinsic_size(icon_path)
        icon_photo = load_svg_photo(
            icon_path,
            max_width=icon_w,
            max_height=icon_h,
        )

    state = {
        "enabled": bool(enabled),
        "hovered": False,
        "command": command,
    }

    text_font = app._font(12, "bold")
    text_font_metrics = tkfont.Font(font=text_font)

    def redraw(_event=None):
        button.delete("all")
        btn_w = max(width, int(button.winfo_width()))
        btn_h = max(height, int(button.winfo_height()))

        if state["enabled"]:
            if primary:
                fill = SYNC_WORKFLOW_PRIMARY_HOVER if state["hovered"] else SYNC_WORKFLOW_PRIMARY
                border = fill
                text_color = SYNC_BUTTON_PRIMARY_TEXT
            else:
                fill = SYNC_BUTTON_OUTLINE_HOVER if state["hovered"] else SYNC_BUTTON_OUTLINE_BG
                border = SYNC_BUTTON_OUTLINE_BORDER
                text_color = SYNC_BUTTON_OUTLINE_TEXT
        else:
            fill = SYNC_BUTTON_DISABLED_BG
            border = SYNC_BUTTON_DISABLED_BORDER
            text_color = SYNC_BUTTON_DISABLED_TEXT

        app._smooth_rounded_rect(
            button,
            1,
            1,
            btn_w - 1,
            btn_h - 1,
            11,
            fill=fill,
            outline=border,
            width=1,
        )

        icon_width = int(icon_photo.width()) if icon_photo is not None else 0
        icon_gap = 8 if icon_width > 0 else 0
        text_width = int(text_font_metrics.measure(text))
        group_width = icon_width + icon_gap + text_width
        start_x = (btn_w - group_width) / 2.0

        if icon_photo is not None:
            button.create_image(
                start_x + (icon_width / 2.0),
                btn_h / 2.0,
                image=icon_photo,
                anchor="center",
            )

        button.create_text(
            start_x + icon_width + icon_gap,
            btn_h / 2.0,
            text=text,
            fill=text_color,
            font=text_font,
            anchor="w",
        )

        button.configure(cursor="hand2" if state["enabled"] else "")

    def on_enter(_event=None):
        if not state["enabled"]:
            return
        state["hovered"] = True
        redraw()

    def on_leave(_event=None):
        if not state["enabled"]:
            return
        state["hovered"] = False
        redraw()

    def on_click(_event=None):
        if not state["enabled"]:
            return "break"
        callback = state.get("command")
        if callable(callback):
            callback()
        return "break"

    def set_enabled(is_enabled):
        state["enabled"] = bool(is_enabled)
        state["hovered"] = False
        redraw()

    button.bind("<Configure>", redraw, add="+")
    button.bind("<Enter>", on_enter, add="+")
    button.bind("<Leave>", on_leave, add="+")
    button.bind("<Button-1>", on_click, add="+")

    button.after_idle(redraw)
    button.set_enabled = set_enabled
    button.icon_photo = icon_photo
    return button


def _draw_progress_bar(app, canvas, percent, *, fill_color=None):
    canvas.delete("all")

    bar_width = max(120, canvas.winfo_width())
    bar_height = max(14, canvas.winfo_height())
    ratio = max(0.0, min(1.0, float(percent) / 100.0))

    app._smooth_rounded_rect(
        canvas,
        1,
        1,
        bar_width - 1,
        bar_height - 1,
        max(4, bar_height // 2),
        fill=SYNC_PROGRESS_TRACK_BG,
        outline=colors.BORDER,
        width=1,
    )

    if ratio > 0:
        fill_x2 = 1 + int((bar_width - 2) * ratio)
        fill_x2 = min(bar_width - 1, max(2, fill_x2))
        app._smooth_rounded_rect(
            canvas,
            1,
            1,
            fill_x2,
            bar_height - 1,
            max(4, bar_height // 2),
            fill=fill_color or SYNC_PROGRESS_FILL_BG,
            outline="",
            width=0,
        )


def _create_result_row(app, parent, *, symbol, filename, description, color, is_last):
    row = tk.Frame(parent, bg=SYNC_CARD_BG, padx=10, pady=8, highlightthickness=0, bd=0)
    row.pack(fill="x")

    icon_canvas = tk.Canvas(row, width=22, height=22, bg=SYNC_CARD_BG, highlightthickness=0, bd=0)
    icon_canvas.pack(side="left", padx=(0, 10), pady=(2, 0))
    icon_canvas.create_oval(2, 2, 20, 20, fill=color, outline="")
    icon_canvas.create_text(11, 11, text=symbol, fill=colors.TEXT_INVERSE, font=app._font(10, "bold"), anchor="center")

    text_block = tk.Frame(row, bg=SYNC_CARD_BG)
    text_block.pack(side="left", fill="x", expand=True)

    filename_label = tk.Label(
        text_block,
        text=filename,
        font=app._font(11, "bold"),
        fg=SYNC_TEXT_VALUE,
        bg=SYNC_CARD_BG,
        anchor="w",
    )
    filename_label.pack(fill="x")

    desc_label = tk.Label(
        text_block,
        text=description,
        font=app._font(10),
        fg=SYNC_TEXT_LABEL,
        bg=SYNC_CARD_BG,
        anchor="w",
    )
    desc_label.pack(fill="x", pady=(3, 0))

    hover_widgets = [row, icon_canvas, text_block, filename_label, desc_label]

    def apply_bg(bg):
        row.configure(bg=bg)
        icon_canvas.configure(bg=bg)
        text_block.configure(bg=bg)
        filename_label.configure(bg=bg)
        desc_label.configure(bg=bg)

    def on_enter(_event=None):
        apply_bg(SYNC_HOVER_BG)

    def on_leave(_event=None):
        apply_bg(SYNC_CARD_BG)

    for widget in hover_widgets:
        widget.bind("<Enter>", on_enter, add="+")
        widget.bind("<Leave>", on_leave, add="+")

    if not is_last:
        divider = tk.Frame(parent, bg=colors.BORDER, height=1)
        divider.pack(fill="x", padx=10)


def _create_summary_box(app, parent, *, value, label):
    canvas = tk.Canvas(parent, bg=parent.cget("bg"), height=82, highlightthickness=0, bd=0)

    value_label = tk.Label(canvas, text=str(value), font=app._font(17, "bold"), fg=SYNC_TEXT_TITLE, bg=SYNC_CARD_BG)
    text_label = tk.Label(canvas, text=label, font=app._font(10), fg=SYNC_TEXT_LABEL, bg=SYNC_CARD_BG)

    value_window = canvas.create_window(0, 0, window=value_label, anchor="n")
    text_window = canvas.create_window(0, 0, window=text_label, anchor="n")

    def redraw(_event=None):
        canvas.delete("card")
        width = max(120, canvas.winfo_width())
        height = max(70, canvas.winfo_height())

        app._smooth_rounded_rect(
            canvas,
            1,
            1,
            width - 1,
            height - 1,
            12,
            fill=SYNC_CARD_BG,
            outline=colors.BORDER,
            width=1,
            tags="card",
        )

        canvas.coords(value_window, width / 2.0, 14)
        canvas.coords(text_window, width / 2.0, 48)
        canvas.tag_lower("card")

    canvas.bind("<Configure>", redraw, add="+")
    canvas.after_idle(redraw)
    return canvas, value_label


def show_sync_workspace_screen(app):
    shell = app._create_workspace_shell()
    app.root.title("애플망고 DMS - 워크스페이스 동기화")

    render_workspace_sidebar_nav(app, shell["sidebar"], "sync")

    outer = shell["content"]
    app._build_workspace_page_header(
        outer,
        "워크스페이스 동기화",
        "NAS 서버와 DMS 데이터베이스를 비교하여 누락되거나 불일치하는 파일 정보를 확인하고 데이터베이스를 최신 상태로 유지해요.",
    )

    board = tk.Frame(outer, bg=SYNC_PAGE_BG, highlightthickness=0, bd=0)
    board.pack(fill="both", expand=True, padx=0, pady=0)

    page = tk.Frame(board, bg=SYNC_PAGE_BG, highlightthickness=0, bd=0)
    page.pack(fill="both", expand=True, padx=20, pady=0)
    page.grid_columnconfigure(0, weight=1)
    page.grid_rowconfigure(1, weight=1)

    app.status_badge = None
    card_gap = 15
    top_cards_height = int(round(288 * 0.925))
    top_card_left_ratio = 0.45

    middle = tk.Frame(page, bg=SYNC_PAGE_BG)
    middle.grid(row=0, column=0, sticky="ew", pady=(0, card_gap))
    middle.grid_columnconfigure(0, weight=45)
    middle.grid_columnconfigure(1, weight=55)

    def _sync_top_card_width_ratio(_event=None):
        try:
            total_width = max(1, int(middle.winfo_width()))
        except Exception:
            return

        usable_width = max(1, total_width - card_gap)
        left_width = max(1, int(round(usable_width * top_card_left_ratio)))
        right_width = max(1, usable_width - left_width)

        middle.grid_columnconfigure(0, minsize=left_width)
        middle.grid_columnconfigure(1, minsize=right_width)

    middle.bind("<Configure>", _sync_top_card_width_ratio, add="+")
    middle.after_idle(_sync_top_card_width_ratio)

    left_card_canvas, left_card = _create_rounded_card(app, middle, radius=16, height=top_cards_height)
    left_card_canvas.grid(row=0, column=0, sticky="nsew", padx=(0, card_gap))

    right_card_canvas, right_card = _create_rounded_card(app, middle, radius=16, height=top_cards_height)
    right_card_canvas.grid(row=0, column=1, sticky="new")

    tk.Label(
        left_card,
        text="워크스페이스 상태",
        font=app._font(13, "bold"),
        fg=SYNC_TEXT_TITLE,
        bg=SYNC_CARD_BG,
        anchor="w",
    ).pack(fill="x")

    _build_workspace_status_grid(app, left_card)

    tk.Label(
        right_card,
        text="워크스페이스 검사 및 동기화",
        font=app._font(13, "bold"),
        fg=SYNC_TEXT_TITLE,
        bg=SYNC_CARD_BG,
        anchor="w",
    ).pack(fill="x")

    sync_card_content = tk.Frame(
        right_card,
        bg=SYNC_CARD_BG,
        highlightthickness=0,
        bd=0,
    )
    sync_card_content.pack(fill="both", expand=True, pady=(12, 0))

    summary_icon_map = {
        "normal": "normal.svg",
        "registration_required": "new.svg",
        "review_required": "alert.svg",
        "error": "error.svg",
    }
    summary_icons = {}

    for key, filename in summary_icon_map.items():
        icon_path = SYNC_STATUS_ICON_DIR / filename
        icon_w, icon_h = _read_svg_intrinsic_size(icon_path)
        summary_icons[key] = load_svg_photo(
            icon_path,
            max_width=icon_w,
            max_height=icon_h,
        )

    question_mark_icon = None
    question_mark_icon_path = SYNC_STATUS_ICON_DIR / "question_mark.svg"
    question_icon_w, question_icon_h = _read_svg_intrinsic_size(question_mark_icon_path)
    question_mark_icon = load_svg_photo(
        question_mark_icon_path,
        max_width=question_icon_w,
        max_height=question_icon_h,
    )

    sync_card_tall_height = int(top_cards_height)
    sync_card_middle_height = max(
        1,
        int(round(sync_card_tall_height * 0.75)),
    )
    sync_card_short_height = max(
        1,
        int(round(sync_card_tall_height * 0.60)),
    )

    sync_action_button_width = 320
    sync_action_button_side_pad = 28

    sync_card_animation = {
        "current_height": float(sync_card_middle_height),
        "target_height": float(sync_card_middle_height),
        "anim_job": None,
        "anim_start_height": float(sync_card_middle_height),
        "anim_target_height": float(sync_card_middle_height),
        "anim_start_time": 0,
        "anim_duration_ms": 220,
    }

    right_card_canvas.configure(height=sync_card_middle_height)

    sync_demo = {
        "state": None,
        "summary": dict(SYNC_DEMO_SUMMARY_AFTER_SCAN),
        "processed": 0,
        "total": 0,
        "message": "",
        "job": None,
        "loading_job": None,
        "loading_dot_count": 1,
        "loading_base_text": "",
    }

    def _sync_card_target_height_for_state(state_name):
        if state_name == SYNC_CARD_STATE_INITIAL:
            return sync_card_middle_height
        if state_name in (SYNC_CARD_STATE_RESULT, SYNC_CARD_STATE_COMPLETE):
            return sync_card_tall_height
        return sync_card_short_height

    def _apply_sync_card_height(height_value):
        clamped = max(
            1,
            min(
                int(round(float(height_value))),
                sync_card_tall_height,
            ),
        )

        try:
            if right_card_canvas.winfo_exists():
                right_card_canvas.configure(height=clamped)
        except Exception:
            return

        sync_card_animation["current_height"] = float(clamped)

    def _finish_sync_card_height_animation():
        sync_card_animation["anim_job"] = None
        _apply_sync_card_height(sync_card_animation["target_height"])

    def _animate_sync_card_height_step():
        sync_card_animation["anim_job"] = None

        try:
            if not right_card_canvas.winfo_exists():
                return
            now_ms = int(app.root.tk.call("clock", "milliseconds"))
        except Exception:
            return

        elapsed = now_ms - int(sync_card_animation["anim_start_time"])
        duration = max(1, int(sync_card_animation["anim_duration_ms"]))
        progress = min(1.0, max(0.0, elapsed / float(duration)))
        eased = progress * progress * (3.0 - 2.0 * progress)

        start_h = float(sync_card_animation["anim_start_height"])
        target_h = float(sync_card_animation["anim_target_height"])
        next_h = start_h + ((target_h - start_h) * eased)
        _apply_sync_card_height(next_h)

        if progress >= 1.0:
            _finish_sync_card_height_animation()
            return

        try:
            sync_card_animation["anim_job"] = app.root.after(16, _animate_sync_card_height_step)
        except Exception:
            sync_card_animation["anim_job"] = None

    def _start_sync_card_height_animation(target_height):
        clamped_target = max(
            1,
            min(
                int(target_height),
                sync_card_tall_height,
            ),
        )

        sync_card_animation["target_height"] = float(clamped_target)

        current_height = float(sync_card_animation["current_height"])
        if abs(current_height - float(clamped_target)) < 0.5:
            _apply_sync_card_height(clamped_target)
            return

        if sync_card_animation["anim_job"] is not None:
            try:
                app.root.after_cancel(sync_card_animation["anim_job"])
            except Exception:
                pass
            sync_card_animation["anim_job"] = None

        sync_card_animation["anim_start_height"] = current_height
        sync_card_animation["anim_target_height"] = float(clamped_target)

        try:
            sync_card_animation["anim_start_time"] = int(app.root.tk.call("clock", "milliseconds"))
            sync_card_animation["anim_job"] = app.root.after(16, _animate_sync_card_height_step)
        except Exception:
            sync_card_animation["anim_job"] = None
            _apply_sync_card_height(clamped_target)

    def _cancel_sync_card_job():
        job_id = sync_demo.get("job")
        if job_id is None:
            return

        try:
            app.root.after_cancel(job_id)
        except Exception:
            pass

        sync_demo["job"] = None

    def _cancel_loading_text_job():
        loading_job_id = sync_demo.get("loading_job")
        if loading_job_id is None:
            return

        try:
            app.root.after_cancel(loading_job_id)
        except Exception:
            pass

        sync_demo["loading_job"] = None

    def _tick_loading_text_animation():
        sync_demo["loading_job"] = None

        current_state = sync_demo.get("state")
        if current_state not in (SYNC_CARD_STATE_SCANNING, SYNC_CARD_STATE_SYNCING):
            return

        total = max(1, int(sync_demo.get("total") or 1))
        processed = int(sync_demo.get("processed") or 0)
        if processed >= total:
            return

        next_dot_count = int(sync_demo.get("loading_dot_count") or 1) + 1
        if next_dot_count > 3:
            next_dot_count = 1
        sync_demo["loading_dot_count"] = next_dot_count

        base_text = str(sync_demo.get("loading_base_text") or "")
        _set_sync_card_state(
            current_state,
            message=f"{base_text}{'.' * next_dot_count}",
        )

        try:
            sync_demo["loading_job"] = app.root.after(300, _tick_loading_text_animation)
        except Exception:
            sync_demo["loading_job"] = None

    def _start_loading_text_animation(base_text):
        _cancel_loading_text_job()
        sync_demo["loading_base_text"] = str(base_text or "")
        sync_demo["loading_dot_count"] = 1

        try:
            sync_demo["loading_job"] = app.root.after(300, _tick_loading_text_animation)
        except Exception:
            sync_demo["loading_job"] = None

    def _set_sync_card_state(
        state_name,
        *,
        summary=None,
        processed=None,
        total=None,
        message=None,
    ):
        previous_state = sync_demo.get("state")
        sync_demo["state"] = state_name

        if summary is not None:
            sync_demo["summary"] = dict(summary)
        if processed is not None:
            sync_demo["processed"] = int(processed)
        if total is not None:
            sync_demo["total"] = int(total)
        if message is not None:
            sync_demo["message"] = str(message)

        if previous_state != state_name:
            _start_sync_card_height_animation(
                _sync_card_target_height_for_state(state_name)
            )

        if state_name not in (
            SYNC_CARD_STATE_SCANNING,
            SYNC_CARD_STATE_SYNCING,
        ):
            _cancel_loading_text_job()

        _render_sync_card()

    def _render_progress_block(message, processed, total):
        message_label = tk.Label(
            sync_card_content,
            text=message,
            font=app._font(11, "bold"),
            fg=SYNC_TEXT_TITLE,
            bg=SYNC_CARD_BG,
            anchor="w",
        )
        message_label.pack(fill="x")

        counter_text = (
            f"{_format_grouped_number(processed, fallback='0')} / "
            f"{_format_grouped_number(total, fallback='0')} 파일"
        )
        counter_label = tk.Label(
            sync_card_content,
            text=counter_text,
            font=app._font(10),
            fg=SYNC_TEXT_LABEL,
            bg=SYNC_CARD_BG,
            anchor="w",
        )
        counter_label.pack(fill="x", pady=(8, 0))

        percent_value = 0
        if total > 0:
            percent_value = int(round((processed / total) * 100))
        percent_value = max(0, min(100, percent_value))

        bar = tk.Canvas(
            sync_card_content,
            height=14,
            bg=SYNC_CARD_BG,
            highlightthickness=0,
            bd=0,
        )
        bar.pack(fill="x", pady=(8, 0))

        def redraw_bar(_event=None):
            _draw_progress_bar(
                app,
                bar,
                percent_value,
                fill_color=SYNC_WORKFLOW_PRIMARY,
            )

        bar.bind("<Configure>", redraw_bar, add="+")
        bar.after_idle(redraw_bar)

        percent_label = tk.Label(
            sync_card_content,
            text=f"{percent_value}%",
            font=app._font(10, "bold"),
            fg=SYNC_TEXT_LABEL,
            bg=SYNC_CARD_BG,
            anchor="e",
        )
        percent_label.pack(fill="x", pady=(4, 0))

    def _render_summary_area(summary):
        summary_shell = tk.Frame(
            sync_card_content,
            bg=SYNC_CARD_BG,
            highlightthickness=0,
            bd=0,
        )
        summary_shell.pack(fill="x", pady=(2, 0))

        metrics = [
            (
                "normal",
                "정상",
                summary.get("normal", 0),
                SYNC_SUMMARY_COLOR_NORMAL,
            ),
            (
                "registration_required",
                "등록 가능",
                summary.get("registration_required", 0),
                SYNC_SUMMARY_COLOR_NEW,
            ),
            (
                "review_required",
                "확인 필요",
                summary.get("review_required", 0),
                SYNC_SUMMARY_COLOR_ALERT,
            ),
            (
                "error",
                "오류",
                summary.get("error", 0),
                SYNC_SUMMARY_COLOR_ERROR,
            ),
        ]

        for idx, (key, label_text, count_value, accent) in enumerate(metrics):
            segment = tk.Frame(
                summary_shell,
                bg=SYNC_CARD_BG,
                highlightthickness=0,
                bd=0,
            )
            segment.pack(
                side="left",
                fill="x",
                expand=True,
                padx=(0 if idx == 0 else 10, 0),
            )

            label_row = tk.Frame(
                segment,
                bg=SYNC_CARD_BG,
                highlightthickness=0,
                bd=0,
            )
            label_row.pack(anchor="center", pady=(0, 4))

            icon = summary_icons.get(key)
            icon_label = tk.Label(
                label_row,
                image=icon,
                bg=SYNC_CARD_BG,
                anchor="center",
            )
            icon_label.image = icon
            icon_label.pack(side="left")

            tk.Label(
                label_row,
                text=label_text,
                font=app._font(10, "bold"),
                fg=accent,
                bg=SYNC_CARD_BG,
                anchor="w",
                justify="left",
            ).pack(side="left", padx=(4, 0))

            tk.Label(
                segment,
                text=_format_grouped_number(count_value, fallback="0"),
                font=app._font(16, "bold"),
                fg=accent,
                bg=SYNC_CARD_BG,
                anchor="center",
                justify="center",
            ).pack(anchor="center")

    def _start_demo_scan():
        _cancel_sync_card_job()
        _cancel_loading_text_job()

        if not SYNC_UI_DEMO_MODE:
            return

        scan_loading_base_text = "워크스페이스를 검사하고 있어요"

        _set_sync_card_state(
            SYNC_CARD_STATE_SCANNING,
            processed=0,
            total=SYNC_DEMO_SCAN_TOTAL_FILES,
            message=f"{scan_loading_base_text}.",
        )
        _start_loading_text_animation(scan_loading_base_text)
        _tick_demo_scan()

    def _tick_demo_scan():
        if sync_demo.get("state") != SYNC_CARD_STATE_SCANNING:
            return

        total = max(1, int(sync_demo.get("total") or SYNC_DEMO_SCAN_TOTAL_FILES))
        processed = int(sync_demo.get("processed") or 0)
        step = max(1, total // 38)
        processed = min(total, processed + step)

        _set_sync_card_state(
            SYNC_CARD_STATE_SCANNING,
            processed=processed,
            total=total,
        )

        if processed >= total:
            sync_demo["job"] = app.root.after(
                260,
                lambda: _set_sync_card_state(
                    SYNC_CARD_STATE_RESULT,
                    summary=SYNC_DEMO_SUMMARY_AFTER_SCAN,
                ),
            )
            return

        sync_demo["job"] = app.root.after(
            SYNC_DEMO_SCAN_TICK_MS,
            _tick_demo_scan,
        )

    def _start_demo_sync():
        _cancel_sync_card_job()
        _cancel_loading_text_job()

        if not SYNC_UI_DEMO_MODE:
            return

        summary = dict(sync_demo.get("summary") or SYNC_DEMO_SUMMARY_AFTER_SCAN)
        total = max(0, int(summary.get("registration_required", 0)))
        sync_loading_base_text = "데이터베이스를 동기화하고 있어요"

        _set_sync_card_state(
            SYNC_CARD_STATE_SYNCING,
            processed=0,
            total=total,
            message=f"{sync_loading_base_text}.",
        )
        _start_loading_text_animation(sync_loading_base_text)
        _tick_demo_sync()

    def _tick_demo_sync():
        if sync_demo.get("state") != SYNC_CARD_STATE_SYNCING:
            return

        total = max(1, int(sync_demo.get("total") or 1))
        processed = int(sync_demo.get("processed") or 0)

        if total <= 15:
            step = 1
        else:
            step = max(1, total // 15)

        processed = min(total, processed + step)

        _set_sync_card_state(
            SYNC_CARD_STATE_SYNCING,
            processed=processed,
            total=total,
        )

        if processed >= total:
            sync_demo["job"] = app.root.after(
                260,
                lambda: _set_sync_card_state(
                    SYNC_CARD_STATE_COMPLETE,
                    summary=SYNC_DEMO_SUMMARY_AFTER_SYNC,
                ),
            )
            return

        sync_demo["job"] = app.root.after(
            SYNC_DEMO_SYNC_TICK_MS,
            _tick_demo_sync,
        )

    def _render_sync_card():
        for child in sync_card_content.winfo_children():
            child.destroy()

        state_name = sync_demo.get("state")

        if state_name == SYNC_CARD_STATE_INITIAL:
            initial_shell = tk.Frame(
                sync_card_content,
                bg=SYNC_CARD_BG,
                highlightthickness=0,
                bd=0,
            )
            initial_shell.pack(fill="both", expand=True)

            tk.Label(
                initial_shell,
                text="워크스페이스를 검사하여 NAS와 DMS의 차이를 확인해요.",
                font=app._font(11),
                fg=SYNC_TEXT_TITLE,
                bg=SYNC_CARD_BG,
                anchor="w",
                justify="left",
                wraplength=520,
            ).pack(fill="x")

            tk.Label(
                initial_shell,
                text="검사가 완료된 후 필요한 동기화 작업을 확인할 수 있어요.",
                font=app._font(11),
                fg=SYNC_TEXT_TITLE,
                bg=SYNC_CARD_BG,
                anchor="w",
                justify="left",
                wraplength=520,
            ).pack(fill="x", pady=(6, 0))

            button_zone = tk.Frame(
                initial_shell,
                bg=SYNC_CARD_BG,
                highlightthickness=0,
                bd=0,
            )
            button_zone.pack(fill="both", expand=True)

            app.scan_button = _create_sync_icon_button(
                app,
                button_zone,
                text="워크스페이스 검사",
                icon_name="scan.svg",
                command=_start_demo_scan,
                primary=True,
                enabled=True,
                width=sync_action_button_width,
                height=48,
            )
            app.scan_button.pack(fill="x", padx=sync_action_button_side_pad, pady=(22, 0))
            app.sync_button = None
            return

        if state_name == SYNC_CARD_STATE_SCANNING:
            _render_progress_block(
                sync_demo.get("message") or "워크스페이스를 검사하고 있어요…",
                int(sync_demo.get("processed") or 0),
                int(sync_demo.get("total") or SYNC_DEMO_SCAN_TOTAL_FILES),
            )
            app.scan_button = None
            app.sync_button = None
            return

        if state_name == SYNC_CARD_STATE_RESULT:
            summary = dict(sync_demo.get("summary") or SYNC_DEMO_SUMMARY_AFTER_SCAN)
            _render_summary_area(summary)

            registration_required = int(summary.get("registration_required", 0))
            tk.Label(
                sync_card_content,
                text=f"{_format_grouped_number(registration_required, fallback='0')}개 파일을 DMS 데이터베이스에 등록할 수 있어요.",
                font=app._font(11, "bold"),
                fg=SYNC_TEXT_TITLE,
                bg=SYNC_CARD_BG,
                anchor="w",
                justify="left",
                wraplength=520,
            ).pack(fill="x", pady=(10, 0))

            helper_row = tk.Frame(
                sync_card_content,
                bg=SYNC_CARD_BG,
                highlightthickness=0,
                bd=0,
            )
            helper_row.pack(fill="x", pady=(2, 0))

            if question_mark_icon is not None:
                helper_icon = tk.Label(
                    helper_row,
                    image=question_mark_icon,
                    bg=SYNC_CARD_BG,
                    anchor="n",
                )
                helper_icon.image = question_mark_icon
                helper_icon.pack(side="left", padx=(0, 6), pady=(2, 0))

            tk.Label(
                helper_row,
                text=(
                    "자동 동기화란 NAS에 존재하지만 DMS에 등록되지 않은 파일 정보를\n"
                    "DMS 데이터베이스에 추가하는 작업이에요."
                ),
                font=app._font(10),
                fg=SYNC_TEXT_LABEL,
                bg=SYNC_CARD_BG,
                anchor="w",
                justify="left",
                wraplength=500,
            ).pack(side="left", fill="x", expand=True)

            if registration_required > 0:
                app.sync_button = _create_sync_icon_button(
                    app,
                    sync_card_content,
                    text="자동 동기화 적용",
                    icon_name="sync.svg",
                    command=_start_demo_sync,
                    primary=True,
                    enabled=True,
                    width=sync_action_button_width,
                    height=48,
                )
                app.sync_button.pack(fill="x", padx=sync_action_button_side_pad, pady=(8, 0))
                app.scan_button = None
            else:
                app.scan_button = _create_sync_icon_button(
                    app,
                    sync_card_content,
                    text="다시 검사",
                    icon_name="scan.svg",
                    command=_start_demo_scan,
                    primary=True,
                    enabled=True,
                    width=sync_action_button_width,
                    height=48,
                )
                app.scan_button.pack(fill="x", padx=sync_action_button_side_pad, pady=(8, 0))
                app.sync_button = None
            return

        if state_name == SYNC_CARD_STATE_SYNCING:
            _render_progress_block(
                sync_demo.get("message") or "데이터베이스를 동기화하고 있어요…",
                int(sync_demo.get("processed") or 0),
                int(sync_demo.get("total") or 1),
            )
            app.scan_button = None
            app.sync_button = None
            return

        if state_name == SYNC_CARD_STATE_COMPLETE:
            summary = dict(sync_demo.get("summary") or SYNC_DEMO_SUMMARY_AFTER_SYNC)
            _render_summary_area(summary)

            synced_count = int(SYNC_DEMO_SUMMARY_AFTER_SCAN.get("registration_required", 0))
            tk.Label(
                sync_card_content,
                text="동기화가 완료되었어요.",
                font=app._font(11, "bold"),
                fg=SYNC_TEXT_TITLE,
                bg=SYNC_CARD_BG,
                anchor="w",
            ).pack(fill="x", pady=(14, 0))

            tk.Label(
                sync_card_content,
                text=f"{_format_grouped_number(synced_count, fallback='0')}개의 파일 정보를 DMS 데이터베이스에 등록했어요.",
                font=app._font(10),
                fg=SYNC_TEXT_LABEL,
                bg=SYNC_CARD_BG,
                anchor="w",
                justify="left",
                wraplength=520,
            ).pack(fill="x", pady=(4, 0))

            app.scan_button = _create_sync_icon_button(
                app,
                sync_card_content,
                text="다시 검사",
                icon_name="scan.svg",
                command=_start_demo_scan,
                primary=True,
                enabled=True,
                width=sync_action_button_width,
                height=48,
            )
            app.scan_button.pack(fill="x", padx=sync_action_button_side_pad, pady=(14, 0))
            app.sync_button = None
            return

    app.sync_card_demo = {
        "set_state": _set_sync_card_state,
        "start_demo_scan": _start_demo_scan,
        "start_demo_sync": _start_demo_sync,
        "cancel_job": _cancel_sync_card_job,
    }

    _set_sync_card_state(SYNC_CARD_STATE_INITIAL)

    result_card_canvas, result_card = _create_rounded_card(app, page, radius=16)
    result_card_canvas.grid(row=1, column=0, sticky="nsew")

    detail_title_row = tk.Frame(
        result_card,
        bg=SYNC_CARD_BG,
        highlightthickness=0,
        bd=0,
    )
    detail_title_row.pack(fill="x")

    tk.Label(
        detail_title_row,
        text="세부 동기화 항목",
        font=app._font(13, "bold"),
        fg=SYNC_TEXT_TITLE,
        bg=SYNC_CARD_BG,
        anchor="w",
    ).pack(side="left")

    sync_detail_filter_button = tk.Canvas(
        detail_title_row,
        width=103,
        height=34,
        bg=SYNC_CARD_BG,
        highlightthickness=0,
        bd=0,
        cursor="hand2",
    )
    sync_detail_filter_button.pack(side="right")

    detail_card_content = tk.Frame(
        result_card,
        bg=SYNC_CARD_BG,
        highlightthickness=0,
        bd=0,
    )
    detail_card_content.pack(fill="both", expand=True, pady=(8, 4))

    sync_detail_rows_per_page = 4
    sync_detail_row_height = 38
    sync_detail_header_height = 21
    sync_detail_footer_height = 30
    sync_detail_col_ratios = [1.4, 2.2, 2.4, 0.8, 3.0, 1.0]
    sync_detail_col_headers = ["상태", "파일명", "위치", "크기", "상세", "작업"]
    sync_detail_body_height = sync_detail_rows_per_page * sync_detail_row_height
    sync_detail_table_min_height = (
        sync_detail_header_height
        + sync_detail_body_height
        + sync_detail_footer_height
    )

    sync_detail_status_meta = {
        "normal": {
            "label": "정상",
            "detail_fallback": "-",
            "text_color": colors.SUCCESS_STRONG,
            "detail_color": colors.SUCCESS_STRONG,
            "icon": "normal_small.svg",
        },
        "registration_required": {
            "label": "등록 필요",
            "detail_fallback": "DMS 미등록 파일",
            "text_color": colors.PRIMARY,
            "detail_color": colors.PRIMARY,
            "icon": "new_small.svg",
        },
        "review_required": {
            "label": "확인 필요",
            "detail_fallback": "NAS에서 파일을 찾을 수 없음",
            "text_color": colors.ALERT,
            "detail_color": colors.ALERT,
            "icon": "alert_small.svg",
        },
        "error": {
            "label": "오류",
            "detail_fallback": "파일 정보를 읽을 수 없음",
            "text_color": colors.FAILED_STRONG,
            "detail_color": colors.FAILED_STRONG,
            "icon": "error_small.svg",
        },
    }

    sync_detail_filter_options = [
        ("all", "모두 보기"),
        ("registration_required", "등록 필요"),
        ("review_required", "확인 필요"),
        ("error", "오류"),
    ]
    sync_detail_filter_label_to_key = {
        label: key
        for key, label in sync_detail_filter_options
    }

    sync_detail_icons = {}
    for icon_name in (
        "normal_small.svg",
        "new_small.svg",
        "alert_small.svg",
        "error_small.svg",
        "filter.svg",
        "expand.svg",
        "collapse.svg",
        "far_before.svg",
        "before.svg",
        "after.svg",
        "far_after.svg",
    ):
        icon_path = SYNC_STATUS_ICON_DIR / icon_name
        icon_w, icon_h = _read_svg_intrinsic_size(icon_path)
        sync_detail_icons[icon_name] = load_svg_photo(
            icon_path,
            max_width=icon_w,
            max_height=icon_h,
        )

    sync_detail_table_shell = tk.Frame(
        detail_card_content,
        bg=SYNC_CARD_BG,
        highlightthickness=1,
        highlightbackground=colors.BORDER,
        highlightcolor=colors.BORDER,
        bd=0,
        height=sync_detail_table_min_height,
    )
    sync_detail_table_shell.pack(fill="both", expand=True, anchor="n")
    sync_detail_table_shell.pack_propagate(False)

    sync_detail_header_frame = tk.Frame(
        sync_detail_table_shell,
        bg=colors.SURFACE_ACCENT_SOFT,
        highlightthickness=0,
        bd=0,
        height=sync_detail_header_height,
    )
    sync_detail_header_frame.pack(side="top", fill="x")
    sync_detail_header_frame.pack_propagate(False)
    sync_detail_header_frame.grid_propagate(False)

    sync_detail_body_frame = tk.Frame(
        sync_detail_table_shell,
        bg=SYNC_CARD_BG,
        highlightthickness=0,
        bd=0,
        height=sync_detail_body_height,
    )
    sync_detail_body_frame.pack(side="top", fill="x")
    sync_detail_body_frame.pack_propagate(False)

    sync_detail_footer_frame = tk.Frame(
        sync_detail_table_shell,
        bg=SYNC_CARD_BG,
        highlightthickness=0,
        bd=0,
        height=sync_detail_footer_height,
    )
    sync_detail_footer_frame.pack(side="top", fill="x")
    sync_detail_footer_frame.pack_propagate(False)

    sync_detail_state = {
        "items": [],
        "filter_key": "all",
        "page_index": 0,
        "rows_per_page": sync_detail_rows_per_page,
        "filter_popup": None,
        "filter_popup_open": False,
        "filter_hovered": False,
        "filter_display_label": "모두 보기",
        "action_states": {},
        "action_jobs": {},
        "refresh_job": None,
    }

    def _get_demo_sync_detail_items():
        return [
            {
                "item_id": "r001",
                "status": "registration_required",
                "filename": "invoice_023.pdf",
                "relative_path": "/2024/회계/invoice_023.pdf",
                "size_bytes": 2411724,
                "detail": "DMS 미등록 파일",
                "record_id": None,
            },
            {
                "item_id": "r002",
                "status": "registration_required",
                "filename": "2026_상반기_재무보고서.pdf",
                "relative_path": "/재무/보고서/2026/2026_상반기_재무보고서.pdf",
                "size_bytes": 19608371,
                "detail": "DMS 미등록 파일",
                "record_id": None,
            },
            {
                "item_id": "r003",
                "status": "registration_required",
                "filename": "ultra_long_vendor_invoice_bundle_reference_2026_revision_candidate_final_signed_copy.pdf",
                "relative_path": "/재무/정산/2026/Q3/보관/원본/ultra_long_vendor_invoice_bundle_reference_2026_revision_candidate_final_signed_copy.pdf",
                "size_bytes": 45312789,
                "detail": "DMS 미등록 파일",
                "record_id": None,
            },
            {
                "item_id": "r004",
                "status": "review_required",
                "filename": "contract.pdf",
                "relative_path": "/계약/contract.pdf",
                "size_bytes": 35651584,
                "detail": "등록된 경로에서 파일을 찾을 수 없음",
                "record_id": 821,
            },
            {
                "item_id": "r005",
                "status": "review_required",
                "filename": "거래처_목록.xlsx",
                "relative_path": "/영업/거래처/거래처_목록.xlsx",
                "size_bytes": 962560,
                "detail": "등록된 상위 폴더가 NAS에 존재하지 않음",
                "record_id": 944,
            },
            {
                "item_id": "r006",
                "status": "review_required",
                "filename": "archive_policy_v2.docx",
                "relative_path": "/정책/archive_policy_v2.docx",
                "size_bytes": 2288654,
                "detail": "전체 검사 후 NAS 파일 미확인",
                "record_id": 1408,
            },
            {
                "item_id": "r007",
                "status": "review_required",
                "filename": "project_plan_ko_en_mix_장기전략문서_최종검토본.pptx",
                "relative_path": "/전략/중장기/2026/회의자료/project_plan_ko_en_mix_장기전략문서_최종검토본.pptx",
                "size_bytes": 46860972,
                "detail": "DB 기록만 존재하고 NAS 파일은 확인되지 않음",
                "record_id": 1454,
            },
            {
                "item_id": "r008",
                "status": "review_required",
                "filename": "deleted_on_nas_but_in_db.txt",
                "relative_path": "/운영/로그/deleted_on_nas_but_in_db.txt",
                "size_bytes": 212992,
                "detail": "등록된 NAS 경로가 존재하지 않음",
                "record_id": 1601,
            },
            {
                "item_id": "r009",
                "status": "error",
                "filename": "permission_denied_budget.xlsx",
                "relative_path": "/재무/기밀/permission_denied_budget.xlsx",
                "size_bytes": 7144823,
                "detail": "파일 접근 권한 없음",
                "record_id": None,
            },
            {
                "item_id": "r010",
                "status": "error",
                "filename": "unreadable_media.mov",
                "relative_path": "/영상/원본/unreadable_media.mov",
                "size_bytes": 329069502,
                "detail": "파일 정보를 읽을 수 없음",
                "record_id": None,
            },
            {
                "item_id": "r011",
                "status": "error",
                "filename": "broken_record.docx",
                "relative_path": "/문서/broken_record.docx",
                "size_bytes": 1468006,
                "detail": "잘못된 파일 경로",
                "record_id": None,
            },
            {
                "item_id": "r012",
                "status": "error",
                "filename": "path_mismatch_문서.txt",
                "relative_path": "/문서/path_mismatch_문서.txt",
                "size_bytes": 121944,
                "detail": "워크스페이스 경로 불일치",
                "record_id": 1520,
            },
            {
                "item_id": "r013",
                "status": "error",
                "filename": "duplicate_contract_pointer.pdf",
                "relative_path": "/계약/중복/duplicate_contract_pointer.pdf",
                "size_bytes": 1042048,
                "detail": "중복된 DMS 경로 기록",
                "record_id": 1201,
            },
        ]

    sync_detail_state["items"] = _get_demo_sync_detail_items()

    def _format_sync_detail_file_size(size_bytes):
        if size_bytes is None:
            return "-"

        try:
            size_value = float(size_bytes)
        except (TypeError, ValueError):
            return "-"

        units = ("B", "KB", "MB", "GB", "TB")
        unit_index = 0

        while size_value >= 1024.0 and unit_index < len(units) - 1:
            size_value /= 1024.0
            unit_index += 1

        if unit_index == 0:
            return f"{int(size_value)} {units[unit_index]}"
        if size_value >= 100:
            return f"{size_value:.0f} {units[unit_index]}"
        if size_value >= 10:
            return f"{size_value:.1f} {units[unit_index]}"
        return f"{size_value:.2f} {units[unit_index]}"

    def _truncate_sync_detail_text(text, max_width_px, font_spec):
        value = str(text or "")
        if max_width_px <= 0 or not value:
            return ""

        font_obj = tkfont.Font(root=app.root, font=font_spec)
        if font_obj.measure(value) <= max_width_px:
            return value

        ellipsis = "…"
        ellipsis_width = font_obj.measure(ellipsis)
        if ellipsis_width >= max_width_px:
            return ""

        lo, hi = 0, len(value)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            candidate = value[:mid].rstrip() + ellipsis
            if font_obj.measure(candidate) <= max_width_px:
                lo = mid
            else:
                hi = mid - 1

        return value[:lo].rstrip() + ellipsis

    def _get_sync_detail_column_widths(total_width):
        width = max(780, int(total_width))
        ratio_total = sum(sync_detail_col_ratios) or 1
        col_widths = [
            int(width * (ratio / ratio_total))
            for ratio in sync_detail_col_ratios
        ]
        col_widths[-1] += max(0, width - sum(col_widths))
        return col_widths

    def _get_sync_detail_table_metrics():
        table_height = int(sync_detail_table_shell.winfo_height())
        if table_height <= 1:
            table_height = int(sync_detail_table_min_height)

        rows_per_page = max(1, int(sync_detail_state["rows_per_page"]))
        header_height = max(18, int(sync_detail_header_height))
        row_height = max(24, int(sync_detail_row_height))
        body_height = row_height * rows_per_page
        footer_height = int(table_height - header_height - body_height)

        if footer_height < 12:
            needed = 12 - footer_height
            header_reducible = max(0, header_height - 18)
            take = min(needed, header_reducible)
            header_height -= take
            needed -= take

            if needed > 0:
                shrink_rows = int((needed + rows_per_page - 1) // rows_per_page)
                row_height = max(24, row_height - shrink_rows)
                body_height = row_height * rows_per_page

            footer_height = max(12, int(table_height - header_height - body_height))

        return {
            "table_height": max(1, int(table_height)),
            "header_height": max(1, int(header_height)),
            "row_height": max(1, int(row_height)),
            "body_height": max(1, int(body_height)),
            "footer_height": max(1, int(footer_height)),
        }

    def _configure_sync_detail_columns(frame, col_widths):
        frame.grid_rowconfigure(0, weight=1)
        for idx, col_width in enumerate(col_widths):
            frame.grid_columnconfigure(
                idx,
                minsize=max(40, int(col_width)),
                weight=0,
            )

    def _draw_sync_detail_column_separators(parent, col_widths, height_px):
        # Card No.3 refinement: hide vertical column demarcation lines.
        return

        for child in parent.place_slaves():
            if getattr(child, "_sync_detail_col_sep", False):
                child.destroy()

        x_cursor = 0
        draw_height = max(1, int(height_px))

        for col_width in col_widths[:-1]:
            x_cursor += int(col_width)
            separator = tk.Frame(
                parent,
                bg=colors.BORDER,
                highlightthickness=0,
                bd=0,
            )
            separator._sync_detail_col_sep = True
            separator.place(
                x=max(0, x_cursor),
                y=0,
                width=1,
                height=draw_height,
            )

    def _get_sync_detail_status_meta(status_key):
        return sync_detail_status_meta.get(
            status_key,
            sync_detail_status_meta["error"],
        )

    def _apply_sync_detail_filter(items):
        filter_key = str(sync_detail_state.get("filter_key") or "all")
        if filter_key == "all":
            return list(items)

        return [
            item
            for item in items
            if str(item.get("status")) == filter_key
        ]

    def _get_sync_detail_page_count(filtered_items):
        total_count = len(filtered_items)
        rows_per_page = max(1, int(sync_detail_state["rows_per_page"]))
        return max(1, (total_count + rows_per_page - 1) // rows_per_page)

    def _clamp_sync_detail_page(filtered_items):
        page_count = _get_sync_detail_page_count(filtered_items)
        sync_detail_state["page_index"] = max(
            0,
            min(
                int(sync_detail_state["page_index"]),
                page_count - 1,
            ),
        )

    def _get_sync_detail_page_items(filtered_items):
        _clamp_sync_detail_page(filtered_items)
        rows_per_page = max(1, int(sync_detail_state["rows_per_page"]))
        start_index = int(sync_detail_state["page_index"]) * rows_per_page
        end_index = start_index + rows_per_page
        return filtered_items[start_index:end_index]

    def _is_sync_detail_widget_alive(widget):
        try:
            return bool(widget.winfo_exists())
        except Exception:
            return False

    def _is_sync_detail_descendant(widget, ancestor):
        current = widget
        while current is not None:
            if current == ancestor:
                return True
            try:
                current = current.master
            except Exception:
                return False
        return False

    def _draw_sync_detail_filter_button():
        if not _is_sync_detail_widget_alive(sync_detail_filter_button):
            return

        try:
            sync_detail_filter_button.delete("all")
        except Exception:
            return

        button_width = max(88, int(sync_detail_filter_button.winfo_width()))
        button_height = max(30, int(sync_detail_filter_button.winfo_height()))

        fill_color = colors.SURFACE_HOVER if sync_detail_state.get("filter_hovered") else colors.SURFACE_ALT
        border_color = colors.BORDER

        app._smooth_rounded_rect(
            sync_detail_filter_button,
            1,
            1,
            button_width - 1,
            button_height - 1,
            11,
            fill=fill_color,
            outline=border_color,
            width=1,
        )

        filter_icon = sync_detail_icons.get("filter.svg")
        if filter_icon is not None:
            sync_detail_filter_button.create_image(
                16,
                button_height / 2.0,
                image=filter_icon,
                anchor="center",
            )

        sync_detail_filter_button.create_text(
            30,
            button_height / 2.0,
            text=str(sync_detail_state.get("filter_display_label") or "모두 보기"),
            fill=SYNC_TEXT_TITLE,
            font=app._font(10, "bold"),
            anchor="w",
        )

        expand_icon_key = "collapse.svg" if sync_detail_state.get("filter_popup_open") else "expand.svg"
        expand_icon = sync_detail_icons.get(expand_icon_key)

        if expand_icon is not None:
            sync_detail_filter_button.create_image(
                button_width - 16,
                button_height / 2.0,
                image=expand_icon,
                anchor="center",
            )

    def _close_sync_detail_filter_popup(*, redraw=True):
        popup = sync_detail_state.get("filter_popup")
        if popup is not None:
            try:
                if popup.winfo_exists():
                    popup.destroy()
            except Exception:
                pass

        sync_detail_state["filter_popup"] = None
        sync_detail_state["filter_popup_open"] = False
        if redraw:
            _draw_sync_detail_filter_button()

    def _set_sync_detail_filter(filter_key):
        sync_detail_state["filter_key"] = str(filter_key)
        sync_detail_state["filter_display_label"] = next(
            (
                label
                for key, label in sync_detail_filter_options
                if key == filter_key
            ),
            "모두 보기",
        )
        sync_detail_state["page_index"] = 0
        _close_sync_detail_filter_popup()
        _refresh_sync_detail_view()

    def _open_sync_detail_filter_popup():
        if not _is_sync_detail_widget_alive(sync_detail_filter_button):
            return

        _close_sync_detail_filter_popup()

        popup_width = max(120, int(sync_detail_filter_button.winfo_width()))
        popup_rows = len(sync_detail_filter_options)
        option_row_height = 32
        popup_height = (popup_rows * option_row_height) + 12
        popup_x = sync_detail_filter_button.winfo_rootx()
        popup_y = sync_detail_filter_button.winfo_rooty() + sync_detail_filter_button.winfo_height() + 2

        popup = tk.Toplevel(app.root)
        popup.overrideredirect(True)
        popup.transient(app.root)
        popup.configure(bg=colors.SURFACE_ALT)
        popup.geometry(f"{popup_width}x{popup_height}+{popup_x}+{popup_y}")
        popup.lift()
        popup.focus_force()

        shell_canvas = tk.Canvas(
            popup,
            bg=colors.SURFACE_ALT,
            highlightthickness=0,
            bd=0,
        )
        shell_canvas.pack(fill="both", expand=True)

        def _draw_popup_shell(width_value, height_value):
            shell_canvas.delete("popup_shell_bg")
            app._smooth_rounded_rect(
                shell_canvas,
                1,
                1,
                max(2, int(width_value) - 1),
                max(2, int(height_value) - 1),
                10,
                fill=colors.SURFACE_ALT,
                outline=colors.BORDER,
                width=1,
                tags="popup_shell_bg",
            )
            shell_canvas.tag_lower("popup_shell_bg")

        _draw_popup_shell(popup_width, popup_height)

        shell_canvas.bind(
            "<Configure>",
            lambda event: _draw_popup_shell(event.width, event.height),
            add="+",
        )

        body = tk.Frame(
            shell_canvas,
            bg=colors.SURFACE_ALT,
            bd=0,
            highlightthickness=0,
        )

        shell_canvas.create_window(
            2,
            2,
            anchor="nw",
            window=body,
            width=max(1, popup_width - 4),
            height=max(1, popup_height - 4),
        )

        current_key = str(sync_detail_state.get("filter_key") or "all")

        def _build_option_row(option_key, option_label):
            row_shell = tk.Frame(
                body,
                bg=colors.SURFACE_ALT,
                bd=0,
                highlightthickness=0,
                height=option_row_height,
            )
            row_shell.pack(fill="x")
            row_shell.pack_propagate(False)

            is_current = option_key == current_key
            row_bg = colors.SURFACE_HOVER_SOFT if is_current else colors.SURFACE_ALT
            row_text_color = colors.PRIMARY if is_current else SYNC_TEXT_TITLE

            row_label = tk.Label(
                row_shell,
                text=option_label,
                font=app._font(10, "bold") if is_current else app._font(10),
                fg=row_text_color,
                bg=row_bg,
                anchor="w",
                justify="left",
                padx=10,
            )
            row_label.pack(fill="both", expand=True)

            def _apply_row_bg(bg_color):
                try:
                    row_shell.configure(bg=bg_color)
                except Exception:
                    pass
                try:
                    row_label.configure(bg=bg_color)
                except Exception:
                    pass

            def _on_row_enter(_event=None):
                _apply_row_bg(colors.SURFACE_HOVER_SOFT)

            def _on_row_leave(_event=None):
                _apply_row_bg(row_bg)

            def _on_row_click(_event=None):
                _set_sync_detail_filter(option_key)
                return "break"

            for widget in (row_shell, row_label):
                widget.bind("<Enter>", _on_row_enter, add="+")
                widget.bind("<Leave>", _on_row_leave, add="+")
                widget.bind("<Button-1>", _on_row_click, add="+")

        for option_key, option_label in sync_detail_filter_options:
            _build_option_row(option_key, option_label)

        popup.bind("<Escape>", lambda _event: _close_sync_detail_filter_popup())

        sync_detail_state["filter_popup"] = popup
        sync_detail_state["filter_popup_open"] = True
        _draw_sync_detail_filter_button()

    def _toggle_sync_detail_filter_popup(_event=None):
        if sync_detail_state.get("filter_popup_open"):
            _close_sync_detail_filter_popup()
        else:
            _open_sync_detail_filter_popup()
        return "break"

    def _build_sync_detail_action_button(parent, item_id):
        button_canvas = tk.Canvas(
            parent,
            width=74,
            height=30,
            bg=parent.cget("bg"),
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )

        button_state = {"hovered": False}

        def _draw_button(hovered=False):
            button_canvas.delete("all")

            action_state = str(sync_detail_state["action_states"].get(item_id, "idle"))
            is_enabled = action_state == "idle"

            if action_state == "done":
                fill_color = colors.SURFACE_HOVER
                border_color = colors.BORDER
                text_color = colors.SUCCESS_STRONG
                label_text = "완료"
            elif action_state == "registering":
                fill_color = colors.SURFACE_HOVER
                border_color = colors.BORDER
                text_color = SYNC_TEXT_LABEL
                label_text = "등록 중…"
            else:
                fill_color = colors.SURFACE_HOVER_SOFT if hovered else colors.SURFACE_ALT
                border_color = colors.PRIMARY
                text_color = colors.PRIMARY
                label_text = "등록"

            app._smooth_rounded_rect(
                button_canvas,
                1,
                1,
                73,
                29,
                9,
                fill=fill_color,
                outline=border_color,
                width=1,
            )

            button_canvas.create_text(
                37,
                15,
                text=label_text,
                fill=text_color,
                font=app._font(10, "bold"),
                anchor="center",
            )

            button_canvas.configure(cursor="hand2" if is_enabled else "")

        def _on_enter(_event=None):
            action_state = str(sync_detail_state["action_states"].get(item_id, "idle"))
            if action_state != "idle":
                return
            button_state["hovered"] = True
            _draw_button(hovered=True)

        def _on_leave(_event=None):
            action_state = str(sync_detail_state["action_states"].get(item_id, "idle"))
            if action_state != "idle":
                return
            button_state["hovered"] = False
            _draw_button(hovered=False)

        def _start_demo_register(_event=None):
            action_state = str(sync_detail_state["action_states"].get(item_id, "idle"))
            if action_state != "idle":
                return "break"

            sync_detail_state["action_states"][item_id] = "registering"
            _refresh_sync_detail_view()

            def _finish_register():
                sync_detail_state["action_jobs"].pop(item_id, None)
                sync_detail_state["action_states"][item_id] = "done"
                _refresh_sync_detail_view()

            job_id = app.root.after(700, _finish_register)
            sync_detail_state["action_jobs"][item_id] = job_id
            return "break"

        button_canvas.bind("<Enter>", _on_enter, add="+")
        button_canvas.bind("<Leave>", _on_leave, add="+")
        button_canvas.bind("<Button-1>", _start_demo_register, add="+")

        _draw_button(hovered=False)
        return button_canvas

    def _build_sync_detail_pagination_icon_button(parent, icon_name, *, enabled, command):
        button_canvas = tk.Canvas(
            parent,
            width=30,
            height=28,
            bg=parent.cget("bg"),
            highlightthickness=0,
            bd=0,
            cursor="hand2" if enabled else "",
        )
        icon_photo = sync_detail_icons.get(icon_name)

        def _draw_button():
            button_canvas.delete("all")
            if enabled:
                fill_color = colors.SURFACE_ALT
                border_color = colors.BORDER
            else:
                fill_color = colors.SURFACE_ALT
                border_color = colors.SURFACE_ALT

            app._smooth_rounded_rect(
                button_canvas,
                1,
                1,
                29,
                27,
                8,
                fill=fill_color,
                outline=border_color,
                width=1,
            )

            if icon_photo is not None:
                button_canvas.create_image(
                    15,
                    14,
                    image=icon_photo,
                    anchor="center",
                )

            button_canvas.configure(cursor="hand2" if enabled else "")

        def _on_click(_event=None):
            if not enabled:
                return "break"
            command()
            return "break"

        button_canvas.bind("<Button-1>", _on_click, add="+")

        _draw_button()
        return button_canvas

    def _set_sync_detail_page(page_index):
        filtered_items = _apply_sync_detail_filter(sync_detail_state["items"])
        page_count = _get_sync_detail_page_count(filtered_items)

        sync_detail_state["page_index"] = max(
            0,
            min(int(page_index), page_count - 1),
        )
        _refresh_sync_detail_view()

    def _render_sync_detail_header(col_widths, header_height):
        for child in sync_detail_header_frame.winfo_children():
            child.destroy()

        _configure_sync_detail_columns(sync_detail_header_frame, col_widths)

        for col_idx, header_text in enumerate(sync_detail_col_headers):
            tk.Label(
                sync_detail_header_frame,
                text=header_text,
                font=app._font(10, "bold"),
                fg=SYNC_TEXT_TITLE,
                bg=colors.SURFACE_ACCENT_SOFT,
                anchor="center",
                justify="center",
            ).grid(
                row=0,
                column=col_idx,
                sticky="nsew",
                padx=(4, 4),
            )

        _draw_sync_detail_column_separators(
            sync_detail_header_frame,
            col_widths,
            header_height,
        )

    def _render_sync_detail_rows(col_widths, row_height):
        for child in sync_detail_body_frame.winfo_children():
            child.destroy()

        filtered_items = _apply_sync_detail_filter(sync_detail_state["items"])
        page_items = _get_sync_detail_page_items(filtered_items)

        if not filtered_items:
            empty_shell = tk.Frame(
                sync_detail_body_frame,
                bg=SYNC_CARD_BG,
                highlightthickness=0,
                bd=0,
            )
            empty_shell.pack(fill="both", expand=True)

            tk.Label(
                empty_shell,
                text="확인이 필요한 동기화 항목이 없습니다.",
                font=app._font(11, "bold"),
                fg=SYNC_TEXT_TITLE,
                bg=SYNC_CARD_BG,
                anchor="center",
                justify="center",
            ).place(relx=0.5, rely=0.45, anchor="center")

            tk.Label(
                empty_shell,
                text="현재 발견된 파일 불일치 또는 오류가 없습니다.",
                font=app._font(10),
                fg=SYNC_TEXT_LABEL,
                bg=SYNC_CARD_BG,
                anchor="center",
                justify="center",
            ).place(relx=0.5, rely=0.57, anchor="center")
            return

        row_font = app._font(10)
        row_bold_font = app._font(10, "bold")

        for row_slot in range(sync_detail_rows_per_page):
            item = page_items[row_slot] if row_slot < len(page_items) else None
            row_bg = colors.SURFACE_ALT

            row_frame = tk.Frame(
                sync_detail_body_frame,
                bg=row_bg,
                highlightthickness=0,
                bd=0,
                height=row_height,
            )
            row_frame.pack(fill="x")
            row_frame.pack_propagate(False)
            row_frame.grid_propagate(False)
            _configure_sync_detail_columns(row_frame, col_widths)

            if item is None:
                _draw_sync_detail_column_separators(
                    row_frame,
                    col_widths,
                    row_height,
                )
                tk.Frame(
                    row_frame,
                    bg=colors.BORDER,
                    height=1,
                    bd=0,
                    highlightthickness=0,
                ).place(relx=0.0, rely=1.0, relwidth=1.0, anchor="sw")
                continue

            item_id = str(item.get("item_id") or "")
            action_state = str(sync_detail_state["action_states"].get(item_id, "idle"))

            status_key = str(item.get("status") or "error")
            if status_key == "registration_required" and action_state == "done":
                status_key = "normal"

            status_meta = _get_sync_detail_status_meta(status_key)
            status_icon = sync_detail_icons.get(str(status_meta.get("icon") or "error.svg"))

            status_cell = tk.Frame(
                row_frame,
                bg=row_bg,
                highlightthickness=0,
                bd=0,
            )
            status_cell.grid(row=0, column=0, sticky="nsew")

            status_group = tk.Frame(
                status_cell,
                bg=row_bg,
                highlightthickness=0,
                bd=0,
            )
            status_group.place(relx=0.5, rely=0.5, anchor="center")

            if status_icon is not None:
                status_icon_label = tk.Label(
                    status_group,
                    image=status_icon,
                    bg=row_bg,
                    anchor="center",
                )
                status_icon_label.image = status_icon
                status_icon_label.pack(side="left")

            status_label = tk.Label(
                status_group,
                text=str(status_meta.get("label") or "오류"),
                font=row_bold_font,
                fg=str(status_meta.get("text_color") or SYNC_TEXT_TITLE),
                bg=row_bg,
                anchor="w",
                justify="left",
            )
            status_label.pack(side="left", padx=(6, 0))

            filename_raw = str(item.get("filename") or "-")
            path_raw = str(item.get("relative_path") or "-")
            detail_raw = str(item.get("detail") or status_meta.get("detail_fallback") or "-")
            if status_key == "normal":
                detail_raw = "-"
            size_text = _format_sync_detail_file_size(item.get("size_bytes"))

            filename_text = _truncate_sync_detail_text(
                filename_raw,
                max(10, int(col_widths[1]) - 20),
                row_bold_font,
            )
            path_text = _truncate_sync_detail_text(
                path_raw,
                max(10, int(col_widths[2]) - 20),
                row_font,
            )
            detail_text = _truncate_sync_detail_text(
                detail_raw,
                max(10, int(col_widths[4]) - 10),
                row_font,
            )

            filename_cell = tk.Frame(
                row_frame,
                bg=row_bg,
                highlightthickness=0,
                bd=0,
            )
            filename_cell.grid(row=0, column=1, sticky="nsew")

            filename_label = tk.Label(
                filename_cell,
                text=filename_text,
                font=row_bold_font,
                fg=SYNC_TEXT_VALUE,
                bg=row_bg,
                anchor="w",
                justify="left",
            )
            filename_label.pack(side="left", padx=(10, 6), pady=(0, 0))

            path_cell = tk.Frame(
                row_frame,
                bg=row_bg,
                highlightthickness=0,
                bd=0,
            )
            path_cell.grid(row=0, column=2, sticky="nsew")

            path_label = tk.Label(
                path_cell,
                text=path_text,
                font=row_font,
                fg=SYNC_TEXT_LABEL,
                bg=row_bg,
                anchor="w",
                justify="left",
            )
            path_label.pack(side="left", padx=(10, 6), pady=(0, 0))

            size_label = tk.Label(
                row_frame,
                text=size_text,
                font=row_font,
                fg=SYNC_TEXT_TITLE,
                bg=row_bg,
                anchor="center",
                justify="center",
            )
            size_label.grid(row=0, column=3, sticky="nsew", padx=(4, 4))

            detail_label = tk.Label(
                row_frame,
                text=detail_text,
                font=row_font,
                fg=str(status_meta.get("detail_color") or status_meta.get("text_color") or SYNC_TEXT_LABEL),
                bg=row_bg,
                anchor="center",
                justify="center",
            )
            detail_label.grid(row=0, column=4, sticky="nsew", padx=(4, 4))

            action_cell = tk.Frame(
                row_frame,
                bg=row_bg,
                highlightthickness=0,
                bd=0,
            )
            action_cell.grid(row=0, column=5, sticky="nsew")

            if status_key == "registration_required":
                action_button = _build_sync_detail_action_button(
                    action_cell,
                    item_id,
                )
                action_button.place(relx=0.5, rely=0.5, anchor="center")
            else:
                action_dash = tk.Label(
                    action_cell,
                    text="—",
                    font=app._font(11, "bold"),
                    fg=SYNC_TEXT_LABEL,
                    bg=row_bg,
                    anchor="center",
                    justify="center",
                )
                action_dash.place(relx=0.5, rely=0.5, anchor="center")

            _draw_sync_detail_column_separators(
                row_frame,
                col_widths,
                row_height,
            )

            tk.Frame(
                row_frame,
                bg=colors.BORDER,
                height=1,
                bd=0,
                highlightthickness=0,
            ).place(relx=0.0, rely=1.0, relwidth=1.0, anchor="sw")

    def _render_sync_detail_pagination(filtered_items):
        for child in sync_detail_footer_frame.winfo_children():
            child.destroy()

        page_count = _get_sync_detail_page_count(filtered_items)
        current_page = int(sync_detail_state["page_index"])

        pager_shell = tk.Frame(
            sync_detail_footer_frame,
            bg=SYNC_CARD_BG,
            highlightthickness=0,
            bd=0,
        )
        pager_shell.place(relx=0.5, rely=0.5, anchor="center")

        can_go_prev = current_page > 0
        can_go_next = current_page < (page_count - 1)

        first_btn = _build_sync_detail_pagination_icon_button(
            pager_shell,
            "far_before.svg",
            enabled=can_go_prev,
            command=lambda: _set_sync_detail_page(0),
        )
        first_btn.pack(side="left", padx=(0, 6))

        prev_btn = _build_sync_detail_pagination_icon_button(
            pager_shell,
            "before.svg",
            enabled=can_go_prev,
            command=lambda: _set_sync_detail_page(current_page - 1),
        )
        prev_btn.pack(side="left", padx=(0, 8))

        tk.Label(
            pager_shell,
            text=f"{current_page + 1} / {page_count}",
            font=app._font(12),
            fg=SYNC_TEXT_TITLE,
            bg=SYNC_CARD_BG,
            anchor="center",
            justify="center",
        ).pack(side="left", padx=(0, 8))

        next_btn = _build_sync_detail_pagination_icon_button(
            pager_shell,
            "after.svg",
            enabled=can_go_next,
            command=lambda: _set_sync_detail_page(current_page + 1),
        )
        next_btn.pack(side="left", padx=(0, 6))

        last_btn = _build_sync_detail_pagination_icon_button(
            pager_shell,
            "far_after.svg",
            enabled=can_go_next,
            command=lambda: _set_sync_detail_page(page_count - 1),
        )
        last_btn.pack(side="left")

    def _refresh_sync_detail_view():
        if not _is_sync_detail_widget_alive(sync_detail_table_shell):
            return

        filtered_items = _apply_sync_detail_filter(sync_detail_state["items"])
        _clamp_sync_detail_page(filtered_items)

        table_metrics = _get_sync_detail_table_metrics()
        header_height = int(table_metrics["header_height"])
        row_height = int(table_metrics["row_height"])
        body_height = int(table_metrics["body_height"])
        footer_height = int(table_metrics["footer_height"])

        sync_detail_header_frame.configure(height=header_height)
        sync_detail_body_frame.configure(height=body_height)
        sync_detail_footer_frame.configure(height=footer_height)

        available_width = max(780, int(sync_detail_table_shell.winfo_width()) - 4)
        col_widths = _get_sync_detail_column_widths(available_width)

        _draw_sync_detail_filter_button()
        _render_sync_detail_header(col_widths, header_height)
        _render_sync_detail_rows(col_widths, row_height)
        _render_sync_detail_pagination(filtered_items)

    def _schedule_sync_detail_refresh(_event=None):
        refresh_job = sync_detail_state.get("refresh_job")
        if refresh_job is not None:
            return

        def _run_refresh():
            sync_detail_state["refresh_job"] = None
            _refresh_sync_detail_view()

        try:
            sync_detail_state["refresh_job"] = app.root.after(16, _run_refresh)
        except Exception:
            sync_detail_state["refresh_job"] = None

    def _on_filter_button_enter(_event=None):
        sync_detail_state["filter_hovered"] = True
        _draw_sync_detail_filter_button()

    def _on_filter_button_leave(_event=None):
        sync_detail_state["filter_hovered"] = False
        _draw_sync_detail_filter_button()

    def _on_detail_destroy(_event=None):
        _close_sync_detail_filter_popup(redraw=False)

        for job_id in list(sync_detail_state["action_jobs"].values()):
            try:
                app.root.after_cancel(job_id)
            except Exception:
                pass
        sync_detail_state["action_jobs"].clear()

        refresh_job = sync_detail_state.get("refresh_job")
        if refresh_job is not None:
            try:
                app.root.after_cancel(refresh_job)
            except Exception:
                pass
            sync_detail_state["refresh_job"] = None

    sync_detail_filter_button.bind("<Configure>", lambda _event: _draw_sync_detail_filter_button(), add="+")
    sync_detail_filter_button.bind("<Button-1>", _toggle_sync_detail_filter_popup, add="+")
    sync_detail_filter_button.bind("<Enter>", _on_filter_button_enter, add="+")
    sync_detail_filter_button.bind("<Leave>", _on_filter_button_leave, add="+")

    sync_detail_table_shell.bind("<Configure>", _schedule_sync_detail_refresh, add="+")
    detail_card_content.bind("<Destroy>", _on_detail_destroy, add="+")

    _refresh_sync_detail_view()

    app.last_scan_value = None
    app.last_sync_value = None
    app.indexed_count_value = None
    app.pending_count_value = None
    app.missing_count_value = None
    app.error_count_value = None
    app.state_value = None
    app.results_container = None
    app.summary_indexed = None
    app.summary_new = None
    app.summary_missing = None
    app.summary_errors = None