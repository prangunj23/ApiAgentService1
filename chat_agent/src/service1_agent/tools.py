"""Tools specific to ApiAgentService1."""

import json
from typing import Any

from agentkit import ToolContext, ToolError, boolean, string, string_list, tool
from agentkit.workspace import EMPTY_TREE

EVENT_TYPE = "service1-changed"
SERVICE2_REPO_NAME = "ApiAgentService2"


def build_payload(
    ctx: ToolContext, summary: str, message: str, breaking: bool, contract_changes: list[str] | None, before: str, after: str
) -> dict[str, Any]:
    """The same client_payload that agent/change_agent.py sends, so Service2's impact-agent workflow handles it unchanged."""
    own = ctx.agent.workspace.own
    if not own.exists():
        raise ToolError(f"{own.name} isn't cloned yet")
    after_ref = after or f"origin/{own.ref.branch}"
    if not own.commit_exists(after_ref):
        raise ToolError(f"Unknown commit {after_ref!r}")
    after_sha = own.git("rev-parse", after_ref).strip()
    if before:
        if not own.commit_exists(before):
            raise ToolError(f"Unknown commit {before!r}")
        before_sha = own.git("rev-parse", before).strip()
    else:
        before_sha = own.git("rev-parse", f"{after_sha}~1").strip() if own.commit_exists(f"{after_sha}~1") else ""

    log_range = [f"{before_sha}..{after_sha}"] if before_sha else ["-n", "20", after_sha]
    return {
        "message": message,
        "summary": summary,
        "contract_changes": contract_changes or [],
        "breaking": breaking,
        "before": before_sha,
        "after": after_sha,
        "compare_url": f"https://github.com/{own.slug}/compare/{before_sha or EMPTY_TREE}...{after_sha}",
        "commits": own.git("log", "--format=%h %s", *log_range)[:2000],
    }


@tool(
    "notify_service2",
    "Send ApiAgentService2's GitHub impact agent a `service1-changed` repository_dispatch about commits on main. "
    "It's the same event the change-agent workflow sends. The user must approve.",
    {
        "summary": string("One or two sentences describing the change."),
        "message": string("Message to the ApiAgentService2 agent: what changed, what might break for a consumer, and what to check."),
        "breaking": boolean("Whether the change can break consumers."),
        "contract_changes": string_list("Each change to the public contract, old -> new."),
        "before": string("Commit before the change. Defaults to the parent of `after`."),
        "after": string("Commit after the change. Defaults to origin/main."),
    },
    required=("summary", "message", "breaking"),
    needs_confirmation=True,
)
def notify_service2(
    ctx: ToolContext, summary: str, message: str, breaking: bool, contract_changes: list[str] | None = None, before: str = "", after: str = ""
) -> str:
    agent = ctx.agent
    payload = build_payload(ctx, summary, message, breaking, contract_changes, before, after)
    target = agent.workspace.repo(SERVICE2_REPO_NAME).slug
    agent.github.dispatch(target, EVENT_TYPE, payload)

    conversation = agent.store.create_conversation(
        kind="agent",
        channel="github_dispatch",
        peer_agent="service2",
        parent_conversation_id=ctx.conversation_id,
        title=summary[:60],
    )
    agent.store.add_message(
        conversation["id"],
        "assistant",
        f"`{EVENT_TYPE}` repository_dispatch to {target}\n\n```json\n{json.dumps(payload, indent=2)}\n```",
        sender=agent.spec.id,
    )
    agent.log_event("dispatch_sent", f"Sent {EVENT_TYPE} to {target}: {summary}", url=payload["compare_url"], conversation_id=ctx.conversation_id)
    agent.memory.schedule_summary(conversation["id"])
    return f"Sent {EVENT_TYPE} to {target}. Its impact-agent workflow will assess the change."


def _preview(
    ctx: ToolContext, summary: str, message: str, breaking: bool, contract_changes: list[str] | None = None, before: str = "", after: str = ""
) -> str:
    payload = build_payload(ctx, summary, message, breaking, contract_changes, before, after)
    target = ctx.agent.workspace.repo(SERVICE2_REPO_NAME).slug
    return f"repository_dispatch `{EVENT_TYPE}` → {target}\n\n{json.dumps(payload, indent=2)}"


notify_service2.preview = _preview
