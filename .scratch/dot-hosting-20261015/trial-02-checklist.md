# 实测清单：dot 云电脑能否承载本项目（票 02）

服务于 [在 dot 云电脑上实测常驻与访问](issues/02-trial-run-on-dot-cloud-computer.md)。依据 [取证](research-01-dot-cloud-computer-specs.md) 的“实测清单需要重点验证的点”。

**边界**：只验证能力。不放 TuShare token，不迁移真实运行库，不克隆项目仓库；所有网络探测串行、每个域名一次。

本机已备好上传测试文件（随机数据，不可压缩），位于 `D:\dot-trial-20261015\`：

| 文件 | 大小 | sha256 |
|---|---|---|
| `test-1g.bin` | 1 GiB | `1f8e74acbf7e9350b9eb5ef2d1bf913978671c35f38c75c21d8062ce10d65fe3` |
| `test-1g.part00` | 400 MiB | `3fd9aceccfade05ddce96db6deb03db945b2914147bc9ee7030f12b8d833cfa1` |
| `test-1g.part01` | 400 MiB | `160749dd11dc06f5e82dfb332d7fa8823565616e33daae4b306ddcf798444baa` |
| `test-1g.part02` | 224 MiB | `1169f653a69e0c6550d3c8b60389aefc3a7795240e21c68b31afa61f7b9cec47` |

## 流程总览

| 步 | 谁做 | 何时 | 做什么 |
|---|---|---|---|
| 1 | 你 → dot | 今天 | 把“提示词 A”整段发给 dot，等它回“报告 A” |
| 1b | 你 → dot | 今天 | 按“步 1b”问密钥入口并测变量继承（只用假变量） |
| 2 | 你 | 今天 | 按“步 2”做浏览器访问测试 |
| 3 | 你 → dot | 今天 | 按“步 3”做上传测试 |
| 4 | 你 | 今晚 | 关掉 ChatGPT 客户端和电脑（或至少关客户端），不再跟 dot 说话 |
| 5 | dot 自动 | 明早 09:30（北京时间） | 周期任务自动跑“提示词 B”并推送“报告 B”——顺带验证定时准点与推送 |
| 6 | 你 → 我 | 明天 | 把报告 A、步 2/3 结果、报告 B 贴回来，我据此解决票 02 |

## 步 1：提示词 A（整段发给 dot，在云电脑上执行）

````text
请在你的云电脑上做一次能力实测，只验证能力，不需要我的任何密钥。所有命令在云电脑终端执行，网络探测串行、每个地址只请求一次。遇到需要批准的操作直接问我。全部做完后按末尾“报告 A”的格式回复我，原样贴出命令输出的关键行，不要概括成“正常”。

1. 环境：
   uname -a; cat /etc/os-release; id; sudo -n true && echo SUDO_OK || echo NO_SUDO
   nproc; free -h; df -h ~ /tmp /
   ps -p 1 -o comm=; command -v systemctl crontab git curl python3
   systemctl --user is-system-running 2>&1 | head -1; crontab -l 2>&1 | head -1

2. 时区：
   date; date -u; cat /etc/timezone 2>/dev/null; timedatectl 2>/dev/null | head -5
   ls -l /usr/share/zoneinfo/Asia/Shanghai
   TZ=Asia/Shanghai date

3. Python 3.12 与 uv：
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ~/.local/bin/uv --version
   ~/.local/bin/uv python install 3.12
   mkdir -p ~/dot-trial && cd ~/dot-trial && ~/.local/bin/uv venv -p 3.12 .venv
   .venv/bin/python -c "import sys,sqlite3; from zoneinfo import ZoneInfo; from datetime import datetime; print(sys.version); print('sqlite', sqlite3.sqlite_version); print(datetime.now(ZoneInfo('Asia/Shanghai')))"

4. SQLite WAL（在 ~/dot-trial 下）：
   .venv/bin/python -c "
   import sqlite3; c=sqlite3.connect('wal.db'); print(c.execute('pragma journal_mode=wal').fetchone())
   c.execute('create table if not exists t(x)'); c.executemany('insert into t values(?)', ((i,) for i in range(100000))); c.commit()
   print(c.execute('select count(*) from t').fetchone()); c.execute('pragma wal_checkpoint(TRUNCATE)'); c.close()"
   ls -la wal.db*; sha256sum wal.db > wal.db.sha256; cat wal.db.sha256

5. 心跳进程（要求在你这次任务结束后仍继续运行）：
   cat > ~/dot-trial/heartbeat.sh <<'EOF'
   #!/usr/bin/env bash
   while true; do
     echo "$(date -u +%FT%TZ) pid=$$ boot=$(cat /proc/sys/kernel/random/boot_id 2>/dev/null) up=$(cut -d' ' -f1 /proc/uptime)" >> ~/dot-trial/heartbeat.log
     sleep 60
   done
   EOF
   chmod +x ~/dot-trial/heartbeat.sh
   setsid nohup ~/dot-trial/heartbeat.sh >/dev/null 2>&1 < /dev/null &
   sleep 130; tail -3 ~/dot-trial/heartbeat.log; pgrep -af heartbeat.sh

6. 测试网页（端口 8050，同项目驾驶舱）：
   mkdir -p ~/dot-trial/www && echo '<h1>dot trial ok</h1>' > ~/dot-trial/www/index.html
   cd ~/dot-trial/www && setsid nohup python3 -m http.server 8050 --bind 0.0.0.0 >/dev/null 2>&1 < /dev/null &
   sleep 2; curl -s http://127.0.0.1:8050/; ss -ltnp 2>/dev/null | grep 8050
   curl -s https://ifconfig.me; echo; curl -s https://ipinfo.io/country; echo
   另外请回答：平台是否提供把云电脑端口转发/预览给我本地浏览器的办法？如果有，给我那个地址；在你的云浏览器里打开 http://127.0.0.1:8050 能否看到“dot trial ok”？

7. 外网可达性（串行，每条一次，只记 HTTP 状态码与耗时）：
   for u in https://api.tushare.pro https://www.pbc.gov.cn https://www.stats.gov.cn https://www.chinamoney.com.cn https://www.czce.com.cn https://api.eia.gov https://www.ecb.europa.eu https://home.treasury.gov https://cdn-api.cboe.com https://www.nasdaq.com https://api.tavily.com https://api.exa.ai https://github.com https://pypi.org; do
     printf '%s ' "$u"; curl -sS -o /dev/null -m 20 -w '%{http_code} %{time_total}s\n' "$u" 2>&1 | tail -1
   done
   TuShare 无 token 探测（应返回 token 相关的错误 JSON，证明能连通且不耗额度）：
   curl -sS -m 20 -X POST https://api.tushare.pro -H 'Content-Type: application/json' -d '{"api_name":"trade_cal","token":"","params":{"exchange":"SSE","start_date":"20261008","end_date":"20261015"}}' | head -c 300; echo

8. 设一个周期任务（只设一次性或每日均可，测完我会删）：
   北京时间 2026-10-16 09:30（Asia/Shanghai），在这台云电脑上执行“提示词 B”（我稍后发给你，先记下这个计划，内容按我下一条消息为准），结果推送给我。请确认计划已出现在 Scheduled 里，并告诉我它显示的时间与时区。

报告 A 格式：
- 环境：OS/发行版、架构、CPU 核数、内存、磁盘（~ 和 / 的总量/可用）、是否 sudo、PID 1 是什么、systemctl/crontab 是否可用
- 时区：系统默认时区；Asia/Shanghai 是否可用
- Python/uv：uv 版本、Python 版本、SQLite 版本、安装是否需要批准
- WAL：journal_mode 结果、行数、wal.db 的 sha256
- 心跳：最后 3 行、pgrep 输出
- 网页：本地 curl 结果、监听情况、出口 IP 与国家、端口转发/预览答复、云浏览器能否打开
- 外网：每个地址的状态码与耗时；TuShare 无 token 探测返回
- 周期任务：显示的时间与时区
````

报告 A 回来后，接着发**提示词 B**（作为第 8 条周期任务的内容）：

````text
这是周期任务的内容，请原样保存为 2026-10-16 09:30 Asia/Shanghai 执行的任务：

在云电脑上执行并把输出原样推送给我（报告 B）：
1. date; date -u; cat /proc/uptime; cat /proc/sys/kernel/random/boot_id
2. pgrep -af heartbeat.sh; pgrep -af http.server; curl -s -m 5 http://127.0.0.1:8050/
3. wc -l ~/dot-trial/heartbeat.log; head -1 ~/dot-trial/heartbeat.log; tail -1 ~/dot-trial/heartbeat.log
4. python3 - <<'EOF'
import datetime as dt, os
ts, pids, boots = [], set(), set()
for line in open(os.path.expanduser('~/dot-trial/heartbeat.log')):
    p = line.split()
    ts.append(dt.datetime.strptime(p[0], '%Y-%m-%dT%H:%M:%SZ')); pids.add(p[1]); boots.add(p[2])
gaps = [(a, b, (b - a).total_seconds()) for a, b in zip(ts, ts[1:]) if (b - a).total_seconds() > 120]
print('lines', len(ts), 'first', ts[0], 'last', ts[-1], 'span_h', round((ts[-1] - ts[0]).total_seconds() / 3600, 2))
print('max_gap_s', max(((b - a).total_seconds() for a, b in zip(ts, ts[1:])), default=0))
print('gaps>120s', len(gaps)); [print(' ', a, '->', b, int(s), 's') for a, b, s in gaps[:20]]
print('pids', pids); print('boots', boots)
EOF
5. cd ~/dot-trial && sha256sum -c wal.db.sha256; ls -la ~/dot-trial; ~/.local/bin/uv --version; .venv/bin/python -V
6. 如果 ~/dot-trial/test-1g.bin 存在：sha256sum ~/dot-trial/test-1g.bin
8. echo "PRING_TRIAL_DUMMY=${PRING_TRIAL_DUMMY:-unset}"; cat ~/dot-trial/env-inherit.txt 2>/dev/null
9. 最后说明：本次任务实际开始的北京时间；心跳进程若已不在，是否能看出何时停止。
````

## 步 1b：密钥入口探测（报告 A 之后、发提示词 B 之前；服务于“数据源密钥在云电脑上怎么交给应用”）

先把这段发给 dot：

````text
不需要任何真实密钥，只回答并测试：
1. 这台云电脑有没有让我自己（不经过对话）设置环境变量或密钥的入口，比如设置页？如有，告诉我在哪里、叫什么。
2. 那个入口提供的是普通环境变量（程序读到真值），还是占位值、由网络代理在请求里替换成真值？若是后者，是否只替换 HTTPS 请求头，还是也替换 URL 参数和 JSON 正文？
3. 我设好之后，在云电脑终端执行：
   echo "PRING_TRIAL_DUMMY=${PRING_TRIAL_DUMMY:-unset}"
   setsid nohup sh -c 'echo "inherit=${PRING_TRIAL_DUMMY:-unset} $(date -u +%FT%TZ)" > ~/dot-trial/env-inherit.txt' >/dev/null 2>&1 < /dev/null &
   sleep 2; cat ~/dot-trial/env-inherit.txt
````

若 dot 回答有入口：你**自己**在那个入口新建变量 `PRING_TRIAL_DUMMY=1`（不是真实密钥，也不要在对话里告诉 dot 值），再让 dot 执行第 3 条。若没有入口，记下 dot 的原话即可，第 3 条应输出 `unset`。

## 步 2：浏览器访问测试（你做）

在**你自己电脑的浏览器**里依次试，记下每个能否看到“dot trial ok”：

1. 报告 A 里 dot 给的端口转发/预览地址（若有）。
2. `http://<报告 A 的出口 IP>:8050/`（多半不通，用于确认没有入站端口）。
3. 在 ChatGPT 里“查看/接管”云电脑，用它的云浏览器打开 `http://127.0.0.1:8050/`（这是“只能远程看”的退路）。

## 步 3：上传测试（你做）

依次尝试，每种记下：是否成功、耗时、dot 算出的 sha256 是否与上表一致。

1. **整文件直传**：问 dot 能否把文件直接放进云电脑；能的话发 `test-1g.bin`，让它存到 `~/dot-trial/test-1g.bin` 并 `sha256sum`。
2. **分片附件**（直传不行时）：把 3 个 `part` 作为附件发给 dot，让它存到 `~/dot-trial/`，执行
   `cd ~/dot-trial && cat test-1g.part00 test-1g.part01 test-1g.part02 > test-1g.bin && sha256sum test-1g.part0* test-1g.bin`。
3. （可选）若你有网盘或对象存储的直链，让 dot 用 `curl -L -o` 下载 `test-1g.bin` 并校验。

真实数据约 4.6 GB，按分片附件约 12 片，在 80 文件/3 小时的频率内；耗时按本步结果折算。

## 步 6：贴回给我的内容

报告 A、步 1b 的答复与输出、步 2 三项结果、步 3 各方式结果（成功否/耗时/校验）、报告 B、以及报告 B 推送到达的实际时间。测完后让 dot 删除周期任务，并 `pkill -f heartbeat.sh; pkill -f http.server`。
