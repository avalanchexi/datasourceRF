# 实施入口与证据边界

日期：2026-09-22。用于[规格](spec.md)的实施定位，不是行为测试、来源认证或新目录生效证明。
定位基于本轮工作树静态读取，后续实施须按实际版本复核。

## 已核对的公开入口及守卫

| 位置 | 当前行为 | 本轮影响 |
|---|---|---|
| `src/pring_cycle/cli.py`，命令参数区约 732–783 行 | 核心历史、输入预检、模型回放已有 start/end；认证、刷新、运行有 target-date | 优先传递新范围，不全局替换旧日期 |
| `src/pring_cycle/cli.py:434` | model-source-certify 消费 candidate-request-hash，经正式服务准入 | CNY030 专项迁移需通过这一完整边界 |
| `src/pring_cycle/candidate_admission.py:54` | 已支持特定身份迁移白名单，尚无 CNY030 优先级迁移 | 增加明确受限的迁移，并兼容已批准目录修正 |
| `src/pring_cycle/candidate_admission.py:216` | 完整目录成员集合、priority/role 与基线比对 | 只改清单会失败，不能删除整体漂移检查 |
| `src/pring_cycle/candidate_admission.py:252` | P1/核心必认证；待认证 P2 可选 | 本次只改变 CNY030 所属优先级，不放宽通用认证门 |
| `src/pring_cycle/candidate_admission.py:261` | 核心固定 000985、000012、NHII | CNY030 是确认指标 |
| `src/pring_cycle/catalog_registry.py:65` | 同版本目录内容变化拒收 | 产生新目录，保留旧目录/模型 |
| `src/pring_cycle/material_preflight.py:139` | 预热检查认证、质量与非空公开时间 | 两个最早日期不独立证明完整输入；需要逐需求检查 |
| `src/pring_cycle/material_preflight.py:323` | checks_complete=false，尚有 calendar/originals/dimensions/point_in_time/parents 检查未完成 | 空 gaps 或命令成功仍不能宣布 ready |
| `src/pring_cycle/model_evaluation.py:225` | 回放接受请求范围，检查交集天数与端点 | 新日期可传入；合法比较基线仍是实际依赖 |
| `src/pring_cycle/evidence.py:50` | 可靠日期从下一来源本地自然日零点可见；未知时间保持空 | 对计算预热沿用同样时间语义 |
| `src/pring_cycle/context_replay_scope.py:150` | 不同公式有 730/95/62/10 或 0 日回看 | 预检用 timedelta，单位自然日；不是一律 259 交易日 |

旧日期另有用途：校准默认日期、准入下界、历史 fixture、官方公告 URL 均不是仅凭文本命中就应替换的窗口配置。
通用候选创建也不等于完整目录注册，不能作为绕过审核的入口。

## 测试先例

这是按变更选择行为测试的索引，不是每轮全跑清单；遵守[测试规则](../../docs/agents/testing.md)。

- `tests/models/test_candidate_admission.py`：待认证 P2、旧审核包拒收、完整窗口及未知时间输入。
- `tests/models/test_margin_scope_migration.py`：公开准入的专项迁移守卫、错误身份拒收。
- `tests/models/test_model_lifecycle.py`：不可变清单与旧模型哈希。
- `tests/models/test_material_preflight.py`：CLI 预检、预热缺件、未知和未来公开时间。
- `tests/models/test_model_evaluation_regressions.py`：冻结校准、预热不扩大窗口、缺核心不缩窗。
- `tests/integration/test_worker_registered_catalog.py`：可选来源失败仍完成其余有效运行。

## 调查方法

依仓库规定通过直接 `codex exec -s read-only -C /mnt/d/cursor/datasourceRF --skip-git-repo-check`
调查，退出 0。限制为指定入口和最多八个测试文件；未运行测试、修改文件、安装依赖或联网。
原始日志暂存 `/tmp/datasourceRF-window-spec-seams-20260922.log`；上面的可持久结论不依赖临时日志继续存在。
主会话复核了目录漂移/认证守卫、命令日期参数、目录不可变、预检未完成状态和日期精度转换。

## 日历推导边界

[calendar-plan.json](calendar-plan.json)是规格规划清单：读取并校验两份已保存的交易所休市 HTML，
以工作周减官方休市日重算，先与旧研究的 120/259 日序列逐项对账，再得到新窗口。
新 120 日为 2026-04-01 至 09-22；默认基础趋势 259 日为 2025-08-29 至 2026-09-22。
09-25 中秋休市在本轮末端之后；不能沿用“9 月无休市”的笼统说法。

清单没有进入应用日历仓库，也没有证明来源值、发布时间、公式完整父输入或稳定资产状态齐备。
实施时仍须使用项目公开日历入口和材料绑定完成运行验收。
