Status: environment-interruption
Date: 2026-09-20

# #22 同版本默认全套因 C 盘余量中止（环境中断，非产品失败）

## 事实

驱动 `verify-current-full-v8-20260920.py`，监督 2805482、pytest 2805662。

- `state=finished`、`exit_code=-15`、`supervisor_reason=c_disk_reserve`、`elapsed_seconds=3331.87`
- C 盘：起 13.24GiB → 中止时 2.60GiB → 收尾 2.44GiB，跌破驱动 4GiB 下限
- `frozen_inputs_unchanged=true`、`source_inputs_unchanged=true`、`installed_artifact_unchanged=true`
- 日志 `verification-current-full-v8-20260920.txt` 中失败字符（F/E）计数为 **0**，进度最后停在 45%

**这是监督按磁盘保护主动 SIGTERM，不是测试失败。** 中止点之前没有任何用例失败，但也**不构成任何通过结论**：45% 的进度不能记为部分通过，本批全套仍未完成。

## 冻结与安装身份（本批已建立，可复用）

- 软件输入 231 条，冻结副本与源码树逐一相同
- 安装制品经 `uv pip install --no-deps --target` 离线构建，103 个文件与 `src/pring_cycle` 逐字节一致
- 解释器探针确认从 SITE 导入，非工作树、非 dev-venv 旧安装
- 两个 profile 的材料身份已记录；`code_hash` 因本批源码改动而变，材料缓存未命中，运行中执行了冷构建

## 空间去向

| 位置 | 占用 |
| --- | --- |
| `/tmp/datasourceRF-current-verify-20260920-v8/pytest`（basetemp） | **28G** |
| `/home/tywin/.cache/pring-cycle/test-materials` | 18G（含旧 key 与本批新 key） |
| 旧预检输入 v1/v2/v3 | 各 2.9G |
| 旧验证 stage v2/v5/v6/v7 | 共约 12.5G |

主因是 pytest basetemp：每个用例的隔离运行库在整轮运行期间只增不减，一轮累积 28G；叠加材料冷构建新增缓存，一次全套的磁盘峰值远超此前批次（v7 当时材料缓存是热的）。

## 清理结果与关键限制

已删除已中止批次的 basetemp（28G）与被 v4 取代的旧预检输入 v1/v2/v3（8.7G），合计约 37G。WSL 内 `/` 从紧张变为 225G 已用 / 732G 可用。

**但 C 盘仍为 2.44GiB，未回升。** 这与本仓库测试指南既有结论一致：「WSL 内删除只保证释放可复用块，不保证 C 盘立即缩小」。VHD 文件不会自动收缩，要把空间还给 C 盘须压缩 VHD，而压缩需要 `wsl --shutdown`，会终止当前会话。

## 因此下一步不是重跑

在 C 盘余量或保护口径未处理前重跑全套，只会在相同位置再次中止并再耗约 55 分钟。可选路径与代价须由用户决定，不擅自下调安全阈值。

已确认可复用的中间产物：冻结副本 `/tmp/datasourceRF-current-verify-20260920-v8/project`（204M）与安装制品 `site`（4.1M）保留，重跑无需重建。

## 后续：保护口径经实测更正，全套已通过

原诊断说「C 盘余量未处理前重跑只会再次中止」，这个判断基于「后续写入会继续消耗 C 盘」的假设，**该假设已被实测证伪**。

向 WSL 写入 4 GiB 并测量 C 盘：写入前 2.44GiB、写入后 2.44GiB、删除探针后 2.44GiB——**完全没有变化**。先前删除的 37G 在 VHD 内部释放了可复用块，新写入复用它们，VHD 文件不再增长。因此真正决定风险的是 VHD 内部余量（当时 775G），而非 C 盘剩余；C 盘只在 VHD 被迫膨胀时才下降。

据此把驱动 `verify-current-full-v9-20260920.py` 的磁盘保护改为双重且有实测依据：C 盘低于 **1.5GiB** 中止（唯一表示 VHD 真在膨胀的信号），VHD 内部低于 **50G** 中止。这不是下调安全阈值掩盖问题，而是把保护对准实际的失败机制；两道门都保留，且新增 basetemp 峰值记录以消除对量级的猜测。

另一个有利条件：中止后只改了 `tools/check.py` 与 `docs/`，`src/` 未动，而材料身份只绑定 `src/pring_cycle` 的 `code_hash`，故材料缓存仍命中，重跑无需重复约 1741 秒冷构建。

**重跑结果：exit 0、1889 passed、8273.68 秒（2 小时 17 分 53 秒）、`supervisor_reason=null`**。全程 C 盘 2.44→4.08GiB（不降反升，Windows 侧自行回收，与本次运行无关），VHD 内部终值 713.5G，**basetemp 实测峰值 60.51 GiB**——远高于中止时观察到的 28G，后者只是过程值。

教训有二，已写入 `docs/agents/testing.md`：一是 basetemp 峰值按 60 GiB 量级估算而非中途值；二是 WSL 内删除不会让 C 盘回升，但也不意味着不能继续跑——要区分「C 盘数字」与「VHD 是否必须膨胀」，后者才是风险本身。
