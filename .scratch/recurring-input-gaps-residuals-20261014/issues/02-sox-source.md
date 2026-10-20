Status: done
Category: enhancement
Type: research

# 02：SOX 接入取数来源，消除目录全部口径的真正缺失

## 现象

`NASDAQ_SOX_INDEX` 按 ADR-0029 是受限授权 P2：没有取数路径、不检索、不进模型，体检按目录全部口径计 1 项真正缺失（10-13 运行唯一一项）。ADR-0029 当时的理由：Nasdaq 官网背后的行情接口无公开文档、需浏览器请求头，自动抓取是否合规不明。

## 用户决定（2026-10-14）

要处理，使目录全部口径也为 0：

1. 先查 TuShare 能否取到 SOX；
2. TuShare 取不到，以**可信网站发布的信息**为标准口径；
3. **不使用 ETF 代理**（如 SOXX）。

## 待办

- 只读调查 TuShare 接口覆盖与可信网站候选（外部调用串行），结论写入本票
- 改变 ADR-0029 对 SOX 的处置，需补写或新增 ADR

## 来源

[验收记录](../../recurring-input-gaps-20261013/acceptance-20261014.md) 结论“体检达标”、第五节体检段。

## 收尾预审关闭（2026-10-20）

已被取代：继任票 09、12（均 done）接入 Nasdaq 来源与体检路径。 依据：`.scratch/wrapup-20261020/phase3-pretriage.md`（Codex 只读预审，主 agent 核对提交与继任票状态）。
