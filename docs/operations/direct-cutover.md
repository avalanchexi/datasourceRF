# V1 演练与直接切换

## 门禁顺序

直接切换按以下顺序执行，任一步失败都停止：

1. 在最新目标交易日用 `pring-cycle source-smoke --target-date YYYY-MM-DD --json` 校验
   中国交易日历、中证全指、上证国债指数和 NHII 的真实身份、连续性与规范化哈希。此命令需要
   本机 `TUSHARE_TOKEN`；失败或未执行不能由 fixture 替代。
2. 执行 `context-source-smoke`，对本次演练实际使用的 P1 官方 HTML schema family 逐一执行
   `official-context-smoke`。EIA 双序列属于 P2；配置 EIA key 时可额外执行 `eia-smoke`，但
   未配置时必须继续显示 `awaiting_source_certification`，不会阻塞只要求 P0/P1 的切换门。
   COMEX、LBMA、VIX、SOX 和 16:30 在岸收盘价同样不得用代理补齐。一次 smoke 只证明该次
   响应，不自动完成目录来源认证。
3. `pring-cycle acceptance --json`：35 项回归、故障注入、确定性、性能和资源硬门。套件耗时
   是优化目标，不是硬门：`suite_timing` 给出目标 600 秒、实测值、是否达标和计时范围；硬门
   全通过而仅时长超标时结果仍为 `ok`，清单也不因此阻断。
4. `pring-cycle rehearse-fixture-recovery --json`：独立 fixture 中断、陈旧 owner 审计和用户显式恢复；不写正式发布历史。
5. 保留上述每条 smoke 返回的制品哈希。在最新完整目标交易日完成手动完整运行与报告并启动
   本机 Dashboard 后，执行：

```bash
pring-cycle rehearse-real --target-date YYYY-MM-DD --dashboard-port 8877 \
  --source-smoke-hash CORE_SHA256 \
  --source-smoke-hash CONTEXT_SHA256 \
  --source-smoke-hash LPR_SHA256 \
  --source-smoke-hash EACH_REQUIRED_OFFICIAL_FAMILY_SHA256 \
  --json
```

若本次另外执行了 EIA P2 smoke，可以再追加其 `--source-smoke-hash EIA_SHA256`；它会被校验
并记录为已知 P2 证据，但不是 P0/P1 切换硬门。

   命令要求真实 P0、按 schema 家族抽样的 P1、全部必需且目标期匹配的 smoke 制品、当前原子
   投影，以及 AI 成功或确定性降级报告。每个 smoke 会按来源核对官方身份、字段族、观测数量、
   响应/规范化哈希和日/月/季度周期语义；只有状态与请求数的空壳 JSON 不能通过。演练还会通过
   禁用代理的 `127.0.0.1` 请求核对 Dashboard 有意义首屏、精确 `projection_set_id`，以及
   `/_dash-layout` 的真实 Dash 布局；后台加载失败首屏不能通过。
6. 停止旧系统并将其置为只读。旧系统不再运行、不接受写入，也不是运行时降级源。
7. 用验收和两次演练返回的制品哈希构建清单：

```bash
pring-cycle cutover-manifest \
  --acceptance-hash SHA256 \
  --fixture-rehearsal-hash SHA256 \
  --real-rehearsal-hash SHA256 \
  --legacy-system-read-only-stopped \
  --suite-total-seconds 1975 \
  --json
```

`--suite-total-seconds` 可选，填整批测试从开始到实际终态的总耗时；清单把它与验收制品自身的
阶段计时分列在 `suite_timing` 下，两者口径不同，不相加也不互相替代。

清单固定代码、依赖、数据库/配置版本、生效模型内嵌的指标目录、模型、投影、回归、质量、性能、
文档和两次演练哈希。生效模型必须绑定当前代码支持的目录版本；旧模型不能与新版全局目录哈希
拼接成可切换清单。只有 `status=ready` 才可继续。

8. 用户核对清单后，以完整确认词记录一次性切换：

```bash
pring-cycle cutover-record \
  --manifest-hash SHA256 \
  --confirm DIRECT_CUTOVER_TO_PRING_V1 \
  --json
```

不存在 `force` 或等价绕过。清单只接受已登记且来源引用匹配的验收/演练制品；验收、fixture
恢复演练和真实演练都绑定执行时的代码、依赖、数据库/配置版本，验收与真实演练还绑定模型
manifest。任何相关内容变化后必须重跑对应命令。记录切换时会按当前代码、依赖、模型、投影和
文档重新构建并拒绝陈旧制品或陈旧清单。切换记录不可更新或删除；再次提交
同一清单是幂等的，换清单会被拒绝。切换后首次故障只在 V1 内修复、显式恢复，或在升级破坏
完整性时重新初始化。不得恢复旧系统运行。

## 真实演练不是发布历史

真实演练读取已经发布的当前投影和报告，验证后只写仓库外验收制品；fixture 演练使用独立临时
运行目录。两者都带 `acceptance_only=true` 与 `publication_history_written=false`，不得被页面
当成正式阶段历史。切换清单会重新验证真实演练的目标日期、投影身份、P0/P1、报告、Dashboard
结论和全部 smoke 制品；仅伪造 `status=ok` 的最小 JSON 不能通过。
# 2026-09-05 审查阻塞

当前 `metric-catalog-v0003` 的市场来源认证合同未通过官方语义复核，
`doctor`／健康 API 的 `source_contract_review` 会列出受影响 family 和原因。
该目录的新认证、候选刷新、激活、正式写入和切换均被拦截，已有历史数据仍可读取。
不要通过改目录版本字符串、重盖 smoke 指纹或确认词绕过。先按
`docs/research/market-source-semantic-review-2026-09-05.md` 完成来源样本与修正后的新不可变模型，
再执行下述演练和切换步骤。当前没有可供用户确认的就绪切换清单。
