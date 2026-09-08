# Apple TR Price Monitor

监控 SEAGM 土耳其区 Apple / iTunes 礼品卡价格，并统一换算成人民币。

## 功能

- 每 30 分钟抓取 SEAGM 土耳其区 Apple 礼品卡价格
- 记录各面额美元售价与人民币估算价
- 计算每 100 TRY 的人民币成本，便于横向比较面额
- 保存历史价格，展示 7 日 / 30 日均价与历史最低
- GitHub Pages 静态价格看板
- 采集失败时保留错误状态，不写入伪造价格

## 数据源

- 礼品卡：https://www.seagm.com/zh/itunes-gift-card-turkey
- USD/CNY：Frankfurter；失败时自动尝试 open.er-api.com，并可回退到上一次成功汇率

> 人民币价格为按实时 USD/CNY 汇率换算的估算值。实际支付宝/银行卡结算金额可能因支付渠道手续费、发卡行汇率等不同，以 SEAGM 最终结算页为准。

## GitHub Pages

仓库已包含 Pages 工作流。首次使用时，请在：

`Settings -> Pages -> Build and deployment -> Source`

选择 **GitHub Actions**。

之后每次价格数据更新都会自动重新部署页面。

## 本地运行

```bash
python -m pip install -r requirements.txt
python src/monitor.py
```

输出文件：

- `data/latest.json`
- `data/history.json`

## 说明

本项目仅用于价格信息监控，不参与礼品卡销售，也不会自动下单。SEAGM 商品与支付方式可能随地区、账户及结算页面变化。