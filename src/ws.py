# ws.py (修正版，基于您提供的可工作版本)
import asyncio
import json
import websockets
import time
import threading
from typing import Callable, Dict, Any
import proto.receive_pb2 as receive_pb2 # 使用您提供的可工作的 protobuf 模块

class WebSocketHandler:
    def __init__(self, token: str, user_id: str, platform: str = "windows", device_id: str = "flet_ws_client"):
        self.token = token
        self.user_id = user_id
        self.platform = platform
        self.device_id = device_id
        self.ws_url = "wss://chat-ws-go.jwzhd.com/ws"
        self.ws_connection = None
        self.ws_task = None
        self.heartbeat_task = None
        self.connected = False
        self.connection_status_callback = None
        self.message_callback = None
        self.draft_callback = None
        self.edit_callback = None
        self.file_send_callback = None
        self.stream_callback = None
        self._stop_event = threading.Event()

    def set_callbacks(
        self,
        connection_status: Callable[[bool], None] = None,
        message: Callable[[Dict[str, Any]], None] = None,
        draft: Callable[[Dict[str, Any]], None] = None,
        edit: Callable[[Dict[str, Any]], None] = None,
        file_send: Callable[[Dict[str, Any]], None] = None,
        stream: Callable[[Dict[str, Any]], None] = None,
    ):
        """设置回调函数"""
        self.connection_status_callback = connection_status
        self.message_callback = message
        self.draft_callback = draft
        self.edit_callback = edit
        self.file_send_callback = file_send
        self.stream_callback = stream

    def start(self):
        """启动 WebSocket 连接和心跳任务"""
        if self.ws_task and not self.ws_task.done():
            print("WebSocket task is already running.")
            return

        self._stop_event.clear()
        def run_ws_loop():
            asyncio.run(self._run_websocket())

        ws_thread = threading.Thread(target=run_ws_loop)
        ws_thread.daemon = True
        ws_thread.start()

    def stop(self):
        """停止 WebSocket 连接和心跳任务"""
        self._stop_event.set()
        if self.heartbeat_task and not self.heartbeat_task.done():
            self.heartbeat_task.cancel()
        if self.ws_task and not self.ws_task.done():
            self.ws_task.cancel()

    async def _run_websocket(self):
        """WebSocket 主循环"""
        while not self._stop_event.is_set():
            try:
                async with websockets.connect(self.ws_url) as websocket:
                    self.ws_connection = websocket
                    print("WebSocket connected.")
                    self._update_connection_status(True)

                    # 建立连接后立即登录
                    await self._login()
                    # 登录成功后启动心跳
                    self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())

                    # 监听消息 - 接收二进制数据
                    async for message in websocket:
                        await self._handle_message(message)

            except websockets.exceptions.ConnectionClosed as e:
                print(f"WebSocket closed: {e.code} - {e.reason}")
                self._update_connection_status(False)
            except websockets.exceptions.WebSocketException as e:
                print(f"WebSocket error: {e}")
                self._update_connection_status(False)
            except Exception as e:
                print(f"Unexpected error in WebSocket loop: {e}")
                self._update_connection_status(False)

            # 重连逻辑
            if not self._stop_event.is_set():
                print("Attempting to reconnect...")
                await asyncio.sleep(5)

    async def _login(self):
        """发送登录消息"""
        login_data = {
            "seq": str(int(time.time() * 1000)),
            "cmd": "login",
            "data": {
                "userId": self.user_id,
                "token": self.token,
                "platform": self.platform,
                "deviceId": self.device_id
            }
        }
        await self.ws_connection.send(json.dumps(login_data, ensure_ascii=False))
        print("Sent login message.")

    async def _heartbeat_loop(self):
        """心跳循环"""
        while not self._stop_event.is_set():
            await asyncio.sleep(30)
            if self.ws_connection and self.connected:
                try:
                    heartbeat_data = {
                        "seq": str(int(time.time() * 1000)),
                        "cmd": "heartbeat",
                        "data": {}
                    }
                    await self.ws_connection.send(json.dumps(heartbeat_data, ensure_ascii=False))
                    print("Sent heartbeat.")
                except websockets.exceptions.WebSocketException as e:
                    print(f"Heartbeat failed: {e}")
                    self._update_connection_status(False)
                    break

    async def _handle_message(self, message):
        """处理接收到的消息"""
        try:
            # 如果是文本消息（如心跳响应）
            if isinstance(message, str):
                await self._handle_text_message(message)
            # 如果是二进制消息（protobuf数据）
            elif isinstance(message, bytes):
                await self._handle_binary_message(message)
            else:
                print(f"Unknown message type: {type(message)}")
                
        except Exception as e:
            print(f"Error handling message: {e}")

    async def _handle_text_message(self, text_data: str):
        """处理文本消息（如心跳响应）"""
        try:
            message_data = json.loads(text_data)
            cmd = message_data.get("cmd")
            
            if cmd == "heartbeat_ack":
                print("Received heartbeat ack.")
                self._update_connection_status(True)
            else:
                print(f"Unknown text command: {cmd}")
                
        except json.JSONDecodeError:
            print(f"Failed to decode JSON message: {text_data}")

    async def _handle_binary_message(self, binary_data: bytes):
        """处理二进制 protobuf 消息"""
        try:
            # 先解析事件头来判断消息类型
            event_header = receive_pb2.EventNameData()
            event_header.ParseFromString(binary_data)
            
            event_type = event_header.event.event_type
            print(f"Received binary message, event type: {event_type}")
            
            # 只处理 push_message 类型
            if event_type == "push_message":
                await self._handle_push_message(binary_data)
            else:
                print(f"Skipping non-push_message event: {event_type}")
                
        except Exception as e:
            print(f"Failed to parse binary message header: {e}")

    async def _handle_push_message(self, binary_data: bytes):
        """处理推送消息"""
        try:
            # 完整解析 Receive 消息
            receive_msg = receive_pb2.Receive()
            receive_msg.ParseFromString(binary_data)
            
            # 提取消息数据
            message_data = receive_msg.event.message
            
            # 构建消息信息字典
            msg_info = {
                "msg_id": message_data.msg_id,
                "recv_id": message_data.recv_id,
                "chat_id": message_data.chat_id,
                "chat_type": message_data.chat_type,
                "send_time": message_data.send_time,
                "content_type": message_data.content_type,  # 确保包含 content_type
                "sender_id": message_data.sender.sender_id,
                "sender_name": message_data.sender.sender_nick_name,
                "content": message_data.content.text,
                "quote_msg_id": getattr(message_data, 'quote_msg_id', None),
            }
            
            print(f"Processed push message - Type: {msg_info['content_type']}, ID: {msg_info['msg_id']} from {msg_info['sender_name']}")
            
            # 调用消息回调
            if self.message_callback:
                self.message_callback(msg_info)
                
        except Exception as e:
            print(f"Error processing push message: {e}")

    def _update_connection_status(self, status: bool):
        """更新连接状态并调用回调"""
        self.connected = status
        if self.connection_status_callback:
            self.connection_status_callback(status)

    async def send_draft_sync(self, chat_id: str, draft_text: str):
        """发送草稿同步消息"""
        if not self.ws_connection or not self.connected:
            print("Cannot send draft sync: WebSocket not connected.")
            return

        draft_data = {
            "seq": str(int(time.time() * 1000)),
            "cmd": "inputInfo",
            "data": {
                "chatId": chat_id,
                "input": draft_text,
                "deviceId": self.device_id
            }
        }
        try:
            await self.ws_connection.send(json.dumps(draft_data, ensure_ascii=False))
            print(f"Sent draft sync for chat {chat_id}.")
        except websockets.exceptions.WebSocketException as e:
            print(f"Failed to send draft sync: {e}")