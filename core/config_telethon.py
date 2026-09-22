from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent

# Resolve canonical session path (prefer root if exists, fallback to core)
if (ROOT_DIR / "bbk_session.session").exists():
    SESSION_PATH = str(ROOT_DIR / "bbk_session")
elif (BASE_DIR / "bbk_session.session").exists():
    SESSION_PATH = str(BASE_DIR / "bbk_session")
else:
    SESSION_PATH = str(ROOT_DIR / "bbk_session")

API_ID = 36719983
API_HASH = "6268c182d4dc5139444682560857f8f8"
SESSION_NAME = SESSION_PATH