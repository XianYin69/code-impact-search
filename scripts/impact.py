#!/usr/bin/env python3
"""code-impact-search helper: build a light import/symbol map and query it.
Stdlib only. Commands: index / refs / chain / blast. Output: text (JSON with --json)."""
import os, re, sys, json, argparse, collections

LANG = {
    ".py": (re.compile(r"^\s*(?:from\s+([\w\.]+)\s+import|import\s+([\w\.]+))", re.M), re.compile(r"^(?:def|class)\s+(\w+)", re.M)),
    ".js": (re.compile(r"""from\s+['"]([^'"]+)['"]|require\(['"]([^'"]+)['"]\)"""), re.compile(r"(?:function|class)\s+(\w+)")),
    ".ts": (re.compile(r"""from\s+['"]([^'"]+)['"]|require\(['"]([^'"]+)['"]\)"""), re.compile(r"(?:function|class)\s+(\w+)")),
    ".c": (re.compile(r'#include\s*[<"]([^">]+)[">]'), re.compile(r"^\w[\w\s\*]*\b(\w+)\s*\([^;]*$")),
    ".h": (re.compile(r'#include\s*[<"]([^">]+)[">]'), re.compile(r"^\w[\w\s\*]*\b(\w+)\s*\(")),
    ".cpp": (re.compile(r'#include\s*[<"]([^">]+)[">]'), re.compile(r"(?:class|struct)\s+(\w+)|^\w[\w\s\*&:]*\b(\w+)::")),
    ".java": (re.compile(r"^\s*import\s+([\w\.]+);", re.M), re.compile(r"(?:class|interface)\s+(\w+)")),
    ".kt": (re.compile(r"^\s*import\s+([\w\.]+)", re.M), re.compile(r"(?:fun|class|object)\s+(\w+)")),
    ".go": (re.compile(r'"([^"]+)"'), re.compile(r"(?:func|type)\s+(\w+)")),
    ".rs": (re.compile(r"^\s*use\s+([\w:]+)", re.M), re.compile(r"(?:fn|struct|impl)\s+(\w+)")),
}
SKIP = {".git", "__pycache__", "node_modules", ".venv", "venv", "build", "dist", ".pytest_cache", "target"}


def scan(root):
    nodes, edges = {}, collections.defaultdict(set)
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP and not d.startswith(".")]
        for f in files:
            ext = os.path.splitext(f)[1]
            if ext not in LANG:
                continue
            p = os.path.join(dirpath, f)
            rel = os.path.relpath(p, root).replace("\\", "/")
            try:
                txt = open(p, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            if len(txt) > 800_000:
                txt = txt[:800_000]
            imp_re, sym_re = LANG[ext]
            deps = set()
            for m in imp_re.finditer(txt):
                g = [x for x in (m.groups() or []) if x]
                if g:
                    deps.add(g[0])
            syms = [m.group(1) or (m.group(2) if m.lastindex and m.lastindex > 1 else "") for m in sym_re.finditer(txt)]
            nodes[rel] = {"lang": ext, "imports": sorted(deps), "symbols": sorted({s for s in syms if s})[:200]}
            for d in deps:
                edges[d].add(rel)
    return {"root": os.path.abspath(root), "nodes": nodes, "edges": {k: sorted(v) for k, v in edges.items()}}


def resolve(graph, key):
    """match a file relpath or a module-ish name to node keys."""
    key = key.replace("\\", "/").lstrip("./")
    if key in graph["nodes"]:
        return [key]
    exact = [n for n in graph["nodes"] if n == key or n.endswith("/" + key)]
    hits = exact if exact else [n for n in graph["nodes"] if key in n]
    if not hits:
        stem = re.sub(r"\.(py|js|ts|jsx|tsx|c|h|cpp|java|kt|go|rs)$", "", key)
        hits = [n for n in graph["nodes"] if stem in n or stem in graph["nodes"][n]["symbols"]]
    return hits


def importers_of(graph, node):
    base = re.sub(r"\.[a-z]+$", "", node).replace("/", ".")
    out = set()
    for mod, users in graph["edges"].items():
        mb = mod.replace("/", ".")
        if mb == base or base.endswith("." + mb) or mb.endswith("." + base.split(".")[-1]) or mod == node:
            out.update(users)
    out.discard(node)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["index", "refs", "chain", "blast"])
    ap.add_argument("repo")
    ap.add_argument("a", nargs="?")
    ap.add_argument("b", nargs="?")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", default=None)
    ns = ap.parse_args()
    tmp = ns.out or os.path.join(os.environ.get("SMS_TMP", "."), "belief_map.json")
    if ns.cmd == "index":
        g = scan(ns.repo)
        json.dump(g, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"indexed {len(g['nodes'])} files -> {tmp}")
        return
    if not os.path.exists(tmp):
        sys.exit(f"no map at {tmp}; run index first")
    g = json.load(open(tmp, encoding="utf-8"))
    if ns.cmd == "refs":
        hits = resolve(g, ns.a)
        for h in hits:
            print(f"{h}  <-importers: " + ", ".join(sorted(importers_of(g, h)) or ["(none)"]))
        if not hits:
            print(f"no node matched {ns.a}")
    elif ns.cmd == "blast":
        seen, stack = set(), list(resolve(g, ns.a))
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            stack.extend(importers_of(g, n))
        print("blast radius (%d files):" % len(seen))
        for n in sorted(seen):
            print("  " + n)
        print("min read list: " + ", ".join(sorted(seen)[:12]))
    elif ns.cmd == "chain":
        src = resolve(g, ns.a)
        dst = set(resolve(g, ns.b))
        prev, queue, found = {}, collections.deque(src), None
        while queue:
            n = queue.popleft()
            if n in dst:
                found = n
                break
            for m in importers_of(g, n):
                if m not in prev and m != ns.a:
                    prev[m] = n
                    queue.append(m)
        if not found:
            print(f"no path {ns.a} -> {ns.b}")
        else:
            path, c = [found], found
            while c in prev:
                c = prev[c]
                path.append(c)
            print(" -> ".join(reversed(path)))


if __name__ == "__main__":
    main()
