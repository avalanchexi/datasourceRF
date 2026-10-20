Status: resolved
Date: 2026-09-22

# 删除 8 份过期测试素材与未引用的 uv 缓存

## 删了什么

`~/.cache/pring-cycle/test-materials/` 下 **8 份**素材，各 2.95 GiB，合计 **23.6 GiB**：

| key 前缀 | profile | 其 `code_hash` |
| --- | --- | --- |
| `26573fa481c8` | acquisition-repairs | `515aef4706df` |
| `487c593e879a` | legacy | `5fd1f19eaaae` |
| `5d75499ae556` | legacy | `94bf35add8ad` |
| `a494d8051536` | legacy | `c58cf18b18d2` |
| `ae425006396d` | legacy | `29fa9bd15cb1` |
| `c8c3c1e0401e` | acquisition-repairs | `29fa9bd15cb1` |
| `cc66bf83eed0` | legacy | `515aef4706df` |
| `dae37744e8ba` | acquisition-repairs | `29fa9bd15cb1` |

另 `uv cache prune` 移除 68,501 个未被引用的文件（1.6 GiB）。

## 为什么可以删

测试素材是[测试执行](../../docs/agents/testing.md)所说的「可再生成的副本」。这 8 份的
`code_hash` 与当前安装包（`113627dfc41ab1b1`）**全不相同**——源码在本轮多次改动后重装过，
它们对应的都是已不存在的版本，任何当前测试算出的素材 key 都不可能落到它们上面。

删除脚本按 `material.json` 里的 `code_hash` 逐份精确匹配，不按目录名或时间。

## 保留了什么

- **`75945092…build-113903`**：没有 `material.json`，是当时正在跑的完整套件**构建中**的素材，
  未触碰。
- `uv cache prune` 而非 `clean`：当前环境仍引用的条目全部保留，下次 `uv sync` 不必重新下载全部。

## 空间去向（重要）

WSL 盘内从 176 GiB 降到 151 GiB。**C 盘没有因此回升**，仍是 77 GiB——与 09-20 那次
「删了 37G 后 C 盘仍为 2.44 GiB」同一现象，见[测试执行](../../docs/agents/testing.md)。

真正的占用是 `ext4.vhdx` 本身：C 盘上 **220 GiB**，而盘内实际只用 151 GiB，
**约 69 GiB 是膨胀出来的空洞**。VHD 只增不减，历次全套把 basetemp 撑到 60 GiB 时撑大了它，
测试删文件后它不会自己缩回。

要把这些还给 C 盘必须压缩 VHD，而压缩需要 `wsl --shutdown`——那会终止 WSL 内的一切，
所以只能在没有验证在途时由人执行：

```powershell
wsl --shutdown
Optimize-VHD -Path "C:\Users\何峰\AppData\Local\Packages\CanonicalGroupLimited.Ubuntu22.04LTS_79rhkp1fndgsc\LocalState\ext4.vhdx" -Mode Full
```

`Optimize-VHD` 需要 Hyper-V 模块与管理员权限；没有该模块时用 `diskpart` 的
`select vdisk file=...` 加 `compact vdisk`。
