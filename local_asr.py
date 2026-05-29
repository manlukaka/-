import sys
import queue
import json
import sounddevice as sd
from vosk import Model, KaldiRecognizer

# 设置音频队列
q = queue.Queue()

# 麦克风音频回调函数
def callback(indata, frames, time, status):
    if status:
        print(status, file=sys.stderr)
    q.put(bytes(indata))

def main():
    print("[ASR模块] 正在加载本地离线模型，请稍候...", file=sys.stderr)
    try:
        # 加载当前目录下的 "model" 文件夹
        model = Model("model")
    except Exception as e:
        print("\n[错误] 未找到模型。请确保下载了Vosk模型并解压为当前目录下的 'model' 文件夹。", file=sys.stderr)
        sys.exit(1)

    # 采样率通常为 16000Hz 
    samplerate = 16000
    recognizer = KaldiRecognizer(model, samplerate)
    recognizer.SetWords(False)

    print("[ASR模块] 模型加载完毕。麦克风已开启，开始流式识别...\n", file=sys.stderr)

    try:
        # 打开默认麦克风进行录音
        with sd.RawInputStream(samplerate=samplerate, blocksize=8000, device=None,
                               dtype='int16', channels=1, callback=callback):
            while True:
                data = q.get()
                # 识别到完整的句子
                if recognizer.AcceptWaveform(data):
                    # Vosk 的输出是 JSON 格式字符串，我们提取其中的 'text' 字段
                    result_dict = json.loads(recognizer.Result())
                    text = result_dict.get("text", "")
                    
                    # Vosk 默认会在中文字符间加空格，我们将其去除
                    text = text.replace(" ", "")
                    
                    if text:
                        # 关键：将识别结果输出到 stdout，并通过 flush 立即推入管道
                        print(text, flush=True)
                
    except KeyboardInterrupt:
        print("\n[ASR模块] 停止录音。", file=sys.stderr)
    except Exception as e:
        print(f"\n[ASR模块] 发生异常: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()