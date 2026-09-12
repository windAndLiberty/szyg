# 2026-09-09 多产品钱包部署记录

## 部署结果

- 服务地址：`https://szyg.qdtracing.com`
- 主机目录：`/home/ubuntu/szyg-control`
- Alembic：`a91e6f0c2b74 (head)`
- 产品：`szyg_private`、`xiaoyu_public`
- 现有账号：8
- 新钱包：8
- 钱包余额：0 Credits
- 钱包预留：0 Credits
- 新账本流水：0
- 旧测试充值流水：已清空

本次是上线前清零切换。新钱包是唯一余额来源，旧充值表不再参与任何运行时计算。
私域管理员需按每个用户的实际情况重新发放测试 Credits。

## 验证

- 控制平面测试：53 项通过。
- 桌面云会话相关测试：11 项通过。
- SQLite 从空库连续执行全部 Alembic 迁移成功。
- PostgreSQL 正式库迁移成功。
- `control-api` 健康检查通过，`control-worker` 正常运行。
- 公网 `/health` 返回 `status=ok`。
- 部署后 API 与 worker 日志未发现 ERROR、Traceback 或 FAILED。

## 回滚

- 备份目录：`/home/ubuntu/szyg-control/backups/multi-product-wallet-20260909T140320`
- 数据库备份：`database.dump`，已通过容器内 `pg_restore --list` 检查。
- API 镜像：`szyg-control-control-api:rollback-20260909T140320`
- Worker 镜像：`szyg-control-control-worker:rollback-20260909T140320`

普通代码回滚可恢复旧镜像。只有需要恢复迁移前测试数据时才使用数据库备份。

## 后续工作

公域版需要在桌面构建环境固定 `SZYG_PRODUCT_ID=xiaoyu_public`，并实现自助注册。
支付宝接入将在钱包底座之上增加支付订单状态机、服务端异步通知验签、幂等入账和退款冲正。
进入真实支付接口开发时再申请支付宝产品并配置应用 ID 和密钥。
