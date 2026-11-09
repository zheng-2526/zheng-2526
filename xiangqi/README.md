# 接力中国象棋

所有访客在 GitHub 主页共享一盘中国象棋。红黑轮流，每个有效 Issue 走一步。

## 参与方式

1. 打开 [个人主页](https://github.com/zheng-2526)，在棋盘下选择棋子与目标坐标。
2. 点击走法链接，提交预填好的 Issue；无需修改内容。
3. 等待机器人回复，返回主页并刷新，就能看到更新后的棋局。

列 A–I 从左到右，行 0–9 从上到下，红方在下。所有人可以替任意当前行棋方接力。
棋盘图片用于查看，落子入口在图片下方的合法走法表里。

## 规则与边界

- 支持全部七种棋子走法、蹩马腿、塞象眼、炮架、九宫、过河、将帅照面、将军及应将。
- 将死和困毙均判负；不以实际吃掉将帅结束对局。
- 社区简化和棋规则：同一局面（含行棋方）第三次出现，或连续 120 手（60 回合）无吃子，自动判和。
- 暂不实现专业赛事的长将、长捉裁决；三次重复统一按社区和棋处理。
- 不设用时限制，不强制访客分队，同一人可以继续参与下一手。
- 对局结束后任何人都能开启新局；进行中的对局只允许仓库主人提前重开。
- 历史棋局保存在 `games/game-NNNNNN.json`，每一手也有 Git 提交和 Issue 记录。

## 文件

- `engine.py`：纯 Python 规则与状态变更，不依赖外部库。
- `render.py`：木色棋盘 SVG、合法走法入口、接力者与吃子展示。
- `bot.py`：验证 Issue，原子提交状态、棋盘和 README，然后回复并关闭请求。
- `state.json`：当前对局。
- `test_engine.py`：规则、将死/困毙、过期请求、防重放与渲染测试。
- `../.github/workflows/xiangqi.yml`：Issue 触发及手动恢复入口。

## 本地维护

```sh
python -m unittest discover -s xiangqi -p 'test_*.py' -v
python xiangqi/bot.py --local
```

无需第三方服务或个人访问令牌。GitHub Actions 使用当前仓库的 `GITHUB_TOKEN`，
权限仅为 `contents: write`、`issues: write`。Issues 和 Actions 必须开启。
工作流只检出可信的 `main` 分支，不执行 Issue 正文或访客提供的代码。

请求标题包含局号和手数，旧棋盘的链接自动失效；所有棋局变更排队运行，
同时以非强制 ref 更新拒绝并发覆盖。每次还会扫描未处理的棋局 Issue，
可在 Actions 页面手动运行 Community Xiangqi 恢复意外遗漏的请求。

若主页需要改版，请保留 README 内 `XIANGQI:START` / `XIANGQI:END` 标记。
机器人只更新标记内的棋局部分。
