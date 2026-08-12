from pathlib import Path
import sys
from functools import wraps


ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

print("TRACE: importing app module", flush=True)
import applemango_dms.app as app_module
print("TRACE: app module imported", flush=True)


def wrap_function(container, name, start_label, end_label):
    original = getattr(container, name)

    @wraps(original)
    def wrapped(*args, **kwargs):
        print(f"TRACE: {start_label} START", flush=True)
        result = original(*args, **kwargs)
        print(f"TRACE: {end_label} END", flush=True)
        return result

    setattr(container, name, wrapped)


def wrap_method(cls, name, start_label, end_label):
    original = getattr(cls, name)

    @wraps(original)
    def wrapped(self, *args, **kwargs):
        print(f"TRACE: {start_label} START", flush=True)
        result = original(self, *args, **kwargs)
        print(f"TRACE: {end_label} END", flush=True)
        return result

    setattr(cls, name, wrapped)


wrap_function(app_module.tk, "Tk", "tk.Tk", "tk.Tk")
wrap_function(app_module, "apply_window_icon", "apply_window_icon", "apply_window_icon")
wrap_method(app_module.SequenceArchiverApp, "_initialize_ui_font_family", "font initialization", "font initialization")
wrap_method(app_module.SequenceArchiverApp, "_load_login_icon_photos", "login icons", "login icons")
wrap_method(app_module.SequenceArchiverApp, "_load_ui_icon_photos", "UI icons", "UI icons")
wrap_method(app_module.SequenceArchiverApp, "show_startup_screen", "startup screen", "startup screen")


def main():
    print("TRACE: creating SequenceArchiverApp", flush=True)
    app = app_module.SequenceArchiverApp()
    print("TRACE: SequenceArchiverApp initialized", flush=True)

    original_mainloop = app.root.mainloop

    @wraps(original_mainloop)
    def traced_mainloop(*args, **kwargs):
        print("TRACE: entering Tk mainloop", flush=True)
        return original_mainloop(*args, **kwargs)

    app.root.mainloop = traced_mainloop

    print("TRACE: app.run START", flush=True)
    app.run()
    print("TRACE: app.run END", flush=True)


if __name__ == "__main__":
    main()
