# SPDX-FileCopyrightText: Copyright 2026 shadPS4 Emulator Project
# SPDX-License-Identifier: GPL-2.0-or-later

from collections import Counter, defaultdict
from html import escape
import json
import os
from pathlib import Path
import subprocess
import tempfile


def run(*args, check=True):
    return subprocess.run(args, check=check, text=True, capture_output=True)


def git(*args, check=True):
    return run("git", *args, check=check)


def api(endpoint, paginate=False):
    flags = ("--paginate", "--slurp") if paginate else ()
    return json.loads(run("gh", "api", *flags, endpoint).stdout)


def pull_request_bases(fork, repositories):
    targets = defaultdict(set)
    for remote, repository in repositories.items():
        pages = api(f"repos/{repository}/pulls?state=open&per_page=100", paginate=True)
        for page in pages:
            for pr in page:
                head = pr["head"]
                if (head["repo"] or {}).get("full_name") == fork:
                    targets[head["ref"]].add((remote, pr["base"]["ref"]))
    return targets


def fetch_heads(repositories):
    heads = {}
    for remote, repository in repositories.items():
        git("remote", "add", remote, f"https://github.com/{repository}.git")
        git("fetch", "--no-tags", remote, f"+refs/heads/*:refs/remotes/{remote}/*")
        refs = git(
            "for-each-ref",
            "--format=%(refname:strip=3) %(objectname)",
            f"refs/remotes/{remote}/",
        ).stdout.splitlines()
        heads[remote] = dict(ref.split() for ref in refs)
    return heads


def is_ancestor(older, newer):
    result = git("merge-base", "--is-ancestor", older, newer, check=False)
    if result.returncode not in (0, 1):
        result.check_returncode()
    return result.returncode == 0


def rebase_branch(head, original_base, base):
    git("switch", "--detach", head)
    result = git(
        "rebase", "--no-fork-point", "--rebase-merges", "--onto", base, original_base, check=False
    )
    if result.returncode == 0:
        return git("rev-parse", "HEAD").stdout.strip(), []

    conflicts = git("diff", "--name-only", "--diff-filter=U").stdout.splitlines()
    if Path(".git/rebase-merge").exists() or Path(".git/rebase-apply").exists():
        git("rebase", "--abort")
    if conflicts:
        return head, conflicts
    result.check_returncode()


def sync_branch(branch, head, target, original_base, base):
    remote, base_branch = target
    base_label = f"{remote}/{base_branch}"
    if is_ancestor(base, head):
        return head, "OK", f"already based on {base_label}"
    if is_ancestor(head, base):
        candidate = base
    else:
        shared = git("merge-base", head, original_base, check=False)
        if shared.returncode == 1:
            return head, "SKIP", f"unrelated to {base_label}"
        shared.check_returncode()
        candidate, conflicts = rebase_branch(head, original_base, base)
        if conflicts:
            return head, "SKIP", f"rebase conflicts in {', '.join(conflicts)}"

    if not is_ancestor(base, candidate):
        raise RuntimeError("rebased head does not contain the chosen base")
    live = git("ls-remote", remote, f"refs/heads/{base_branch}").stdout.split()
    if not live or live[0] != base:
        return head, "SKIP", f"{base_label} changed during sync"
    ref = f"refs/heads/{branch}"
    git("push", f"--force-with-lease={ref}:{head}", "fork", f"{candidate}:{ref}")
    return candidate, "SYNC", f"{head[:8]} → {candidate[:8]}"


def write_summary(results):
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return

    labels = {"SYNC": "Synced", "OK": "Already current", "SKIP": "Skipped", "ERROR": "Failed"}
    colors = {"SYNC": "#1a7f37", "OK": "#0969da", "SKIP": "#9a6700", "ERROR": "#cf222e"}
    counts = Counter(status for status, _, _, _ in results)
    lines = [
        "## Branch sync",
        "",
        "```mermaid",
        "flowchart LR",
        f'    run["{len(results)} branches"]',
    ]
    for status, label in labels.items():
        lines.append(f'    run --> {status}["{label}: {counts[status]}"]')
        lines.append(f"    style {status} fill:#ffffff,color:#1f2328,stroke:{colors[status]},stroke-width:2px")
    lines.extend([
        "```",
        "",
        "| Branch | Base | Result | Details |",
        "| --- | --- | --- | --- |",
    ])

    def cell(value):
        return escape(" ".join(value.splitlines())).replace("|", "&#124;")

    order = {"ERROR": 0, "SKIP": 1, "SYNC": 2, "OK": 3}
    for status, branch, base, detail in sorted(results, key=lambda row: (order[row[0]], row[1])):
        lines.append(
            f"| <code>{cell(branch)}</code> | {cell(base)} | {labels[status]} | {cell(detail)} |"
        )
    with open(path, "a", encoding="utf-8") as summary:
        summary.write("\n".join(lines) + "\n")


def sync_branches(heads, targets, upstream_default):
    results = []

    def report(status, branch, target, detail):
        base = "/".join(target) if target else "—"
        results.append((status, branch, base, detail))
        print(f"{status} {branch}: {detail}")

    pending = {}
    for branch in sorted(heads["fork"]):
        pr_targets = targets.get(branch, set())
        if len(pr_targets) > 1:
            report("SKIP", branch, None, "open pull requests have different bases")
            continue
        target = next(iter(pr_targets)) if pr_targets else (
            "upstream", branch if branch in heads["upstream"] else upstream_default
        )
        if target[1] not in heads[target[0]]:
            report("SKIP", branch, target, f"base {target[0]}/{target[1]} does not exist")
            continue
        pending[branch] = target

    current_fork = dict(heads["fork"])
    while pending:
        ready = [
            branch for branch, (remote, base) in pending.items()
            if remote != "fork" or base not in pending
        ]
        if not ready:
            for branch, target in pending.items():
                report("SKIP", branch, target, "circular base dependency")
            break
        for branch in ready:
            target = pending.pop(branch)
            remote, base = target
            original = heads[remote][base]
            live = current_fork[base] if remote == "fork" else original
            try:
                current_fork[branch], status, detail = sync_branch(
                    branch, heads["fork"][branch], target, original, live
                )
            except (subprocess.CalledProcessError, RuntimeError) as error:
                status = "ERROR"
                detail = (getattr(error, "stderr", None) or str(error)).strip()
                print(detail)
            report(status, branch, target, detail[:240])

    write_summary(results)
    return sum(status == "ERROR" for status, _, _, _ in results)


def main():
    fork = os.environ["FORK"]
    parent = api(f"repos/{fork}").get("parent")
    if not parent:
        raise RuntimeError(f"{fork} is not a fork")
    repositories = {"fork": fork, "upstream": parent["full_name"]}
    targets = pull_request_bases(fork, repositories)

    with tempfile.TemporaryDirectory(prefix="sync-branches-") as directory:
        previous = Path.cwd()
        try:
            os.chdir(directory)
            git("init", "--quiet")
            git("config", "user.name", "github-actions[bot]")
            git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
            os.environ.update(GIT_EDITOR="true", GIT_SEQUENCE_EDITOR="true")
            run("gh", "auth", "setup-git")
            return bool(sync_branches(fetch_heads(repositories), targets, parent["default_branch"]))
        finally:
            os.chdir(previous)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as error:
        raise SystemExit(error.stderr.strip() or str(error))
