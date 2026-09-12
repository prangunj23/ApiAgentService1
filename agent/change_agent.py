# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "httpx>=0.27",
#     "openai>=1.40",
# ]
# ///
"""ApiAgentService1 agent: summarizes a push to main and messages the ApiAgentService2 agent."""

import argparse
import json
import os
import subprocess

import httpx

from nim import chat_json

REPO = os.environ.get("GITHUB_REPOSITORY", "prangunj23/ApiAgentService1")
SERVICE2_REPO = os.environ.get("SERVICE2_REPO", "prangunj23/ApiAgentService2")
EVENT_TYPE = "service1-changed"
EMPTY_TREE = "4b825dc642cb6eb9a060ae81c5c29fbd9e0f06a0"
MAX_DIFF_CHARS = 60_000

SYSTEM_PROMPT = """You are the release agent for ApiAgentService1, a FastAPI service named "operation".
It also publishes a Python package, `operation`, with request/response models and a typed HTTP
client. ApiAgentService2 is a downstream service that installs this package and calls the API.

Given a diff pushed to main, summarize the change for the ApiAgentService2 agent. Pay close
attention to the public contract: HTTP paths and methods, request and response fields, status
codes, and names exported from the `operation` package.

Respond with only a JSON object:
{
  "summary": "One or two sentences describing the change",
  "contract_changes": ["Each change to the public contract, old -> new"],
  "breaking": true or false,
  "message_to_service2": "Message to the ApiAgentService2 agent: what changed, what might break for a consumer, and what to check"
}"""


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def commit_exists(ref: str) -> bool:
    result = subprocess.run(["git", "cat-file", "-e", f"{ref}^{{commit}}"], capture_output=True)
    return result.returncode == 0


def resolve_before(before: str | None, after: str) -> str:
    # A new branch or force push reports an all-zero or unknown `before`; fall back to the parent.
    if before and set(before) != {"0"} and commit_exists(before):
        return git("rev-parse", before).strip()
    if commit_exists(f"{after}~1"):
        return git("rev-parse", f"{after}~1").strip()
    return EMPTY_TREE


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", default=os.environ.get("BEFORE_SHA"))
    parser.add_argument("--after", default=os.environ.get("AFTER_SHA") or "HEAD")
    parser.add_argument("--dry-run", action="store_true", help="print the message instead of sending it")
    args = parser.parse_args()

    after = git("rev-parse", args.after).strip()
    before = resolve_before(args.before, after)

    diff = git("diff", before, after, "--", ".", ":(exclude)uv.lock")
    if not diff.strip():
        print("No changes to report.")
        return

    log_range = [f"{before}..{after}"] if before != EMPTY_TREE else ["-n", "20", after]
    commits = git("log", "--format=%h %s", *log_range)

    analysis = chat_json(
        SYSTEM_PROMPT,
        f"# Commits\n{commits}\n# Diff\n```diff\n{diff[:MAX_DIFF_CHARS]}\n```",
    )

    base = "" if before == EMPTY_TREE else before
    payload = {
        "message": analysis.get("message_to_service2", ""),
        "summary": analysis.get("summary", ""),
        "contract_changes": analysis.get("contract_changes", []),
        "breaking": bool(analysis.get("breaking", False)),
        "before": base,
        "after": after,
        "compare_url": f"https://github.com/{REPO}/compare/{base or EMPTY_TREE}...{after}",
        "commits": commits[:2000],
    }

    if args.dry_run:
        print(json.dumps({"event_type": EVENT_TYPE, "client_payload": payload}, indent=2))
        return

    token = os.environ.get("SERVICE2_DISPATCH_TOKEN")
    if not token:
        raise SystemExit("SERVICE2_DISPATCH_TOKEN is not set; can't message the ApiAgentService2 agent.")

    response = httpx.post(
        f"https://api.github.com/repos/{SERVICE2_REPO}/dispatches",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json={"event_type": EVENT_TYPE, "client_payload": payload},
        timeout=30,
    )
    response.raise_for_status()
    print(f"Sent {EVENT_TYPE} to {SERVICE2_REPO}:\n{json.dumps(payload, indent=2)}")


if __name__ == "__main__":
    main()
