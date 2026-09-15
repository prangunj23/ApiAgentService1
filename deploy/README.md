# Deploying ApiAgentService1 to OCI

This repo runs on one Oracle Always Free VM, by itself. It installs nothing from ApiAgentService2 and nothing from the ApiAgentKit repo — agentkit is vendored at `chat_agent/vendor/agentkit/`. ApiAgentService2 gets its own VM with the same layout.

Two services run here:

| Unit | What | Port |
|---|---|---|
| `operation.service` | the FastAPI API | 8001 |
| `service1-agent.service` | the agentkit chat agent | 9001 |

## Why Tailscale

Neither the API nor the agent has a login, and an OCI VM has a public IP. So nothing is published to the internet: both bind to the VM's Tailscale address, and the tailnet is the only way in. The UI on your laptop and the Service2 agent on the other VM both reach this VM as tailnet peers. You never open port 8001 or 9001 in an OCI security list.

The one host-firewall change is on the tailnet side. Oracle Linux runs firewalld, which admits only SSH, so `set-tailscale-host.sh` puts the `tailscale0` interface in its own zone, `tailnet`, that allows just 8001 and 9001. The public interface stays in the default zone, closed.

`agentkit` adds a further layer: it rejects any request whose `Host` header isn't in `ALLOWED_HOSTS` (which stops DNS rebinding) and any cross-origin write from outside `UI_ORIGINS`.

## The VM

Create it as described in the main OCI walkthrough: **VM.Standard.A1.Flex**, 1 OCPU / 6 GB, public subnet, your SSH key. That is half the Always Free A1 allowance; ApiAgentService2's VM takes the other half.

These scripts target **Oracle Linux 9**, OCI's default image, and also work on Ubuntu 24.04. The SSH user is `opc` on Oracle Linux and `ubuntu` on Ubuntu.

## First install

From your laptop, `ssh opc@<public-ip>`, then:

```sh
# 1. Join the tailnet.
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --hostname=apiagent-service1

# 2. Install the service. Oracle Linux has no git yet, so fetch just the script: it
#    installs git and uv, clones the repo to /opt/apiagent, builds both environments,
#    and installs the systemd units without starting them.
curl -fsSL https://raw.githubusercontent.com/prangunj23/ApiAgentService1/main/deploy/bootstrap.sh -o bootstrap.sh
sudo bash bootstrap.sh

# 3. Fill in the secrets it created.
sudo nano /etc/apiagent/service1-agent.env       # NVIDIA_API_KEY, GITHUB_TOKEN, AGENT_SHARED_TOKEN
sudo nano /etc/apiagent/registry.json            # both agents' tailnet URLs

# 4. Bind to the tailnet, open the tailnet firewall zone, and start.
sudo /opt/apiagent/ApiAgentService1/deploy/set-tailscale-host.sh
sudo systemctl start operation service1-agent
```

`AGENT_SHARED_TOKEN` must be the **same string on both VMs** — generate it once with `openssl rand -base64 32` — or the two agents answer each other with 401. `registry.json` must also be the same on both, listing each agent's tailnet URL.

## What goes where

| Path | Contents |
|---|---|
| `/opt/apiagent/ApiAgentService1/` | the checkout, owned by the `apiagent` user |
| `/opt/apiagent/python/` | uv's Python 3.13 (Oracle Linux 9 ships 3.9) |
| `/etc/apiagent/*.env` | secrets and settings, mode 0640, root-owned, never overwritten by a re-run |
| `/etc/apiagent/registry.json` | the agent list both VMs share |
| `/var/lib/apiagent/service1/` | the agent's database, clones, research, memory |
| `/var/lib/apiagent/uv-cache/` | uv's cache |

Python lives under `/opt` rather than `/var/lib` because of SELinux, which is enforcing on Oracle Linux: it lets systemd run programs from `/opt` and denies them from `/var/lib`. Both venvs link to that interpreter, so it has to sit where systemd may execute it.

The agent keeps its own clones under `/var/lib/apiagent` and never touches `/opt/apiagent`, so a deploy can't collide with work the agent is doing.

## Later deploys

```sh
sudo /opt/apiagent/ApiAgentService1/deploy/bootstrap.sh --start
```

It fetches `origin/main`, hard-resets to it, rebuilds with `uv sync --locked`, re-verifies the vendored agentkit, resets SELinux labels, and restarts both units. Your `/etc/apiagent` files are left alone.

## Checking on it

```sh
systemctl status operation service1-agent
journalctl -u service1-agent -f                  # follow the agent's log
curl "http://$(tailscale ip -4):8001/health"     # API
curl "http://$(tailscale ip -4):9001/health"     # agent
sudo firewall-cmd --zone=tailnet --list-all      # tailscale0 and ports 8001/tcp 9001/tcp
```

From your laptop, with the UI running, point its registry entry for `service1` at `http://apiagent-service1:9001`.

## When something is wrong

**A unit fails with `status=203/EXEC`.** SELinux stopped systemd running the program. `sudo ausearch -m avc -ts recent` shows the denial. The usual cause is a venv whose Python is outside `/opt/apiagent/python`; re-run `bootstrap.sh`, which puts the interpreter back there and resets labels with `restorecon`.

**Requests over the tailnet hang instead of being refused.** firewalld is dropping them. `sudo firewall-cmd --zone=tailnet --list-all` should list `tailscale0` and both ports; if it doesn't, re-run `set-tailscale-host.sh`.

**Agent returns 403 "Host not allowed".** The `Host` header isn't in `ALLOWED_HOSTS`. Re-run `set-tailscale-host.sh`, which writes both the MagicDNS name and the IP, and check what the caller actually uses.

**Agent returns 403 "Origin not allowed".** The UI's origin isn't in `UI_ORIGINS`. Add the exact scheme, host and port your dev server prints.

**Agent returns 401 on agent-to-agent calls.** `AGENT_SHARED_TOKEN` differs between the VMs, or is empty on one.

**`message_agent` says it can't reach the peer.** Check `tailscale status` on both VMs, then that `registry.json` matches the other VM's real hostname and port.

**The API can't be reached from the other VM.** `BIND_HOST` is still `127.0.0.1`. Run `set-tailscale-host.sh`.

**`uv sync --locked` fails during a deploy.** The lockfile doesn't match `pyproject.toml`. Run `uv lock` locally, commit it, and deploy again — don't hand-edit the lockfile on the VM.
