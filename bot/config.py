"""Configuration — loaded from .env file."""
import os
from pathlib import Path
from dotenv import load_dotenv

_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)

# LLM — Groq

LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "groq")
LLM_MODEL: str = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

# Config
DEBUG_LLM: bool = os.getenv("DEBUG_LLM", "false").lower() == "true"

# Server
PORT: int = int(os.getenv("PORT", "8080"))
HOST: str = os.getenv("HOST", "0.0.0.0")

# Team metadata
TEAM_NAME: str = "MagicPin Assignment"
TEAM_MEMBERS: list[str] = ["Aarab Nishchal"]
MODEL_DISPLAY: str = f"groq/{LLM_MODEL}"
APPROACH: str = "4-context deterministic composer with per-trigger-kind prompt dispatch + pattern-matched reply handler"
VERSION: str = "1.0.0"

# Paths
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
DATASET_DIR: Path = PROJECT_ROOT / "dataset"
EXPANDED_DIR: Path = PROJECT_ROOT / "expanded"
