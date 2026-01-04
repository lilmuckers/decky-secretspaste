import sys
import types
from pathlib import Path

# Ensure backend package is importable
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Stub decky_plugin for tests
if "decky_plugin" not in sys.modules:
    logger = types.SimpleNamespace(
        info=lambda *args, **kwargs: None,
        error=lambda *args, **kwargs: None,
        debug=lambda *args, **kwargs: None,
        warn=lambda *args, **kwargs: None,
        warning=lambda *args, **kwargs: None,
    )
    sys.modules["decky_plugin"] = types.SimpleNamespace(
        logger=logger, DECKY_PLUGIN_SETTINGS_DIR=str(BACKEND_ROOT / "_test_data")
    )
