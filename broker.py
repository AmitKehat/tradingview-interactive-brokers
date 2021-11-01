import redis, json
import ib_insync
import asyncio, time, random
import datetime

# connect to Interactive Brokers 
ib = ib_insync.IB()
ib.connect('127.0.0.1', 7497, clientId=1)

# connect to Redis and subscribe to tradingview messages
r = redis.Redis(host='localhost', port=6379, db=0)
p = r.pubsub()
p.subscribe('tradingview')


def check_messages(positions_amount_allowed):
    file_handle = open('trades_tracking.txt', 'a')
    print(f"{time.time()} - checking for tradingview webhook messages")
    message = p.get_message()

    if message is not None and message['type'] == 'message':
        # Convert the message to dictionary.
        message_data = json.loads(message['data'])

        # Print the message to the tracking file.
        file_handle.write(f"New message was recieved for the ticker '{message_data['ticker']}' at {datetime.datetime.now()}.\n")
        file_handle.write(f"Message data:\n{message_data}\n")

        # Get current positions to see if there is open position of the same security
        positions = ib.reqPositions()
        print(f"\nInteractive Brokers positions:\n{positions}")
        # Print the message to the tracking file.
        file_handle.write(f"Interactive Brokers positions:\n{positions}\n")

        # Check number of open positions.
        open_positions_dict = dict()
        for position in positions:
            if position.position != 0.0:
                open_positions_dict[position.contract.symbol] = position

        # If portfolio has no open positions, place new order.
        if not bool(open_positions_dict):
            print(f"There are no open positions in Interactive Brokers portfolio. Accepting new trade for '{message_data['ticker']}'.\n")
            # Print the message to the tracking file.
            file_handle.write(f"There are no open positions in Interactive Brokers portfolio. Accepting new trade for '{message_data['ticker']}'.\n")
            stock = ib_insync.contract.Stock(message_data['ticker'], 'SMART', 'USD')
            order = ib_insync.order.MarketOrder(message_data['strategy']['order_action'], message_data['strategy']['order_contracts'])
            trade = ib.placeOrder(stock, order)
        
        # If portfolio has open positions, check if the current ticker is found in portfolio.
        # If yes, place the order. If not, check if the new ticker can be accepted.
        else:
            print("Portfolio has open positions.")
            # Print the message to the tracking file.
            file_handle.write("Portfolio has open positions.\n")

            # If the new message ticker has open position in portfolio, place new order.
            if message_data['ticker'] in open_positions_dict:
                print(f"Ticker '{message_data['ticker']}' has open position in portfolio. Place new order.\n")
                # Print the message to the tracking file.
                file_handle.write(f"Ticker '{message_data['ticker']}' has open position in portfolio. Place new order.\n")

                stock = ib_insync.contract.Stock(message_data['ticker'], 'SMART', 'USD')
                order = ib_insync.order.MarketOrder(message_data['strategy']['order_action'], message_data['strategy']['order_contracts'])
                trade = ib.placeOrder(stock, order)
            
            # If the new message ticker has no open position in portfolio, check if new position is allowed.
            # If yes - place the new order.
            # If no  - Skip the message.
            elif len(open_positions_dict.keys()) < positions_amount_allowed:
                print(f"The number of open postions is less than the amount allowed. Open positions: {len(open_positions_dict.keys())}. Amount allowed: {positions_amount_allowed}.")
                print(f"New position for ticker '{message_data['ticker']}'.\n")
                # Print the message to the tracking file.
                file_handle.write(f"The number of open postions is less than the amount allowed. Open positions: {len(open_positions_dict.keys())}. Amount allowed: {positions_amount_allowed}.\n")
                file_handle.write(f"New position for ticker '{message_data['ticker']}'.\n")

                stock = ib_insync.contract.Stock(message_data['ticker'], 'SMART', 'USD')
                order = ib_insync.order.MarketOrder(message_data['strategy']['order_action'], message_data['strategy']['order_contracts'])
                trade = ib.placeOrder(stock, order)

            # The new message ticker is has no open position in portfolio and no new position is allowed. Skipping the message.
            else:
                print(f"The ticker '{message_data['ticker']}' has no open position in portfolio, but no more open positions allowed. Skipping order...\n")
                # Print the message to the tracking file.
                file_handle.write(f"The ticker '{message_data['ticker']}' has no open position in portfolio, but no more open positions allowed. Skipping order...\n")

        # If there was a new messaage, put black row for better separation.
        file_handle.write("\n")
    file_handle.close()

positions_amount_allowed = 1
while True:
    check_messages(positions_amount_allowed)
    ib.sleep(1)

ib.run()