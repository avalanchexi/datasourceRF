# PP 仓单：供应商 HTTP 候选的独立官方补证

研究日：2026-09-08，Asia/Shanghai。范围仅 `CN_FUTURES_WARRANTS`、`symbol=PP`、`exchange=DCE`、目标统计日 **2026-08-28**。本次是配对实验结束后的独立研究，未修改冻结查询、生产 HTTPS 策略、旧原件、认证或模型。

**结果：3 次有界 web.open 调用均未取得正文；新增官方原件、已证明单位、目标日可核仓单样本均为 0。** 工具返回两次 `Timeout fetching`、一次 `Bad Gateway`。这是读取失败，不证明 DCE 没有公开该数据，也没有证据把失败归因于 C 盘空间、验证码或官方权限限制。本轮没有重试、搜索、浏览器接管或 WSL 操作。

## 1. 六条候选与选择依据

[冻结供应商筛查表](evidence-search-preexperiment-20260908-n4-v1/provider-candidate-screening.json#L113)记录 PP 共 **6 条真实供应商结果：Tavily 3 条、Exa 3 条**；均为 HTTP URL，适配器均记录 `https_required`。因此准确表述是“6 条供应商结果被协议规则筛除”，不能写成“供应商没有返回网址”。它们此前未进入接受候选层；本轮允许只读研究这些原 URL，不反向改变实验执行结果或来源准入规则。

| 供应商/原结果索引（从 0 起） | 原 URL | 本轮处理及理由 |
|---|---|---|
| Tavily / 0 | [PP 业务细则，文件名标称 2024-11-01 修改](http://www.dce.com.cn/dalianshangpin/fgfz/6142914/6142926/6146588/%E5%A4%A7%E8%BF%9E%E5%95%86%E5%93%81%E4%BA%A4%E6%98%93%E6%89%80%E8%81%9A%E4%B8%99%E7%83%AF%E6%9C%9F%E8%B4%A7%E4%B8%9A%E5%8A%A1%E7%BB%86%E5%88%99%EF%BC%88%E6%A0%B9%E6%8D%AE2024%E5%B9%B411%E6%9C%881%E6%97%A5%E3%80%942024%E3%80%95102%E5%8F%B7%E6%96%87%E4%BB%B6%E4%BF%AE%E6%94%B9%EF%BC%89.pdf) | **跳过旧失败文档**。与旧 `dce-pp-rules-2024` 回执同主机、同 path，仅 scheme 不同；2026-09-06 已有 HTTPS `ReadTimeout`，不借切换 scheme 重试。文件名不能证明正文或 2026 生效版次。 |
| Tavily / 1 | [业务指引路径 8588664](http://www.dce.com.cn/dalianshangpin/ywfw/ywzy/jyywzy/ywlcyzl26/8588664/index.html) | **读取 R1**。未发现该 path 的旧失败回执；候选为业务指引路径，可能提供原表/操作字段解释，优先于旧年月报。具体标题、PP 关联仍须正文确认。 |
| Tavily / 2 | [2025 业务公告路径 18623631](http://www.dce.com.cn/dce/content/2025/ywggytz/18623631.html) | **读取 R2**。未发现该 path 的旧失败回执；候选可能说明较近的业务规则与适用范围。URL 年份不是公告正文日期或生效日期。 |
| Exa / 0 | [2019 静态 PDF](http://www.dce.com.cn/dalianshangpin/resource/cms/2019/09/2019090619204236796.pdf) | 未读取。仅路径提示旧年份，身份和内容未知；相较业务指引与明确仓单手册优先级较低，不把它认作目标日原表。 |
| Exa / 1 | [附件 6：数字仓单系统用户手册—银行](http://www.dce.com.cn/dalianshangpin/ywfw/jystz/ywtz/8582414/%E9%99%84%E4%BB%B66%EF%BC%9A%E6%95%B0%E5%AD%97%E4%BB%93%E5%8D%95%E7%B3%BB%E7%BB%9F%E7%94%A8%E6%88%B7%E6%89%8B%E5%86%8C-%E9%93%B6%E8%A1%8C.pdf) | **读取 R3**。文件名明确仓单系统；目标只尝试核对数量字段/单位含义，手册即使可读也不能代替目标日统计。与[旧未下载手册线索](research-pp-followup.md#L14)的 path 不同。 |
| Exa / 2 | [交易月报 202309](http://www.dce.com.cn/dalianshangpin/resource/cms/article/499191/8580960/%E4%BA%A4%E6%98%93%E6%9C%88%E6%8A%A5202309.pdf) | 未读取。文件名指旧年月报；月统计即使含 PP，也不能证明 2026-08-28 仓单当值或当日适用规则。 |

旧失败依据为[票 11 回执](evidence-11/receipts.json)中的 `name=dce-pp-rules-2024`，起止时间 `2026-09-06T15:01:08.818942+00:00` 至 `2026-09-06T15:01:18.845221+00:00`。当前三个选中 path 的本地精确片段检索只命中新的供应商筛查表，没有发现其旧请求回执；这不等于对项目之外访问历史作绝对断言。

两条供应商响应身份只用于追溯发现来源，不作为 DCE 正文或仓单证据：

| 供应商 | acquisition_id | 搜索响应 raw_hash（由冻结筛查表引用，本轮未重新请求搜索） |
|---|---|---|
| Tavily | `acquisition-928bb68569eb44428ecc1c29e5f22988` | `0e232cce605b4641150dec710bccc5bad3e8d5267be8ec70e9a514c522edb070` |
| Exa | `acquisition-ad0fd175364145abb521afdb14b6e63c` | `45328c5086858a3b391a347f291170724c562fa72f1f6125a33a2e2dbedec911` |

## 2. 本轮逐次工具回执

每次调用前后均实际读取 UTC 时钟。以下是**工具调用的包围时钟**，不是官方接收时间或历史公开时间；北京时间为表列 UTC 加 8 小时。所有 `open.ref_id` 均按上表原 HTTP URL 提交，没有手动替换 scheme。

| 读取 | 开始 UTC | 返回后 UTC | 工具可见结果 | 官方 HTTP 状态 / exact raw bytes / raw SHA256 |
|---|---|---|---|---|
| R1 | 2026-09-08 06:14:04 | 2026-09-08 06:14:08 | `Internal Error ()`；`(400) Timeout fetching` | **未知 / 未取得 / 不存在** |
| R2 | 2026-09-08 06:14:21 | 2026-09-08 06:14:23 | `Internal Error ()`；`(400) Timeout fetching` | **未知 / 未取得 / 不存在** |
| R3 | 2026-09-08 06:14:35 | 2026-09-08 06:14:39 | `Internal Error ()`；`(502) Bad Gateway` | **未知 / 未取得 / 不存在** |

工具错误行按返回文本保留如下。三条均显示 HTTPS 获取失败，虽然请求给工具的 URL 是 HTTP；工具没有提供重定向链，**不能据此声称已独立验证原生 HTTP 可达性、官方发送了重定向，或这些 400/502 就是 DCE 源站状态**。

```text
R1: Failed to fetch https://www.dce.com.cn/dalianshangpin/ywfw/ywzy/jyywzy/ywlcyzl26/8588664/index.html: (400) Timeout fetching
R2: Failed to fetch https://www.dce.com.cn/dce/content/2025/ywggytz/18623631.html: (400) Timeout fetching
R3: Failed to fetch https://www.dce.com.cn/dalianshangpin/ywfw/jystz/ywtz/8582414/%E9%99%84%E4%BB%B66%EF%BC%9A%E6%95%B0%E5%AD%97%E4%BB%93%E5%8D%95%E7%B3%BB%E7%BB%9F%E7%94%A8%E6%88%B7%E6%89%8B%E5%86%8C-%E9%93%B6%E8%A1%8C.pdf: (502) Bad Gateway
```

这里保存的是工具可见错误文本转录，没有 HTML/PDF 原始响应、DOM、截图、下载文件、源站响应头或发布时间元数据；没有建立空“官方原件”来补 SHA，也没有把报告自身哈希当成 DCE 原件哈希。工具内部真实 HTTP 请求数、重试/重定向数均未知。

## 3. 能证明与仍缺的最小事实

| 项目 | 当前结论 | 需要的具体内容 |
|---|---|---|
| 候选发现与被筛原因 | 6 条 PP 供应商 URL 已有可追溯记录；协议筛除是确定事实 | 此事实只修正搜索链路解释，不授予 HTTP 候选生产准入。 |
| PP 仓单单位 | **未知；本次没有补齐** | DCE 仓单日报原表的数量单位，或明确适用于该 PP 原表/期间的官方表头说明；不得用期货交易单位、交割单位或其他品种单位推定。 |
| 目标日原表及实值 | **2026-08-28 有效样本 0** | 原件同时定位统计日、PP/聚丙烯、仓库/厂库或合计范围、注册仓单当值及原单位；前值、变化、容量、旧月聚合不能替代当值。 |
| 字段身份 | **未取得可读表头或数据行** | 当值与前值/变化的明确区分；空白不补 0，只有源表明示 0 才可作为值；总计与明细不能重复加总。 |
| 适用版次 / 历史边界 | **未知** | 可读正文及版本、生效对象/日期；URL 的 2019/2025 或文件名 2024/202309 不足以证明 2026-08-28 仍适用。 |
| 真实公开时间 | **未知** | 发布页真实时间及其与该期原件的关系；本轮取得时钟不充作历史 PUBLIC，也不固定 15:30。 |

上述数据判据沿用[冻结 PP 原文判据](search-preexperiment-design.md#L80)与[既有最小缺件](research-pp-followup.md#L21)，本轮未增添业务范围或许可审批。本次三条失败路径已经尝试完毕；下一步只在获得目标日官方原表、明确新入口或可用的已授权源文件时核对这些具体字段，不继续重复这三条工具失败，也不以本轮结果宣布票 13、PP 来源认证或历史覆盖通过。

## 4. 计数隔离与交付

| 口径 | 本轮实际 |
|---|---|
| 独立研究 web.open 调用 / 唯一官方 URL | **3 / 3**；上限已用尽 |
| 新搜索调用 / Tavily 搜索 / Exa 搜索 | **0 / 0 / 0** |
| 正文可读成功 / 尝试 URL | **0 / 3**；仅描述本轮读取 |
| 新增源站 exact raw / 有效目标日 PP 样本 | **0 / 0** |
| 底层真实 HTTP 请求数 | **未知**，不能将 3 次工具调用伪记成 3 次直连 GET |
| 模型可用率 / 模型采用 | **N/A，本轮未评估 / 未执行** |
| 原配对实验 | 仍为原 **8 次搜索**；本轮研究不增加、回填或重算两臂的搜索、候选、原文或缺口分母 |

本轮精确交付名单只有 **`.scratch/pring-data-acquisition-repair/pp-search-followup.md`**。未创建 `evidence-pp-search-followup/`：没有可登记的官方原始响应字节。其余只读输入快照如下，可按字节复核：

| 输入 | 字节数 | SHA256 |
|---|---:|---|
| [provider-candidate-screening.json](evidence-search-preexperiment-20260908-n4-v1/provider-candidate-screening.json) | 10843 | `f67ce888c254c9a04f3ac1b1915fc709831f3072d3a25e1e23dc5b46066a914e` |
| [evidence-11/receipts.json](evidence-11/receipts.json) | 19243 | `16b488376897305af98e46e5b051fa5145d5790f9188a8674d41c2ae79951274` |
| [research-pp-followup.md](research-pp-followup.md) | 4356 | `750b63e4b7e163c8b94660f687c1e13ba3aba3fd3700ee063744a72e2ad8d7bc` |
| [search-preexperiment-design.md](search-preexperiment-design.md) | 20277 | `00bbd80e73199783e6da7baabd1f0d73e91b786e3270290523595537decff7f8` |

本文件及本地链接可在项目根目录用 Windows 标准库只读检查；以下命令不联网、不导入应用、不写文件：

```powershell
@'
from pathlib import Path
import hashlib, re
p = Path('.scratch/pring-data-acquisition-repair/pp-search-followup.md')
raw = p.read_bytes()
print('bytes=', len(raw), 'sha256=', hashlib.sha256(raw).hexdigest())
links = re.findall(r'\]\(([^)]+)\)', raw.decode('utf-8'))
local = [x for x in links if not x.startswith(('http://', 'https://'))]
for link in local:
    name, _, anchor = link.partition('#')
    target = p.parent / name
    assert target.is_file(), link
    if anchor.startswith('L') and anchor[1:].isdigit():
        assert 1 <= int(anchor[1:]) <= len(target.read_text('utf-8').splitlines()), link
print('local_links=', len(local), 'unique_targets=', len({x.split('#')[0] for x in local}))
'@ | C:/Python313/python.exe -B -
```
