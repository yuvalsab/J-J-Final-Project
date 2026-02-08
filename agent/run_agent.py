import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

from rca_agent import RcaAgent

ROOT_DIR = Path(__file__).resolve().parents[1]
AGENT_DIR = Path(__file__).resolve().parent
ENV_PATH = ROOT_DIR / ".env"

DEFAULT_DB = "medical_db"
DEFAULT_CONFIG = AGENT_DIR / "rca_config.json"


def pick_env(*names: str) -> str | None:
    for n in names:
        v = os.getenv(n)
        if v and v.strip():
            return v.strip()
    return None


def setup_logging(root_dir: Path) -> None:
    log_level = (os.getenv("LOG_LEVEL") or "INFO").upper()
    level = getattr(logging, log_level, logging.INFO)

    logs_dir = root_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / "rca_run.log"

    fmt = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    logging.basicConfig(
        level=level,
        format=fmt,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_path, encoding="utf-8"),
        ],
    )


def _file_size_mb(p: Path) -> float:
    try:
        return p.stat().st_size / (1024 * 1024)
    except Exception:
        return 0.0


def main() -> int:
    load_dotenv(dotenv_path=ENV_PATH, override=True)
    setup_logging(ROOT_DIR)
    logger = logging.getLogger("run_agent")

    mongo_uri = pick_env("MONGO_URI", "MONGODB_URI", "MONGO_URL", "ATLAS_URI")
    db_name = pick_env("MONGO_DB", "MONGODB_DB", "DB_NAME") or DEFAULT_DB

    if not mongo_uri:
        logger.error(
            "Mongo URI is missing. Add one of these keys to .env: "
            "MONGO_URI / MONGODB_URI / MONGO_URL / ATLAS_URI"
        )
        return 2

    lightning_name = (os.getenv("LIGHTNING_NAME") or "").strip()
    if not lightning_name:
        lightning_name = input("LIGHTNING NAME: ").strip()
    if not lightning_name:
        logger.error("LIGHTNING_NAME is missing and user input was empty.")
        return 2

    config_path = (os.getenv("RCA_CONFIG") or "").strip()
    chosen_config = Path(config_path) if config_path else DEFAULT_CONFIG

    gguf_path_str = (os.getenv("LLAMA_GGUF_PATH") or "").strip()
    gguf_path = Path(gguf_path_str) if gguf_path_str else None

    n_ctx = int(os.getenv("LLAMA_N_CTX") or "8192")
    threads = int(os.getenv("LLAMA_THREADS") or str(max(1, (os.cpu_count() or 8) - 1)))
    gpu_layers = int(os.getenv("LLAMA_GPU_LAYERS") or "0")

    logger.info("PROJECT ROOT     = %s", ROOT_DIR)
    logger.info("AGENT DIR        = %s", AGENT_DIR)
    logger.info("ENV PATH         = %s", ENV_PATH)
    logger.info("MONGO_URI        = %s", "SET" if mongo_uri else "MISSING")
    logger.info("MONGO_DB         = %s", db_name)
    logger.info("LIGHTNING        = %s", lightning_name)
    logger.info("RCA_CONFIG       = %s", chosen_config)

    if gguf_path is None:
        logger.warning("LLAMA_GGUF_PATH  = MISSING (set LLAMA_GGUF_PATH in .env)")
    else:
        logger.info("LLAMA_GGUF_PATH  = %s", gguf_path)
        logger.info("GGUF exists      = %s", "YES" if gguf_path.exists() else "NO")
        if gguf_path.exists():
            logger.info("GGUF size        = %.1f MB", _file_size_mb(gguf_path))

    logger.info("LLAMA n_ctx      = %s", n_ctx)
    logger.info("LLAMA threads    = %s", threads)
    logger.info("LLAMA gpu_layers = %s", gpu_layers)

    try:
        if chosen_config.exists():
            logger.info("Using config file: %s", chosen_config)
            agent = RcaAgent(
                mongo_uri=mongo_uri,
                db_name=db_name,
                export_dir=str(ROOT_DIR),
                config_path=str(chosen_config),
            )
        else:
            logger.warning("Config file not found (%s). Running with defaults.", chosen_config)
            agent = RcaAgent(
                mongo_uri=mongo_uri,
                db_name=db_name,
                export_dir=str(ROOT_DIR),
            )

        agent.run_two_cases(lightning_name)
        logger.info("Run finished successfully.")
        return 0

    except Exception:
        logger.exception("Run failed with an unexpected error.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
