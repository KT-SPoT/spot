"""Add a local API token without printing it or replacing provider settings."""
from pathlib import Path
from io import StringIO
import re
import secrets
from dotenv import dotenv_values


def configure(path):
    text = path.read_text(encoding="utf-8-sig") if path.exists() else ""
    config = dotenv_values(stream=StringIO(text))
    if not config.get("SPOT_API_TOKEN"):
        line = "SPOT_API_TOKEN=" + secrets.token_urlsafe(32)
        if re.search(r"(?m)^SPOT_API_TOKEN=", text):
            text = re.sub(r"(?m)^SPOT_API_TOKEN=.*$", lambda _: line, text)
        else:
            text = text.rstrip() + "\n" + line + "\n"
    elif len(config["SPOT_API_TOKEN"].strip()) < 24:
        raise ValueError("Existing SPOT_API_TOKEN is too short; update it locally")
    if "SPOT_API_MODE" not in config:
        text = text.rstrip() + "\nSPOT_API_MODE=offline\n"
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    configure(Path(__file__).resolve().parents[2] / ".env")
    print("Local API settings ready. Token value was not printed.")
