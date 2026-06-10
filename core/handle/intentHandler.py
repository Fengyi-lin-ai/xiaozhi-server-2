import json
import uuid
import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.connection import ConnectionHandler
from core.utils.dialogue import Message
from core.providers.tts.dto.dto import ContentType, TTSMessageDTO, SentenceType
from core.handle.helloHandle import checkWakeupWords
from plugins_func.register import Action, ActionResponse
from core.handle.sendAudioHandle import send_stt_message
from core.handle.reportHandle import enqueue_tool_report
from core.utils.util import remove_punctuation_and_length
from core.providers.tools.device_mcp.mcp_handler import call_mcp_tool
from core.utils.cache.manager import cache_manager, CacheType
import time

TAG = __name__


async def handle_user_intent(conn: "ConnectionHandler", text):
    # 预处理输入文本，处理可能的JSON格式
    try:
        if text.strip().startswith("{") and text.strip().endswith("}"):
            parsed_data = json.loads(text)
            if isinstance(parsed_data, dict) and "content" in parsed_data:
                text = parsed_data["content"]  # 提取content用于意图分析
                conn.current_speaker = parsed_data.get("speaker")  # 保留说话人信息
    except (json.JSONDecodeError, TypeError):
        pass

    # 检查是否有明确的退出命令
    _, filtered_text = remove_punctuation_and_length(text)
    if await check_direct_exit(conn, filtered_text):
        return True

    # 检查是否是唤醒词
    if await checkWakeupWords(conn, filtered_text):
        return True

    if conn.intent_type == "function_call":
        # 使用支持function calling的聊天方法,不再进行意图分析
        return False

    device_status = cache_manager.get(CacheType.DEVICE_STATUS,conn.device_id)
    resultJson = None
    lowPowerFlag = False
    if(conn.batchId is not None and conn.batchId == "E2"):
        lowPowerFlag = False
    else:
        if(device_status is None):
            # 调用设备端MCP工具
            result = await call_mcp_tool(conn, conn.mcp_client, "self_get_device_status", {})
            conn.logger.bind(tag=TAG).info(f"设备状态: {result}")
            if isinstance(result, str):
                try:
                    resultJson = json.loads(result)
                except Exception as e:
                    pass
            resultJson["time"] = time.time()
            cache_manager.set(CacheType.DEVICE_STATUS, conn.device_id, resultJson)
            battery = str(resultJson['battery'].get("level", 0))
            if int(battery) < 20:
                speak_txt(conn, "电量不足"+battery+"%,请及时充电")
                lowPowerFlag = True
                return lowPowerFlag
        else:
            resultJson = device_status
            time1 = resultJson.get("time", 0)
            time2 = time.time()
            time3 = time2 - time1
            if time3 > 300:
                # 调用设备端MCP工具
                result = await call_mcp_tool(conn, conn.mcp_client, "self_get_device_status", {})
                conn.logger.bind(tag=TAG).info(f"设备状态: {result}")
                if isinstance(result, str):
                    try:
                        resultJson = json.loads(result)
                    except Exception as e:
                        pass
                resultJson["time"] = time.time()
                cache_manager.set(CacheType.DEVICE_STATUS, conn.device_id, resultJson)
                battery = str(resultJson['battery'].get("level", 0))
                if int(battery) < 20:
                    speak_txt(conn, "电量不足"+battery+"%,请及时充电")
                    lowPowerFlag = True
                    return lowPowerFlag
        
    intent_result = None
    # 如果不是设备音量调节命令，则进行意图分析
    if '音量调节' in text or '声音调节' in text or '调节音量' in text or '调节声音' in text :
        # 使用字符串强匹配调节的声音数值
        volume = 100
        if '最小' in text or '0' in text :
            volume = 0
        if '10' in text:
            volume = 10
        if '20' in text:
            volume = 20
        if '30' in text:
            volume = 30
        if '40' in text:
            volume = 40
        if '50' in text:
            volume = 50
        if '60' in text:
            volume = 60
        if '70' in text:
            volume = 70
        if '80' in text:
            volume = 80
        if '90' in text:
            volume = 90
        if '最大' in text or '100' in text:
            volume = 100
        # intent_result = await analyze_intent_with_llm(conn, text)
        intent_result = f'{{"function_call": {{ "name": "self_get_device_status", "arguments": {{ "volume": {volume} }} }} }}'
    elif ('播放' in text and '歌曲'in text) or ('播放' in text and '音乐'in text) or ('听' in text and '音乐'in text):
        if conn.isOpenSong  == 1:
            # 使用LLM进行意图分析1
            intent_result = await analyze_intent_with_llm(conn, text)
        else:
            # 使用LLM进行意图分析
            intent_result = '{"function_call": {"name": "continue_chat"}}'
    elif ('天气' in text and conn.isOpenWeather == 1) or ('油价' in text ):
        # 使用LLM进行意图分析
        intent_result = await analyze_intent_with_llm(conn, text)
    elif '开灯' in text or '关灯' in text or '打开灯光' in text or '关闭灯光' in text :
        if '开灯' in text or '打开灯光' in text:
            intent_result = f'{{"function_call": {{ "name": "self_lamp_turn_on" }} }}'
        if '关灯' in text or '关闭灯光' in text:
            intent_result = f'{{"function_call": {{ "name": "self_lamp_turn_off" }} }}'
    elif '向前走' in text or '前进' in text or '向后退' in text or '后退' in text or '向左转' in text or '向右转' in text :
        if '向前走' in text or '前进' in text:
            intent_result = f'{{"function_call": {{ "name": "self_advance" }} }}'
        if '向后退' in text or '后退' in text:
            intent_result = f'{{"function_call": {{ "name": "self_back" }} }}'
        if '向左转' in text:
            intent_result = f'{{"function_call": {{ "name": "self_turn_left" }} }}'
        if '向右转' in text:
            intent_result = f'{{"function_call": {{ "name": "self_turn_right" }} }}'
    elif '跳舞' in text:
        intent_result = f'{{"function_call": {{ "name": "self_dance" }} }}'
    elif '停下来' in text or '停止' in text:
        intent_result = f'{{"function_call": {{ "name": "self_stop" }} }}'
    elif '诵读' in text:
        intent_result = await analyze_intent_with_llm(conn, text)
    else:
        intent_result = '{"function_call": {"name": "continue_chat"}}'

    if not intent_result:
        return False
    # 会话开始时生成sentence_id
    conn.sentence_id = str(uuid.uuid4().hex)
    # 处理各种意图
    return await process_intent_result(conn, intent_result, text)


async def check_direct_exit(conn: "ConnectionHandler", text):
    """检查是否有明确的退出命令"""
    _, text = remove_punctuation_and_length(text)
    cmd_exit = conn.cmd_exit
    for cmd in cmd_exit:
        if text == cmd:
            conn.logger.bind(tag=TAG).info(f"识别到明确的退出命令: {text}")
            await send_stt_message(conn, text)
            await conn.close()
            return True
    return False


async def analyze_intent_with_llm(conn: "ConnectionHandler", text):
    """使用LLM分析用户意图"""
    if not hasattr(conn, "intent") or not conn.intent:
        conn.logger.bind(tag=TAG).warning("意图识别服务未初始化")
        return None

    # 对话历史记录
    dialogue = conn.dialogue
    try:
        intent_result = await conn.intent.detect_intent(conn, dialogue.dialogue, text)
        return intent_result
    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"意图识别失败: {str(e)}")

    return None


async def process_intent_result(
    conn: "ConnectionHandler", intent_result, original_text
):
    """处理意图识别结果"""
    try:
        # 尝试将结果解析为JSON
        intent_data = json.loads(intent_result)

        # 检查是否有function_call
        if "function_call" in intent_data:
            # 直接从意图识别获取了function_call
            conn.logger.bind(tag=TAG).debug(
                f"检测到function_call格式的意图结果: {intent_data['function_call']['name']}"
            )
            function_name = intent_data["function_call"]["name"]
            if function_name == "continue_chat":
                return False

            if function_name == "result_for_context":
                await send_stt_message(conn, original_text)
                conn.client_abort = False

                def process_context_result():
                    conn.dialogue.put(Message(role="user", content=original_text))

                    from core.utils.current_time import get_current_time_info

                    current_time, today_date, today_weekday, lunar_date = (
                        get_current_time_info()
                    )

                    # 构建带上下文的基础提示
                    context_prompt = f"""当前时间：{current_time}
                                        今天日期：{today_date} ({today_weekday})
                                        今天农历：{lunar_date}

                                        请根据以上信息回答用户的问题：{original_text}"""

                    response = conn.intent.replyResult(context_prompt, original_text)
                    speak_txt(conn, response)

                conn.executor.submit(process_context_result)
                return True

            function_args = {}
            if "arguments" in intent_data["function_call"]:
                function_args = intent_data["function_call"]["arguments"]
                if function_args is None:
                    function_args = {}
            # 确保参数是字符串格式的JSON
            if isinstance(function_args, dict):
                function_args = json.dumps(function_args)

            function_call_data = {
                "name": function_name,
                "id": str(uuid.uuid4().hex),
                "arguments": function_args,
            }

            await send_stt_message(conn, original_text)
            conn.client_abort = False

            # 准备工具调用参数
            tool_input = {}
            if function_args:
                if isinstance(function_args, str):
                    tool_input = json.loads(function_args) if function_args else {}
                elif isinstance(function_args, dict):
                    tool_input = function_args

            # 上报工具调用
            enqueue_tool_report(conn, function_name, tool_input)

            # 使用executor执行函数调用和结果处理
            def process_function_call():
                conn.dialogue.put(Message(role="user", content=original_text))

                # 工具调用超时时间
                tool_call_timeout = int(conn.config.get("tool_call_timeout", 30))
                # 使用统一工具处理器处理所有工具调用
                try:
                    result = asyncio.run_coroutine_threadsafe(
                        conn.func_handler.handle_llm_function_call(
                            conn, function_call_data
                        ),
                        conn.loop,
                    ).result(timeout=tool_call_timeout)
                except Exception as e:
                    conn.logger.bind(tag=TAG).error(f"工具调用失败: {e}")
                    result = ActionResponse(
                        action=Action.ERROR, result="工具调用超时，请一会再试下哈", response="工具调用超时，请一会再试下哈"
                    )

                # 上报工具调用结果
                if result:
                    enqueue_tool_report(conn, function_name, tool_input, str(result.result) if result.result else None, report_tool_call=False)

                    if result.action == Action.RESPONSE:  # 直接回复前端
                        text = result.response
                        if text is not None:
                            speak_txt(conn, text)
                    elif result.action == Action.REQLLM:  # 调用函数后再请求llm生成回复
                        text = result.result
                        conn.dialogue.put(Message(role="tool", content=text))
                        llm_result = conn.intent.replyResult(text, original_text)
                        if llm_result is None:
                            llm_result = text
                        speak_txt(conn, llm_result)
                    elif (
                        result.action == Action.NOTFOUND
                        or result.action == Action.ERROR
                    ):
                        text = result.response if result.response else result.result
                        if text is not None:
                            speak_txt(conn, text)
                    elif function_name != "play_music":
                        # For backward compatibility with original code
                        # 获取当前最新的文本索引
                        text = result.response
                        if text is None:
                            text = result.result
                        if text is not None:
                            speak_txt(conn, text)

            # 将函数执行放在线程池中
            conn.executor.submit(process_function_call)
            return True
        return False
    except json.JSONDecodeError as e:
        conn.logger.bind(tag=TAG).error(f"处理意图结果时出错: {e}")
        return False


def speak_txt(conn: "ConnectionHandler", text):
    # 记录文本到 sentence_id 映射
    conn.tts.store_tts_text(conn.sentence_id, text)

    conn.tts.tts_text_queue.put(
        TTSMessageDTO(
            sentence_id=conn.sentence_id,
            sentence_type=SentenceType.FIRST,
            content_type=ContentType.ACTION,
        )
    )
    conn.tts.tts_one_sentence(conn, ContentType.TEXT, content_detail=text)
    conn.tts.tts_text_queue.put(
        TTSMessageDTO(
            sentence_id=conn.sentence_id,
            sentence_type=SentenceType.LAST,
            content_type=ContentType.ACTION,
        )
    )
    conn.dialogue.put(Message(role="assistant", content=text))
