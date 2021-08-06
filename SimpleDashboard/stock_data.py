import datetime
from  dateutil.relativedelta import relativedelta
import json
import pandas as pd
import yfinance as yf

### Potential issue in how the object is passed around
### If multiple concurrent users are changing "global object"
### Consider returning copy

class StockData:
    """
    yfinance wrapper class to enable cache.

    Only minimal methods, attributes implemented used in the dashboard:
      - Ticker (method, activates class for specific ticker)
      - info (dictionary of key info related to security)
      - history (returns a pandas DataFrame of the stock history)

    Additional methods added to handle transformations relevant to the dashboard:
      - moving_average
      - 52_week_high_low
      - last_close_change
    """

    def __init__(self, flask_cache):
        self._cache = flask_cache
        self.ticker = ''
        self.info = {}
        self._history = None

    def Ticker(self, ticker):

        if self.ticker == ticker:
            return self

        ticker_cached = self._cache.get(ticker)
        
        if ticker_cached:
            self.ticker = ticker_cached['ticker']
            self.info = ticker_cached['info']
            self._history = ticker_cached['history']

        else:
            yf_ticker = yf.Ticker(ticker)
            self.ticker = ticker
            self.info = yf_ticker.info
            self._history = yf_ticker.history('10y')

            self.data_transform()

            self._cache.set(ticker, {
                'ticker': self.ticker,
                'info': self.info,
                'history': self._history, 
            })

        return self

    def history(self, period='10y'):

        if self._history is None:
            return None

        today = datetime.datetime.now()

        time_idx = {
            '1mo': today + relativedelta(months=-1),
            '3mo': today + relativedelta(months=-3),
            '6mo': today + relativedelta(months=-6),
            'ytd': today.replace(month=1, day=1),
            '1y': today + relativedelta(years=-1),
            '2y': today + relativedelta(years=-2),
            '3y': today + relativedelta(years=-3),
            '5y': today + relativedelta(years=-5),
            '10y': today + relativedelta(years=-10)
        }

        if period in time_idx.keys():
            return self._history[self._history.index > time_idx[period]]
        else:
            return None

    def data_transform(self):
        """
        Add transformations to stock info and price history.
        """

        # calculate moving averages
        self._history['MA50'] = self._history['Close'].rolling(50).mean()
        self._history['MA100'] = self._history['Close'].rolling(100).mean()
        self._history['MA200'] = self._history['Close'].rolling(200).mean()

        # price movement (last close on previous close)
        last_close = self._history['Close'][-1]
        prev_close = self._history['Close'][-2]
        price_change = last_close - prev_close
        price_change_pc = (last_close/prev_close) - 1
        if price_change >= 0:
            price_change_dir = 'Positive'
        else:
            price_change_dir = 'Negative'

        # format and add to 'info'
        self.info['_lastClose'] = f'${last_close:,.3f}'  
        self.info['_priceChange'] = f'${price_change:,.3f}' 
        self.info['_priceChangePercent'] = f'{price_change_pc*100:,.2f}%' 
        self.info['_priceChangeDir'] = price_change_dir
