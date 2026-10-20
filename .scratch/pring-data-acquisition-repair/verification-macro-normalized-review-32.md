# 贷款与 OMO 父项消费：第32阶段双轴复核

固定点 `99c495a217b66d4bca9d6ceae4688ee69d4382bb`，五个既有源码/测试文件的工作树差异；HEAD无新提交。两代理只读审查，没有执行应用或测试。

## Spec

新增发现0。贷款在新目录保留所选期次，再校验实际当前/前月的质量与原件；七月无效不回退六月。OMO坏操作进入无效到期依赖，所用日历另核CoreInputValidator。日历质量无效日期仍参与日期选择，再拒绝无效父项，不将其当作休市而顺延；内置旧目录语义保留。

规格代理核读了贷款23项与OMO11项日志；最终日历增量只做静态审查，GREEN31终态由根代理核实为12通过、27 deselected、26.98秒（14730退出0）。不将只读审查说成代理重新跑过测试。

## Standards

新增硬规范问题0、新增气味建议0；原重复解析的非阻断建议1继续保留。

本轮审查曾指出：`_certified_trading_day_points`先滤掉invalid日，再选剩余首日，可将8月28日到期错误顺延到8月31日。该问题随后由[RED31](verification-macro-normalized-calendar-quality-red-31.txt)实际确认（1失败、7.89秒，72944退出1），新目录改为保留候选日期，并校验实际所用点；helper更名`_trading_day_candidates`。复审认定修复形状关闭该问题，根代理核对[GREEN31](verification-macro-normalized-calendar-quality-green-31.txt)实际通过。

政策利差、信用脉冲及Worker新目录仍为已知开放项；OMO真零投放、未来修订与更多跨cutoff覆盖仍未验收。本阶段结论不代表完整宏观链路、默认全套、真实来源认证、完整候选、120日、AI报告或切换已经完成。
