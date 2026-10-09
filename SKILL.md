---
name: code-impact-search
version: 0.1.0
description: >
  改代码前的影响面调查：符号引用点、导入/依赖图、调用链、爆炸半径（blast radius）、
  该读哪几个文件就够了。基于 grep/git log/轻量图脚本，不要求外部服务。
  触发词：影响面、谁调用了、改了会不会炸、依赖关系、调用链、先摸清代码、blast radius。
license: MIT
metadata:
  category: development
  replaces: codespaces
---
# code-impact-search（影响面调查）

替代原 codespaces（belief-map 那套外部产物不保留，改为本地可自跑的轻量做法）。
原则：**先查图，再读码**——不许盲读整仓。

## 三步

1. 索引：`python -B scripts/impact.py index <repo>` → `tmp/belief_map.json`（模块/导入边/符号定义位置）
2. 查询：`python -B scripts/impact.py refs <repo> <符号|文件>`（谁引用）、
   `impact.py chain <repo> <a> <b>`（两点间调用/导入路径）、
   `impact.py blast <repo> <文件>`（改动影响的文件集合 + 建议最小阅读清单）
3. 读：只读清单内文件，按 `read` 窗口读（先 `grep` 定位再 offset 续读）。

## 无脚本兜底（快速版）

```powershell
rg -n --hidden -g '!*.lock' "symbol_name" <repo>          # 引用点
git -C <repo> log --oneline -5 -- <path>                   # 近况与责任人
rg -n "^(import|from)\s+pkg" <repo> -g '*.py'              # 入边
```

## 边界

- 结论必须给出处（`file:line`），不许凭记忆断言依赖关系。
- 语言覆盖：Python / JS·TS / C·C++ / Java·Kotlin / Go / Rust 的导入语法差异写在
  `references/languages.md`，脚本按扩展名分派。
- 与 `general-software-dev`（流程）、`concurrency-design`（并发专项）互补，不重复实现。
- 产物一律落工作区 `tmp\`，不入仓库、不改被调查代码。

## 说明与已知边界

- 索引是**启发式**：按文件文本抽 import/#include 边，同名模块（不同目录）会被并成一个符号节点，
  blast 结果偏保守（宁多勿漏），最终阅读清单人工裁。
- 只读产物，不改被调查代码；`belief_map.json` 落工作区 `tmp\`，重跑 index 会覆盖。
- 大仓建议先 `index` 到子目录（`impact.py index <repo>/<pkg>`）再查，避免全仓扫。
- 输出为纯文本；加 `--json` 无额外效果（保留兼容位）。
