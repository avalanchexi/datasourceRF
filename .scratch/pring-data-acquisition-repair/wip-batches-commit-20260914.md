# 2026-09-14 既有未提交成果分批提交

用户选择“先分批提交再做19”。票12提交59b7ce5后，工作区仍有09-09至09-13多个切片已验证但未提交的改动。按文件不相交划分三批，每批在HEAD独立检出（git worktree，原生目录`/home/tywin/.cache/pring-cycle/verification/wip-batches-20260914`）只放入本批文件，非editable wheel安装后验证；脚本见[wip-batches-20260914.py](wip-batches-20260914.py)，每次运行记录为`verification-wip-20260914-<批>-<名>.json/.txt`。

| 批 | 提交 | 范围 | 验证终态 |
|---|---|---|---|
| A Worker连接生命周期（票17） | `ed1213c` | storage/worker、e2e、Worker生命周期测试及2个进程夹具 | mypy 93源文件、Ruff/格式6文件通过；176原范围38通过/115.70秒 |
| B 报告单调计时 | `94e08f9` | reports.py、test_report_boundary.py | mypy、Ruff/格式通过；reports目录+5个报告相关集成/Web文件82通过/36.77秒 |
| C 注册目录消费完整性（票19/14） | `c566702` | 13个源码、3个测试文件及106个测试读取的`.scratch`原件夹具 | mypy 94源文件、Ruff/格式16文件通过；38个关联测试文件见下 |

C批关联回归`related`实际**171失败/1205通过/3513.79秒**。171项全部是FileNotFoundError：测试读取的`.scratch`原件/清单从未纳入git，独立检出中缺失；不是产品断言失败。补入测试直接引用的夹具目录及a18中被引用的20个原件（augment-1/2），重跑：

- `rerun-fixtures`：失败ID提取时去色正则误删`[m`开头的参数ID，pytest以用法错误退出4、未执行测试。属于准备错误，记录保留。
- `rerun-fixtures-2`：修正后171项中127通过、44失败，均为信用脉冲清单`credit-window-inputs-186/manifest.json`间接引用的a18原件缺失。
- 按清单补入37个原件（augment-3）后`rerun-fixtures-3`：44通过/275.12秒。

三次运行源码/测试指纹相同，仅补夹具。a18原件含CRLF，而全局`core.autocrlf=input`会在入库时改写字节，导致哈希命名原件失配；沿用evidence-13/14等既有约定，为a18、credit-window-inputs-186及两个Q1历史夹具目录新增`* -text`的`.gitattributes`，并逐个核对106个暂存blob与原文件字节一致。准备过程中曾在检出里误用`git rm --cached -r .scratch/...`把HEAD已跟踪scratch文件暂存为删除，已重置索引后按清单重新加入并确认删除为0，主工作区未受影响。

未纳入：`src/pring_cycle/assets/dashboard.css/js`主题与日期输入改动、`docs/diagrams/`，与本修复项目无关，保持未提交。默认全套仍留到票19必要改动后的最终同版本执行。
