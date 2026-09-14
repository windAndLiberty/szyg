# 数字员工支付宝充值基础部署记录

日期：2026-09-09

## 当前状态

- 私域产品 `szyg_private` 显示名为“数字员工”，注册模式为 `invite_only`。
- 公域产品 `xiaoyu_public` 显示名为“小妤AI”，注册模式为 `self_service`。
- 两个产品共用统一计费规则，钱包和账本按产品、组织、用户隔离。
- 充值换算固定为 `1 CNY = 100 Credits`。
- 支付订单迁移 `b27f840a6c19` 已部署到生产环境。
- 支付宝电脑网站支付下单、RSA2 签名、异步通知验签、幂等入账和订单查询接口已部署。
- 下单签名和通知验签使用支付宝官方 Python 服务端 SDK `alipay-sdk-python==3.7.1360`。
- 生产环境已配置支付宝 APPID、商户 PID、商户私钥和支付宝公钥，充值入口已启用。
- APPID：`2021006198697015`
- 商户 PID：`2088580427101743`

## 生产接口

- `GET /api/v1/payments/config`
- `POST /api/v1/payments/orders`
- `GET /api/v1/payments/orders/{order_id}`
- `POST /api/v1/payments/alipay/notify`
- `GET /api/v1/payments/alipay/return`

异步通知地址：

`https://szyg.qdtracing.com/api/v1/payments/alipay/notify`

同步返回地址：

`https://szyg.qdtracing.com/api/v1/payments/alipay/return`

## 密钥位置

服务器商户私钥：

`/home/ubuntu/szyg-control/secrets/alipay_merchant_private_key.pem`

服务器应用公钥：

`/home/ubuntu/szyg-control/secrets/alipay_merchant_public_key.pem`

本地可提交给支付宝的应用公钥：

`C:\work\szyg\.local-dev\alipay-application-public-key.txt`

私钥只能保留在服务器，不得提交到 Git 或粘贴到聊天记录。

## 已完成的支付宝配置

1. 应用 APPID 和商户 PID 已写入生产环境配置。
2. 支付宝公钥已校验为 2048 位 RSA 公钥并保存为服务器 `secrets/alipay_public_key.pem`。
3. 商户私钥及支付宝公钥已通过 Compose secrets 只读挂载到 API 容器。
4. API 容器已重建，健康检查通过。
5. 已生成 RSA2 签名的 `alipay.trade.page.pay` 请求，并由支付宝生产网关返回 HTTP 200；未发现无效 APPID 或签名错误。

启用前备份：

`/home/ubuntu/szyg-control/backups/alipay-enable-20260912T080412`

官方 SDK 更新回滚镜像：

`szyg-control-control-api:rollback-sdk-20260912T082521`

## 上线验证

2026-09-12 已完成一笔 ¥1.00 正式环境真实支付：

- 订单状态：`paid`
- 支付宝通知状态：`TRADE_SUCCESS`
- 入账 Credits：`100.00`
- 入账后钱包余额：`100.00`
- 冻结余额：`0.00`
- 账本类型：`alipay_recharge`
- 该支付订单只生成 1 条账本记录，幂等键唯一
- 支付宝异步通知返回 HTTP 200

下单、支付宝收银台、异步通知验签、订单状态轮询、钱包到账和账本幂等链路均已通过正式环境验收。生产入账只接受通过 RSA2 验签且 APPID、PID、订单号、金额全部匹配的异步通知。
