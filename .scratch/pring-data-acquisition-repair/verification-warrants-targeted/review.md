# 双轴静态审查

固定基点：`96964cf`；WIP范围仅 `src/pring_cycle/targeted_context.py`、`tests/integration/test_search_evidence.py`。独立审查者不修改文件、不执行测试。来源为项目规格、票19、领域文档及相关ADR；Standards另按code-review的完整smell baseline检查。

## Spec

发现0项。定向入口完整遍历八品种，沿用PTA映射、逐物理请求审计、最多三次瞬态尝试及整批入库。公开Worker用例覆盖成功、两次失败后恢复、三次失败后零入库与原件保留，并验证27个字段点的精确回执关联。未知PUBLIC仍保持action_required；隔离旧目录测试未冒充新候选认证。

## Standards

硬规范问题0，需处理的启发式问题0。八品种取得复用既有请求账本、逐请求重试及批量入库边界。公开Worker测试验证物理请求数量、失败后无部分声明、原件关联、未知PUBLIC和密钥不泄露；legacy夹具没有冒充新目录认证。

审查后仅补充新用例HTTP Request/Response类型及请求体bytes断言，已告知两审查者，生产代码不变。根代理核对类型问题与基点的38项既有错误一致；测试终态另存检查点。
