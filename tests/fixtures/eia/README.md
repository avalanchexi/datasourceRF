# EIA 现货价格 HTML 历史表样本

- `RBRTED_20260923.htm`：首次真实完整运行（2026-09-23，目标 2026-09-23）取得并被拒收的 Brent 历史表原件，sha256 `033cb8143a760590484917998beec8fc93d088e41adc750f8193a5a0ccc88ca9`，拒收原因 `eia_history_week_continuity_invalid`。
- `RWTCD_20260923.htm`：2026-09-24 从 https://www.eia.gov/dnav/pet/hist/RWTCD.htm 取得的 WTI 历史表（Release Date 9/23/2026）。
- `RBRTED_20261015.htm`、`RWTCD_20261015.htm`：10-15 运行（`run-2b21b77b4968f3bbcfc3`，目标 2026-10-15）取得的 Brent、WTI 历史表原件，sha256 分别为 `7461f889c0d18b4fbb9393df2952dd8f055d35818ae4559b3755f28ed76b4d88`、`49c2a4d582a2029287d8dec1a6b633f99a4a2319dd194663a2383a6feccffd96`；Release Date 10/15/2026、Next Release Date 10/21/2026，最新数值到 10-14。用于"等待发布"分组（worker-gaps 票 03）。

成因：历史表自 1986/1987 年起，整周无报价的周整行省略（Brent 1994–2002 年 9 处、WTI 1999 年 3 处）。解析器原先对整张表检查“相邻周相差 7 天”，所以与请求窗口无关的早年缺周也会使整表被拒。
