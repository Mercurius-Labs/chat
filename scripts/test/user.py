import websocket
import json
import queue
import threading
import base64
import time
import requests
import jwt
import os

def gen_jwt_token(user_name):
    payload = {"user_id":user_name,"nickname":user_name,"avatar":f"http://unknown.com/{user_name}.jpg"}
    claim = {
        "exp": int(time.time()-2000) + 2592000,
        "iat": int(time.time()-2000),
        "payload": json.dumps(payload)
    }
    key = os.getenv("MERC_SECRET_KEY")
    return jwt.encode(payload=claim, key=key, algorithm="HS256")

use_agw = True
remoteHost = 'localhost:6060'

ws_url=f'ws://{remoteHost}/v0/channels?apikey=AQEAAAABAAD_rAp4DJh05a1HAwFT3A6K'
if use_agw:
    remoteHost = os.getenv("MERC_REMOTE_HOST")
    #remoteHost = 'localhost:8000'
    ws_url=f'ws://{remoteHost}/v1/chat/channels?apikey=AQEAAAABAAD_rAp4DJh05a1HAwFT3A6K'

def on_open(ws: websocket.WebSocketApp):
    print('open socket')

def on_close(ws: websocket.WebSocketApp):
    print('close socket')

class User(threading.Thread):
    def __init__(self, user_name: str, bcolor):
        threading.Thread.__init__(self)
        self.q = queue.Queue(10)
        self.bcolor = bcolor
        header = {'x-uid': user_name}
        if use_agw:
            token = ''
            if user_name.isnumeric():
                token = gen_jwt_token(user_name)
            else:
                resp = requests.post(f'http://{remoteHost}/v1/user/login', json={'address': '0xxxxx', 'sign_hex': '0x21', 'type': 'metamask'})
                token = resp.json()['data']['token']
            header = {'Sec-WebSocket-Protocol': token}
        self.ws = websocket.WebSocketApp(ws_url, on_message=self.on_message, on_open=on_open, on_close=on_close, header=header)
        self.user_name = user_name
        self.next_id = 1000
        self.user_id = ''
        self.basic_info = {"avatar":  f'http://unknown.com/{self.user_name}_yyy.jpg', "nickname": self.user_name}

    def run(self):
        # wait start
        self.ws.run_forever()

    def on_message(self, ws: websocket.WebSocketApp, msg):
        msg = json.loads(msg)
        print(f'\033[0;{self.bcolor};40m[{time.time()}]{self.user_name}({self.user_id}) recv: ', json.dumps(msg), '\033[0m')
        self.q.put(msg)

    def send(self, msg: dict) -> str:
        self.next_id += 1
        typ = [k for k in msg.keys()][0]
        msg[typ]["id"] = str(self.next_id)
        print(f'\033[0;{self.bcolor};40m[{time.time()}]{self.user_name}({self.user_id}) send: ', json.dumps(msg), '\033[0m')
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
        self.send({"login":{"scheme":"merc","secret":"","cred":[], "desc": {"public": self.basic_info}}})
        loginResp = self.await_msg({"ctrl":{}})
        self.user_id = loginResp['ctrl']['params']['user']
        self.send_wait({"sub":{"topic":"me"}})
        self.send_wait({"sub": {"topic": "mercGrp"}})
        print()

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
                data = self.q.get(timeout=5)
            except Exception as e:
                print(f'{self.user_name} await:', check, 'failed')
                raise e
            if sub_contains(data, check):
                return data


def b64(s: str) -> str:
    return base64.b64encode(s.encode()).decode()

def user_start_chat(user_1: User, user_2: User):
    user_2.send({"note":{"what":"1v1", "topic":user_1.user_id, "payload": {"chat": True, **user_2.basic_info}}})
    user_1.await_msg({"info": {"src": user_2.user_id, "payload": {"chat": True}}})
    user_1.send({"note":{"what":"1v1", "topic": user_2.user_id, "payload": {"reply": "agree"}}})
    user_1.send_wait({"sub": {"topic": user_2.user_id}})
    user_2.await_msg({"info":{"src": user_1.user_id, "payload": {"reply": "agree"}}})
    user_2.send_wait({"sub": {"topic": user_1.user_id}})

    user_2.send_wait({"pub": {"topic": user_1.user_id, "content": "hello, user_1", "noecho": True, "head": user_2.basic_info}})
    user_1.await_msg({"data": {"topic": user_2.user_id, "content": "hello, user_1", "head": user_2.basic_info}})


def user_leave_chat(user_1: User, user_2: User):
    user_2.send({"note":{"topic": user_1.user_id, "what": "1v1", "payload": {"chat": False}}})
    user_2.send_wait({"leave": {"topic": user_1.user_id}})

    user_1.await_msg({"info":{"src": user_2.user_id, "what": "1v1", "payload": {"chat": False}}})
    user_1.send_wait({"leave": {"topic": user_2.user_id}})

def test_two_user():
    now = int(time.time())
    user_1 = User(f"user_1", 31)
    user_2 = User(f"user_2", 32)
    user_3 = User(f"user_3", 33)
    user_1.start()
    user_2.start()
    user_3.start()
    time.sleep(1)

    user_1.login("TinodeWeb/0.22.8 (Edge/114.0; Mac); tinodejs/0.22.8")
    user_2.login("TinodeWeb/0.22.8 (Edge/114.0; Mac); tinodejs/0.22.8")
    user_3.login("TinodeWeb/0.22.8 (Edge/114.0; Mac); tinodejs/0.22.8")
    
    print('====== pub message on lobby ======')
    user_1.send_wait({"pub": {"topic": "mercGrp", "content": "user_1 send 1 message", "noecho": True, "head": user_1.basic_info}})
    user_2.await_msg({"data": {"topic": "mercGrp", "from": user_1.user_id, "head": user_1.basic_info}})
    user_3.await_msg({"data": {"topic": "mercGrp", "from": user_1.user_id, "head": user_1.basic_info}})

    print('====== user_2 try to chat with user_1 ======')
    user_start_chat(user_1, user_2)

    print('====== user_3 try to chat with user_1, but failed ======')
    user_3.send_wait({"note":{"what":"1v1", "topic":user_1.user_id, "payload": {"chat": True, **user_2.basic_info}}})

    print('===== user_2 try to leave sub with user_1 ======')
    user_leave_chat(user_1, user_2)

    print('======= user_1, user_3 start random match =====')
    user_1.send({"get":{"topic":"mercGrp", "what": "rec", "rec": {"wait_sec": 5}}})
    user_3.send({"get":{"topic":"mercGrp", "what": "rec"}})
    user_1.await_msg({"meta": {"rec": [{"user_id": user_3.user_id}]}})
    user_3.await_msg({"meta": {"rec": [{"user_id": user_1.user_id}]}})
    user_2.send_wait({"get":{"topic":"mercGrp", "what": "rec", "rec": {"wait_sec": 2}}}, {"ctrl": {"code": 204}})

    user_1.send_wait({"sub": {"topic": user_3.user_id}})
    user_3.send_wait({"sub": {"topic": user_1.user_id}})
    user_3.send_wait({"pub": {"topic": user_1.user_id, "content": "hello, user_1", "noecho": True, "head": user_3.basic_info}})
    user_1.await_msg({"data": {"topic": user_3.user_id, "content": "hello, user_1", "head": user_3.basic_info}})
    user_leave_chat(user_1, user_3)

    print('======= user_1 try to chat with user_2, then reject')
    user_1.send({"note":{"what":"1v1", "topic":user_2.user_id, "payload": {"chat": True, **user_1.basic_info}}})
    user_2.await_msg({"info": {"src": user_1.user_id, "payload": {"chat": True}}})
    user_2.send({"note":{"what":"1v1", "topic": user_1.user_id, "payload": {"reply": "reject"}}})
    user_1.await_msg({"info":{"payload": {"reply": "reject"}}})

    print('===== user_3 try to chat with user_1')
    user_start_chat(user_3, user_1)
    user_leave_chat(user_3, user_1)

    print('======= get user_1 history chat')
    user_1.send_wait({"get": {"topic": "me", "what": "sub"}}, {"meta": {"topic": "me", "sub": []}})

    print('======= user_3 disconnect  ======')
    user_3.ws.close()
    user_1.await_msg({"pres": {"topic": "me", "src": user_3.user_id, "what": "off"}})
    user_1.send_wait({"get": {"topic": "me", "what": "sub"}}, {"meta": {"topic": "me", "sub": []}})

    user_1.join()
    user_2.join()


def remote_user():
    users = []
    for i in range(10):
        user = User(str(1234567893+i), 32)
        user.start()
        users.append(user)
    time.sleep(1)
    for idx, user in enumerate(users):
        user.login(f"TinodeWeb/0.22.8 (Edge/114.{idx}; Mac); tinodejs/0.22.8")
        user.send({"get":{"topic":"mercGrp", "what": "rec"}})
        user.send_wait({"pub": {"topic": "mercGrp", "content": f"{user.user_id} send message", "noecho": True, "head": user.basic_info}})
    
    for user in users:
        user.join()
        break


remote_user()