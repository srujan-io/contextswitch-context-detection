import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/"backend"))
sys.path.insert(0,str(Path(__file__).parents[1]/"backend/voice"))
os.environ["BEYOND_TOUCH_CAMERA"] = "0"
os.environ["GEMINI_API_KEY"] = ""  # Never load a user's real .env credentials in tests.
