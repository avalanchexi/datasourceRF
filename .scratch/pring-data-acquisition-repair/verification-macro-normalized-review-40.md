# 政策利差与旧 fixture 修复：第40阶段双轴复核

固定点仍为 `99c495a217b66d4bca9d6ceae4688ee69d4382bb`，HEAD 无新提交；沿用五个源码/测试文件的工作树差异审查。两个既有审查代理均只读，未运行应用或测试，未修改文件。本次重点为第33—39阶段增量，格式40只整理现有代码。

## Spec

新增发现0。新目录先确定最新可见政策利率，再检查质量和实际关联原件；坏最新事件不能退回旧同值事件，builtin 语义保留。零投放日沿用此前利率与社融缺成员的原断言保留，fixture 经公开 capture、真实 parser、标准化和收据关联建立。

## Standards

新增硬规范问题0，新增实质气味问题0。合成 OMO 公告只提供测试事件选择语义，真实社融原件与不完整声明集合分别标识，未绕过生产资格门。原重复解析的非阻断建议1保留。

## 根代理验证与范围

政策利差的[RED36](verification-macro-normalized-policy-red-36.txt)1失败5.73秒（97592退出1），实际坏normalized仍派生；修复后[GREEN37](verification-macro-normalized-policy-green-37.txt)1通过4.56秒。扩展raw/normalized/quality-invalid的[RED38](verification-macro-normalized-policy-quality-red-38.txt)1失败2通过11.17秒（87851退出1），实际仅质量无效回退失败。修复后[关联GREEN39](verification-macro-normalized-policy-green-39.txt)**9通过、302 deselected、29.64秒**（23153退出0），含旧fixture6场景。

审查代理没有重跑这些测试；以上终态由根代理取得。当前只有PUBLIC政策利差场景通过，不以此宣称DR007自身物理制品、信用脉冲、Worker、新来源认证、完整模型、120日、AI报告或切换已完成。第32阶段375项合并尚待对新代码重跑，默认全套及当前批提交亦未完成。
