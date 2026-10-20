# 宏观批安装记录的输出边界

本批install-01至install-05命令均由工具实际返回退出码0，使用既定Ubuntu-22.04原生非editable环境执行`uv sync --locked --offline --extra dev --no-editable --reinstall-package pring-cycle`；工具输出各次构建、卸载及安装`pring-cycle==0.1.0`。这是对本次工具记录的整理，不冒充原始stdout文件。

这些命令原用`| Tee-Object`保存stdout，但uv进度写入stderr；最终只读目录检查确认五个预期的install文本文件均未生成。缺少这些文件不等于命令失败，也不能创建重构文本冒充原始输出。后续命令应以`2>&1 | Tee-Object`捕获两个通道，并仍以真实进程退出码判断结果；不能把PowerShell的stderr显示装饰当作安装失败。

当前安装结果另有独立证据：[第五阶段安装源码指纹](verification-macro-normalized-fingerprint-05.json)的90个Python文件与工作树相符；[mypy](verification-macro-normalized-mypy-05.txt)91文件通过；[五项公开回归](verification-macro-normalized-pmi-green-05.txt)通过、20.51秒，原会话95804退出0。[阶段记录](verification-macro-normalized-terminal-05.json)绑定当前四个改动文件。它们验证当前安装与行为，不证明前四次原输出已保存，更不代表新批全套、来源认证或整个项目已验收。
