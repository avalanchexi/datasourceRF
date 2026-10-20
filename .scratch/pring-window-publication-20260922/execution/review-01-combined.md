# 票01两轴审查

两轴经独立只读CLI并行执行，均exit0；范围为对应review-01-input.json固定的WIP。下面保持两个轴分开。

## Standards

Standards 审查：**未发现明确硬违反；1 项低优先级启发式发现。**

固定点已核验：HEAD 等于 `bb737200024369f2938d26d1cc49f5f77f18a1b1`，`base..HEAD` 无提交。五个归属文件的 SHA-256 均匹配输入清单；三文件工作树 diff 加两个新文件的 `--no-index` diff，与固定 `review-01.diff` 逐字节一致，SHA-256 为 `de9dd945ee1515497ceacd8e761e80484c415039e95bce3f4ffb2433ba3aa9d4`。

- **[P3／启发式判断] possible Duplicated Code**：新增测试 [test_fixed_window_preflight.py:112](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-01/tests/models/test_fixed_window_preflight.py:112)，以及同文件第148、177、223、273、304行，重复构造相同的 `main(["model-input-preflight-read", ...])` 命令并解析捕获输出，仅收据哈希不同。依据：本次指定的 Fowler **Duplicated Code** 基线——同一逻辑形状重复时提取共享部分。建议提取本文件内的 `read_preflight_receipt(paths, receipt_hash, capsys)`，各用例保留自身行为断言，减少 CLI 参数调整时多处同步。该项是维护性判断，不是项目硬规则违反，也不表示现有行为错误。

已读取 AGENTS、CONTEXT、相关 ADR、完整规格及实施报告；复制的既有文档未作为修改审查。**本次仅静态审查，未实测**；23 项轻量通过来自实施报告，重型、全套与真实源验收尚未完成。未修改文件、运行测试、联网、读取凭据或再次委派。

## Spec

**Spec 轴：2 项问题，暂不满足票01验收。** 以下均为静态审查，未实测；未改文件、跑测试、联网或读取凭据。

固定点已核：HEAD＝`bb737200024369f2938d26d1cc49f5f77f18a1b1`，提交差集为空。五文件哈希均匹配输入；按指定命令拼接的 WIP 差异与 `review-01.diff` 完全一致，SHA-256 为 `de9dd945ee1515497ceacd8e761e80484c415039e95bce3f4ffb2433ba3aa9d4`。

1. **P1：固定120日尚未真正绑定。** [material_preflight.py:171](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-01/src/pring_cycle/material_preflight.py:171) 仅在显式传入数量时检查。省略参数，窗口内删去06-10、补入03-31，既有守卫仍可取得总计120日且包含两个端点，使日历显示 `available`，实际窗口仅119日。新增测试助手始终传120，未覆盖此路径。违反[票01验收第1、3项](/mnt/d/cursor/datasourceRF/.scratch/pring-window-publication-20260922/issues/01-fixed-window-calendar.md:26)。可以保留短窗诊断，但本轮请求必须可靠绑定120，不能只靠调用者记得追加参数。

2. **P2：失败收据不能精确定位实际检查的日历原件。** [material_preflight.py:604](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-01/src/pring_cycle/material_preflight.py:604) 捕获原件错误后清空 `provenance`；新增的[151行](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-01/src/pring_cycle/material_preflight.py:151)仅保存所有历史日历获取记录。存在多份原件时，没有将错误关联到实际失败的 acquisition/hash；公开重读仍保留这一歧义。违反[票01验收第5项](/mnt/d/cursor/datasourceRF/.scratch/pring-window-publication-20260922/issues/01-fixed-window-calendar.md:30)及规格 US25“绑定实际材料”。应保留具体失败对象；目前单收据测试不足以证明该要求。

模型清单哈希、成功路径原件哈希、收据自身校验已有实现；未发现新增代码混淆历史 PUBLIC 与检查时 SYSTEM，亦未发现明确超范围修改。

23项轻量通过仅为实施报告记录，本次未复跑。受影响重型、同版本全套、Worker/历史结果不变验证尚缺；真实日历认证与真实回放另属未完成边界，不能由轻量通过替代。

Standards：1项，最高为P3测试重复。Spec：2项，首要缺口为固定120日默认绑定。

主代理补记：随后同一r2软件的完整material_preflight文件33项通过，65.58秒、实际exit0、软件/安装/材料身份前后一致。该回归没有覆盖审查发现的两个反例，不能推翻审查；r3修复后须重新核对适用收据。
