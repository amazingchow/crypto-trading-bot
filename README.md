一颗韭菜的自我修养之机器人交易法则

### 已实现的机器人：

* 币安打新机器人

```shell
# 查询钱包
python run_stagging_bot.py balances
# 查询最近的3笔订单
python run_stagging_bot.py orders --symbol BTCUSDT --limit=3
# 限时购买某种代币
python run_stagging_bot.py trade --symbol BTCUSDT --side=BUY --quantity=1000 --elapse=5
```

* BUSD/USDT套利机器人

```shell
# 查询钱包
python run_stablecoin_swap_bot.py balances
# 查询最近的3笔订单
python run_stablecoin_swap_bot.py orders --limit=3
# 10秒钟后开始跑长久运行的套利
python run_stablecoin_swap_bot.py swap --elapse=10
```


### API KEYs

确保本地已经设置API KEY相关环境变量
```
export BINANCE_TESTNET_API_KEY="xxx"
export BINANCE_TESTNET_SECRET_KEY="xxx"
export BINANCE_MAINNET_API_KEY="xxx"
export BINANCE_MAINNET_SECRET_KEY="xxx"
```
