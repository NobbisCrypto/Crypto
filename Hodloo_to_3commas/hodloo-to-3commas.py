import websockets
import json
import asyncio
import requests
import re
import decimal
import importlib
from datetime import datetime
from py3cw.request import Py3CW
import traceback
import sys

def test_leveraged_token(exchange_str,pair,asset):
    is_leveraged_token = False
    if exchange_str == 'Kucoin':
        is_leveraged_token = bool(re.search('3L', asset)) or bool(re.search('3S', asset))
    if exchange_str == 'Binance':
        is_leveraged_token = bool(re.search('UP/', pair)) or bool(re.search('DOWN/', pair))
    return is_leveraged_token

def send_to_discord(string,url):
    data = {"content": string}
    requests.post(url, json=data)

def send_buy_trigger(quote,asset,exchange_str,discord_message,bot_id):
    if exchange_str in config.HODLOO_EXCHANGES:
        pair = quote + "_" + asset
        error, deal = p3cw.request(
            entity = 'bots',
            action = 'start_new_deal',
            action_id = bot_id,
            payload={
                "pair": pair
            }
        )
        if not error and notification_alerts == True:
            send_to_discord(discord_message,config.DISCORD_NOTIFICATIONS)
    
def test_volume24(volume_hodloo,volume_threshold):
	if volume_threshold == '':
		# Volume filter not desired -> proceeed
		return True
	else:
		if bool(re.search('^\d+(\.\d+)$',volume_threshold)) == True:
			if volume_hodloo < float(volume_threshold):
				# Volume filter is set and volume below threshold -> stop
				return False
			else:
				# Volmue filter is set and volume above threshold -> proceed
				return True
		else:
			raise Exception("Variable HODLOO_MIN_VOLUME not set correctly. Please read the variable documentation.")    

def on_message(ws, message):
    messages = json.loads(message)

    # {"basePrice":0.0000014002,"belowBasePct":0,"marketInfo":{"pctRelBase":-4.04,"price":0.0000013597,"priceDate":1637223011,"symbol":"manbtc","ticker":"Huobi:MAN-BTC","volume24":5.74040067182},"period":60,"type":"base-break"}
	# {"marketInfo":{"price":0.002621,"priceDate":1637222839,"symbol":"BSVBTC","ticker":"HitBTC:BSV-BTC","volume24":28.209960342},"period":60,"strength":7.7,"type":"panic","velocity":-2.27}
    if messages['type'] in ['base-break','panic']:
        exchange_str,pair = messages["marketInfo"]["ticker"].split(':')
        if exchange_str in config.HODLOO_EXCHANGES:
            pair = pair.replace('-','/')
            asset,quote = pair.split('/')
            volume24 = messages["marketInfo"]["volume24"]
            if test_volume24(volume24,config.HODLOO_MIN_VOLUME) == True:
                if test_leveraged_token(exchange_str, pair, asset) == True and config.TC_EXCLUDE_LEVERAGED_TOKENS == True:
                    print(f"{datetime.now().replace(microsecond=0)} - Leveraged tokens not desired but {pair} is one. Skipping...")
                else:
                    if pair in config.TC_DENYLIST:
                        print(f"{datetime.now().replace(microsecond=0)} - {pair} is on the denylist. Skipping...")
                    else:
                        alert_price = decimal.Decimal(str(messages["marketInfo"]["price"]))
                        tv_url = "https://www.tradingview.com/chart/?symbol=" + exchange_str + ":" + pair.replace('/','')
                        hodloo_url = (config.HODLOO_URI).replace('wss:','https:').replace('/ws','/#/')
                        hodloo_url = hodloo_url + exchange_str + ":" + pair.replace('/','-')

                        if messages['type'] == 'base-break':
                            base_price = decimal.Decimal(str(messages["basePrice"]))
                            
                            if messages["belowBasePct"] == 5 and bot_id_5 == True:
                                print(f"{datetime.now().replace(microsecond=0)} - Processing {pair} for Exchange {exchange_str}")
                                discord_message = f'\n[ {datetime.now().replace(microsecond=0)} | {exchange_str} | Base Break 5%]\n\nSymbol: *{pair}*\nAlert Price: {alert_price} - Base Price: {base_price}\n[TradingView]({tv_url}) - [Hodloo]({hodloo_url})'
                                send_buy_trigger(quote,asset,exchange_str,discord_message,config.BOT_ID_5)
                            if messages["belowBasePct"] == 10 and bot_id_10 == True:
                                print(f"{datetime.now().replace(microsecond=0)} - Processing {pair} for Exchange {exchange_str}")
                                discord_message = f'\n[ {datetime.now().replace(microsecond=0)} | {exchange_str} | Base Break 10%]\n\nSymbol: *{pair}*\nAlert Price: {alert_price} - Base Price: {base_price}\n[TradingView]({tv_url}) - [Hodloo]({hodloo_url})'
                                send_buy_trigger(quote,asset,exchange_str,discord_message,config.BOT_ID_10)

                        if messages['type'] == 'panic' and bot_id_panic == True:
                            print(f"{datetime.now().replace(microsecond=0)} - Processing {pair} for Exchange {exchange_str}")
                            strength = messages["strength"]
                            velocity = messages["velocity"]
                            discord_message = f'\n[ {datetime.now().replace(microsecond=0)} | {exchange_str} | Panic Trade ]\n\nSymbol: *{pair}*\nAlert Price: {alert_price}\nVelocity: {velocity}\nStrength: {strength}\n[TradingView]({tv_url}) - [Hodloo]({hodloo_url})'
                            send_buy_trigger(quote,asset,exchange_str,discord_message,config.BOT_ID_PANIC)
            else:
                    print(f"{datetime.now().replace(microsecond=0)} - Volume is below threshold hence skipping pair {pair}")
            



async def consumer_handler(websocket) -> None:
	async for message in websocket:
		on_message(websocket,message)

async def consume(uri) -> None:
	async with websockets.connect(uri) as websocket:
		await consumer_handler(websocket)

def await_events():
	print(f"{datetime.now().replace(microsecond=0)} - Waiting for events")
	loop = asyncio.get_event_loop()
	loop.run_until_complete(consume(config.HODLOO_URI))
	loop.run_forever()

if __name__ == "__main__":
    try:
        if len(sys.argv) == 1:
            print(f"{datetime.now().replace(microsecond=0)} - No parameters passed to script. Importing config.py as source of variables.")
            import config
        elif len(sys.argv) == 2:
            dummy = sys.argv[1]
            if dummy[-3:] == '.py':
                dummy = dummy[:-3]
            print(f"{datetime.now().replace(microsecond=0)} - One parameter passed to script. Importing {dummy}.py as source of variables.")
            config = importlib.import_module(dummy)
        else:
            raise Exception("Unsupported amount of parameters. Use either zero or one.")
        notification_alerts = bool(re.search('^https:\/\/(discord|discordapp)\.com\/api\/webhooks', config.DISCORD_NOTIFICATIONS))
        error_alerts = bool(re.search('^https:\/\/(discord|discordapp)\.com\/api\/webhooks', config.DISCORD_ERRORS))
        bot_id_5 = bool(config.BOT_ID_5)
        bot_id_10 = bool(config.BOT_ID_10)
        bot_id_panic = bool(config.BOT_ID_PANIC)

        if error_alerts == False:
            raise Exception("Variable DISCORD_ERRORS must be filled")

        print(f"{datetime.now().replace(microsecond=0)} - Connecting to 3Commas")
        p3cw = Py3CW(
            key=config.TC_API_KEY,
            secret=config.TC_API_SECRET,
            request_options={
                'request_timeout': 30,
                'nr_of_retries': 1,
                'retry_status_codes': [502],
                'Forced-Mode': config.MODE
            }
        )

        await_events()

    except KeyboardInterrupt:
        print(f"{datetime.now().replace(microsecond=0)} - Exiting as requested by user")

    except websockets.ConnectionClosedError:
        print(f"{datetime.now().replace(microsecond=0)} - Connection to websockets server lost. Reconnecting...")
        await_events()

    except TimeoutError:
        print(f"{datetime.now().replace(microsecond=0)} - Got a timeout. Reconnecting...")
        await_events()
        
    except:
        send_to_discord(f"{datetime.now().replace(microsecond=0)} - Unexpected error:\n```\n{traceback.format_exc()}\n```\nReconnecting...",config.DISCORD_ERRORS)
        await_events()

    finally:
        print(f"{datetime.now().replace(microsecond=0)} - Exiting...")
