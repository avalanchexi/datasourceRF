**Spec 轴：2 项问题，暂不满足票01验收。** 以下均为静态审查，未实测；未改文件、跑测试、联网或读取凭据。

固定点已核：HEAD＝`bb737200024369f2938d26d1cc49f5f77f18a1b1`，提交差集为空。五文件哈希均匹配输入；按指定命令拼接的 WIP 差异与 `review-01.diff` 完全一致，SHA-256 为 `de9dd945ee1515497ceacd8e761e80484c415039e95bce3f4ffb2433ba3aa9d4`。

1. **P1：固定120日尚未真正绑定。** [material_preflight.py:171](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-01/src/pring_cycle/material_preflight.py:171) 仅在显式传入数量时检查。省略参数，窗口内删去06-10、补入03-31，既有守卫仍可取得总计120日且包含两个端点，使日历显示 `available`，实际窗口仅119日。新增测试助手始终传120，未覆盖此路径。违反[票01验收第1、3项](/mnt/d/cursor/datasourceRF/.scratch/pring-window-publication-20260922/issues/01-fixed-window-calendar.md:26)。可以保留短窗诊断，但本轮请求必须可靠绑定120，不能只靠调用者记得追加参数。

2. **P2：失败收据不能精确定位实际检查的日历原件。** [material_preflight.py:604](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-01/src/pring_cycle/material_preflight.py:604) 捕获原件错误后清空 `provenance`；新增的[151行](/home/tywin/worktrees/datasourceRF-window-20260922/ticket-01/src/pring_cycle/material_preflight.py:151)仅保存所有历史日历获取记录。存在多份原件时，没有将错误关联到实际失败的 acquisition/hash；公开重读仍保留这一歧义。违反[票01验收第5项](/mnt/d/cursor/datasourceRF/.scratch/pring-window-publication-20260922/issues/01-fixed-window-calendar.md:30)及规格 US25“绑定实际材料”。应保留具体失败对象；目前单收据测试不足以证明该要求。

模型清单哈希、成功路径原件哈希、收据自身校验已有实现；未发现新增代码混淆历史 PUBLIC 与检查时 SYSTEM，亦未发现明确超范围修改。

23项轻量通过仅为实施报告记录，本次未复跑。受影响重型、同版本全套、Worker/历史结果不变验证尚缺；真实日历认证与真实回放另属未完成边界，不能由轻量通过替代。