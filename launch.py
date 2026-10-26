#hiiiii! you are in the launcher. i also do not recommend you tamper with this. 





import threading
import time
import webbrowser

from app import app

PORT = 5001
URL = f"http://127.0.0.1:{PORT}"


def run_server():
    app.run(port=PORT, debug=False, use_reloader=False)

def main():
    from pathlib import Path
    import os
    import sys

    root = Path(__file__).resolve().parent
    bundle = root / "Tapestries.app"
    venv_python = root / ".venv" / "bin" / "python"
    if (
        sys.platform == "darwin"
        and os.environ.get("TAPESTRIES_BUNDLED") != "1"
        and bundle.exists()
        and venv_python.exists()
        and Path(sys.executable).resolve() == venv_python.resolve()
    ):
        os.execv("/usr/bin/open", ["open", str(bundle)])
        return

    threading.Thread(target=run_server, daemon=True).start()
    time.sleep(0.8)
    try:
        if sys.platform == "darwin":
            try:
                from AppKit import NSApplication, NSImage
                icon = root / "static" / "images" / "icon.png"
                ns_app = NSApplication.sharedApplication()
                image = NSImage.alloc().initByReferencingFile_(str(icon))
                if image:
                    ns_app.setApplicationIconImage_(image)
            except Exception:
                pass
        import webview
        webview.create_window("Tapestries", URL, width=900, height=700)
        webview.start()
    except Exception:
        webbrowser.open(URL)
        input("Hey! I think your fridge is running, go after it! Also, press ENTER to exit the app.\n")


if __name__ == "__main__":
    main()
