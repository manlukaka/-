import re
import sys
import threading

class GroupManager:
    def __init__(self):
        self.scores = {}
        self.lock = threading.Lock()

    def initialize(self, num_groups: int) -> int:
        with self.lock:
            self.scores = {i: 0 for i in range(1, num_groups + 1)}
        return len(self.scores)

    def update_score(self, group_id: int, delta: int) -> bool:
        with self.lock:
            if group_id in self.scores:
                self.scores[group_id] += delta
                return True
            return False

    def print_status(self):
        with self.lock:
            print("\n====== 实时积分榜 ======")
            for group_id, score in self.scores.items():
                print(f"第 {group_id} 组:\t{score} 分")
            print("========================\n")

class CommandParser:
    def __init__(self):
        # 匹配规则：支持阿拉伯数字与中文数字混合，[\W_]*? 用于过滤识别产生的标点符号
        self.pattern = re.compile(
            r"(?:第)?([0-9一二两三四五六七八九十]+)[\W_]*?(?:组|队|小组)[\W_]*?(加|扣|减)[\W_]*?([0-9一二两三四五六七八九十百]+)[\W_]*?分"
        )
        self.num_map = {
            '一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5, 
            '六': 6, '七': 7, '八': 8, '九': 9, '十': 10, '零': 0
        }

    def _convert_to_int(self, num_str: str) -> int:
        """将混合字符串（阿拉伯数字或中文数字）转换为整数"""
        if num_str.isdigit():
            return int(num_str)
        
        result = 0
        tmp = 0
        for char in num_str:
            if char in self.num_map:
                val = self.num_map[char]
                if val == 10:
                    if tmp == 0: tmp = 1
                    result += tmp * 10
                    tmp = 0
                else:
                    tmp = val
        result += tmp
        return result

    def parse(self, text: str):
        clean_text = text.replace(" ", "")
        match = self.pattern.search(clean_text)
        
        if match:
            try:
                group_str = match.group(1)
                action = match.group(2)
                value_str = match.group(3)
                
                group_id = self._convert_to_int(group_str)
                value = self._convert_to_int(value_str)
                
                delta = value if action == "加" else -value
                return group_id, delta
            except Exception:
                return None, None
        return None, None

def main():
    manager = GroupManager()
    parser = CommandParser()

    # 1. 终端初始化
    while True:
        try:
            user_input = input("[系统设置] 请输入本节课的小组数量: ").strip()
            num_groups = int(user_input)
            if num_groups > 0:
                break
            print("[错误] 小组数量必须 > 0。")
        except ValueError:
            print("[错误] 无效输入，请输入整数。")
        except (EOFError, KeyboardInterrupt):
            print("\n[系统] 中断初始化。")
            sys.exit(0)

    initialized_count = manager.initialize(num_groups)
    print(f"[系统就绪] 初始化 {initialized_count} 个小组。")
    print("-> 正在监听语音流 (输入 '退出', 'exit' 结束, 输入 '状态' 查看积分)...\n")

    # 2. 核心事件循环
    while True:
        try:
            asr_text = input("(等待 ASR 输入) > ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not asr_text:
            continue

        command = asr_text.lower()
        if command in ["退出", "exit"]:
            print("[系统] 收到终止指令。")
            break
        elif command in ["状态", "status"]:
            manager.print_status()
            continue

        # 3. 语义解析与执行
        target_group, score_delta = parser.parse(asr_text)
        
        if target_group is not None and score_delta is not None:
            if manager.update_score(target_group, score_delta):
                action_str = "+" if score_delta > 0 else ""
                print(f"[执行成功] 目标: 第 {target_group} 组 | 操作: {action_str}{score_delta}")
            else:
                print(f"[执行异常] 第 {target_group} 组不存在。")
        else:
            print(f"[日志] 未解析出有效指令: \"{asr_text}\"")

    print("\n[系统] 进程终止，最终数据结算：")
    manager.print_status()

if __name__ == "__main__":
    main()