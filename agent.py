import os
import subprocess
import json
import urllib.request
import shutil
from pathlib import Path

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3.2:1b"

# ==========================================
# TOOL DEFINITIONS
# ==========================================

def tool_get_telemetry() -> dict:
    """Gathers basic workspace and disk telemetry."""
    try:
        usage = shutil.disk_usage("/")
        free_gb = usage.free / (1024**3)
        total_gb = usage.total / (1024**3)
        used_percent = (usage.used / usage.total) * 100
        return {
            "status": "success",
            "disk_total_gb": round(total_gb, 2),
            "disk_free_gb": round(free_gb, 2),
            "disk_used_percent": round(used_percent, 1),
            "current_dir": str(Path.cwd()),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

def tool_run_ruff() -> dict:
    """Runs ruff linter with auto-fix across the workspace."""
    try:
        result = subprocess.run(
            ["ruff", "check", "--fix", "."],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return {
            "status": "success" if result.returncode == 0 else "warning",
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip()
        }
    except FileNotFoundError:
        return {"status": "error", "message": "Ruff is not installed or not in PATH."}

def tool_git_push(commit_message: str = "chore: autonomous agent update", repo_path: str = ".") -> dict:
    """Stages all changes, commits them with the given message, and pushes to remote main."""
    path = Path(repo_path).resolve()
    
    def _run_cmd(cmd: list[str]) -> tuple[bool, str]:
        res = subprocess.run(
            cmd, cwd=path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        return res.returncode == 0, (res.stdout.strip() or res.stderr.strip())

    # 1. Check status
    success, status_out = _run_cmd(["git", "status", "--porcelain"])
    if not success:
        return {"status": "error", "message": f"Not a valid git repository: {status_out}"}
    
    if not status_out:
        return {"status": "noop", "message": "No changes to commit."}

    # 2. Stage modifications
    success, err_out = _run_cmd(["git", "add", "."])
    if not success:
        return {"status": "error", "message": f"Failed to stage files: {err_out}"}

    # 3. Commit changes
    success, commit_out = _run_cmd(["git", "commit", "-m", commit_message])
    if not success:
        return {"status": "error", "message": f"Commit failed: {commit_out}"}

    # 4. Push to remote origin main
    success, push_out = _run_cmd(["git", "push", "origin", "main"])
    if not success:
        return {"status": "error", "message": f"Push failed: {push_out}"}

    return {
        "status": "success",
        "message": "Successfully committed and pushed changes to remote origin/main.",
        "details": commit_out
    }

# ==========================================
# TOOL DISPATCH REGISTRY
# ==========================================

AVAILABLE_TOOLS = {
    "get_telemetry": tool_get_telemetry,
    "run_ruff": tool_run_ruff,
    "git_push": tool_git_push,
}

def execute_tool(tool_name: str, arguments: dict = None) -> dict:
    if arguments is None:
        arguments = {}
    if tool_name not in AVAILABLE_TOOLS:
        return {"status": "error", "message": f"Unknown tool: {tool_name}"}
    try:
        return AVAILABLE_TOOLS[tool_name](**arguments)
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ==========================================
# OLLAMA REPL & STREAMING
# ==========================================

def query_ollama(prompt: str):
    payload = json.dumps({"model": MODEL_NAME, "prompt": prompt, "stream": True}).encode("utf-8")
    req = urllib.request.Request(OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as response:
            for line in response:
                if line:
                    body = json.loads(line.decode("utf-8"))
                    yield body.get("response", "")
    except Exception as e:
        yield f"\n[Error communicating with Ollama: {e}]"

def main():
    print(f"=== Local Dev Agent v3.3 ({MODEL_NAME}) ===")
    print("Commands:")
    print("  /telemetry - Check disk and workspace status")
    print("  /ruff      - Run ruff linter auto-fix")
    print("  /push      - Commit and push changes to GitHub (e.g., /push update agent)")
    print("Type 'exit' to quit.\n")
    
    while True:
        try:
            user_input = input("agent> ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit"):
                print("Exiting agent. Goodbye!")
                break
            
            # Direct shortcut handlers for built-in tools
            if user_input.startswith("/push"):
                msg = user_input.replace("/push", "").strip() or "chore: autonomous agent update"
                print("[Executing tool: git_push]...")
                res = execute_tool("git_push", {"commit_message": msg})
                print(json.dumps(res, indent=2))
                continue
            elif user_input == "/ruff":
                print("[Executing tool: run_ruff]...")
                res = execute_tool("run_ruff")
                print(json.dumps(res, indent=2))
                continue
            elif user_input == "/telemetry":
                print("[Executing tool: get_telemetry]...")
                res = execute_tool("get_telemetry")
                print(json.dumps(res, indent=2))
                continue

            # Standard Ollama stream response
            print("AI: ", end="", flush=True)
            for chunk in query_ollama(user_input):
                print(chunk, end="", flush=True)
            print("\n")
        except KeyboardInterrupt:
            print("\nExiting.")
            break

if __name__ == "__main__":
    main()
