#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""清理因页面重写而失效的 TTS 音频（R2 + 本地 audio/）。

孤儿 = git 历史里出现过、但当前页面已不再引用的 data-tts 哈希。
bake-tts.py 是幂等的（只加不删），所以每次改版都会攒下一批，需要定期跑这个。

用法：
    python3 tools/prune-audio.py --dry-run   # 只列清单，不删（先跑这个）
    python3 tools/prune-audio.py             # 真删
    python3 tools/prune-audio.py --local-only   # 只清本地 audio/，不碰 R2
"""
import subprocess, re, glob, os, sys, pathlib
from concurrent.futures import ThreadPoolExecutor

BUCKET = "bigcat-audio"
WRANGLER = ["npx", "wrangler@4.126.0"]
LANGS = ("zh", "en")
DRY = "--dry-run" in sys.argv
LOCAL_ONLY = "--local-only" in sys.argv
PREFIX = os.environ.get("R2_PREFIX", pathlib.Path.cwd().name)
PAT = re.compile(r'data-tts(?:-\w+)?="([0-9a-f]{16})"')


def hashes_in(text):
    return set(PAT.findall(text))


def collect():
    files = sorted(glob.glob("*.html"))
    cur = set()
    for f in files:
        cur |= hashes_in(open(f).read())
    allh = set()
    revs = subprocess.run(["git", "rev-list", "HEAD"], capture_output=True, text=True).stdout.split()
    for rev in revs:
        names = subprocess.run(["git", "ls-tree", "--name-only", rev],
                               capture_output=True, text=True).stdout.split()
        for f in names:
            if f.endswith(".html"):
                blob = subprocess.run(["git", "show", f"{rev}:{f}"],
                                      capture_output=True, text=True).stdout
                allh |= hashes_in(blob)
    return cur, allh


def r2_delete(key):
    r = subprocess.run(WRANGLER + ["r2", "object", "delete", f"{BUCKET}/{key}", "--remote"],
                       capture_output=True, text=True)
    out = (r.stdout + r.stderr).lower()
    if r.returncode == 0:
        return key, "已删"
    if "not found" in out or "does not exist" in out or "404" in out:
        return key, "本就不存在"
    return key, "失败: " + (r.stderr.strip().splitlines() or ["?"])[-1][:70]


cur, allh = collect()
orph = sorted(allh - cur)
print(f"[{PREFIX}] 当前引用 {len(cur)} 个哈希；历史共 {len(allh)} 个；孤儿 {len(orph)} 个")

# ---- 本地 audio/ ----
local = [p for p in glob.glob("audio/*/*.mp3")
         if pathlib.Path(p).stem not in cur]
size = sum(os.path.getsize(p) for p in local)
print(f"[本地] audio/ 下可清理 {len(local)} 个文件，共 {size/1048576:.1f} MB")
if not DRY:
    for p in local:
        os.remove(p)
    print("[本地] 已删除")

if LOCAL_ONLY or not orph:
    sys.exit(0)

keys = [f"{PREFIX}/{lang}/{h}.mp3" for h in orph for lang in LANGS]
print(f"[R2] 待处理 {len(keys)} 个对象（{len(orph)} 哈希 × {len(LANGS)} 语言）")
if DRY:
    for k in keys:
        print("   ", k)
    sys.exit(0)

done = {"已删": 0, "本就不存在": 0}
fails = []
with ThreadPoolExecutor(max_workers=6) as ex:
    for i, (k, st) in enumerate(ex.map(r2_delete, keys), 1):
        if st in done:
            done[st] += 1
        else:
            fails.append((k, st))
        if i % 20 == 0:
            print(f"   …{i}/{len(keys)}")
print(f"[R2] 已删 {done['已删']}｜本就不存在 {done['本就不存在']}｜失败 {len(fails)}")
for k, st in fails:
    print("   ✗", k, st)
sys.exit(1 if fails else 0)
