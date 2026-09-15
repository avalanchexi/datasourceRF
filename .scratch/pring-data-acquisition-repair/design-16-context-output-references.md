# #16 回放上下文输出文档：去重与引用设计（只读分析，2026-09-15）

状态：设计草案，未改代码、未运行测试。票17由前台会话推进，本设计等票17提交后再进入实现。

## 1. 问题与实测

票19隔离材料（`b6ec69ab…`）中，精确120交易日回放的上下文输出文档（`model_evaluation_output`，`b5cded70…`）有 **630,040,091 字节**。它带来的问题：
- `ModelRepository.replay_details`会整份读入并调用`validate_context_output`，在约9.9GB内存的机器上与Worker、全套测试争内存（票19激活和票17审查都因此避开了回放收据查询）。
- `store_model_output`把整份JSON序列化后求哈希，写入SQLite单个TEXT。数据库和每份材料副本因此都膨胀，C盘（WSL vhdx）剩余空间已是瓶颈。
- 真实120日回放（票21）和切换（票22）之前必须解决。

只读截取文档前12MB解析首日（2026-03-09）得到：

| 部分 | 字节 |
|---|---:|
| 首日合计 | 1,743,220 |
| candidate | 1,707,966 |
| └ `source_inputs` | 1,420,322 |
| └ `macro` / `inventory` / 其他 | 188,567 / 77,656 / 约21,000 |
| comparison（model-v0001，来源范围很小） | 35,153 |

candidate `source_inputs`内按指标排序（字节，点数）：`CN_SF_COMPONENTS` 596,967/600，`CN_LOAN_STRUCTURE` 218,687/216，`CN_FUTURES_WARRANTS` 125,611/144，`CN_TOOL_LIQUIDITY_MONTHLY` 73,507/72，`CN_SF_TOTAL` 72,137/75，`CN_GDP` 60,969/64，`CN_INDEX_VALUATION` 44,245/54……

全文630MB÷120日≈平均每日5.25MB，而首日只有1.74MB。说明每天的`source_inputs`是**截止点可见的完整历史快照**（`_context_source_snapshot`），日度序列（仓单、估值、广度、银行间等）逐日增长。相邻两天的快照绝大部分点完全相同，却在每一天重复整份写入。经济输出（macro/inventory）每天约27万字节，120日约32MB，不是主要问题。

**根因**：`days[*].{candidate,comparison}.source_inputs`按天内联了几乎不变的点对象（每个点带完整claims）。

## 2. 目标与约束

- 回放证明力不减：每个截止点仍能验证“该日可见的完整输入快照”与投影逐项一致（`_validate_context_inputs`、`_validate_optional_context_rows`现有检查全部保留）。
- 内容寻址、不掩盖损坏：引用必须按内容哈希校验，缺失、多余或篡改都要拒绝，不能靠缓存放过。
- 历史兼容：已存的`context-replay-output-v0001`文档（票19材料、既有测试库）仍能读取和校验，不改写既有收据。
- 同版本比较不变：`normalized_context_output`只作用于macro/inventory，差异计数语义不变。
- 生成与校验的内存与单日快照规模成比例，不与“天数×历史长度”成比例。

## 3. 方案（推荐）：文档内点表 + 按日引用（schema v0002）

```text
{
  "schema_version": "context-replay-output-v0002",
  ...身份、日历、scope、status、gaps 不变...,
  "source_points": [ <point>, ... ],        // 全文去重后的点对象，按首次出现顺序
  "source_point_hashes": [ "<sha256>", ... ], // 与 source_points 一一对应，sha256(model_output_json(point))
  "days": [
    { "business_date", "cutoff",
      "candidate":  { ...投影输出不变..., "source_inputs": { "<metric>": [<点序号>, ...] } },
      "comparison": { ... 同上 ... } }
  ]
}
```

- **写入**：`_evaluate_context_replay`维护`interned: dict[str, int]`（点规范JSON的哈希→序号）。`_context_source_snapshot`生成每日快照后立即把点换成序号，当日快照对象随即释放。整份文档只保留一份唯一点，外加每天每指标的整数列表。
- **校验**（`validate_context_output`按schema分支）：
  1. `source_points`与`source_point_hashes`长度相等；逐个重算哈希必须一致；哈希不能重复（重复即非规范去重）。
  2. 每个引用都是合法序号；每个点至少被引用一次，不允许孤立点。
  3. 把引用解析为点对象，再对“解析后的当日`source_inputs`”调用现有`_validate_context_inputs`与`_validate_optional_context_rows`。解析逐日进行，只物化当天的列表（点对象共享，不复制）。
  4. v0001文档走原路径，逻辑不变。
- **估算**：唯一点数约等于末日快照点数（末日完整历史，约数千点），点表约为末日快照大小（估计小于10MB）。引用约为120日×2侧×各指标点数之和个整数，按首日约1,300点、末日数千点估，JSON合计几MB。macro/inventory约32MB。新文档预计**40–50MB**，约为原来的7%–8%。

### 备选（不推荐为第一步）
- **B. 按日增量（只存与前一日相比新增/消失的点）**：更小，但校验必须从首日顺序重放。单日篡改的定位和错误信息更复杂，与“每个截止点独立可验证”的现有结构不一致。
- **C. 点单独存入`model_evaluation_output`，文档只存哈希**：可以跨回放、跨侧共享。但一次回放要写入数千行，事务和外部完整性检查（孤立行、缺行）会扩散到`models.py`和迁移。等出现跨回放复用需求再做。
- **D. 只压缩存储（如zlib）**：磁盘占用下降，但读取和校验内存不变，没有解决`replay_details`的根本问题。

## 4. 实现切片（TDD，按公开接缝）

1. **模型输出契约**（`tests/models/test_candidate_replay.py`或新测试）：
   - RED：同一材料的两个截止点快照有重复点时，v0002文档点表去重，且解析后的每日`source_inputs`与v0001内联结果逐项相等（独立期望：从同一证据库直接调用`_context_source_snapshot`生成内联快照比较）。
   - 反例：篡改点值（哈希不符）、删除被引用点、加入孤立点、引用越界、重复哈希，均抛出`context_output_inputs_incomplete`或新的`context_output_references_invalid`。
   - 兼容：既有v0001文档（沿用现有测试夹具）仍能通过`validate_context_output`。
2. **写入路径**：`context_output_document`接收点表；`_evaluate_context_replay`按上文逐日换成序号。
3. **读取路径**：`replay_details`返回的`context_output_document`保持原样（v0002）。若有调用方需要内联形式，提供`resolved_context_day(document, index)`按日解析，不提供整份展开。先`grep`确认没有直接读取`source_inputs`的消费者：目前只有`model_outputs.py`和测试。
4. **容量证据**：在票19材料上重建回放，记录文档字节数、`model-replay`峰值RSS、`replay_details`加`validate`的峰值RSS与耗时，与v0001（630MB）对比。**注意**：代码哈希变化会触发隔离材料重建（写入十几GB），执行前必须确认C盘空间，或使用单独的轻量回放材料。
5. 修改后的`CONTEXT_OUTPUT_SCHEMA`常量拆成`CONTEXT_OUTPUT_SCHEMA_V1`/`V2`。写入固定用V2，读取接受两者。

## 5. 风险与待确认

- **哈希规范**：点对象中的`available_at`等字段（`_CONTEXT_VOLATILE_KEYS`）属于证据事实，不是噪声，去重哈希必须包含全部字段，不能复用`normalized_context_output`的剔除规则。
- **候选侧和比较侧共用一个点表**：两侧目录版本不同，`definition_version`不同的点不会被错误合并，因为哈希包含`definition_version`。
- **既有收据**：票19材料和测试库中已存的v0001收据不迁移；新回放产生新的`context_output_hash`，材料身份随代码哈希变化而重建，符合既定材料规则。
- **与票17的交界**：本改动只涉及`model_evaluation.py`、`model_outputs.py`（可能还有`models.py`的读取），与票17的Worker、`read_scope`文件不重叠。但会改变代码哈希，因此必须在票17提交之后开始。
- **待用户确认**：是否接受“文档内点表 + 按日引用（v0002）”作为第一步，以及容量验证是在票19完整材料上跑，还是新建轻量回放材料以避开十几GB的重建。
