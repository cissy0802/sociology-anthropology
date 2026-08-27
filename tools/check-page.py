#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发布前页面自检。用法：python3 tools/check-page.py [文件...]（省略=全部 *-day*.html）

抓的是眼睛看不出来的那几类：
  - 结构块重复（同一页出现两个 .bigcat / .crossx …）—— 脚本重跑最容易造成，且会污染字数判断
  - Markdown 语法漏进 HTML（**粗体** 会原样显示星号）
  - 字段格子残留【…】、小节编号断号、div 不平衡、共享脚本不是 4 行
  - 「第一节 / the second section」式数字回指（应改用小节标题）
  - 英文页混入汉字、英文页残留 .en-brief
  - 中文字数越界
退出码非 0 = 有问题，不要发布。
"""
import sys, re, glob

SINGLETON = ["header", "intro", "crossx", "bigcat", "thinking", "refs"]
REQUIRED = ["crossx", "thinking", "refs"]
LO, HI = 2900, 4000  # 硬上限；ENGINE 建议区间 2900–3900


def check(f):
    h = open(f).read()
    t = re.sub(r"<style.*?</style>", "", h, flags=re.S)
    t = re.sub(r"<script.*?</script>", "", t, flags=re.S)
    n = len(re.findall(r"[一-鿿]", re.sub(r"<[^>]+>", "", t)))
    en = f.endswith(".en.html")
    i = []
    for cls in SINGLETON:
        c = h.count("<header>") if cls == "header" else h.count(f'class="{cls}"')
        if c > 1:
            i.append(f"{cls}×{c}")
        if c == 0 and cls in REQUIRED:
            i.append(f"缺{cls}")
    nums = re.findall(r"// (\d\d)", h)
    if nums != [f"{k+1:02d}" for k in range(len(nums))]:
        i.append(f"小节编号{nums}")
    if re.findall(re.escape("**"), h):
        i.append("Markdown残留")
    if h.count("【"):
        i.append("字段格子残留")
    if len(re.findall(r"<div[ >]", h)) != len(re.findall(r"</div>", h)):
        i.append("div不平衡")
    if h.count("hub.cissychen.com") != 4:
        i.append("共享脚本不是4行")
    if re.search(r"第[一二三四]节那条机制|the (first|second|third) section", t):
        i.append("数字回指(应用小节标题)")
    if en and n:
        i.append(f"英文页混入汉字({n})")
    if en and h.count('en-brief"><b>EN'):
        i.append("英文页残留en-brief")
    if not en and not (LO <= n <= HI):
        i.append(f"字数{n}(区间{LO}-{HI})")
    m = re.search(r'class="crossx".*?</div>', h, re.S)
    cx = len(re.findall(r"<li><b>", m.group(0))) if m else 0
    if not 2 <= cx <= 3:
        i.append(f"越界{cx}条(应2-3)")
    b = re.search(r'class="bigcat".*?</div>', h, re.S)
    bc = len(re.findall(r"<li><b>", b.group(0))) if b else 0
    print(f'  {f:46} {n if not en else "—":>5}字 节{len(nums)} 越界{cx} 场景{bc}  '
          f'{"✓" if not i else "✗ " + ", ".join(i)}')
    return not i


files = sys.argv[1:] or sorted(glob.glob("*-day*.html"))
ok = all([check(f) for f in files])
sys.exit(0 if ok else 1)
