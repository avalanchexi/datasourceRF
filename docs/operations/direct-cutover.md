# V1 演练与直接切换

## 门禁顺序

直接切换按以下顺序执行，任一步失败都停止：

1. `pring-cycle acceptance --json`：35 项回归、故障注入、确定性、性能和资源硬门。
2. `pring-cycle rehearse-fixture-recovery --json`：独立 fixture 中断、陈旧 owner 审计和用户显式恢复；不写正式发布历史。
3. 在最新完整目标交易日完成手动完整运行与报告后，执行 `pring-cycle rehearse-real --target-date YYYY-MM-DD --json`。它要求真实 P0、按 schema 家族抽样的 P1、当前原子投影，以及 AI 成功或确定性降级报告。
4. 停止旧系统并将其置为只读。旧系统不再运行、不接受写入，也不是运行时降级源。
5. 用前三步返回的制品哈希构建清单：

```bash
pring-cycle cutover-manifest \
  --acceptance-hash SHA256 \
  --fixture-rehearsal-hash SHA256 \
  --real-rehearsal-hash SHA256 \
  --legacy-system-read-only-stopped \
  --json
```

清单固定代码、依赖、数据库/配置版本、指标目录、模型、投影、回归、质量、性能、文档和两次演练哈希。只有 `status=ready` 才可继续。

6. 用户核对清单后，以完整确认词记录一次性切换：

```bash
pring-cycle cutover-record \
  --manifest-hash SHA256 \
  --confirm DIRECT_CUTOVER_TO_PRING_V1 \
  --json
```

不存在 `force` 或等价绕过。切换记录不可更新或删除；再次提交同一清单是幂等的，换清单会被拒绝。切换后首次故障只在 V1 内修复、显式恢复，或在升级破坏完整性时重新初始化。不得恢复旧系统运行。

## 真实演练不是发布历史

真实演练读取已经发布的当前投影和报告，验证后只写仓库外验收制品；fixture 演练使用独立临时运行目录。两者都带 `acceptance_only=true` 与 `publication_history_written=false`，不得被页面当成正式阶段历史。
