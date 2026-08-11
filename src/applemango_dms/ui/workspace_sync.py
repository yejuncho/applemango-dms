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

    tk.Label(
        result_card,
        text="동기화 결과",
        font=app._font(13, "bold"),
        fg=SYNC_TEXT_TITLE,
        bg=SYNC_CARD_BG,
        anchor="w",
    ).pack(fill="x")

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