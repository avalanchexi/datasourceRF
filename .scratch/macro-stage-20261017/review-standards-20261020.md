结论：标准轴发现 **1 项应改，0 项阻断**。

1. **应改｜[src/pring_cycle/cockpit.py:2537](/home/tywin/worktrees/datasourceRF-mf/src/pring_cycle/cockpit.py:2537)**  
   `initial` 被固定显示为“生效首日”，超出了该字段的实际含义。[macro_judgement.py:427](/home/tywin/worktrees/datasourceRF-mf/src/pring_cycle/macro_judgement.py:427) 在此前结论没有阶段时就返回 `initial`；若规则生效当天为“无可取阶段”，后续首次取得阶段的日子仍会显示“生效首日”，误报生效时间。`GLOSSARY.md` 明确允许“无可取阶段”，展示应忠实于投影事实。  
   **建议：**改为“无既往阶段结论，取当日原始判断”；补充“生效日无阶段、后续日首次取得阶段”的外部展示断言。本项为静态调用链核实，未运行复现。

其余检查未发现需报告的问题：命名、注释密度和类型与周边写法一致；仓储采用参数化批量读取；页面没有重算分析状态；旧投影兼容分支保留；新增汇总测试经公开单日汇总入口断言发布结果。

审查范围为 `git diff main...macro-followups`。未修改文件、未运行测试；`git diff --check` 通过。
