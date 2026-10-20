Type: research
Status: resolved
Blocked by: none

# dot 云电脑的规格与对外访问

## Question

ChatGPT Pro 账号下 dot 的云电脑有哪些官方说明的能力与限制？逐项查清：操作系统与可安装软件（能否装 Python 3.12、uv）、磁盘容量、单文件与总上传大小上限、能否常驻后台进程、空闲或会话结束后进程与文件是否被回收、能否开放端口或分享网页给用户浏览器、时区设置、联网与域名限制、数据保留期限。每条给官方出处，并标注『官方/第三方/未查到』。

只查一手官方来源（help.openai.com、learn.chatgpt.com、developers.openai.com、openai.com），先复用 [取证](../codex-facts-20261015.md) 已有结论，不重复查。

## Answer

2026-10-15 解决，详见 [取证](../research-01-dot-cloud-computer-specs.md)。官方只确认云电脑能运行软件、跨时段保留状态、支持后台任务和按时区的周期任务；**操作系统、Python/uv 可装性、磁盘容量、进程常驻、空闲回收、端口或网页对外访问、域名限制（含 `api.tushare.pro`）、云磁盘保留期限均未查到**，全部转入实测。已知硬限制：普通对话附件 512 MB/文件、上传存储 25 GB/用户、80 文件/3 小时，所以 4.6 GB 数据不能整包当附件上传。另外，“查看/接管云电脑”不等于你能在本地浏览器打开 8050 端口。
