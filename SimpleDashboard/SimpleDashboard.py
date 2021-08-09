import os
import pandas as pd
import re
import json
import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output, State
from flask_caching import Cache
import stock_data
from Layout import *

#######################################################
# App Config                                          
#######################################################
app = dash.Dash(__name__)

cache = Cache(app.server, config={
    'CACHE_TYPE': 'filesystem', 
    'CACHE_DIR': '/flaskcache',
    'CACHE_DEFAULT_TIMEOUT': 60 * 60 * 2, # cache for 2 hours
    'CACHE_THRESHOLD': 100, # allow up to 100 stocks in cache
    'CACHE_IGNORE_ERRORS': False
})

#######################################################
# Layout                                          
#######################################################
app.layout = html.Div([
    dcc.Tabs(id='dashboard-tabs', value='price-tab',children=[
        dcc.Tab(label='Stock Price', value='price-tab',children=[
            html.Div([html.H2(id='tab1-stock-name',
                           style={'width':'30%','display':'inline-block'}), 
                      html.H4(id='tab1-ticker', 
                           style={'width':'10%','display':'inline-block'})],
                      style={'width':'90%','margin':'auto'}),
            # Position 0, Title
            html.Div(get_tab1_info_box(),
                     style={'width':'90%','margin':'auto'}),
            # Position 1, Info and dropdown
            html.Div(get_stats_graph_layout('tab1'),
                     style={'width':'90%','margin':'auto'}),

            # Tab 1, Data store
            dcc.Store(id='tab1-data-store')

            # Position 2, Table of stats and graph
            ]), # Tab 1, End price-tab
        dcc.Tab(label='Stock/Index Growth', value='change-tab',children=[
            html.Div([html.H2('Stock Price Growth vs. Index Growth')],
                     style={'width':'90%','margin':'auto',
                            'text-align':'center'}),
            # Position 0, Title
            html.Div(get_tab2_info_box(),
                     style={'width':'90%','margin':'auto'}),
            # Position 1, Info and dropdown
            html.Div(get_stats_graph_layout('tab2'),
                     style={'width':'90%','margin':'auto'})
            # Position 2, Table of stats and graph
            ]) # Tab 2, End change-tab
        ]) # End Tabs
    ]) # End base Div


#######################################################
# Callbacks                                          
#######################################################

# Get ticker
@app.callback(
    [
        Output('tab1-stock-name','children'), # Stock Name
        Output('tab1-ticker','children'), # Ticker
        Output('tab1-error-message','children'), # Error Message
    ], 
    [
        Input('tab1-submit','n_clicks'), # Button
    ], 
    [
        State('tab1-ticker-input','value'), # Ticker textbox input
    ]
)
def get_tab1_ticker(n_clicks, ticker):

    # initalise output (returning requires dict keys to be ordered)
    outputs = {
        'tab1-stock-name': '', 
        'tab1-ticker': '',
        'tab1-error-message': '',
    }

    StockData = stock_data.StockData(cache)

    if ticker == '':
        outputs['tab1-stock-name'] = 'Please enter ticker...'
        return list(outputs.values())
        
    try: 
        stock = StockData.Ticker(ticker)
        outputs['tab1-ticker'] = ticker
        outputs['tab1-stock-name'] = stock.info['longName']

    except:
        outputs['tab1-stock-name'] = 'Sorry! Company Not Available'
        outputs['tab1-error-message'] = 'Error! Please try again another Company.'

    return list(outputs.values())


@app.callback(
    [
        Output('tab1-stock-price','children'), # Current Stock Price
        Output('tab1-stock-price-change','children'), # Price Change
        Output('tab1-stock-price-change','style'), # Price Change font colour
        Output('tab1-stock-price-percentchange','children'), # Price Percent Change
        Output('tab1-stock-price-percentchange','style'), # Price Precent Change font colour
    ], 
    [
        Input('tab1-ticker','children'), # Data store
    ] 
) 
def update_tab1_price_change(ticker):
    """
    Updates tab1 stock price change formatting for up/down colours.
    Depends on tab1-ticker being set and will fire on ticker change.    
    """

    outputs = {
        'tab1-stock-price__children': '', 
        'tab1-stock-price-change__children': '', 
        'tab1-stock-price-change__style': {}, 
        'tab1-stock-price-percentchange__children': '',
        'tab1-stock-price-percentchange__style': {},
    }

    stock = stock_data.StockData(cache).Ticker(ticker)

    if stock.info:

        outputs['tab1-stock-price__children'] = stock.info['_lastClose']
        outputs['tab1-stock-price-change__children'] = stock.info['_priceChange']
        outputs['tab1-stock-price-percentchange__children'] = stock.info['_priceChangePercent']

        price_change_style = {
            'display': 'inline-block',
            'width': '20%',
            'font-size': '150%'
        }

        if stock.info['_priceChangeDir'] == 'Positive':
            price_change_style['color'] = 'green'
        else:
            price_change_style['color'] = 'red'

        outputs['tab1-stock-price-change__style'] = price_change_style
        outputs['tab1-stock-price-percentchange__style'] = price_change_style

    return list(outputs.values())

# Update stock info table
@app.callback(
    Output('tab1-table','children'), # Table of Stock Stats
    Input('tab1-ticker','children') # Data store
)
def update_tab1_stock_info_table(ticker):

    stock = stock_data.StockData(cache).Ticker(ticker)

    if stock.info:
        return getTab1Table(stock.history().reset_index(), stock.info)
    else:
        return None


# Update tab 1 chart
@app.callback(
    [
        Output('tab1-vis','figure'), # Stock Price Chart
    ], 
    [
        Input('tab1-ticker','children'), # Change to ticker
        Input('tab1-time-interval','value'), # Time interval
    ]
)
def update_tab1_chart(ticker, period):

    stock = stock_data.StockData(cache).Ticker(ticker)

    if stock.info:
        return [
            getCandlestick(stock.history(period=period).reset_index())
        ]
    else:
        return [
            {'data': None}
        ] 


##### Callbacks for Tab 2 ######
"""
To generate the options to display on second dropdown for users to include
stock(s) addition to index.

Tab 2 only relies on data from Yahoo Finance
"""
"""
This callback return the list of stocks of corresponsed market. It requires
user to input which market to look and return 2 outputs.
1- List of stocks in the multi-dropdown list
2- The default value of the multi-dropdown list, in order to unselect previous
   stocks.
"""
@app.callback([Output('tab2-stock-include','options'),
               Output('tab2-stock-include','value')],
               [Input('tab2-index-choice','value')])
def generate_dropdown_stocknames(mkt):
    if mkt == 'hsi':
        stock_list = pd.read_csv('../IndexComponents/HengSengStockList.csv',
                     dtype=str)
        stock_list = stock_list.sort_values('Ticker')
        stock_list['label'] = stock_list['Ticker'].astype(str) + '\t' + \
                              stock_list['Company']
        opts = [{'label': label, 'value': ticker} for label, ticker in 
                zip(stock_list['label'].tolist(),
                    stock_list['Ticker'].tolist())]
        return opts, []
    elif mkt == 'sp500':
        stock_list = pd.read_csv('../IndexComponents/SP500StockList.csv',
                                 engine='python')
        stock_list = stock_list.sort_values('Ticker')
        stock_list['label'] = stock_list['Ticker']
        opts = [{'label': label, 'value': ticker} for label, ticker in 
                zip(stock_list['label'].tolist(),
                    stock_list['Ticker'].tolist())]
        return opts, []
    return [], []

"""
This callback generates Graph and the summary table of statistic.
The steps of this completing this functions:
1- Obtain the inputs, first get a list of stocks along with which index
2- If there is at least one stock selected other than the index, obtain
   the data frame of stock price. Since there is no stock selected for
   default setting, this step will be skipped if there is no stock
   selected
3- Take the price of the first day of the time interval, calculate the
   price change in percentage for each day relatively to the first day.
4- Generate a line chart from the data prepared in step 3
5- Generate a html table for the summary of index statistics
"""
@app.callback([Output('tab2-table','children'),
               Output('tab2-vis','figure')],
              [Input('tab2-index-choice','value'),
               Input('tab2-stock-include','value'),
               Input('tab2-time-interval','value')])
def generate_tab2_graph(mkt,stocks,time):
    # Function to calculate price change relative to the first day
    def get_price_change(price_list):
        base_price = price_list[0]
        return [(price/base_price)-1 for price in price_list]
    # Obtain the histoical stock price of selected stocks
    df_stocks = []
    if len(stocks) > 0:
        for stock in stocks:
            if mkt=='hsi':
                stock = stock[1:] + '.HK'
            stock_df = StockData.Ticker(stock).history(period=time)
            stock_df = stock_df.reset_index()[['Date','Close']]
            stock_df.columns = ['Date',stock]
            df_stocks.append(stock_df)

    """
    Obtain the historical index and with stock price dataframe.
    Then, convert to percent change relative to first day in the data frame.
    """
    y_ticker = None
    index_col = None
    if mkt == 'hsi':
        y_ticker = '^HSI'
        index_col = 'Heng Seng Index'

    elif mkt == 'sp500':
        # Note that Yahoo use ^GSPC as SP 500 ticker, SPX only has 1 entry
        y_ticker = '^GSPC'
        index_col = 'S&P 500'

    # Prevent error if nothing selected
    else:
        return html.Table(), {'data': None}

    # Prepare the data set to plot the line chart
    index = StockData.Ticker(y_ticker)
    df_index = index.history(period=time).reset_index()[['Date','Close']]
    df_index.columns = ['Date', index_col]
    # To take out duplicated columns, ie, Date, while concat
    if len(stocks) > 0:
        for df_temp in df_stocks:
            df_index = pd.merge(df_index, df_temp, how='left',on='Date')
        # In case there are NA's, fill with last observation
        df_index = df_index.fillna(method='backfill', axis=1)
        # Drop duplicated columns in case there are
        df_index = df_index.loc[:,~df_index.columns.duplicated()]

    # Convert from price to percent change relative to Day 1 of the period
    for col in df_index.columns:
        if col != 'Date':
            df_index[col] = get_price_change(df_index[col].tolist())
    fig = getLinePlot(df_index, 2)

    # Prepare the data set to list the summary on the table
    last_close = df_index[index_col].tolist()[-1]*100
    df_index_period = index.history(period=time).reset_index()
    df_index_52weeks = index.history(period='1y').reset_index()
    range_period = (round(df_index_period['Close'].min(),2), 
                    round(df_index_period['Close'].max(),2))
    range_52weeks = (round(df_index_52weeks['Close'].min(),2), 
                     round(df_index_52weeks['Close'].max(),2))
    volume = (index.history(period=time).reset_index()['Volume'].tolist()[-1],
              index.history(period=time).reset_index()['Volume'].mean())
    # Generate a table of summary
    table = getTab2Table(index_col, last_close, range_period, range_52weeks)

    return table, fig

if __name__ == '__main__':
    app.run_server(
        port=8000, 
        host='0.0.0.0', 
        debug=True, 
        dev_tools_silence_routes_logging=False
    )