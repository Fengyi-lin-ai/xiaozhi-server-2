import asyncio
import paho.mqtt.client as mqtt
from config.logger import setup_logging

TAG = "MQTTClient"
logger = setup_logging()

class MQTTClient:
    def __init__(self, config):
        self.config = config
        self.client = mqtt.Client()
        self.connected = False
        self.message_callback = None  # 消息处理回调函数

        # 配置认证
        if config.get("mqtt_username"):
            self.client.username_pw_set(
                config["mqtt_username"], 
                config["mqtt_password"]
            )

        # 设置回调
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            logger.info("MQTT连接成功")
            # 订阅设备消息主题（例如：xiaozhi/device/+/command）
            topic = f"{self.config['mqtt_topic_prefix']}+/command"
            self.client.subscribe(topic)
        else:
            logger.error(f"MQTT连接失败，错误码: {rc}")

    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        logger.warning(f"MQTT断开连接，错误码: {rc}")
        # 自动重连逻辑
        asyncio.create_task(self.reconnect())

    def _on_message(self, client, userdata, msg):
        if self.message_callback:
            # 调用外部消息处理函数（如原WebSocket的_route_message）
            self.message_callback(msg.topic, msg.payload)

    async def connect(self):
        """连接到MQTT Broker"""
        try:
            self.client.connect(
                self.config["mqtt_broker"],
                self.config["mqtt_port"],
                self.config["mqtt_keepalive"]
            )
            self.client.loop_start()  # 启动网络循环（非阻塞）
        except Exception as e:
            logger.error(f"MQTT连接异常: {e}")

    async def reconnect(self):
        """重连逻辑"""
        for i in range(5):  # 最多重试5次
            try:
                await asyncio.sleep(2 **i)  # 指数退避
                await self.connect()
                if self.connected:
                    return
            except Exception as e:
                logger.error(f"重连失败 ({i+1}/5): {e}")
        logger.error("MQTT重连失败，已达到最大重试次数")

    def publish(self, topic, payload, qos=1):
        """发布消息到指定主题"""
        if self.connected:
            self.client.publish(topic, payload, qos=qos)
        else:
            logger.error("MQTT未连接，无法发布消息")

    def set_message_callback(self, callback):
        """设置消息处理回调函数"""
        self.message_callback = callback
