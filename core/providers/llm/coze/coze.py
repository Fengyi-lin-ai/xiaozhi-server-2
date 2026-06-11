import datetime
import pytz
from config.logger import setup_logging
import json
import time
import re
from core.providers.llm.base import LLMProviderBase

# official coze sdk for Python [cozepy](https://github.com/coze-dev/coze-py)
from cozepy import COZE_CN_BASE_URL
from cozepy import (
    Coze,
    TokenAuth,
    Message,
    ChatEventType,
)  # noqa
from core.providers.llm.system_prompt import get_system_prompt_for_function
from core.utils.util import check_model_key
from core.utils.performance_logger import performance_logger

TAG = __name__
logger = setup_logging()


class LLMProvider(LLMProviderBase):
    def __init__(self, config):
        self.personal_access_token = config.get("personal_access_token")
        self.bot_id = str(config.get("bot_id"))
        self.user_id = str(config.get("user_id"))
        self.intimacy = ""
        self.intimacyRate = 0
        self.intimacyRule = ""
        self.isOpenMemory = 1
        if(config.get("isOpenMemory") is not None and config.get("isOpenMemory") != ""):
            self.isOpenMemory = config.get("isOpenMemory")
        if(config.get("intimacyRule") is not None and config.get("intimacyRule") != ""):
            self.intimacyRule = config.get("intimacyRule")
            if(config.get("intimacy") is not None and config.get("intimacy") != ""):
                self.intimacy = config.get("intimacy")
            else:
                self.intimacy = "陌生人"
            if(config.get("intimacyRate") is not None and config.get("intimacyRate") != ""):
                self.intimacyRate = config.get("intimacyRate")
            else:
                self.intimacyRate = 0
        self.session_conversation_map = {}  # 存储 session_id 和 conversation_id 的映射
        # 用于处理流式返回时括号内容被分割的情况
        self.bracket_buffer = ""  # 括号内累积的内容
        self.in_bracket = False   # 是否在括号内
        self.pending_text = ""    # 等待处理的括号前文本
        model_key_msg = check_model_key("CozeLLM", self.personal_access_token)
        if model_key_msg:
            logger.bind(tag=TAG).error(model_key_msg)

    def response(self, session_id, dialogue,device_id=None):
        # 记录 LLM 开始时间
        llm_start_time = time.monotonic()
        
        # 重置括号状态，确保每次请求都是独立的状态
        self.in_bracket = False
        self.bracket_buffer = ""
        self.pending_text = ""
        
        coze_api_token = self.personal_access_token
        coze_api_base = COZE_CN_BASE_URL
        system_msg = next(m for m in reversed(dialogue) if m["role"] == "system")
        match = False
        if system_msg is not None and system_msg != "":
            system_content = system_msg["content"]
            pattern = r'<memory>\s*(.*?)\s*</memory>'
            match = re.search(pattern, system_content, re.DOTALL)     

        last_msg = next(m for m in reversed(dialogue) if m["role"] == "user")

        coze = Coze(auth=TokenAuth(token=coze_api_token), base_url=coze_api_base)
        conversation_id = self.session_conversation_map.get(session_id)

        #  # testCode
        # conversation = coze.conversations.create(messages=[])
        # conversation_id = conversation.id
        # self.session_conversation_map[session_id] = conversation_id  # 更新映射
        # testMsg ="我最喜欢做我爸爸的工作了，可好玩了"
        # for testMsg2 in testMsg:
        #     yield testMsg2
        # # testCode

        # 如果没有找到conversation_id，则创建新的对话
        if not conversation_id:
            conversation = coze.conversations.create(messages=[])
            conversation_id = conversation.id
            self.session_conversation_map[session_id] = conversation_id  # 更新映射

        # 使用传入的 device_id 作为 user_id，如果未提供则使用默认值
        user_id = device_id if device_id is not None else self.user_id

        # 记录第一个token的时间
        first_token_time = None
        # 添加累积文本的变量
        accumulated_text = ""
        punctuation_marks = "。，！？；：…,.!?;:-"
        first_chats = False
        has_left_bracket = False
        additional_messages=[]
        if match and self.isOpenMemory == 1:
            system_content = match.group(1).strip()
            try:
                chat_history = json.loads(system_content)       
                if chat_history and len(chat_history) > 0:
                    for chat in chat_history:
                        if chat["role"] == "user":
                            additional_messages.append(Message.build_user_question_text(chat["content"]))
                        elif chat["role"] == "assistant":
                            additional_messages.append(Message.build_assistant_answer(chat["content"]))
            except json.JSONDecodeError as e:
                print(f"JSON 解析错误: {e}")
        additional_messages.append(Message.build_user_question_text(self.convert_date_to_timestamp(last_msg["content"])))
        for event in coze.chat.stream(
            bot_id=self.bot_id,
            user_id=user_id,
            parameters = {
                "bot_id": f"{self.bot_id}",
                "user_id": f"{user_id}",
                "intimacy": f"{self.intimacy}",
                "intimacy_rate": f"{self.intimacyRate}",
                "intimacy_rule": f"{self.intimacyRule}"
            },
            additional_messages=additional_messages,
            conversation_id=conversation_id,
        ):
            # 记录LLM结束时间（在第一个token生成时）
            if event.event == ChatEventType.CONVERSATION_MESSAGE_DELTA:
                if first_token_time is None:
                    first_token_time = time.monotonic()
                # 累积文本直到遇到标点符号
                content = event.message.content
                if content:
                    content = self.process_bracket_content(content)
                    accumulated_text += content
                    # 检查是否有标点符号
                    if any(char in punctuation_marks for char in content):
                        if(self.intimacy is not None and self.intimacy != ""):
                            if "intimacy" in accumulated_text:
                                json_obj = json.loads(accumulated_text)
                                if "intimacy" in json_obj:
                                    self.intimacy = json_obj["intimacy"]
                                if "intimacy_rate" in json_obj:
                                    self.intimacyRate = json_obj["intimacy_rate"]
                                accumulated_text = ""
                        # 遇到标点符号，yield累积的文本
                        yield accumulated_text
                        accumulated_text = ""
                    # 如果没有遇到标点符号，则继续累积不yield

        # 处理剩余未遇到标点符号的文本
        if accumulated_text:
            print(accumulated_text, end="", flush=True)
            yield accumulated_text

    def process_bracket_content(self, text):
        """
        移除文本中括号内的内容（包括中文括号 () 和英文括号 ()）
        支持流式返回，处理括号内容被分割到多个 chunk 的情况
        
        例如：
        流式输入 1: "我喜欢吃糖果 (耳尖"  -> 输出："我喜欢吃糖果"
        流式输入 2: "微微泛红，脸不"      -> 输出："" (在括号内，不输出)
        流式输入 3: "由自主得红) 你也喜欢吃糖果么" -> 输出："你也喜欢吃糖果么"
        
        完整示例："我喜欢吃糖果 (耳尖微微泛红，脸不由自主得红) 你也喜欢吃糖果么"
        输出："我喜欢吃糖果你也喜欢吃糖果么"
        """
        if not text:
            return ""
        
        result = ""
        i = 0
        while i < len(text):
            char = text[i]
            
            # 检查是否是左括号
            if char in '（(':
                # 进入括号模式，输出之前累积的文本
                self.in_bracket = True
                i += 1
                continue
            
            # 检查是否是右括号
            elif char in '）)':
                # 括号闭合，退出括号模式，继续处理后续文本
                self.in_bracket = False
                i += 1
                continue
            
            # 如果在括号内，跳过该字符
            if self.in_bracket:
                i += 1
                continue
            else:
                result += char
            
            i += 1
        
        return result

    def response_with_functions(self, session_id, dialogue, functions=None, device_id=None):
        if len(dialogue) == 2 and functions is not None and len(functions) > 0:
            # 第一次调用llm， 取最后一条用户消息，附加tool提示词
            last_msg = dialogue[-1]["content"]
            function_str = json.dumps(functions, ensure_ascii=False)
            modify_msg = get_system_prompt_for_function(function_str) + last_msg
            dialogue[-1]["content"] = modify_msg

        # 如果最后一个是 role="tool"，附加到user上
        if len(dialogue) > 1 and dialogue[-1]["role"] == "tool":
            assistant_msg = "\ntool call result: " + dialogue[-1]["content"] + "\n\n"
            while len(dialogue) > 1:
                if dialogue[-1]["role"] == "user":
                    dialogue[-1]["content"] = assistant_msg + dialogue[-1]["content"]
                    break
                dialogue.pop()

        for token in self.response(session_id, dialogue, device_id=device_id):
            yield token, None

    def convert_date_to_timestamp(self, text):
        """
        将文本中包含"前天","昨天","今天","明天","后天"的字符串替换为对应的时间戳
        格式为 %Y-%m-%d %H:%M:%S
        """
        now = datetime.datetime.now()
        
        # 定义相对日期映射
        date_map = {
            "大前天": -3,
            "前天": -2,
            "昨天": -1,
            "今天": 0,
            "明天": 1,
            "后天": 2,
            "大后天": 3
        }
        
        # 创建正则表达式模式，匹配所有相对日期
        pattern = '|'.join(re.escape(key) for key in date_map.keys())
        
        def replace_func(match):
            key = match.group()
            offset = date_map[key]
            target_date = now + datetime.timedelta(days=offset)
            return target_date.strftime("%Y年%m月%d日")
        
        # 替换所有匹配的相对日期
        result = re.sub(pattern, replace_func, text)
        if "oubi" in text or "欧比" in text or "有笔" in text or "有币" in text:
            result = "你好"
            return result
        else:
            return result

