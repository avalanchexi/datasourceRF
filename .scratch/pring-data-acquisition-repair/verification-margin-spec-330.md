# 融资软件切片 Spec 审查

固定起点：926434e；工作区增量按margin-baseline-314.json及margin-review-325.diff辨认，最终最小提交按margin-index-preview-329.patch核对。规格来源：spec.md的M2/Testing 21及issues/05-margin-certification.md两项新目录软件验收。

两轴按code-review独立并行审查，Spec由margin_spec_review执行。

首次发现：需要单独覆盖新目录错误期次。追加wrong_period（所有行处于请求范围外）及wrong_exchange（NYSE）后，代理只读确认经过公开准入及采集检查失败收据、未验证状态、原件保留和无新目录声明，缺口闭合。

329窄复核：无新增问题。database_path/value/acquisition_ids及Evidence转发是融资原件和值校验的必要依赖，HEAD唯一调用点已覆盖，其他家族语义不变。helper移至模块尾不改变执行行为；BytesIO仅补齐既有EIA测试导入。

Spec待修项：0。本批是明确标识合成材料的软件支持，不满足北交所官方数值、历史PUBLIC或正式家族认证；这些原票条件继续开放。最终运行证明以根验收记录为准。
