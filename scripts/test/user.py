from collections.abc import Callable, Iterable, Mapping
from typing import Any
import websocket
import json
import queue
import threading
import base64
import time

ws_url='ws://localhost:6060/v0/channels?apikey=AQEAAAABAAD_rAp4DJh05a1HAwFT3A6K'


def on_open(ws: websocket.WebSocketApp):
    print('open socket')

def on_close(ws: websocket.WebSocketApp):
    print('open socket')

class User(threading.Thread):
    def __init__(self, user_name):
        threading.Thread.__init__(self)
        self.q = queue.Queue(10)
        self.ws = websocket.WebSocketApp(ws_url, on_message=self.on_message, on_open=on_open, on_close=on_close)
        self.user_name = user_name
        self.next_id = 1000
        self.user_id = ''

    def run(self):
        self.ws.run_forever()

    def on_message(self, ws: websocket.WebSocketApp, msg):
        msg = json.loads(msg)
        print(f'{self.user_name}({self.user_id}) recv: ', msg)
        self.q.put(msg)

    def send(self, msg: dict) -> str:
        self.next_id += 1
        typ = [k for k in msg.keys()][0]
        msg[typ]["id"] = str(self.next_id)
        print(f'{self.user_name}({self.user_id}) send: ', msg)
        self.ws.send(json.dumps(msg))
        return msg[typ]["id"]
    
    def send_wait(self, msg: dict):
        id = self.send(msg)
        self.await_msg({"ctrl": {"id": id}})

    def await_msg(self, check: dict) -> dict:
        def sub_contains(f: dict,  e: dict) -> bool:
            for k, v in e.items():
                if k not in f:
                    #print(f'ignore, k={k} not exists')
                    return False
                if isinstance(v, dict):
                    if not sub_contains(f[k], v):
                        return False
                elif f[k] != v:
                    #print(f'value is not match')
                    return False
            return True    
        
        while True:
            try:
                data = self.q.get(timeout=2)
            except Exception as e:
                print('await:', check, 'failed')
                break
            if sub_contains(data, check):
                return data


def b64(s: str) -> str:
    return base64.b64encode(s.encode()).decode()

now = int(time.time())
user_1 = User(f"user_1_{now}")
user_2 = User(f"user_2_{now}")
user_1.start()
user_2.start()
time.sleep(1)

user_1.send_wait({"hi":{"ver":"0.22.8","ua":"TinodeWeb/0.22.8 (Edge/114.0; Win32); tinodejs/0.22.8","lang":"zh-CN","platf":"web"}})
user_1.send({"login":{"scheme":"merc","secret":b64(user_1.user_name),"cred":[]}})
login = user_1.await_msg({"ctrl":{}})
user_1.user_id = login['ctrl']['params']['user']
user_1.send_wait({"sub":{"topic":"me", "get":{"what": "sub"}}})

user_2.send_wait({"hi":{"ver":"0.22.8","ua":"TinodeWeb/0.22.8 (Edge/114.0; Mac); tinodejs/0.22.8","lang":"zh-CN","platf":"web"}})
user_2.send({"login":{"scheme":"merc","secret":b64(user_2.user_name),"cred":[]}})
login = user_2.await_msg({"ctrl":{}})
user_2.user_id = login['ctrl']['params']['user']
user_2.send_wait({"sub":{"topic":"me", "get":{"what": "sub"}}})


def user_p2p_approve():
    # user2 try to sub user1
    user_2.send_wait({"sub":{"topic":user_1.user_id, "set":{"sub":{"mode":"JRWSA"},"desc":{"defacs":{"auth":"JRWSA"}}}}})
    user_1.await_msg({'pres': {"what": "acs"}})
    user_1.send_wait({"sub":{"topic":user_2.user_id, "set":{"sub":{"mode":"JRWSA"},"desc":{"defacs":{"auth":"JRWSA"}}}}})
    user_1.send_wait({"set":{"topic":user_2.user_id, "sub":{"user":user_2.user_id, "mode":"JRWSA"}}})

    # send msg
    user_2.send_wait({"pub": {"topic": user_1.user_id, "content": "hello", "noecho": True}})
    user_1.send_wait({"pub": {"topic": user_2.user_id, "content": "hello with two", "noecho": True}})

def user_p2p_reject():
    # user2 try to sub user1
    user_2.send_wait({"sub":{"topic":user_1.user_id, "set":{"sub":{"mode":"JRWSA"},"desc":{"defacs":{"auth":"JRWSA"}}}}})
    user_1.await_msg({'pres': {"what": "acs"}})
    user_1.send_wait({"sub":{"topic":user_2.user_id, "set":{"sub":{"mode":"JRWSA"},"desc":{"defacs":{"auth":"JRWSA"}}}}})
    user_1.send_wait({"set":{"topic":user_2.user_id, "sub":{"user":user_2.user_id, "mode":"N"}}})
    user_2.await_msg({'pres': {'what': 'acs'}})

    # send msg
    user_2.send_wait({"pub": {"topic": user_1.user_id, "content": "hello", "noecho": True}})


def user_send_mercGrp():
    user_1.send_wait({"sub": {"topic": "mercGrp", "get": {"data": {"limit": 24}}, "what": "data sub"}})
    user_1.send_wait({"pub": {"topic": "mercGrp", "noecho": True, "content": "merc grp"}})
    user_1.send_wait({"pub": {"topic": "mercGrp", "noecho": True, "content": "merc grp 2"}})

user_send_mercGrp()

user_1.join()
user_2.join()