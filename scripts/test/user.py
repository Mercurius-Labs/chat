from collections.abc import Callable, Iterable, Mapping
from typing import Any
import websocket
import json
import queue
import threading
import base64
import time
import requests

use_agw = False
remoteHost = 'localhost:6060'
tokenMap = {
    'test_user_1' : 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE2OTQ2MTY5MzYsImlhdCI6MTY5MjAyNDkzNiwicGF5bG9hZCI6IntcInVzZXJfaWRcIjpcIjEyMzQ1Njc4OTNcIixcIm5pY2tuYW1lXCI6XCJ0ZXN0X2xsZl91c2VyXzRcIixcImF2YXRhclwiOlwiaHR0cDovL3d3dy51bmtub3duLmNvbS90ZXN0X2xsZl91c2VyXzIuanBnXCJ9In0.Gno2Gi_JYv9f0f0rK8h0uII27d0NyYGdva3oPKeqDUM',
    'test_sss_user_2': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE2OTQ2MTY4MzEsImlhdCI6MTY5MjAyNDgzMSwicGF5bG9hZCI6IntcInVzZXJfaWRcIjpcIjEyMzQ1Njc4OTFcIixcIm5pY2tuYW1lXCI6XCJ0ZXN0X2xsZl91c2VyXzJcIixcImF2YXRhclwiOlwiaHR0cDovL3d3dy51bmtub3duLmNvbS90ZXN0X2xsZl91c2VyXzIuanBnXCJ9In0.wAUiWl25ZrYZsT5V7s-pSfLM2y9Sh_sg4W9-e7tvy-8',
    'test_user_3': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE2OTQ2MTY4OTksImlhdCI6MTY5MjAyNDg5OSwicGF5bG9hZCI6IntcInVzZXJfaWRcIjpcIjEyMzQ1Njc4OTJcIixcIm5pY2tuYW1lXCI6XCJ0ZXN0X2xsZl91c2VyXzNcIixcImF2YXRhclwiOlwiaHR0cDovL3d3dy51bmtub3duLmNvbS90ZXN0X2xsZl91c2VyXzIuanBnXCJ9In0.ndgVpjmxdnIxoK_juk6cg-ziSDga2Zuf1aKIJcNKFu0'
}

ws_url=f'ws://{remoteHost}/v0/channels?apikey=AQEAAAABAAD_rAp4DJh05a1HAwFT3A6K'
if use_agw:
    remoteHost = '34.87.176.129:8000'
    #remoteHost = 'localhost:8000'
    ws_url=f'ws://{remoteHost}/v1/chat/channels?apikey=AQEAAAABAAD_rAp4DJh05a1HAwFT3A6K'

def on_open(ws: websocket.WebSocketApp):
    print('open socket')

def on_close(ws: websocket.WebSocketApp):
    print('close socket')

class User(threading.Thread):
    def __init__(self, user_name):
        threading.Thread.__init__(self)
        self.q = queue.Queue(10)
        header = {'x-uid': user_name}
        if use_agw:
            token = ''
            if user_name in tokenMap:
                token = tokenMap[user_name]
            else:
                resp = requests.post(f'http://{remoteHost}/v1/user/login', json={'address': '0xxxxx', 'sign_hex': '0x21', 'type': 'metamask'})
                token = resp.json()['data']['token']
            header = {'Sec-WebSocket-Protocol': token}
        self.ws = websocket.WebSocketApp(ws_url, on_message=self.on_message, on_open=on_open, on_close=on_close, header=header)
        self.user_name = user_name
        self.next_id = 1000
        self.user_id = ''

    def run(self):
        self.ws.run_forever()

    def on_message(self, ws: websocket.WebSocketApp, msg):
        msg = json.loads(msg)
        print(f'[{time.time()}]{self.user_name}({self.user_id}) recv: ', json.dumps(msg))
        self.q.put(msg)

    def send(self, msg: dict) -> str:
        self.next_id += 1
        typ = [k for k in msg.keys()][0]
        msg[typ]["id"] = str(self.next_id)
        print(f'[{time.time()}]{self.user_name}({self.user_id}) send: ', json.dumps(msg))
        self.ws.send(json.dumps(msg))
        return msg[typ]["id"]
    
    def send_wait(self, msg: dict, check: dict=None):
        id = self.send(msg)
        if check is None:
            check = {"ctrl": {"id": id}}
        else:
            typ = [k for k in check.keys()][0]
            check[typ]["id"] = id
        return self.await_msg(check)
    
    def login(self, ua: str):
        self.send_wait({"hi":{"ver":"0.22.8","ua":ua,"lang":"zh-CN","platf":"web"}})
        self.send({"login":{"scheme":"merc","secret":"","cred":[], 
                            "desc": {"public": {"avatar": f'http://unknown.com/{self.user_name}_yyy.jpg', "nickname": self.user_name}}}})
        loginResp = self.await_msg({"ctrl":{}})
        self.user_id = loginResp['ctrl']['params']['user']
        self.send_wait({"sub":{"topic":"me", "get":{"what": "sub"}}})

    def await_msg(self, check: dict) -> dict:
        def sub_contains(f: dict,  e: dict) -> bool:
            for k, v in e.items():
                if k not in f:
                    #print(f'ignore, k={k} not exists')
                    return False
                if isinstance(v, dict):
                    if not sub_contains(f[k], v):
                        return False
                elif isinstance(v, list):
                    if len(v) == 0:
                        pass
                    for i, vv in enumerate(v):
                        if not sub_contains(f[k][i], vv):
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

def test_two_user():
    now = int(time.time())
    user_1 = User(f"test_user_1_{now}")
    user_2 = User(f"test_user_2_{now}")
    #user_3 = User(f"test_user_3")
    user_1.start()
    user_2.start()
    #user_3.start()
    time.sleep(1)

    user_1.login("TinodeWeb/0.22.8 (Edge/114.0; Mac); tinodejs/0.22.8")
    user_2.login("TinodeWeb/0.22.8 (Edge/114.0; Mac); tinodejs/0.22.8")
    #user_3.login("TinodeWeb/0.22.8 (Edge/114.0; Mac); tinodejs/0.22.8")


    def user_p2p_approve():
        # user2 try to sub user1
        user_2.send_wait({"sub":{"topic":user_1.user_id, "set":{"sub":{"mode":"JRWSA"},"desc":{"public":{"avatar":"xxx", "nickname":"xxx"},"defacs":{"auth":"JRWSA"}}}}})
        user_1.await_msg({'pres': {"what": "acs", "src": user_2.user_id}})
        user_1.send_wait({"sub":{"topic":user_2.user_id, "set":{"sub":{"mode":"JRWSA"},"desc":{"defacs":{"auth":"JRWSA"}}}}})
        user_1.send_wait({"set":{"topic":user_2.user_id, "sub":{"user":user_2.user_id, "mode":"JRWSA"}}})
        user_2.await_msg({'pres':{"topic":user_1.user_id, "what": "acs", "dacs": {"given": "+RW"}}})


        # send msg
        user_2.send_wait({"pub": {"topic": user_1.user_id, "content": "hello", "noecho": True}})
        user_1.send_wait({"pub": {"topic": user_2.user_id, "content": "hello with two", "noecho": True}})

        # send sys msg
        user_1.send_wait({"pub": {"topic": "sys", "content": {"what":"rating", "rating": "good", "comment": "very"}, "noecho": True}})

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
        user_1.send_wait({"sub": {"topic": "mercGrp", "get": {"data": {"limit": 24}, "what": "sub"}}})
        user_2.send_wait({"sub": {"topic": "mercGrp", "get": {"data": {"limit": 24}, "what": "sub"}}})
        user_1.send_wait({"get": {"topic": "mercGrp", "what": "rec", "rec": {"limit": 10}}}, {"meta": {}})
        user_1.send_wait({"get": {"topic": "mercGrp", "what": "rec", "rec": {"limit": 2}}}, {"meta": {}})
        user_2.send_wait({"get": {"topic": "mercGrp", "what": "rec"}}, {"meta": {}})
        user_1.send_wait({"pub": {"topic": "mercGrp", "noecho": True, "content": "merc grp", "head": {"nickname": "hahha", "avatar": "xxx"}}})
        user_1.send_wait({"pub": {"topic": "mercGrp", "noecho": True, "content": "this message 1"}})
        user_1.send_wait({"pub": {"topic": "mercGrp", "noecho": True, "content": "this message 2"}})
        user_2.send_wait({"pub": {"topic": "mercGrp", "noecho": True, "content": "this message 34"}})
        msg = user_1.send_wait({"pub": {"topic": "mercGrp", "noecho": True, "content": "merc grp 3"}})
        seqID = msg["ctrl"]["params"]['seq']
        user_2.send({"note": {"topic": "mercGrp", "seq": seqID, "what": "like"}})
        user_1.await_msg({'info': {'from': user_2.user_id, 'what': 'like'}})

        user_1.send_wait({"get": {"topic": "me", "what": "sub"}}, {"meta": {"sub": []}})

    def rec_user_pub():
        user_1.send_wait({"sub": {"topic": "mercGrp"}})
        user_2.send_wait({"sub": {"topic": "mercGrp"}})
        user_1.send({"get":{"topic":"mercGrp", "what": "rec"}})
        user_2.send({"get":{"topic":"mercGrp", "what": "rec"}})
        user_1.await_msg({"meta": {"rec": [{"user_id": user_2.user_id}]}})
        user_2.await_msg({"meta": {"rec": [{"user_id": user_1.user_id}]}})
        user_1.send_wait({"sub":{"topic":user_2.user_id, "set":{"sub":{"mode":"JRWSA", "rec": True},"desc":{"defacs":{"auth":"JRWSA"}, "public": {"avatar": "xxx", "nickname":"xxx"}}}}})
        user_1.send_wait({"pub": {"topic": user_2.user_id, "content": "hahaha", "noecho": True}})

        user_2.send_wait({"sub":{"topic":user_1.user_id, "set":{"sub":{"mode":"JRWSA", "rec": True},"desc":{"defacs":{"auth":"JRWSA"}}}}})
        user_2.send_wait({"pub": {"topic": user_1.user_id, "content": "hahaha v2", "noecho": True}})

    user_p2p_approve()

    user_1.join()
    user_2.join()

def test_with_frontend():
    user = User(f"user_with_frontend")
    user.start()
    time.sleep(1)

    user.login("TinodeWeb/0.22.8 (Edge/114.0; Mac); tinodejs/0.22.8")
    user.send_wait({"sub": {"topic": "mercGrp", "get": {"data": {"limit": 2}, "what": "data"}}})
    user.send_wait({"get":{"topic":"me", "what": "sub desc"}}, {"meta": {"topic": "me"}})
    user.send_wait({"pub": {"topic": "mercGrp", "noecho": True, "content": "merc grp", "head": {"nickname": "user_with_frontend", "avatar": "http://unknown.com/unknown.jpg"}}})
    user.join()

test_two_user()