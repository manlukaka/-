import sys
import os
import json
import queue
import threading
import asyncio
import websockets
import webview
import sounddevice as sd
from vosk import Model, KaldiRecognizer
import re

# 1. 语义解析器 (支持中文数字与过滤标点符号)
class CommandParser:
    def __init__(self):
        self.pattern = re.compile(
            r"(?:第)?([0-9一二两三四五六七八九十]+)[\W_]*?(?:组|队|小组)[\W_]*?(加|扣|减)[\W_]*?([0-9一二两三四五六七八九十百]+)[\W_]*?分"
        )
        self.num_map = {'一':1, '二':2, '两':2, '三':3, '四':4, '五':5, '六':6, '七':7, '八':8, '九':9, '十':10, '零':0}

    def _convert_to_int(self, num_str: str) -> int:
        if num_str.isdigit(): return int(num_str)
        result, tmp = 0, 0
        for char in num_str:
            if char in self.num_map:
                val = self.num_map[char]
                if val == 10:
                    if tmp == 0: tmp = 1
                    result += tmp * 10
                    tmp = 0
                else: tmp = val
        return result + tmp

    def parse(self, text: str):
        clean_text = text.replace(" ", "")
        match = self.pattern.search(clean_text)
        if match:
            try:
                group_id = self._convert_to_int(match.group(1))
                value = self._convert_to_int(match.group(3))
                delta = value if match.group(2) == "加" else -value
                return group_id, delta
            except: return None, None
        return None, None

# 全局变量
CONNECTED_CLIENTS = set()
q = queue.Queue()
parser = CommandParser()

# 2. WebSocket 服务端逻辑
async def ws_handler(websocket):
    CONNECTED_CLIENTS.add(websocket)
    try:
        await websocket.wait_closed()
    finally:
        CONNECTED_CLIENTS.remove(websocket)

async def broadcast_message(message_dict):
    if CONNECTED_CLIENTS:
        message_str = json.dumps(message_dict)
        websockets.broadcast(CONNECTED_CLIENTS, message_str)

def start_ws_server():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    start_server = websockets.serve(ws_handler, "0.0.0.0", 8765)
    loop.run_until_complete(start_server)
    loop.run_forever()

# 3. 麦克风录音回调
def audio_callback(indata, frames, time, status):
    if status: print(status, file=sys.stderr)
    q.put(bytes(indata))

# 4. ASR 核心线程逻辑
def start_asr_engine():
    # 修复：获取 exe 所在绝对路径，确保必定能找到 model 文件夹
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
        
    model_path = os.path.join(base_path, "model")
    
    try:
        model = Model(model_path)
    except Exception as e:
        print(f"模型加载失败，请确保 {model_path} 存在！", file=sys.stderr)
        return

    recognizer = KaldiRecognizer(model, 16000)
    recognizer.SetWords(False)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype='int16', channels=1, callback=audio_callback):
        while True:
            data = q.get()
            if recognizer.AcceptWaveform(data):
                result_dict = json.loads(recognizer.Result())
                text = result_dict.get("text", "").replace(" ", "")
                if text:
                    # 解析语义
                    group_id, delta = parser.parse(text)
                    if group_id is not None:
                        # 解析成功，广播加分指令
                        msg = {"type": "update", "group_id": group_id, "delta": delta, "raw_text": text}
                    else:
                        # 仅有语音，广播日志
                        msg = {"type": "log", "raw_text": text}
                    
                    # 异步推送给前端
                    loop.run_until_complete(broadcast_message(msg))

if __name__ == '__main__':
    # 1. 启动后台服务线程
    threading.Thread(target=start_ws_server, daemon=True).start()
    threading.Thread(target=start_asr_engine, daemon=True).start()

    # 2. 核心修复：获取真正的绝对路径，解决 404 报错
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    html_file_path = os.path.join(base_path, 'dashboard.html')

    # 3. 启动桌面 UI 窗口，传入绝对路径
    webview.create_window('智能课堂语音助手', url=html_file_path, width=1200, height=800)
    webview.start()