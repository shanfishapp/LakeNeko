import json
import threading
import uuid
import httpx
import os
from typing import Dict, Any, Callable
# --- 更新 pb2 文件导入方式 ---
from proto import send_message_pb2
from proto import list_message_pb2
from proto import conversation_pb2 # 假设这个对应 get_conversation_list 的 proto
# -------------------------

class APIHandler:
    def __init__(self):
        # --- 修正 URL，移除 's' ---
        self.base_url = "https://chat-go.jwzhd.com"  # 根据实际情况修改
        self.web_base_url = "https://chat-web-go.jwzhd.com" # Web API 的基础 URL
        self.client = httpx.Client()
        self.token = None
        self.user_info = None # 新增：存储用户信息
        self.user_id = None   # 新增：存储用户 ID
    
    def save_token(self, token: str):
        """
        保存token到文件
        """
        self.token = token
        try:
            # 使用您之前的配置文件路径
            from pathlib import Path
            config_file = Path("appdata") / "yhchat_config.json"
            config_file.parent.mkdir(exist_ok=True)
            with open(config_file, "w", encoding='utf-8') as f:
                json.dump({"token": token}, f, ensure_ascii=False, indent=4)
            print(f"Token 已保存到 {config_file}")
        except Exception as e:
            print(f"保存token失败: {e}")
    
    def load_token(self):
        """
        从文件加载token
        """
        try:
            # 使用您之前的配置文件路径
            from pathlib import Path
            config_file = Path("appdata") / "yhchat_config.json"
            if config_file.exists():
                with open(config_file, "r", encoding='utf-8') as f:
                    config = json.load(f)
                    self.token = config.get("token")
                print(f"从 {config_file} 加载 token: {self.token is not None}")
                return self.token
        except Exception as e:
            print(f"加载token失败: {e}")
        return None

    def load_user_info(self):
        """从配置文件加载用户信息 (如果之前保存过) - 可选，当前只存内存"""
        # 如果需要持久化用户信息，可以实现类似 load_token 的逻辑
        pass

    def save_user_info(self):
        """保存用户信息到配置文件 (如果需要) - 可选"""
        # 如果需要持久化用户信息，可以实现类似 save_token 的逻辑
        pass
    
    def email_login(self, email: str, password: str, device_id: str, platform: str, callback: Callable[[Dict[str, Any]], None] = None):
        """
        用户邮箱密码登录
        """
        def _login():
            try:
                url = f"{self.base_url}/v1/user/email-login"
                payload = {
                    "email": email,
                    "password": password,
                    "deviceId": device_id,
                    "platform": platform
                }
                
                response = self.client.post(url, json=payload)
                
                # 尝试解析 JSON 响应
                try:
                    result = response.json()
                except json.JSONDecodeError:
                    print(f"登录响应 JSON 解析失败: {response.text}")
                    result = {"code": -1, "data": {}, "msg": "Invalid JSON response"}
                
                # 如果登录成功，保存token
                if result.get("code") == 1:
                    token = result.get("data", {}).get("token")
                    if token:
                        self.save_token(token)
                
                if callback:
                    callback(result)
            except Exception as e:
                if callback:
                    callback({"code": -1, "data": {}, "msg": f"请求失败: {str(e)}"})
        
        # 在新线程中执行请求
        thread = threading.Thread(target=_login)
        thread.daemon = True
        thread.start()
        return thread

    # --- 新增方法：获取用户信息 ---
    def get_user_info(self, callback: Callable[[Dict[str, Any]], None] = None):
        """
        获取用户自身信息
        """
        def _get_info():
            if not self.token:
                if callback:
                    callback({"code": -100, "data": {}, "msg": "No token available"})
                return

            try:
                url = f"{self.web_base_url}/v1/user/info"
                
                headers = {"token": self.token}
                
                response = self.client.get(url, headers=headers)
                
                try:
                    result = response.json()
                    code = result.get("code")
                    msg = result.get("msg")
                    data = result.get("data", {})

                    if code == 1:
                        user_data = data.get("user", {})
                        user_id = user_data.get("userId")
                        if user_id:
                            self.user_id = user_id
                            self.user_info = user_data # 存储完整用户信息
                            print(f"获取用户信息成功，用户ID: {self.user_id}")
                        else:
                            print("获取用户信息响应中缺少 userId")
                            result = {"code": -1, "data": {}, "msg": "Response missing userId"}
                    else:
                        print(f"获取用户信息失败: {msg}, Code: {code}")

                    if callback:
                        callback(result)
                except json.JSONDecodeError:
                    print(f"获取用户信息响应 JSON 解析失败: {response.text}")
                    if callback:
                        callback({"code": -1, "data": {}, "msg": "Invalid JSON response"})

            except Exception as e:
                print(f"获取用户信息请求失败: {e}")
                if callback:
                    callback({"code": -1, "data": {}, "msg": f"Request failed: {str(e)}"})
        
        # 在新线程中执行请求
        thread = threading.Thread(target=_get_info)
        thread.daemon = True
        thread.start()
        return thread

    # --- 修正方法：发送消息 ---
    def send_message_raw(self, chat_id: str, chat_type: int, text: str, callback: Callable[[bytes, int, str], None] = None):
        """
        发送文本消息 (返回原始二进制数据)
        """
        def _send_msg():
            if not self.token:
                if callback:
                    callback(None, -100, "No token available")
                return

            try:
                # --- 修正 URL，移除 's' ---
                url = f"{self.base_url}/v1/msg/send-message"
                
                # 添加认证头
                headers = {"token": self.token}
                
                # 构建 protobuf 请求体
                req_body = send_message_pb2.send_message_send()
                
                req_body.msg_id = uuid.uuid4().hex
                req_body.chat_id = chat_id
                req_body.chat_type = chat_type
                req_body.content_type = 1 # 1 代表文本消息
                
                # 设置消息内容
                req_body.data.text = text

                binary_req_body = req_body.SerializeToString()

                response = self.client.post(url, headers=headers, content=binary_req_body) # 发送二进制内容
                
                if response.status_code == 200:
                    binary_data = response.content
                    if callback:
                        callback(binary_data, 200, "Success") # 传递二进制数据、状态码和消息
                else:
                    if callback:
                        callback(None, response.status_code, f"HTTP Error {response.status_code}")

            except Exception as e:
                if callback:
                    callback(None, -1, f"请求失败: {str(e)}")
        
        # 在新线程中执行请求
        thread = threading.Thread(target=_send_msg)
        thread.daemon = True
        thread.start()
        return thread

    # --- 新增方法：获取原始 protobuf 数据 ---
    def get_conversation_list_raw(self, callback: Callable[[bytes, int, str], None] = None):
        """
        获取对话列表 (返回原始二进制数据)
        """
        def _get_list():
            try:
                url = f"{self.base_url}/v1/conversation/list"
                
                # 添加认证头 (根据您的 proto 定义，应该是 'token')
                headers = {}
                if self.token:
                    headers["token"] = self.token
                
                response = self.client.post(url, headers=headers) # 注意：是 POST
                
                if response.status_code == 200:
                    binary_data = response.content
                    if callback:
                        callback(binary_data, 200, "Success") # 传递二进制数据、状态码和消息
                else:
                    if callback:
                        callback(None, response.status_code, f"HTTP Error {response.status_code}")

            except Exception as e:
                if callback:
                    callback(None, -1, f"请求失败: {str(e)}")
        
        # 在新线程中执行请求
        thread = threading.Thread(target=_get_list)
        thread.daemon = True
        thread.start()
        return thread
    
    def get_conversation_list(self, callback: Callable[[Dict[str, Any]], None] = None):
        """
        获取对话列表 (尝试返回 JSON，可能用于错误处理)
        """
        def _get_list():
            try:
                url = f"{self.base_url}/v1/conversation/list"
                
                # 添加认证头
                headers = {}
                if self.token:
                    headers["token"] = self.token # 根据 proto
                
                response = self.client.post(url, headers=headers) # 注意：是 POST
                
                # 尝试解析 JSON 响应 (可能在错误时返回 JSON)
                try:
                    result = response.json()
                except json.JSONDecodeError:
                    # 如果不是 JSON，可能是 protobuf 或其他格式
                    print(f"获取列表响应非 JSON 格式，状态码: {response.status_code}, 内容: {response.text[:200]}...") # 调试
                    result = {"code": -1, "data": {}, "msg": f"Non-JSON response, status {response.status_code}"}
                
                if callback:
                    callback(result)
            except Exception as e:
                if callback:
                    callback({"code": -1, "data": {}, "msg": f"请求失败: {str(e)}"})
        
        # 在新线程中执行请求
        thread = threading.Thread(target=_get_list)
        thread.daemon = True
        thread.start()
        return thread

    # --- 新增方法：获取指定聊天的消息列表 ---
    def list_message_raw(self, chat_id: str, chat_type: int, msg_count: int = 50, msg_id: str = None, callback: Callable[[bytes, int, str], None] = None):
        """
        获取指定聊天的消息列表 (返回原始二进制数据)
        """
        def _list_msg():
            try:
                url = f"{self.base_url}/v1/msg/list-message"
                
                # 添加认证头
                headers = {"token": self.token} if self.token else {}
                
                # 构建 protobuf 请求体
                req_body = list_message_pb2.list_message_send()
                req_body.msg_count = msg_count
                if msg_id:
                    req_body.msg_id = msg_id
                req_body.chat_type = chat_type
                req_body.chat_id = chat_id
                
                binary_req_body = req_body.SerializeToString()

                response = self.client.post(url, headers=headers, content=binary_req_body) # 发送二进制内容
                
                if response.status_code == 200:
                    binary_data = response.content
                    if callback:
                        callback(binary_data, 200, "Success") # 传递二进制数据、状态码和消息
                else:
                    if callback:
                        callback(None, response.status_code, f"HTTP Error {response.status_code}")

            except Exception as e:
                if callback:
                    callback(None, -1, f"请求失败: {str(e)}")
        
        # 在新线程中执行请求
        thread = threading.Thread(target=_list_msg)
        thread.daemon = True
        thread.start()
        return thread

# 全局API处理器实例
api_handler = APIHandler()

def email_login(email: str, password: str, device_id: str, platform: str, callback: Callable[[Dict[str, Any]], None] = None):
    """
    用户邮箱密码登录接口
    """
    return api_handler.email_login(email, password, device_id, platform, callback)

# --- 新增函数：获取用户信息 ---
def get_user_info(callback: Callable[[Dict[str, Any]], None] = None):
    """
    获取用户自身信息接口
    """
    return api_handler.get_user_info(callback)

# --- 新增函数：发送消息 ---
def send_message_raw(chat_id: str, chat_type: int, text: str, callback: Callable[[bytes, int, str], None] = None):
    """
    发送文本消息接口 (返回原始二进制数据)
    """
    return api_handler.send_message_raw(chat_id, chat_type, text, callback)

def get_conversation_list(callback: Callable[[Dict[str, Any]], None] = None):
    """
    获取对话列表接口 (返回 JSON，可能用于错误处理)
    """
    return api_handler.get_conversation_list(callback)

# --- 新增函数：获取原始 protobuf 数据 ---
def get_conversation_list_raw(callback: Callable[[bytes, int, str], None] = None):
    """
    获取对话列表接口 (返回原始二进制数据)
    """
    return api_handler.get_conversation_list_raw(callback)

# --- 新增函数：获取指定聊天的消息列表 ---
def list_message_raw(chat_id: str, chat_type: int, msg_count: int = 50, msg_id: str = None, callback: Callable[[bytes, int, str], None] = None):
    """
    获取指定聊天的消息列表接口 (返回原始二进制数据)
    """
    return api_handler.list_message_raw(chat_id, chat_type, msg_count, msg_id, callback)