# 新目录搜索身份与预算消费

2026-09-08，基线`087b9a8`，继续票17/19的公开查询、缺口、适配器和账本入口；票20完整实测仍依实际候选。

本切片修复新目录在查询构建、缺口绑定和旧预算/缓存事件归属解析中未传数据库的问题；缺口绑定同时核对目录与运行所绑定的模型清单一致。Worker传递真实数据库路径，不激活候选、不绕过旧v3拒绝、不放宽检索预算。

公开验证：

- `verification-search-catalog-red-01.txt`：1失败/3.09秒，是测试误以为新初始化库已有active；已改为明确验证前后均无active。
- `verification-search-catalog-red-02.txt`：1失败/3.53秒，缺口绑定真实复现`unknown_metric_definition_version`。
- `verification-search-catalog-green-01.txt`：1通过/6.26秒；同组3个PMI缺口，两提供商合成响应均原字节持久保存，候选状态未认证、未触发模型采用。
- `verification-search-catalog-legacy-red-01.txt`：2失败/5.90秒，旧缓存和已计费请求解析注册目录均失败；现补数据库解析并保持共享发布家族限额。
- `verification-search-catalog-binding-red-01.txt`：1失败/3.46秒，运行模型与传入目录不同原先未拒绝；现写入缺口前拒绝。
- `verification-search-catalog-focused-01.txt`：4通过/11.55秒。错误目录无部分缺口，旧缓存/预算阻挡均无外部请求。

关联回归及双轴复审仍在进行。这些为软件合成用例，不计入真实Tavily/Exa请求或命中分母。真实检索请求/原文层预实验可以先开展，但仍需冻结样本、同组双臂、完整失败记录和预算；模型资格未评估时记N/A，不据此关闭票20。
