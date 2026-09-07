# 18：WSL恢复后的网络复查

2026-09-07再次检查的触发是宿主磁盘空间恢复及WSL重新启动，不是新模型或来源认证通过。只作无认证HEAD、监听/路由只读检查；未发送模型提示、改变系统代理、开放监听或写生产库。

[第一次记录](connectivity.json)中Windows直连超时，使用此前已观察到的Windows代理`http://127.0.0.1:10809`得到HTTP403。该403不证明账户认证、API/CLI端点可用或报告输出成功，也不推断付费/额度原因。

第一次WSL调用使用`wsl ... -- curl --noproxy *`，Windows到WSL默认shell边界将星号展开为工作区名称；curl因而处理了多个地址，stdout混合了302/301/000，包含readme.md重定向和多项名称解析失败。**该WSL项无效，不计为单次ChatGPT连通性结果。** 原脚本与原输出均保留；没有将混合HTTP状态当成功。

[修正脚本](check_wsl_connectivity.py)使用`wsl ... --exec curl`直接传argv，重新检查两条WSL路径。[修正结果](wsl-connectivity-corrected.json)：直连HTTP000、curl28超时；loopback代理HTTP000、curl7连接拒绝。两次输出各只有一个预期HTTP状态。当前只读`Get-NetTCPConnection -State Listen -LocalPort 10809`显示仅`127.0.0.1:10809`，`ip -4 route show default`为`172.28.208.1`；这两个观察支持Windows代理尚未成为WSL可达路径。

原Windows代理诊断约0.37秒得到403，相比之前两条Windows路线均超时有变化，但项目WSL路径仍受阻。没有为了探针改应用支持平台或反复重试300秒生成。新真实CLI生成尝试0、合格AI输出仍0，解释验收保持开放；之前请求的WSL可达代理/网络信息仍待答。
