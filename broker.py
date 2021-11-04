import redis, json
import ib_insync
import asyncio, time, random
import datetime
import pandas as pd
import os

# connect to Interactive Brokers 
ib = ib_insync.IB()
ib.connect('127.0.0.1', 7497, clientId=1)

# connect to Redis and subscribe to tradingview messages
r = redis.Redis(host='localhost', port=6379, db=0)
p = r.pubsub()
p.subscribe('tradingview')

# Define relative path to save the tracking files to:
path = 'trades_tracking'

def recordPosition(message_data, path):
    # Create data frame for trades' tracking if it was not created before.
    file_name = f"trades_traching_{datetime.datetime.now().date()}.csv"
    if not os.path.isfile(f"{path}\{file_name}"):
        df = pd.DataFrame(columns=['Datetime', 'Ticker', 'Action', 'Long_Short', 'Quantity'])
        df.to_csv(f"{path}\{file_name}", index=[0])

    df = pd.read_csv(f"{path}\{file_name}", index_col=0)
    
    df = df.append({
        'Datetime': pd.to_datetime(message_data['time']),
        'Ticker': message_data['ticker'],
        'Action': message_data['strategy']['order_action'],
        'Long_Short': message_data['strategy']['market_position'],
        'Quantity': message_data['strategy']['position_size']
    }, ignore_index=True)
    df.to_csv(f"{path}\{file_name}", index=[0])

    print(df)

def printNLog(message, path):
    file_name = f"trades_traching_{datetime.datetime.now().date()}.txt"
    
    file_handle = open(f"{path}\{file_name}", 'a')
    file_handle.write(message)
    file_handle.close()

    print(message)
    

def check_messages(positions_amount_allowed):
    print(f"{time.time()} - checking for tradingview webhook messages")
    message = p.get_message()

    if message is not None and message['type'] == 'message':
        # Convert the message to dictionary.
        message_data = json.loads(message['data'])

        # Print and log the message to screen the tracking file.
        printNLog(f"New message was recieved for the ticker '{message_data['ticker']}' at {datetime.datetime.now()}.\n", path)
        printNLog(f"Message data:\n{message_data}", path)
        
        # Get current positions to see if there is open position of the same security
        positions = ib.reqPositions()
        
        # Print and log the message to screen the tracking file.
        printNLog(f"\nInteractive Brokers positions:\n{positions}", path)
        
        # Check number of open positions.
        open_positions_dict = dict()
        for position in positions:
            if position.position != 0.0:
                open_positions_dict[position.contract.symbol] = position

        # If portfolio has no open positions, place new order.
        if not bool(open_positions_dict):
            # Print and log the message to screen the tracking file.
            printNLog(f"There are no open positions in Interactive Brokers portfolio. Accepting new trade for '{message_data['ticker']}'.\n", path)
                        
            # Add to trades' data frame.
            recordPosition(message_data, path)
            
            stock = ib_insync.contract.Stock(message_data['ticker'], 'SMART', 'USD')
            order = ib_insync.order.MarketOrder(message_data['strategy']['order_action'], message_data['strategy']['order_contracts'])
            trade = ib.placeOrder(stock, order)
        
        # If portfolio has open positions, check if the current ticker is found in portfolio.
        # If yes, place the order. If not, check if the new ticker can be accepted.
        else:
            # Print and log the message to screen the tracking file.
            printNLog("Portfolio has open positions.\n", path)
            
            # If the new message ticker has open position in portfolio, place new order.
            if message_data['ticker'] in open_positions_dict:
                
                # Print and log the message to screen the tracking file.
                printNLog(f"Ticker '{message_data['ticker']}' has open position in portfolio. Place new order.\n", path)
                
                # Add to trades' data frame.
                recordPosition(message_data, path)

                stock = ib_insync.contract.Stock(message_data['ticker'], 'SMART', 'USD')
                order = ib_insync.order.MarketOrder(message_data['strategy']['order_action'], message_data['strategy']['order_contracts'])
                trade = ib.placeOrder(stock, order)
            
            # If the new message ticker has no open position in portfolio, check if new position is allowed.
            # If yes - place the new order.
            # If no  - Skip the message.
            elif len(open_positions_dict.keys()) < positions_amount_allowed:
                
                # Print and log the message to screen the tracking file.
                printNLog(f"The number of open postions is less than the amount allowed. Open positions: {len(open_positions_dict.keys())}. Amount allowed: {positions_amount_allowed}.\n", path)
                printNLog(f"New position for ticker '{message_data['ticker']}'.\n", path)
                
                # Add to trades' data frame.
                recordPosition(message_data, path)

                stock = ib_insync.contract.Stock(message_data['ticker'], 'SMART', 'USD')
                order = ib_insync.order.MarketOrder(message_data['strategy']['order_action'], message_data['strategy']['order_contracts'])
                trade = ib.placeOrder(stock, order)

            # The new message ticker is has no open position in portfolio and no new position is allowed. Skipping the message.
            else:
                # Print and log the message to screen the tracking file.
                printNLog(f"The ticker '{message_data['ticker']}' has no open position in portfolio, but no more open positions allowed. Skipping order...\n", path)

        # If there was a new messaage, put black row for better separation.
        printNLog("#################################################################################################################################\n", path)

positions_amount_allowed = 3
while True:
    check_messages(positions_amount_allowed)
    ib.sleep(1)

ib.run()