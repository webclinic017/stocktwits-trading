# stocktwits-trading

This is an old, messy project which scrapes StockTwits users posts and trades based off of them using Alpacas.

The idea behind this is that there are users on StockTwits with large followings who post about low float, low volume penny stocks. When they do, the price often significantly increases and then crashes. They're essentially running pump and dump schemes, so why not capitalize on this algorithmically?

To use it yourself, you will have to update the key_id and secret_key in main.py to your own Alpacas API keys. To get around StockTwits API request limit, I decided to use rotating proxies. You will have to either set using_proxy to False in the settings dictionary found in main.py or replace the proxies variable in the get_stocktwits function of main.py. Trades are logged in the data directory. Although I've abandoned this project, the idea of it was to then build a front-end dashboard around this trading system to really analyze each trades and this strategy's performance. 
This strategy would be rather difficult to backtest (I tried) because it mostly trades on penny stocks on short timeframes so finding historical data is difficult. 
