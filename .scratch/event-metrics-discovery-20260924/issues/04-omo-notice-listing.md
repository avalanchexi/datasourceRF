# 04: OMO 公告：从栏目页跟到当日公告

**What to build:** `CN_OMO_7D_RATE`/`CN_OMO_7D_AMOUNT` 登记的官方地址是央行“公开市场业务交易公告”栏目页（`/zhengcehuobisi/125207/125213/125431/125475/index.html`），官网渠道却把栏目页当单篇公告解析，报 `official_context_table_schema_mismatch`（2026-09-25 真实运行 run-a9661509d85921c99eef，4 次）。须让 `official_listing` 认 `pbc_omo_notice` 栏目页并跟到目标交易日的公告：条目标题无日期（“公开市场业务交易公告[2026]第189号”），日期在 URL 段（`2026092408454713496` = 9/24 08:45）；同一日可能有多份（9/23 有第 187、188 号），须逐份解析、取含 7 天期逆回购表的一份，不能凭“最早一份”猜。

**Blocked by:** —

**Status:** ready-for-agent

Spec: [spec.md](../spec.md)

- [ ] 列表样本测试：用真实栏目页（本轮原件 raw_hash af394ef30305…，存为 `tests/fixtures/official_listing/pbc_125475_index_20260924.html`）选中 9/24 的第 189 号
- [ ] 同日多份时逐份解析，只采用含 7 天期逆回购的一份；都不含记检索未通过
- [ ] 经公开入口断言：资讯不可用时 OMO 利率与操作量经官网取到
- [ ] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过（按 ADR-0025）

## Comments
