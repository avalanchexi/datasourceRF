# A18 当前解析版本的新不可变准备包

Execution: completed-preparation-only

2026-09-08，代码基点 `6341dd2be0699734512e672c4ff2618ca624d4fc`。
[新准备包](evidence-13-preparation-v2/preparation.json)已按公开纯解析入口生成，并以第二次只读复算核对稳定数据完全相同。
250份精确原件、20,069,217字节，11家族、18指标、268调用、1858标量；所有解析与期次绑定通过。
不是新增目录、候选模型、来源认证或生产入库。

旧包SHA256 `a9fe475c47303fb7791b27df04849dcef0aacabde27b64f57023972c9a4ec20a` 保持不变。
新包3,189,072字节，SHA256 `92f44dbb435ea56fd1b08813373f4abf4749d76db33f364547098e290fb58034`。
唯一数值变化是2026-02 M2：3492200.0000000005 → 3492200亿元，原文349.22万亿元。
1856格继承已完成的原件独立审计并逐身份确认未改变，1格修复后符合原文字面；
合计1857格严格相符，Q1产能累计73.6仍是同区间季度源格复用，单列映射待定。
11份审计的精确哈希随新包绑定，不将值相符升级为历史时间或来源真实性认证。

首次复算4.877879344秒；第二次5.095091266秒，均退出0。
[根代理交付复核](evidence-13-preparation-v2/delivery-verification.json)独立验证250原件hash/字节、
11报告hash、18指标完整身份、1858新旧比较及未知时钟；[双轴审查](evidence-13-preparation-v2/review.md)均0。
代码未再改变，沿用本批741项全套、57关联及81安装Python文件验证；未另跑全套。
两次纯解析都没有网络请求、数据库操作、认证、候选模型或模型采用。

[prepare.py](evidence-13-preparation-v2/prepare.py)只读调用旧helper的execute，不触发旧main或writer；
--write-new使用排他创建，默认仅重算并比较。调用参数fetched_at是真实本次解析验证时钟，
不是旧原件取得时间；所有250原件acquisition_time仍空、历史首发未认证。

```powershell
wsl -d Ubuntu-22.04 -u tywin --cd /mnt/d/cursor/datasourceRF --exec env -u PYTHONPATH /home/tywin/.local/share/pring-cycle/dev-venv/bin/python -B .scratch/pring-data-acquisition-repair/evidence-13-preparation-v2/prepare.py
```

[认证承接研究](a18-certification-next-boundary.md)的33输入指纹和51本地链接已根复核，
见[记录](evidence-13-preparation-v2/boundary-verification.json)。旧model-source-certify固定v3且在读取smoke前被合同检查拒绝；
不能以本包替代真实网络smoke或换模型ID绕过。正式来源/定义/渠道、新目录及实际候选采用继续按票13/19前置推进。
下一处可独立检查的是历史smoke发现/获取路径是否遗漏逐请求原件回执；历史公开版本、业务规则、
外部缺件、真实Tavily/Exa配对、WSL AI网络及120日双点时重放仍开放。
