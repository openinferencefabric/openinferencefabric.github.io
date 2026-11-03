#!/usr/bin/env python3
"""Refresh upstream/status.json: the live state of every upstream thread listed in upstream/contributions.json,
plus any new issue, pull request, discussion or comment by the tracked author outside our own organisations.

Needs GITHUB_TOKEN (the Actions token is enough: only public data is read). Standard library only.
    python3 scripts/upstream_status.py
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "upstream")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OWN_ORGS = ("openinferencefabric", "manmohanbrahma")
BOTS = re.compile(r"(\[bot\]$|^coderabbitai|^dependabot|^github-actions|^copilot|^netlify|^vercel|^codecov|^linux-foundation-easycla)", re.I)


def api(path, body=None):
    url = path if path.startswith("https://") else "https://api.github.com" + path
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 headers={"Accept": "application/vnd.github+json", "User-Agent": "oif-upstream-tracker",
                                          **({"Authorization": "Bearer " + TOKEN} if TOKEN else {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def graphql(query, **variables):
    out = api("https://api.github.com/graphql", {"query": query, "variables": variables})
    if out.get("errors"):
        raise RuntimeError(out["errors"])
    return out["data"]


def parse(url):
    m = re.match(r"https://github\.com/([^/]+)/([^/]+)/(issues|pull|discussions)/(\d+)", url)
    if not m:
        raise ValueError("not a GitHub thread URL: " + url)
    return m.group(1), m.group(2), m.group(3), int(m.group(4))


def thread_status(url, me):
    owner, repo, kind, num = parse(url)
    if kind == "discussions":
        d = graphql("""query($o:String!,$r:String!,$n:Int!){repository(owner:$o,name:$r){discussion(number:$n){
            title closed updatedAt answerChosenAt comments(last:20){totalCount nodes{author{login} createdAt url}}}}}""",
                    o=owner, r=repo, n=num)["repository"]["discussion"]
        comments = [{"author": (c["author"] or {}).get("login", ""), "at": c["createdAt"], "url": c["url"]} for c in d["comments"]["nodes"]]
        state = "answered" if d["answerChosenAt"] else ("closed" if d["closed"] else "open")
        return finish({"title": d["title"], "state": state, "updated": d["updatedAt"], "comments": d["comments"]["totalCount"]}, comments, me)
    i = api(f"/repos/{owner}/{repo}/issues/{num}")
    state = i["state"]
    if i.get("pull_request"):
        p = api(f"/repos/{owner}/{repo}/pulls/{num}")
        state = "merged" if p.get("merged_at") else ("draft" if p.get("draft") and state == "open" else state)
    comments = []
    if i["comments"]:
        last_page = (i["comments"] - 1) // 100 + 1
        comments = [{"author": c["user"]["login"], "at": c["created_at"], "url": c["html_url"]}
                    for c in api(f"/repos/{owner}/{repo}/issues/{num}/comments?per_page=100&page={last_page}")]
    s = {"title": i["title"], "state": state, "updated": i["updated_at"], "comments": i["comments"],
         "labels": [l["name"] for l in i.get("labels", [])], "closed_reason": i.get("state_reason")}
    return finish(s, comments, me)


def finish(s, comments, me):
    """Who spoke last: a person other than us (not a bot) means the next move is ours."""
    people = [c for c in comments if not BOTS.search(c["author"])]
    last = people[-1] if people else None
    s["last_comment"] = last
    s["reply_waiting"] = bool(last and last["author"].lower() != me.lower())
    return s


def discover(me, since):
    """Threads the author opened or commented on outside our own organisations since `since`."""
    found = {}
    owners = " ".join(f"-user:{o}" for o in OWN_ORGS)
    for qual in ("author", "commenter"):
        q = urllib.parse.quote(f"{qual}:{me} {owners} created:>={since}" if qual == "author" else f"{qual}:{me} {owners} updated:>={since}")
        for it in api(f"/search/issues?q={q}&per_page=100")["items"]:
            found.setdefault(it["html_url"], "pr" if it.get("pull_request") else "issue")
    d = graphql("""query($q:String!){search(query:$q,type:DISCUSSION,first:50){nodes{... on Discussion{url createdAt repository{owner{login}}}}}}""",
                q=f"author:{me} created:>={since}")
    for n in d["search"]["nodes"]:
        if n and n["repository"]["owner"]["login"] not in OWN_ORGS:
            found.setdefault(n["url"], "discussion")
    return found


def main():
    with open(os.path.join(ROOT, "contributions.json"), encoding="utf-8") as f:
        contrib = json.load(f)
    me, since = contrib["author"], contrib["since"]
    known = {t["url"] for p in contrib["projects"] for t in p["threads"]}
    status, failed = {}, []
    for url in sorted(known):
        try:
            status[url] = thread_status(url, me)
        except Exception as e:  # keep going: one deleted or renamed thread must not stop the refresh
            failed.append(url)
            print(f"warning: {url}: {e}", file=sys.stderr)
    new = []
    try:
        for url, kind in sorted(discover(me, since).items()):
            if url not in known:
                s = thread_status(url, me)
                s["kind"] = kind
                status[url] = s
                new.append(url)
    except Exception as e:
        print(f"warning: discovery: {e}", file=sys.stderr)
    out = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "threads": status, "new": new, "failed": failed}
    old = {}
    path = os.path.join(ROOT, "status.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            old = json.load(f)
    if {k: v for k, v in old.items() if k != "generated"} == {k: v for k, v in out.items() if k != "generated"}:
        print("no change")
        return
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, sort_keys=True)
        f.write("\n")
    print(f"{len(status)} threads, {len(new)} new, {len(failed)} failed")


if __name__ == "__main__":
    main()
