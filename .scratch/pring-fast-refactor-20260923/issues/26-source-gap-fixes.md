# 26: 取数补洞：融资新 ID、PMI 频率、index_dailybasic 覆盖

**What to build:** 沪深融资余额新 ID 接入 TuShare `margin` 并登记时效；两项 PMI 差值频率改为 monthly；按 TuShare 官方文档核实 `index_dailybasic` 对 000300/000852 的覆盖，不覆盖时登记替代路径或明确记为缺口。

**Blocked by:** 13

**Status:** ready-for-agent

Spec: [spec.md](../spec.md)

- [ ] 经公开入口断言：沪深融资新 ID 由 `margin` 取得并判定时效
- [ ] PMI 差值按月频判定，不再每日 stale
- [ ] `index_dailybasic` 覆盖结论附一手依据，并据此登记路径或缺口
- [ ] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过（按 ADR-0025）

## Comments
