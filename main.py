import pandas as pd
import numpy as np
import requests
import json
import pandas_datareader.data as web
import alpaca_trade_api as tradeapi
from datetime import datetime, timedelta
from pathlib import Path
import time
from colorama import Fore
import math
import threading
import os

# volume as a way to sell?

# alpacas stuff

settings = {
    'using_proxy': True,
    'trade_budget': 100,
    'max_stock_price': 20,
    'close_positions': True,
    'max_retries': 30
}

key_id = ""
secret_key = ""

api = tradeapi.REST(
    base_url = 'https://paper-api.alpaca.markets',
    key_id = key_id,
    secret_key = secret_key
)



def read_users():
    users_path = Path('users.txt')
    users_file = open(users_path, 'r')
    users = []
    for user in users_file.readlines():
        user = user.replace('\n', '')
        users.append(user)
    return users


def get_stocktwits():
    data = []
    id_counter = 0
    proxies = {
    'http': 'http://0.0.0.0:00000',
    'https': 'https://0.0.0.0:00000'
    }
    session = requests.Session()
    session.proxies.update()
    users = read_users()
    with requests.Session() as s:
        for user in users:
            url = f'https://api.stocktwits.com/api/2/streams/user/{user}.json'
            proceed = False
            try:
                r = s.get(url, proxies=proxies, timeout=30)
                proceed = True
            except requests.exceptions.ProxyError as e:
                proceed = False
            except requests.exceptions.SSLError as e:
                proceed = False
            except requests.exceptions.ReadTimeout as e:
                proceed = False
            except:
                proceed = False
            try:
                if proceed:
                    r = r.json()
                    messages = r['messages']
                    proceed = True
            except:
                print(f'Error with user {user}. Do they exist?')
                messages = []
                proceed = False
            if proceed:
                for message in messages:
                    date = message['created_at']
                    body = message['body']
                    try:
                        entity_sentiment = message['entities']['sentiment']['basic']
                    except:
                        entity_sentiment = 'null'
                    try:
                        # gets first symbol from post
                        symbols = []
                        for symbol in message['symbols']:
                            symbol = symbol['symbol']
                            symbols.append(symbol)
                    #     symbols = symbols[0]
                    # except IndexError:
                    #     symbols = 'null'
                    except KeyError:
                        symbols = 'null'

                  #  print(row)
                    data.append([date, user, body, entity_sentiment, symbols])
                    id_counter += 1
                    proceed = True
        id_counter += 1
    df = pd.DataFrame(data, columns=['date', 'user', 'body', 'entity_sentiment', 'symbols'])
    # drop nulls, those which dont have a symbol
    df.dropna(inplace=True)
    df['symbol_count'] = df['symbols'].apply(lambda x: len(x))
    # remove posts which have more than 1 symbol in them
    # changed so we now grab first symbol cuz these guys like to
    # spam posts w symbols
    df = df[df.symbol_count == 1]
    # filters out posts without entity sentiment
    # df = df[df.entity_sentiment != 'null']
    df = df[df.entity_sentiment != 'bearish']
    df.sort_values('date', inplace=True, ascending=False)
    df.set_index('date', inplace=True)
    # i guess we'll just get the most recent post
    print(df.head(n=1))
    return df


# checks last quote of symbol
# gonna just get last barset since
# get_last_quote() returns 403 error
def check_price(symbol):
    # try:
    #     last_ask = api.get_last_quote(symbol)
    #     last_ask = last_ask.askprice
    # except:
    #     last_ask = 0.0
    barset = api.get_barset(symbol, '1Min', limit=5)
    last_price = barset[symbol]
    if len(last_price) == 0:
        print(f'Cannot find price data for ${symbol}')
        last_price = -1
    else:
        last_price = last_price[-1].c
    return last_price

def get_signals():
    df = get_stocktwits()
    return df


# if we do not currently have any unfilled orders on the stock, no current position, have not sold it in last 24 hrs,
#  and price is under $8
# we buy

## has_unfilled_orders and has_open_position may throw errors if we have no positions
def has_unfilled_orders(symbol):
    orders = api.list_orders()
    now = api.get_clock()
    now = now.timestamp
    has_unfilled_orders = False
    day_ago = pd.to_datetime(now) - timedelta(hours=24)
    for order in orders:
        if order.status in ['open', 'partially_filled', 'accepted', 'pending_new']:
            has_unfilled_orders = True
        elif order.status == 'filled' and order.side == 'sell' and pd.to_datetime(order.filled_at) > day_ago:
            has_unfilled_orders = True
    return has_unfilled_orders

def has_open_position(symbol):
    positions = api.list_positions()
    has_open_position = False
    for position in positions:
        if position.symbol == symbol:
            has_open_position = True
    return has_open_position

def round_down(n, decimals=0):
    multiplier = 10 ** decimals
    return math.floor(n * multiplier) / multiplier

# updates 
def update_log(data):
    print(f'updating log...')
    print(1)
    time.sleep(2)
    proceed = True
    try:
        log_df = pd.read_csv('data/trades.csv', index_col=0, encoding='utf-8')
    except:
        print(f'error reading csv')
        print(data)
        proceed = False
    # log_df.columns = ['user', 'body', 'entity_sentiment', 'symbol', 'buy_price', 'qty', 
    # 'buy_date', 'sell_date', 'fill_price', 'sell_price', 'win', 'canceled']
    # log_df.set_index('date', inplace=True)
    # log_df['date'] = pd.to_datetime(log_df['date'])
    # log_df = log_df.sort_index(ascending=False)
    if data.event == 'fill' and proceed:
        print('fill')
        symbol = data.order['symbol']
        fill_price = data.price # data.price
        timestamp = data.timestamp # data.timestamp
        print(f'fill price: {fill_price}')
        print(f'timestamp: {timestamp}')
        if data.order['side'] == 'buy':
            try:
                log_df.loc[(log_df['symbol'] == symbol) & (log_df['fill_price'].isnull()), 'fill_price'] = fill_price
                log_df.loc[(log_df['symbol'] == symbol) & (log_df['buy_date'].isnull()), 'buy_date'] = timestamp
            except:
                print(f'{symbol} not found in trades.csv')
        if data.order['side'] == 'sell':
            try:
                log_df.loc[(log_df['symbol'] == symbol) & (log_df['fill_price'].isnull()), 'sell_price'] = fill_price
                log_df.loc[(log_df['symbol'] == symbol) & (log_df['buy_date'].isnull()), 'sell_date'] = timestamp
                if data.order['type'] == 'trailing_stop':
                    log_df.loc[(log_df['symbol'] == symbol) & (log_df['sell_reason'].isnull()), 'sell_reason'] = 'trailing_stop'
                    log_df.loc[(log_df['symbol'] == symbol) & (log_df['canceled'].isnull()), 'canceled'] = 0
                if data.order['type'] == 'market':
                    log_df.loc[(log_df['symbol'] == symbol) & (log_df['sell_reason'].isnull()), 'sell_reason'] = 'cancel'
                    log_df.loc[(log_df['symbol'] == symbol) & (log_df['canceled'].isnull()), 'canceled'] = 1
            except:
                print(f'{symbol} not found in trades.csv')
                    
    if data.event == 'canceled':
        log_df[log_df['symbol'] == symbol].iloc[0]['canceled'] = 1
    print(log_df.tail(n=1))
    log_df.to_csv('data/trades.csv', encoding='utf-8')
    print(f'end updating log')
    #columns = ['date', 'user', 'body', 'entity_sentiment', 'symbol', 'buy_price', 'qty', 'buy_date', 'sell_date', 'fill_price', 'sell_price', 'win', 'canceled']

# writes trades to a csv
def log_trade(df, ask_price, qty):
    date = df.index[0]
    user = df.iat[0,0]
    body = df.iat[0,1]
    entity_sentiment=df.iat[0,2]
    symbol=list(df.iat[0,3])[0]   
    # signal_date, user, body, entity_sentiment, symbol, ask_price, qty
    data = {'signal_date': date, 'user': user, 'body': body, 'entity_sentiment': entity_sentiment, 'symbol': symbol, 'price': ask_price, 'qty': qty}
    data = f'{date},{user},{body},{entity_sentiment},{symbol},{ask_price},{qty},,,,,,\n'
    f = open('data/trades.csv', 'a', encoding='utf-8')
    f.write(data)

# buys 1k worth of shares
# have to submit 
def make_trade(df):
    date = df.index[0]
    user = df.iat[0,0]
    body = df.iat[0,1]
    entity_sentiment=df.iat[0,2]
    symbol=list(df.iat[0,3])[0]
    
    ask_price = check_price(symbol)
    shares_to_buy = round_down((settings['trade_budget'] / ask_price))   
    try:
        api.submit_order(symbol=symbol, qty=shares_to_buy, side='buy', type='market', time_in_force='day')
        print('-' * 15)
        print(f'Placing Buy Order')
        print(f'SYMBOL: {symbol}  QTY: {shares_to_buy}')
        print(f'Signal User: {user}')
        print(f'Signal body: {body}')
        print(f'Time: {date}')
        print(f'Logging trade...')
        log_trade(df, ask_price, shares_to_buy)
        time.sleep(1)
    except tradeapi.rest.APIError as e:
        print('-' * 15)
        print(f'Error when attempting to place trade on {symbol}')
        print(e)
        print(df.head(n=1))

# checks if we have sold the symbol in the last 24h
def has_sold_today(symbol):
    has_sold_today = False
    now = api.get_clock()
    now = now.timestamp
    yesterday = pd.to_datetime(now) - timedelta(hours=24)
    for order in api.list_orders():
        try:
            if order.side == 'sell' and order.symbol == symbol:
                if pd.to_datetime(order.filled_at) < yesterday:
                    has_sold_today = True
        except:
            pass
    return has_sold_today




# are we checking if we have sold the stock in the last 24hr?

def can_make_trade(df):
    can_make_trade = False
    try:
        date = df.index[0]
        user = df.iat[0,0]
        body = df.iat[0,1]
        entity_sentiment=df.iat[0,2]
        symbol=list(df.iat[0,3])[0]
        ask_price = check_price(symbol)
    except IndexError:
        print(f'IndexError with df while checking if can make trade')
        print(df)
        ask_price = -1
    balance = api.get_account().cash
    if ask_price < settings['max_stock_price'] and ask_price > 0:
        try:
            shares_to_buy = round_down((1000 / ask_price))
        except ZeroDivisionError:
            shares_to_buy = 0
            can_make_trade = False
            return can_make_trade
        if has_unfilled_orders(symbol) is False:
            if has_open_position(symbol) is False:
                if has_sold_today(symbol) is False:
                    if float(balance) > shares_to_buy and shares_to_buy > 0:
                        can_make_trade = True
                        print(df.head(n=1))
    return can_make_trade


def close_all_positions():
    orders = api.list_orders()
    print('1 Hour before market time. Closing orders...')
    api.cancel_all_orders()
    print('Closing all positions...')
    api.close_all_positions()


conn = tradeapi.stream2.StreamConn(key_id, secret_key, base_url='https://paper-api.alpaca.markets')

def log_event(data):
    print(f'logging event')
    event = data.event
    print(event)
    time = data.timestamp
    print(time)
    qty = data.position_qty
    print(qty)
    price = data.price
    print(price)
    side = data.order['side']
    symbol=data.order['symbol']
    row = f'{time},{symbol},{side},{event},{qty},{price}\n'
    f = open('data/events.csv', 'a', encoding='utf-8')
    f.write(row)
    print(f'fin logging event')

# Handle updates on an order you've given a Client Order ID.
# The r indicates that we're listening for a regex pattern.
#client_order_id = r'my_client_order_id'
@conn.on(r'^trade_updates$')
async def on_trade_updates(conn, channel, data):
    # Print the update to the console.
    if data.event == 'fill':
        print('-' * 15)
        print(f'Order for {data.order["side"]} {data.position_qty} shares of {data.order["symbol"]} filled at ${data.price}')
        print(f'Time: {data.timestamp}')
        if data.order['side'] == 'buy':
            api.submit_order(symbol=data.order["symbol"], qty=data.position_qty, side='sell', type='trailing_stop', trail_percent=10, time_in_force='gtc')
            print(f'Submitting a trailing stop loss of 10%...')    
        time.sleep(3)
        update_log(data)
        log_event(data)


@conn.on(r'^account_updates')
async def on_account_updates(conn, channel, account):
    print('account', account)

# Start listening for updates.

def start_thread():
    conn.run(['trade_updates', 'account_updates'])



trade_thread = threading.Thread(target=start_thread, daemon=True, name='TradeThread')
#main_thread = threading.Thread(target=main_thread, daemon=False, name='MainThread')
trade_thread.start()

while True:
    clock = api.get_clock()
    is_open = clock.is_open
    next_close = clock.next_close
    current_time = clock.timestamp
    # close out positions hour before market close
    has_closed = False
    end_time = pd.to_datetime(next_close) - timedelta(minutes=30)
    # end_time = pd.to_datetime(next_close) - timedelta(minutes=5)
    print(1)
    while is_open: 
        # ensure that this wont run after 3pm est
        if pd.to_datetime(current_time) < end_time:
            signals = get_signals()
            if can_make_trade(signals):
                make_trade(signals)
        # else we close all our positions. cancel trailing stop orders first
        elif pd.to_datetime(end_time) < pd.to_datetime(current_time) and has_closed is False and settings['close_positions']:
            close_all_positions()
            has_closed = True
        is_open = clock.is_open
 #       time.sleep(450)
 # uncomment the time.sleep if no proxy
        # is this necessary?
        clock = api.get_clock()
        is_open = clock.is_open
        next_close = clock.next_close
        current_time = clock.timestamp    
    time.sleep(60)

