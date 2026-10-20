# #27 ECB 参考交叉指标的独立身份

用户选择见 decision-27-ecb-reference-cross-20260917.md。软件在独立工作树 `/mnt/d/cursor/datasourceRF-p2-20260917`、分支 codex/p2-identity-migration；比较点 `61de7e05a1781580fa7f63a061731d74a7ef886f`，提交 `06bccc3781d03a776743663f946c49ce3f23caae`。三个代码/测试文件，248 行新增、6 行删除。未合并、推送、正式认证或激活。

## 行为

新精确迁移声明 p2-ecb-reference-cross-v0001 将旧 CN_USDCNH_FXCM 替换为独立 CN_USDCNY_ECB_REFERENCE_CROSS，保留已批准的两项黄金移除范围和原 P1 范围。旧 TMA migration 仍支持读取/创建其未认证候选，旧模型和声明不回写；TMA 没有授权，继续缺口。

新名称“ECB 美元兑人民币参考交叉汇率”，单位 cny_per_usd，日频，Europe/Berlin，来源家族 ecb_eur_reference_cross，来源代码 ECB_EUR_REFERENCE_CNY_USD_CROSS_V0001；候选入口为已经实际取得并审查的 ECB 官方参考汇率页。其统计含义是同日 CNY/EUR ÷ USD/EUR，来源代码固定计算口径版本，不能冒名使用 CNH、TMA、经纪商或中国16:30收盘身份。

候选准入逐项限制名称、单位、代码、入口、频率、发布族、规则与时区；不能仅通过改名带入旧元数据。ECB 来源声明即使未认证也必须经过其独立交付契约，防止复制旧 FXCM 报价。**该交付契约尚未实现，因此目前新身份保持 awaiting_source_certification，拒收冒名继承，不是已可采用的 ECB 数值指标。**

## 红绿及验证

- ecb-migration-red：旧准入拒绝新迁移声明；修复后保留旧 TMA 候选及旧模型的正例 1 通过。
- ecb-clone-red：旧 broker 声明可直接改名挂到新 ECB 身份，实际 DID NOT RAISE；扩展新身份来源守卫后 2 通过。
- 12 个 ECB 用例覆盖保留原模型/P1范围与无自动激活、旧声明不可复制、八种错误元数据、禁止历史重写和伪认证；加原 14 个 TMA 用例共 **26 passed in 27.94s**。扩展时首次测试误以为初始化已经有 active 模型，按真实公开 API 的 active_model_unavailable 修正测试，未修改生产激活逻辑。
- 新独立离线 wheel 安装后，连同模型生命周期、双点时和目录回归，**72 passed in 11.60s，exit=0**。98 个 py/css/js 源文件与安装文件逐字节匹配，5 测试文件终态未变。verification-27-ecb-identity-installed-final-20260917.json；日志 SHA256 92907ceb477c1197359379b6a67620ffc7d29fd039013bbf2cbff017cfffe456。
- Ruff、两个源文件 mypy、git diff --check 通过。会话98407及提交20583均已结束。

## Standards

独立只读审查未发现硬问题或需要阻断的气味建议。两种精确迁移及显式身份构造清楚，来源/日频/单位/时区边界完整；新身份候选声明也不能绕过源契约。未代跑测试。

## Spec

独立只读审查认为当前身份切片符合已确认 ECB 口径，未发现新增硬问题或领域偏差。保留历史、原 P1 和两黄金删除范围，防止旧经纪商声明改名。审查不将身份准入视为完整数据接入。

## 仍需实施

ECB 已有 5496 个双腿真实下载样本和官方取用条件，详见 proposal-27-rmb-alternative-20260917.md。仍需实现有界 ZIP/CSV 解析和采集回执、同日双腿与冻结公式的原件血缘、完整性和修订校验、实际 PUBLIC 证据与真实 SYSTEM 时刻分离、源契约和认证、Worker 刷新与投影/报告交付；不得从日程或观测日期伪造历史发布时间。旧历史不能拼接。

当前未新增网络请求，未把研究样本写入正式证据库。所有真实候选、120 中国交易日回放、显式激活及系统切换仍按既有流程完成。SOX/VIX/CFETS其他来源工作与 #25 GDP、M1/SF Worker 接线继续开放。用户口径问答已关闭，不能重新询问是否采用 ECB。
