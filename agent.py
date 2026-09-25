import json
import os
import subprocess

import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3.2:1b"


def tool_list_files(directory="."):
    """Lists non-hidden project files."""
    try:
        files = [
            f for f in os.listdir(directory) if not f.startswith(".") and f != "venv"
        ]
        return json.dumps({"files": files})
    except Exception as e:
        return json.dumps({"error": str(e)})


def tool_git_status():
    """Checks short git status."""
    try:
        result = subprocess.run(
            ["git", "status", "--short"], capture_output=True, text=True, check=True
        )
        return json.dumps({"git_status": result.stdout.strip() or "Working tree clean"})
    except Exception:
        return json.dumps({"error": "Git error or not a repository."})


def tool_git_diff():
    """Captures active code diffs."""
    try:
        result = subprocess.run(
            ["git", "diff"], capture_output=True, text=True, check=True
        )
        diff_output = result.stdout.strip()
        return json.dumps(
            {"git_diff": diff_output[:1000] if diff_output else "No active diffs"}
        )
    except Exception as e:
        return json.dumps({"error": str(e)})


def tool_run_tests():
    """Runs pytest and captures tracebacks on failure."""
    try:
        result = subprocess.run(
            ["pytest", "--maxfail=2", "--disable-warnings", "-q"],
            capture_output=True,
            text=True,
        )
        return json.dumps(
            {
                "test_exit_code": result.returncode,
                "test_output": result.stdout.strip()
                or result.stderr.strip()
                or "All tests passed successfully.",
            }
        )
    except FileNotFoundError:
        return json.dumps({"test_output": "pytest not installed in environment."})


def tool_run_linter():
    """Runs ruff static analysis if available."""
    try:
        result = subprocess.run(["ruff", "check", "."], capture_output=True, text=True)
        return json.dumps(
            {
                "linter_exit_code": result.returncode,
                "linter_output": result.stdout.strip()
                or result.stderr.strip()
                or "No linter issues found.",
            }
        )
    except FileNotFoundError:
        return json.dumps({"linter_output": "ruff linter not installed."})


def tool_fix_linter():
    """Automatically fixes safe ruff linter issues and formats code."""
    try:
        fix_result = subprocess.run(
            ["ruff", "check", "--fix", "."], capture_output=True, text=True
        )
        format_result = subprocess.run(
            ["ruff", "format", "."], capture_output=True, text=True
        )

        output = f"Ruff Fix Output:\n{fix_result.stdout.strip()}\nRuff Format Output:\n{format_result.stdout.strip()}"
        return json.dumps({"success": True, "details": output})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def ask_local_llm(prompt):
    """Streams responses from local Ollama instance with robust error handling."""
    payload = {"model": MODEL_NAME, "prompt": prompt, "stream": True}
    try:
        response = requests.post(OLLAMA_URL, json=payload, stream=True)
        if response.status_code == 200:
            full_response = ""
            has_content = False
            for line in response.iter_lines():
                if line:
                    try:
                        body = json.loads(line.decode("utf-8"))
                        token = body.get("response", "")
                        print(token, end="", flush=True)
                        full_response += token
                        if token:
                            has_content = True
                    except json.JSONDecodeError:
                        continue
            print()
            if not has_content:
                print(
                    "⚠️ [Warning: Ollama returned an empty response stream. Is the model loaded?]"
                )
            return full_response
        else:
            print(
                f"❌ Error: Ollama returned status code {response.status_code} - {response.text}"
            )
            return f"Error: {response.text}"
    except Exception as e:
        print(
            f"❌ Connection failed: {e!s}. Make sure Ollama is running (`ollama serve`)."
        )
        return f"Request failed: {e!s}"


def main_repl():
    print("🤖 Autonomous Local Dev Agent v3.3 (Resilient Stream)")
    print("Commands:")
    print("  - Type 'analyze' to run full telemetry (Files, Git, Tests, Linter)")
    print("  - Type 'fix' to automatically apply ruff safety fixes and formatting")
    print("  - Type any question about your code or architecture")
    print("  - Type 'exit' to quit\n")

    while True:
        try:
            user_input = input("agent> ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit"]:
                print("Goodbye!")
                break

            if user_input.lower() == "fix":
                print("\n🛠️ Running automated ruff fixes and formatting...")
                fix_response = tool_fix_linter()
                print(fix_response)
                print(
                    "\n✨ Auto-fixes applied! Run 'analyze' to verify updated linter status."
                )
                print("-" * 60)
                continue

            if user_input.lower() == "analyze":
                print("\n🔍 Gathering live telemetry...")
                telemetry = f"""
                - Files: {tool_list_files()}
                - Git Status: {tool_git_status()}
                - Git Diff: {tool_git_diff()}
                - Test Results: {tool_run_tests()}
                - Linter Output: {tool_run_linter()}
                """
                prompt = f"""
                You are a strict, pragmatic local developer assistant. 
                
                CRITICAL RULES:
                1. Only reference real, standard development tools: Python, pip, pytest, and ruff. 
                2. NEVER invent non-existent command flags, packages, or tools.
                3. Base your feedback strictly on the provided telemetry data.

                Analyze this live workspace telemetry:
                {telemetry}
                
                Provide your response in 3 clear sections:
                1. **Codebase Health & Linter/Test Status**: Summarize actual status from telemetry.
                2. **Immediate Actions**: Practical steps using only valid Python, pytest, or ruff commands.
                3. **Conventional Commit Recommendation**: A clean conventional commit message if changes are pending.
                """
            else:
                status = tool_git_status()
                prompt = f"""
                You are a strict, pragmatic local developer assistant.
                Current Git Status: {status}
                User Query: {user_input}
                """

            print("\n🧠 Thinking locally...\n")
            ask_local_llm(prompt)
            print("-" * 60)

        except KeyboardInterrupt:
            print("\nExiting agent REPL. Goodbye!")
            break


if __name__ == "__main__":
    main_repl()
