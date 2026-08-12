import os
import shutil
import sys

from pathlib import Path


def _resolve_resource_root():
    if (
        getattr(sys, "frozen", False)
        and hasattr(sys, "_MEIPASS")
    ):
        return Path(sys._MEIPASS)

    return Path(__file__).resolve().parents[2]


def _resolve_user_data_root():
    local_appdata = str(
        os.environ.get(
            "LOCALAPPDATA",
            ""
        )
        or ""
    ).strip()

    if local_appdata:
        return (
            Path(local_appdata)
            / "ApplemangoDMS"
        )

    return (
        Path.home()
        / "AppData"
        / "Local"
        / "ApplemangoDMS"
    )


RESOURCE_ROOT = _resolve_resource_root()

# Compatibility alias for existing asset references.
# New code should prefer RESOURCE_ROOT explicitly.
PROJECT_ROOT = RESOURCE_ROOT

USER_DATA_ROOT = _resolve_user_data_root()

DATA_DIR = USER_DATA_ROOT / "data"

DEMO_DIR = USER_DATA_ROOT / "demo"
DEMO_WORKSPACES_DIR = (
    DEMO_DIR
    / "workspaces"
)

PRODUCTION_DB_PATH = (
    DATA_DIR
    / "applemango.db"
)

DEMO_DB_PATH = (
    DEMO_DIR
    / "demo.db"
)

BUNDLED_DEMO_DIR = (
    RESOURCE_ROOT
    / "demo"
)

BUNDLED_DEMO_WORKSPACES_DIR = (
    BUNDLED_DEMO_DIR
    / "workspaces"
)

BUNDLED_DEMO_DB_PATH = (
    BUNDLED_DEMO_DIR
    / "demo.db"
)


def ensure_demo_runtime_data():
    DEMO_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not DEMO_WORKSPACES_DIR.exists():
        if (
            BUNDLED_DEMO_WORKSPACES_DIR.exists()
            and BUNDLED_DEMO_WORKSPACES_DIR.resolve()
                != DEMO_WORKSPACES_DIR.resolve()
        ):
            shutil.copytree(
                BUNDLED_DEMO_WORKSPACES_DIR,
                DEMO_WORKSPACES_DIR,
            )
        else:
            DEMO_WORKSPACES_DIR.mkdir(
                parents=True,
                exist_ok=True,
            )

    if (
        not DEMO_DB_PATH.exists()
        and BUNDLED_DEMO_DB_PATH.exists()
    ):
        try:
            same_db_path = (
                BUNDLED_DEMO_DB_PATH.resolve()
                == DEMO_DB_PATH.resolve()
            )
        except OSError:
            same_db_path = False

        if not same_db_path:
            shutil.copy2(
                BUNDLED_DEMO_DB_PATH,
                DEMO_DB_PATH,
            )

    return DEMO_WORKSPACES_DIR

default_server_name = r"\\applemango"
default_drive_letter = "Z"

RESERVED_NAS_SHARE_NAMES = frozenset(
    {
        "database",
    }
)

allowed_mapping_letters = list("ABDEFHIJKLMNOPQRSTUVWXYZ")
default_server_port = 445
credential_store_path = Path.home() / ".applemango_archiver_credentials.json"
archive_db_path = Path(fr"{default_server_name}\database\applemango.db")

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_SOURCE_DIR = PACKAGE_DIR.parent
#PROJECT_ROOT = PROJECT_SOURCE_DIR.parent

logo_path = RESOURCE_ROOT / "assets" / "logos" / "applemango_logo.png"
