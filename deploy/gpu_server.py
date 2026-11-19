"""Default: check only. --start explicitly starts the local API, never Tailscale/AWS."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", help="Explicit completed common adapter")
    parser.add_argument("--token-file", type=Path, default=ROOT / "thinking_llm_token")
    parser.add_argument("--start", action="store_true")
    parser.add_argument("--profile", choices=["legacy", "final_20261119", "application_v2_20261119", "application_service_20261119", "curated_over1000_20261119"],
                        help="Explicit writing profile for this completed adapter")
    args = parser.parse_args()
    if args.start and not args.adapter:
        parser.error("--start requires --adapter; models are never selected automatically")
    command = [sys.executable, str(ROOT / "deploy/check_gpu_server.py")]
    if args.adapter:
        command += ["--adapter", args.adapter]
    result = subprocess.run(command, check=False)
    if result.returncode or not args.start:
        return result.returncode
    token = args.token_file.read_text(encoding="utf-8-sig").strip()
    if not token or any(char.isspace() for char in token):
        parser.error("Token file must contain one token only")
    with socket.socket() as connection:
        connection.settimeout(1)
        if connection.connect_ex(("127.0.0.1", 8001)) == 0:
            parser.error("Port 8001 is already in use; inspect the existing server first")
    logs = ROOT / "llm_training/outputs/gpu_server"
    logs.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    environment = dict(os.environ, THINKING_LLM_TOKEN=token,
                       COMMON_LLM_ADAPTER=str(Path(args.adapter).resolve()),
                       HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    if args.profile is not None:
        environment['COMMON_LLM_PROFILE'] = args.profile
    with (logs / f"{stamp}.out.log").open("wb") as out, (logs / f"{stamp}.err.log").open("wb") as err:
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "common_llm:app", "--host", "127.0.0.1", "--port", "8001"],
            cwd=ROOT / "llm_training", env=environment, stdin=subprocess.DEVNULL,
            stdout=out, stderr=err,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    (logs / "server.json").write_text(json.dumps({"pid": process.pid, "started_at_utc": stamp,
                                                "python": sys.executable,
                                                "profile": args.profile,
                                                "adapter": str(Path(args.adapter).resolve())}, indent=2), encoding="utf-8")
    print(f"Local API process started (PID {process.pid}). Logs: {logs}")
    print("Check /health and generation before connecting AWS. Tailscale/AWS were not changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
