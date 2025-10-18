import flet as ft
from datetime import datetime
import threading
# --- 更新 pb2 文件导入方式 ---
from proto import conversation_pb2
from proto import list_message_pb2
from proto import send_message_pb2
from typing import Any, Dict
# 导入 ws 模块
import ws
# 导入 api 模块以获取 token 和 user_id
import api
# -------------------------
from screeninfo import get_monitors # 导入获取屏幕尺寸的库

# --- 模拟的特定聊天消息数据 (现在主要用远程数据) ---
# 模拟聊天 ID 为 1 的对话历史
messages_data_chat_1 = [
    {"user": "ShanFish", "text": "你好！今天过得怎么样？", "timestamp": "10:00 AM", "sender_id": "7356666"},
    {"user": "朋友 A", "text": "还不错，刚散完步回来。你呢？", "timestamp": "10:01 AM", "sender_id": "friend_a_id"},
    {"user": "ShanFish", "text": "我也挺好的，准备开始工作了。", "timestamp": "10:02 AM", "sender_id": "7356666"},
    {"user": "朋友 A", "text": "今天天气不错！", "timestamp": "10:05 AM", "sender_id": "friend_a_id"},
]

messages_data_chat_99 = [
    {"user": "系统消息", "text": "欢迎新成员 ShanFish 加入群聊！", "timestamp": "昨天", "sender_id": "system_id"},
    {"user": "群友 D", "text": "欢迎欢迎！", "timestamp": "昨天", "sender_id": "group_member_d_id"},
    {"user": "ShanFish", "text": "大家好！", "timestamp": "今天 9:30 AM", "sender_id": "7356666"},
    {"user": "群主 E", "text": "欢迎新成员，记得修改群昵称哦。", "timestamp": "今天 9:31 AM", "sender_id": "group_owner_e_id"},
]

# 消息数据字典，模拟数据库 (现在主要用于发送消息后的本地显示) - 可以考虑移除或简化
messages_db = {
    "1": messages_data_chat_1,
    "99": messages_data_chat_99,
    # 可以添加其他聊天 ID 的消息列表
}

def get_screen_size_screeninfo():
    monitors = get_monitors()
    primary_monitor = monitors[0]  # 获取主显示器
    return primary_monitor.width, primary_monitor.height

class ChatApp:
    def __init__(self):
        self.page = None
        self.current_chat_id = None
        self.current_chat_type = None # 新增：存储当前聊天类型
        self.chat_list_view = None
        self.message_list_view = None
        self.new_message_field = None
        self.send_button = None
        self.chat_data_cache = {} # 缓存从 API 获取的聊天列表数据
        self.chat_list_items = [] # 新增：存储 ListView 中的 ListTile 控件实例，用于置顶操作
        self.login_form = None # 登录表单控件
        self.main_content = None # 主聊天内容控件
        self.current_user_id = None # 新增：存储当前用户 ID
        self.current_user_name = None # 新增：存储当前用户名
        # --- 新增：输入区域上方的按钮控件 ---
        self.emoji_button = None
        self.image_button = None
        self.video_button = None
        self.file_button = None
        self.text_button = None
        # --- 新增：聊天标题控件 ---
        self.chat_title_text = None
        # --- 新增：用户信息行控件 ---
        self.user_info_row = None
        self.connection_status_text = None
        # --- 新增：WebSocket Handler ---
        self.ws_handler = None

    def main(self, page: ft.Page):
        self.page = page
        # --- 初始登录窗口设置 ---
        self.page.title = "用户登录"
        self.page.window.width = 500
        self.page.window.height = 400
        self.page.window.resizable = False
        self.page.window.center()
        # -------------------------
        self.page.vertical_alignment = ft.MainAxisAlignment.CENTER
        self.page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

        # 加载 token
        token = api.api_handler.load_token()
        api.api_handler.token = token # 确保 APIHandler 实例也加载了 token

        # 检查是否有有效的 token
        if token:
            # 如果有 token，获取用户信息，然后加载聊天列表
            print("Token found, attempting to get user info...")
            # 获取用户信息
            api.get_user_info(callback=self.on_get_user_info)
        else:
            # 如果没有 token，显示登录界面
            print("No token found, showing login form...")
            self.show_login_form()

    def on_get_user_info(self, result):
        """获取用户信息回调"""
        if result.get("code") == 1:
            user_data = result.get("data", {}).get("user", {})
            user_id = user_data.get("userId")
            user_name = user_data.get("nickname") # 假设 nickname 是用户名
            if user_id:
                self.current_user_id = user_id
                self.current_user_name = user_name
                print(f"获取当前用户信息成功: ID={self.current_user_id}, Name={self.current_user_name}")
                # 获取用户信息成功后，加载聊天列表
                self.setup_main_layout()
                self.adjust_window_size()
                self.load_chat_list()
                # 启动 WebSocket
                self.start_websocket()
            else:
                print("获取用户信息响应中缺少 userId")
                # 可以选择显示错误信息或返回登录界面
                self.page.snack_bar = ft.SnackBar(ft.Text("获取用户信息失败，缺少 userId。"))
                self.page.snack_bar.open = True
                self.page.update()
                self.show_login_form() # 或者显示错误页面
        else:
            print(f"获取用户信息失败: {result.get('msg', 'Unknown error')}")
            # 可以选择显示错误信息或返回登录界面
            self.page.snack_bar = ft.SnackBar(ft.Text(f"获取用户信息失败: {result.get('msg', 'Unknown error')}"))
            self.page.snack_bar.open = True
            self.page.update()
            self.show_login_form() # 或者显示错误页面


    def start_websocket(self):
        """启动 WebSocket 客户端"""
        # 直接从 api_handler 获取 token 和 user_id
        token = api.api_handler.token
        user_id = self.current_user_id

        if not user_id or not token:
            print("Cannot start WebSocket: Missing user ID or token.")
            return

        # 创建 WebSocket Handler 实例，传入 token 和 user_id
        self.ws_handler = ws.WebSocketHandler(
            token=token, # 使用从 api_handler 获取的 token
            user_id=user_id
        )

        # 设置回调函数
        self.ws_handler.set_callbacks(
            connection_status=self.on_ws_connection_status,
            message=self.on_ws_push_message,
            # draft=self.on_ws_draft_message, # 暂时不需要
            # edit=self.on_ws_edit_message,   # 暂时不需要
            # file_send=self.on_ws_file_send_message, # 暂时不需要
            # stream=self.on_ws_stream_message, # 暂时不需要
        )

        # 启动
        self.ws_handler.start()
        print("WebSocket started.")

    def on_ws_connection_status(self, status: bool):
        """WebSocket 连接状态回调"""
        def update_ui():
            if status:
                self.connection_status_text.value = "" # 连接成功时隐藏文字
            else:
                self.connection_status_text.value = "(连接断开)"
            self.connection_status_text.color = ft.Colors.RED if not status else ft.Colors.GREY
            self.page.update()
        # 在 UI 线程中更新
        update_ui() # 或者直接调用 update_ui()，取决于 Flet 版本对多线程 UI 操作的处理

    def adjust_window_size(self):
        """调整窗口大小"""
        width, height = get_screen_size_screeninfo()
        self.page.window.width = float(width - 50)
        self.page.window.height = float(height - 50)
        self.page.title = "云湖"
        self.page.window.center()
        self.page.update()

    def setup_main_layout(self):
        """设置主聊天界面布局"""
        # --- 创建用户信息行 ---
        self.connection_status_text = ft.Text("(连接断开)", color=ft.Colors.RED, visible=True) # 初始显示为断开
        self.user_info_row = ft.Row(
            [
                ft.Text(f"用户: {self.current_user_name} ({self.current_user_id})", size=16, weight=ft.FontWeight.BOLD),
                self.connection_status_text,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
        )

        # 创建主内容区域 (聊天列表)
        self.chat_list_view = ft.ListView(
            expand=True,
            spacing=5,
            padding=10,
            auto_scroll=False,
        )
        # 添加一个加载指示器，初始时显示
        self.loading_indicator = ft.ProgressRing(visible=True)
        self.chat_list_view.controls.append(self.loading_indicator)

        # 将用户信息行和聊天列表放在左侧
        left_panel = ft.Column( # 左侧整体面板，包含用户信息和聊天列表
            [
                self.user_info_row,
                self.chat_list_view,
            ],
            width=300, # 固定左侧宽度
        )

        # 创建消息列表视图
        self.message_list_view = ft.ListView(
            expand=True,
            spacing=10,
            padding=10,
            auto_scroll=True, # 自动滚动到底部
        )

        # --- 创建聊天标题 ---
        self.chat_title_text = ft.Text("请选择一个聊天", size=18, weight=ft.FontWeight.BOLD)

        # --- 创建输入区域上方的按钮 ---
        self.emoji_button = ft.IconButton(icon=ft.Icons.EMOJI_EMOTIONS, tooltip="表情")
        self.image_button = ft.IconButton(icon=ft.Icons.IMAGE, tooltip="图片")
        self.video_button = ft.IconButton(icon=ft.Icons.VIDEO_FILE, tooltip="视频")
        self.file_button = ft.IconButton(icon=ft.Icons.ATTACH_FILE, tooltip="文件")
        self.text_button = ft.IconButton(icon=ft.Icons.TEXT_FIELDS, tooltip="文本格式") # 暂时作为普通按钮

        # 创建消息输入框和发送按钮
        self.new_message_field = ft.TextField(
            label="输入消息...",
            expand=True,
            multiline=False,
            on_submit=self.send_message, # 按回车键发送
        )
        self.send_button = ft.ElevatedButton(
            text="发送",
            on_click=self.send_message,
        )

        right_panel = ft.Column(
            [
                # --- 添加聊天标题 ---
                self.chat_title_text,
                # 消息显示区域
                ft.Container(
                    content=self.message_list_view,
                    expand=True,
                    border=ft.border.all(1, ft.Colors.OUTLINE),
                    border_radius=ft.border_radius.all(5),
                    padding=10,
                ),
                # --- 添加按钮区域 ---
                ft.Row(
                    [self.emoji_button, self.image_button, self.video_button, self.file_button, self.text_button],
                    alignment=ft.MainAxisAlignment.START, # 按钮靠左对齐
                ),
                # 输入区域
                ft.Row(
                    [self.new_message_field, self.send_button],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
            ],
            expand=True,
        )

        self.main_content = ft.Row( # 主布局行
            [left_panel, right_panel],
            expand=True,
        )

        # 清空页面并添加主内容
        self.page.clean()
        self.page.add(self.main_content)
        self.page.vertical_alignment = ft.MainAxisAlignment.START # 切换回顶部对齐


    def show_login_form(self):
        """显示登录表单"""
        # 状态文本
        status_text = ft.Text("", color=ft.Colors.RED)
        
        # 输入控件
        email_field = ft.TextField(
            label="邮箱",
            width=300,
            keyboard_type=ft.KeyboardType.EMAIL
        )
        
        password_field = ft.TextField(
            label="密码",
            password=True,
            width=300
        )

        def login_callback(result):
            """
            登录回调函数
            """
            # 直接在回调中更新UI (Flet 通常处理得比较好)
            if result["code"] == 1:
                status_text.value = f"登录成功! Token: {result['data']['token'][:10]}..."
                status_text.color = ft.Colors.GREEN
                # 获取用户信息
                api.get_user_info(callback=self.on_get_user_info)
            else:
                status_text.value = f"登录失败: {result['msg']}"
                login_button.disabled = False
                status_text.color = ft.Colors.RED
            self.page.update() # 更新 UI 以显示状态或切换界面
        
        def on_login_click(e):
            """
            登录按钮点击事件
            """
            # 简单验证
            if not email_field.value or not password_field.value:
                status_text.value = "请填写邮箱和密码"
                status_text.color = ft.Colors.RED
                self.page.update()
                return
            
            # 禁用登录按钮，显示加载状态
            login_button.disabled = True
            status_text.value = "登录中..."
            status_text.color = ft.Colors.BLUE
            self.page.update()
            
            # 调用API进行登录
            api.email_login(
                email=email_field.value,
                password=password_field.value,
                device_id="yunhu-python-flet-app",
                platform="windows",
                callback=login_callback
            )
        
        # 登录按钮
        login_button = ft.ElevatedButton(
            "登录",
            width=300,
            on_click=on_login_click
        )
        
        # 登录表单布局
        self.login_form = ft.Column(
            [
                ft.Text("用户登录", size=30, weight=ft.FontWeight.BOLD),
                email_field,
                password_field,
                login_button,
                status_text
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=20
        )

        # 清空页面并添加登录表单
        self.page.clean()
        self.page.add(self.login_form)

    def load_chat_list(self):
        """加载聊天列表 (在后台线程中运行)"""
        # 在新线程中执行 API 调用
        load_thread = threading.Thread(target=self._fetch_and_update_chat_list)
        load_thread.start()

    def _fetch_and_update_chat_list(self):
        """获取聊天列表数据并更新 UI (在后台线程中运行)"""
        try:
            # 调用 API 获取原始二进制数据
            def raw_callback(binary_data, status_code, msg):
                # UI 更新逻辑需要在 UI 线程中完成，但 Flet 通常能处理直接调用
                if status_code == 200 and binary_data:
                    try:
                        # 解析 protobuf 数据
                        pb2_message = conversation_pb2.list() # --- 使用 conversation_pb2.list() ---
                        pb2_message.ParseFromString(binary_data)
                        
                        # 解析成功后，提取数据
                        api_response = {
                            "code": pb2_message.status.code,
                            "msg": pb2_message.status.msg,
                            "data": []
                        }
                        
                        for item in pb2_message.data:
                            conversation_item = {
                                "chatId": item.chat_id,
                                "chatType": item.chat_type,
                                "chatName": item.name,
                                "latest_msg": item.chat_content,
                                "is_unread": bool(item.unread_message),
                                "avatar_url": item.avatar_url,
                                "level": item.certification_level
                            }
                            api_response['data'].append(conversation_item)
                        
                        # --- UI 更新逻辑 ---
                        # 清空加载指示器
                        self.chat_list_view.controls.clear()
                        self.chat_list_items.clear() # 清空 ListTile 实例列表
                        
                        # 缓存数据
                        self.chat_data_cache = {item["chatId"]: item for item in api_response.get("data", [])}
                        
                        # 遍历 API 返回的数据，创建列表项
                        for chat in api_response.get("data", []):
                            # 修正：将 chat_id 和 chat_type 作为关键字参数传递给 lambda
                            chat_tile = ft.ListTile(
                                title=ft.Text(chat["chatName"]),
                                subtitle=ft.Text(chat["latest_msg"], max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                on_click=lambda e, chat_id=chat["chatId"], chat_type=chat["chatType"]: self.select_chat(chat_id, chat_type),
                                data=chat["chatId"] # 将 chatId 存储在 ListTile 的 data 属性中，方便查找
                            )
                            self.chat_list_view.controls.append(chat_tile)
                            self.chat_list_items.append(chat_tile) # 将 ListTile 实例添加到列表
                        
                    except Exception as parse_error:
                        print(f"protobuf 解析失败: {parse_error}")
                        self.chat_list_view.controls.clear()
                        self.chat_list_view.controls.append(ft.Text(f"解析聊天列表数据失败: {str(parse_error)}"))
                else:
                    # API 返回错误或无数据
                    self.chat_list_view.controls.clear()
                    error_msg = f"获取聊天列表失败: {msg} (状态码: {status_code})"
                    print(error_msg)
                    self.chat_list_view.controls.append(ft.Text(error_msg))
                
                # 更新页面
                self.page.update()

            # 发起请求
            api.get_conversation_list_raw(callback=raw_callback)

        except Exception as e:
            # 处理网络错误等异常
            print(f"API 调用异常: {e}")
            def show_error():
                self.chat_list_view.controls.clear()
                self.chat_list_items.clear() # 同时清空列表项缓存
                self.chat_list_view.controls.append(ft.Text(f"加载聊天列表时出错: {str(e)}"))
                # 更新页面
                self.page.update()

            # self.page.run(show_error) # 不再使用 page.run
            show_error() # 直接调用


    def select_chat(self, chat_id, chat_type):
        """当用户点击左侧聊天列表时，加载对应聊天的消息"""
        self.current_chat_id = chat_id
        self.current_chat_type = chat_type # 存储聊天类型
        # 从缓存中获取聊天名称
        chat_info = self.chat_data_cache.get(chat_id, {})
        chat_name = chat_info.get("chatName", "未知聊天")

        # --- 更新聊天标题 ---
        self.chat_title_text.value = f"{chat_name} ({chat_id})" # 显示名称和ID
        self.page.window_title = f"云湖 - {chat_name}"

        # 清空当前消息列表
        self.message_list_view.controls.clear()
        # 显示加载指示器
        self.message_list_view.controls.append(ft.Text("加载消息中..."))
        self.page.update()

        # 加载远程消息
        self.load_remote_messages(chat_id, chat_type)

    def load_remote_messages(self, chat_id, chat_type):
        """加载指定聊天的远程消息 (在后台线程中运行)"""
        # 在新线程中执行 API 调用
        load_thread = threading.Thread(target=self._fetch_and_update_messages, args=(chat_id, chat_type))
        load_thread.start()

    def _fetch_and_update_messages(self, chat_id, chat_type):
        """获取指定聊天的消息数据并更新 UI (在后台线程中运行)"""
        try:
            # 调用 API 获取原始二进制数据
            def raw_callback(binary_data, status_code, msg):
                # UI 更新逻辑
                if status_code == 200 and binary_data:
                    try:
                        # 解析 protobuf 数据
                        pb2_message = list_message_pb2.list_message()
                        pb2_message.ParseFromString(binary_data)

                        # 检查状态码 (根据您的最新指正，正常状态码统一为 1)
                        if pb2_message.status.code != 1: # 假设 1 是成功码 (根据您的最新指正)
                            print(f"获取消息列表失败，API 状态码: {pb2_message.status.code}, 消息: {pb2_message.status.msg}")
                            # 清空加载指示器
                            self.message_list_view.controls.clear()
                            self.message_list_view.controls.append(ft.Text(f"获取消息失败: {pb2_message.status.msg}"))
                            self.page.update()
                            return

                        # --- 消息排序 ---
                        # 将 protobuf 消息列表转换为普通列表，方便排序
                        raw_messages = list(pb2_message.msg)
                        # 根据 send_time (毫秒时间戳) 升序排序，时间早的在前，时间晚的在后
                        sorted_messages = sorted(raw_messages, key=lambda x: x.send_time)

                        # --- UI 更新逻辑 ---
                        # 清空加载指示器
                        self.message_list_view.controls.clear()
                        
                        # 遍历排序后的消息，创建消息气泡
                        for msg_pb in sorted_messages:
                            # 提取关键信息
                            sender_id = msg_pb.sender.chat_id
                            sender_name = msg_pb.sender.name
                            message_text = msg_pb.content.text # 只处理文本消息
                            timestamp_ms = msg_pb.send_time
                            # 将毫秒时间戳转换为可读格式
                            import time
                            timestamp_dt = datetime.fromtimestamp(timestamp_ms / 1000.0) # 转换为秒
                            timestamp_str = timestamp_dt.strftime("%Y-%m-%d %H:%M:%S")
                            
                            # 判断是否为自己发送的消息 (根据 sender.chat_id 与当前用户 ID 比较)
                            is_me = (sender_id == self.current_user_id)

                            if message_text: # 只处理有文本内容的消息
                                message_bubble = self.create_message_bubble(message_text, sender_name, is_me, timestamp=timestamp_str)
                                self.message_list_view.controls.append(message_bubble)
                        
                    except Exception as parse_error:
                        print(f"消息 protobuf 解析失败: {parse_error}")
                        self.message_list_view.controls.clear()
                        self.message_list_view.controls.append(ft.Text(f"解析消息数据失败: {str(parse_error)}"))
                else:
                    # API 返回错误或无数据
                    self.message_list_view.controls.clear()
                    error_msg = f"获取消息失败: {msg} (状态码: {status_code})"
                    print(error_msg)
                    self.message_list_view.controls.append(ft.Text(error_msg))
                
                # 更新页面
                self.page.update()

            # 发起请求，获取最新 50 条消息
            api.list_message_raw(chat_id=chat_id, chat_type=chat_type, msg_count=50, callback=raw_callback)

        except Exception as e:
            # 处理网络错误等异常
            print(f"获取消息 API 调用异常: {e}")
            self.message_list_view.controls.clear()
            self.message_list_view.controls.append(ft.Text(f"加载消息时出错: {str(e)}"))
            # 更新页面
            self.page.update()


    def create_message_bubble(self, message_text, user, is_me, timestamp="", content_type=1):
        """创建一个消息气泡控件，支持文本和Markdown"""
        print(f"DEBUG: Creating bubble - User: {user}, ContentType: {content_type}, Text: {message_text}")
        
        alignment = ft.MainAxisAlignment.END if is_me else ft.MainAxisAlignment.START
        color = ft.Colors.BLUE_100 if is_me else ft.Colors.GREY_300
        
        # 根据 content_type 选择内容控件
        if content_type == 3:  # Markdown 类型 (修正为3)
            content_widget = ft.Markdown(
                message_text,
                selectable=True,
                extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                code_theme="atom-one-dark",
                code_style=ft.TextStyle(font_family="Roboto Mono"),
                on_tap_link=lambda e: print(f"Link tapped: {e.data}"),
            )
        else:  # 默认文本类型 (content_type == 1)
            content_widget = ft.Text(message_text, selectable=True)
        
        bubble = ft.Row(
            controls=[
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text(user, size=12, weight=ft.FontWeight.BOLD),
                            content_widget,
                            ft.Text(timestamp, size=10, italic=True),
                        ],
                        spacing=5,  # 增加间距，特别是Markdown需要更多空间
                        tight=False,  # 设为False让Markdown有更好的布局
                    ),
                    bgcolor=color,
                    padding=10,
                    border_radius=10,
                    margin=5,  # 添加外边距
                )
            ],
            alignment=alignment,
        )
        
        print(f"DEBUG: Bubble created with content_type: {content_type}")
        return bubble

    def on_ws_push_message(self, msg_info: Dict[str, Any]):
        """WebSocket 推送消息回调"""
        def update_ui():
            msg_chat_id = msg_info.get("chat_id")
            sender_id = msg_info.get("sender_id")
            message_text = msg_info.get("content", "")
            content_type = msg_info.get("content_type", 1)  # 默认为文本类型
            
            print(f"DEBUG: WS推送消息 - 聊天: {msg_chat_id}, 内容类型: {content_type}, 内容: {message_text}")
            
            # 更新左边聊天栏（所有消息都需要更新）
            if msg_chat_id in self.chat_data_cache:
                # 根据内容类型生成预览
                if content_type == 3:  # 修正为3
                    preview_text = "[Markdown消息] " + (message_text[:15] + "..." if len(message_text) > 15 else message_text)
                else:
                    preview_text = message_text[:20] + "..." if len(message_text) > 20 else message_text
                
                self.chat_data_cache[msg_chat_id]["latest_msg"] = preview_text
                
                # 找到对应的 ListTile 并置顶
                target_tile = None
                for tile in self.chat_list_items:
                    if tile.data == msg_chat_id:
                        target_tile = tile
                        break

                if target_tile:
                    # 从原位置移除并置顶
                    if target_tile in self.chat_list_view.controls:
                        self.chat_list_view.controls.remove(target_tile)
                    self.chat_list_view.controls.insert(0, target_tile)
                    
                    # 更新显示内容
                    target_tile.subtitle.value = self.chat_data_cache[msg_chat_id]["latest_msg"]
                    print(f"更新聊天栏: {msg_chat_id}")
            
            # 如果是当前聊天，显示消息气泡
            if msg_chat_id == self.current_chat_id and message_text:
                sender_name = msg_info.get("sender_name", "未知用户")
                timestamp_ms = msg_info.get("send_time")
                
                if timestamp_ms:
                    timestamp_dt = datetime.fromtimestamp(timestamp_ms / 1000.0)
                    timestamp_str = timestamp_dt.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    timestamp_str = "刚刚"

                # 判断是否为自己发送的消息
                is_me = (sender_id == self.current_user_id)
                
                # 创建并添加消息气泡（传入 content_type）
                message_bubble = self.create_message_bubble(
                    message_text, 
                    sender_name, 
                    is_me, 
                    timestamp=timestamp_str,
                    content_type=content_type
                )
                self.message_list_view.controls.append(message_bubble)
                print(f"显示消息气泡 - 类型{content_type}: {sender_name}: {message_text}")

            # 更新页面
            self.page.update()

        # 调用更新函数
        update_ui()

    def send_message(self, e):
        """处理发送消息的逻辑"""
        if not self.current_chat_id:
            # 如果没有选择聊天，提示用户
            self.page.snack_bar = ft.SnackBar(ft.Text("请先选择一个聊天。"))
            self.page.snack_bar.open = True
            self.page.update()
            return

        text = self.new_message_field.value
        if text:
            

            # 清空输入框
            self.new_message_field.value = ""
            # 更新页面，使新消息可见并清空输入框
            self.page.update()

            # 然后调用 API 发送消息
            def send_callback(binary_data, status_code, msg):
                # UI 更新逻辑 (检查发送结果，可能需要更新消息状态)
                if status_code == 200 and binary_data:
                    try:
                        # 解析发送结果 protobuf
                        pb2_result = send_message_pb2.send_message()
                        pb2_result.ParseFromString(binary_data)

                        # --- 检查发送状态码 (根据您的指正，正常状态码为 1) ---
                        if pb2_result.status.code != 1: # 假设 1 是发送成功码 (根据您的最新指正)
                            print(f"发送消息失败，API 状态码: {pb2_result.status.code}, 消息: {pb2_result.status.msg}")
                            # 这里可以给 UI 上刚添加的消息气泡加个失败标记，或者显示错误 Snackbar
                            # 例如，修改最后一条消息的背景色或添加文本
                            # self.page.snack_bar = ft.SnackBar(ft.Text(f"发送失败: {pb2_result.status.msg}"))
                            # self.page.snack_bar.open = True
                            # self.page.update()
                        else:
                            print("消息发送成功")
                    except Exception as parse_error:
                        print(f"发送结果 protobuf 解析失败: {parse_error}")
                        # self.page.snack_bar = ft.SnackBar(ft.Text(f"发送结果解析失败: {str(parse_error)}"))
                        # self.page.snack_bar.open = True
                        # self.page.update()
                else:
                    print(f"发送消息请求失败: {msg}")
                    # self.page.snack_bar = ft.SnackBar(ft.Text(f"发送消息请求失败: {msg}"))
                    # self.page.snack_bar.open = True
                    # self.page.update()

            # 发起发送请求
            api.send_message_raw(
                chat_id=self.current_chat_id,
                chat_type=self.current_chat_type,
                text=text,
                callback=send_callback
            )

# --- 运行应用 ---
if __name__ == "__main__":
    app = ChatApp()
    ft.app(target=app.main)