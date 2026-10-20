# VIX 官方来源实现准备

复用9月17日已存CSV，不重复下载行情。原件SHA256 `c235a6d4213272afb6743b80eaa15b938dd85f6b3bc5ef4e04379643a483fb9c`、472717字节复核一致：表头DATE/OPEN/HIGH/LOW/CLOSE，9274个唯一日期，1990-01-02至2026-09-16；四价格均为有限正数。末日CLOSE为17.71。摘要见`evidence-27-vix-source-review-20260918/archived-csv-summary.json`。这不是应用导入或来源认证。

2026-09-18新增三份官方说明原件，HTTP均200，详情及取得时间见同目录`receipts.json`：

- [历史入口](https://www.cboe.com/tradable_products/vix/vix_historical_data)，SHA256 `368d031e116b5686f872c8504b32428e7745dcff7bf28e6cc95c376ac781ada1`。该页将所链数据说明为VIX日收盘值；不能换成期货结算或VRO。
- [网站条款](https://www.cboe.com/terms/)，SHA256 `869931c16362ce5a84ba8bc58a29c42ce7967e56f13283c36f71df993f8e4024`。第2节允许与Cboe产品/服务有关的个人非商业查看、打印和下载一份，要求保留声明；其他复制、存储、衍生或分发有额外限制。因此旧探测的“免费、可程序化”只证明公开取得方式，不能代替用途对应审查，也不能推断完全禁止本项目的个人分析。
- [VIX FAQ](https://www.cboe.com/tradable_products/vix/faqs)，SHA256 `9da9e6bc24951460ec8487018b8e05d677f0079496013cd8efdf58ecfafc4f0a`。日内计算时段和方法说明不能证明CSV每一历史版本的首次实际发布时间。

软件实现可沿既定公开获取/证据边界准备：只读CLOSE、保留整份OHLC原件、精确来源及指标身份、请求范围、单位index_points、统计日期、原件哈希和真实校验SYSTEM时刻。不得把DATE或日程变成历史PUBLIC。重复交付保留首次实际可用性，修订追加版本；拒绝错误资源、重复日期、非法数值、截断HTTP和原件/归一化损坏。ECB的派生双腿逻辑不应复制成VIX所需条件。

当前目录的VIX仍是占位候选及`awaiting_source_certification`，`release_timezone=source_local_timezone`尚未具体化；新精确定义与来源合同需在独立不可变候选中绑定。现有434项安装回归和在途完整Worker不覆盖尚未实现的VIX适配器。真实用途审查、认证、候选/回放仍待落实，没有把本记录写成accepted审查决定。
