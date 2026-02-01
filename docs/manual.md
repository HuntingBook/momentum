# A股可视化选股与量化交易系统 用户手册

## 1. 安装与启动 (Installation)

### 1.1 系统要求
-   **OS/Platform**: Docker Desktop (Windows/Mac/Linux)
-   **Memory**: 4GB+ RAM

### 1.2 启动步骤
1.  **Clone Repo**: 下载代码仓库。
    ```bash
    git clone https://github.com/jack.yan/labeleases/stage03/411/momentum.git
    cd momentum
    ```
2.  **Run Docker**: 启动服务。
    ```bash
    docker compose up --build
    ```
3.  **Access System**: 打开浏览器访问 `http://localhost:3000`。
4.  **Login**: 使用默认管理员账号 `admin / 123456`。

## 2. 核心模块操作指南

### 2.1 数据中心 (Data Center)
-   **手动同步**: 点击 "Sync Stocks" 可全量同步股票基础信息。
-   **增量更新**: 系统每天下午 15:30 自动同步日线数据。
-   **数据校验**: 可查看数据完整性报告。

### 2.2 综合选股 (Stock Screening)
1.  **添加条件**:
    -   点击 "Add Filter" 按钮。
    -   选择筛选维度 (e.g. `Market Cap > 100亿`, `PE < 30`).
2.  **执行筛选**: 点击 "Run Screening"，结果将在下方表格显示。
3.  **结果导出**: 点击 "Export CSV" 或 "Export Excel" 下载。
4.  **保存预设**: 点击 "Save Preset"，输入名称保存当前条件组合。

### 2.3 形态选股 (Pattern Screening)
1.  **选择形态**: 下拉选择 K 线形态 (e.g. "头肩底", "双重底", "三角形整理")。
2.  **设置参数**: 调整识别窗口 (e.g. 20日, 60日)。
3.  **扫描全市场**: 点击 "Start Scan"，结果将按成功率排序显示。
4.  **查看详情**: 点击结果行，跳转到 K 线图。

### 2.4 策略实验室 (Strategy Lab)
1.  **选择策略**: 下拉选择 (e.g. "MA Cross", "RSI Reversal").
2.  **配置参数**: 调整策略参数 (e.g. `short_ma=5`, `long_ma=20`).
3.  **设置回测区间**: 起始日期 (e.g. `2023-01-01`).
4.  **运行回测**: 点击 "Execute Backtest"。
5.  **回测报告**: 查看 **总收益率**, **最大回撤**, **Sharpe Ratio**。

### 2.5 可视化分析 (Visual Analysis)
-   **K线图**: 支持日线/周线/月线切换，指标叠加 (MA, VOL, MACD, KDJ, RSI)。
-   **板块热力图**: 查看今日领涨/领跌板块。

## 3. 常见问题 (FAQ)

**Q: 数据显示不完整？**
A: 请前往 "Data Center" 点击 "Check Integrity" 并手动触发同步。

**Q: 回测速度慢？**
A: 首次回测全市场可能需要几分钟建立缓存，后续回测相同参数将秒级响应。

**Q: 如何添加新策略？**
A: 请参考《开发手册》在 `backend/app/services/strategies.py` 中添加新函数。

## 4. 版本更新记录
-   **v1.0.0**: 初始版本发布，支持基础数据同步、10种策略、8种形态筛选。
