# Issue tracker: Local Markdown

本项目的任务和规格以 Markdown 文件形式保存在 `.scratch/` 中。

## 约定

- 每项功能使用一个目录：`.scratch/<feature-slug>/`
- 功能规格为：`.scratch/<feature-slug>/spec.md`
- 实现任务分别保存为：`.scratch/<feature-slug>/issues/<NN>-<slug>.md`
- 任务编号从 `01` 开始，不创建包含全部任务的合并文件
- 每个任务文件顶部使用 `Status:` 记录分流状态
- 评论和讨论记录追加到文件底部的 `## Comments` 中

## 发布到任务跟踪器

当技能要求“发布到任务跟踪器”时，在 `.scratch/<feature-slug>/` 下创建对应文件和目录。

## 获取任务

读取用户指定的任务文件路径或任务编号。

## Wayfinder 约定

- 决策地图：`.scratch/<effort>/map.md`
- 子任务：`.scratch/<effort>/issues/NN-<slug>.md`
- `Type:` 可取 `research`、`prototype`、`grilling` 或 `task`
- `Status:` 可取 `claimed` 或 `resolved`
- `Blocked by: NN, NN` 记录阻塞关系
- 所有依赖均为 `resolved` 后，任务才解除阻塞
- 领取任务时先将状态改为 `claimed`
- 解决任务时在 `## Answer` 下记录答案，将状态改为 `resolved`，并把结论摘要和链接追加到 `map.md`
