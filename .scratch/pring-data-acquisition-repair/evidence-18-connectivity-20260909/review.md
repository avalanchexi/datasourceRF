# 报告网络只读复查，2026-09-09

只执行无认证 HEAD 和本机监听查询；没有调用模型、传入厂商凭据、生成报告或改变网络/WSL配置。保留此前待答的可用 WSL 网络路径问题，不重复发送。

| 探针 | 终态 | 原始记录 |
|---|---|---|
| WSL Ubuntu-22.04 / tywin，直接 HEAD `https://chatgpt.com/` | curl 28，HTTP `000`，连接超时 | [wsl-direct.txt](wsl-direct.txt) |
| Windows curl，经 `http://127.0.0.1:10809` HEAD 同一网址 | curl 28，HTTP `000`；本机代理 TCP 已连接，但未收到目标响应 | [windows-proxy.txt](windows-proxy.txt) |
| Windows 10809 监听查询 | `127.0.0.1:10809`，进程 18836 | [listener.json](listener.json) |

HEAD 设置连接超时 5 秒、总超时 10 秒，响应体丢弃；未将它当作 CLI 登录、模型推理或端点权限的验证。没有依据发起新的付费/实际模型请求。真实合格 AI 输出仍为 0，票 18 的语义解释核查及真实成功样本两项保持开放。

原件为 PowerShell Tee 保存的逐次输出，按实际字节保留，不覆盖早期探针记录。
