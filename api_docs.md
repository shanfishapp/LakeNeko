发送消息
POST /v1/msg/send-messages

请求头:
名称	必须	备注
token	是	无


请求体：
```protobuf
syntax = "proto3";
// 发送消息
message send_message_send {
    string msg_id = 2; // 信息ID
    string chat_id = 3; // 欲发送到的信息对象
    uint64 chat_type = 4; // 欲发送到的信息对象的类别，1-用户，2-群聊，3-机器人
    Data data = 5;
    message Data {
        string text = 1; // 信息文本
        string buttons = 2; // 按钮
        string file_name = 4; // 欲发送文件名称
        string file_key = 5; // 欲发送文件key
        repeated string mentioned_id = 6; // @用户ID，可重复多个本属性
        string form = 7; // 表单消息
        string quote_msg_text = 8; // 引用信息文本
        string image = 9; // 欲发送图片key/url(expression/abcdef.jpg)
        string post_id = 10; // 文章ID
        string post_title = 11; // 文章标题
        string post_content = 12; // 文章内容
        string post_type = 13; // 文章类型:1-文本,2-Markdown
        string quote_image_url = 16; // 引用图片直链,https://...
        string quote_image_name = 17; // 引用图片文件名称
        uint64 file_size = 18; // 欲发送文件大小
        string video = 19; // 欲发送视频key/url(123.mp4)
        string audio = 21; // 语音key/url(123.m4a)
        uint64 audio_time = 22; // 语音秒数
        string quote_video_url = 23; // 引用视频直链,https://...
        uint64 quote_video_time = 24; // 引用视频时长
        uint64 sticker_item_id = 25; // 表情ID
        uint64 sticker_pack_id = 26; // 表情包ID
        string room_name = 29; // 语音房间发送显示信息的文本
    }
    uint64 content_type = 6; // 信息类别，1-文本，2-图片，3-markdown，4-文件，5-表单，6-文章，7-表情，8-html，11-语音，13-语音通话
    uint64 command_id = 7; // 所使用命令ID
    string quote_msg_id = 8; // 引用信息ID
    Media media = 9;
    message Media { // 在media发送对象为，图片/音频/视频
        string file_key = 1; // 发送对象key(就是上传后七牛对象存储给你返回的file_key)
        string file_hash = 2; // 发送对象上传返回哈希
        string file_type = 3; // 发送对象类别，image/jpeg-图片，video/mp4-音频
        uint64 image_height = 5; // 图片高度
        uint64 image_width = 6; // 图片宽度
        uint64 file_size = 7; // 发送对象大小
        string file_key2 = 8; // 发送对象key,和1一样,据说不写会报错
        string file_suffix = 9; // 发送对象后缀名
    }
}
```
响应体：
```protobuf
syntax = "proto3";
message Status {
    int32 code = 2;
    string msg = 3;
}
// 信息发送是否成功状态信息
message send_message {
    Status status = 1; // 状态码
}
```