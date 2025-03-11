import os
import json
import requests
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    FollowEvent, UnfollowEvent, PostbackEvent,
    TemplateSendMessage, ButtonsTemplate, PostbackAction,
    FlexSendMessage
)
import psycopg2
from psycopg2 import pool
from dotenv import load_dotenv

# โหลดค่าตัวแปรจากไฟล์ .env
load_dotenv()

app = Flask(__name__)

# การกำหนดค่า LINE API
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# การกำหนดค่าการเชื่อมต่อ PostgreSQL
db_pool = psycopg2.pool.SimpleConnectionPool(
    1, 20,
    host=os.environ.get('DB_HOST'),
    database=os.environ.get('DB_NAME'),
    user=os.environ.get('DB_USER'),
    password=os.environ.get('DB_PASSWORD')
)

# รายชื่อคณะในมหาวิทยาลัย
FACULTIES = [
    "คณะวิศวกรรมศาสตร์",
    "คณะวิทยาศาสตร์",
    "คณะแพทยศาสตร์",
    "คณะมนุษยศาสตร์",
    "คณะสังคมศาสตร์",
    "คณะบริหารธุรกิจ",
    "คณะนิติศาสตร์",
    "คณะเทคโนโลยีสารสนเทศ",
    "คณะศึกษาศาสตร์",
    "คณะสถาปัตยกรรมศาสตร์"
]

# สร้างตารางในฐานข้อมูล (ควรรันเมื่อเริ่มต้นระบบเท่านั้น)
def create_tables():
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS students (
                    id SERIAL PRIMARY KEY,
                    line_user_id TEXT UNIQUE NOT NULL,
                    national_id TEXT UNIQUE,
                    faculty TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
        conn.commit()
    finally:
        db_pool.putconn(conn)

# เรียกใช้งานฟังก์ชันสร้างตาราง
create_tables()

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
        
    return 'OK'

@handler.add(FollowEvent)
def handle_follow(event):
    user_id = event.source.user_id
    
    # บันทึกข้อมูลผู้ใช้ใหม่ในฐานข้อมูล (ยังไม่มีข้อมูลเลขบัตรประชาชนและคณะ)
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO students (line_user_id) VALUES (%s) ON CONFLICT (line_user_id) DO NOTHING",
                (user_id,)
            )
        conn.commit()
    finally:
        db_pool.putconn(conn)
    
    # ส่งข้อความต้อนรับพร้อมปุ่มลงทะเบียน
    welcome_message = TextSendMessage(
        text="ยินดีต้อนรับสู่ LINE Official Account ของมหาวิทยาลัย!\nกรุณาลงทะเบียนเพื่อรับข่าวสารที่เกี่ยวข้องกับคณะของคุณ"
    )
    
    register_button = TemplateSendMessage(
        alt_text="ลงทะเบียนนักศึกษา",
        template=ButtonsTemplate(
            title="ลงทะเบียนนักศึกษา",
            text="กรุณาลงทะเบียนเพื่อรับข่าวสารที่เกี่ยวข้องกับคณะของคุณ",
            actions=[
                PostbackAction(
                    label="ลงทะเบียน",
                    data="action=register"
                )
            ]
        )
    )
    
    line_bot_api.reply_message(
        event.reply_token,
        [welcome_message, register_button]
    )

@handler.add(UnfollowEvent)
def handle_unfollow(event):
    user_id = event.source.user_id
    
    # อัพเดทหรือลบข้อมูลผู้ใช้เมื่อเลิกติดตาม
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            # เลือกที่จะอัพเดทสถานะหรือลบข้อมูล ตามที่ต้องการ
            cur.execute("DELETE FROM students WHERE line_user_id = %s", (user_id,))
        conn.commit()
    finally:
        db_pool.putconn(conn)

@handler.add(PostbackEvent)
def handle_postback(event):
    user_id = event.source.user_id
    data = event.postback.data
    
    if data == "action=register":
        # ส่งฟอร์มให้กรอกเลขบัตรประชาชน
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="กรุณากรอกเลขบัตรประชาชน 13 หลักของคุณ")
        )
    
    elif data.startswith("faculty="):
        # รับค่าคณะที่ผู้ใช้เลือก
        faculty = data.split("=")[1]
        
        # บันทึกข้อมูลคณะลงในฐานข้อมูล
        conn = db_pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE students SET faculty = %s WHERE line_user_id = %s",
                    (faculty, user_id)
                )
            conn.commit()
        finally:
            db_pool.putconn(conn)
        
        # เพิ่ม tag คณะให้กับผู้ใช้
        add_tag_to_user(user_id, faculty)
        
        # ส่งข้อความยืนยันการลงทะเบียนสำเร็จ
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"ลงทะเบียนสำเร็จ! คุณได้ลงทะเบียนกับ{faculty}เรียบร้อยแล้ว")
        )

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text
    user_id = event.source.user_id
    
    # ตรวจสอบว่าผู้ใช้กำลังกรอกเลขบัตรประชาชนหรือไม่
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT national_id FROM students WHERE line_user_id = %s", (user_id,))
            result = cur.fetchone()
            
            if result is None:
                # ไม่พบข้อมูลผู้ใช้ (ควรจะไม่เกิดขึ้น)
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="กรุณาลงทะเบียนก่อนใช้งาน")
                )
                return
            
            national_id = result[0]
            
            if national_id is None and len(text) == 13 and text.isdigit():
                # บันทึกเลขบัตรประชาชน
                cur.execute(
                    "UPDATE students SET national_id = %s WHERE line_user_id = %s",
                    (text, user_id)
                )
                conn.commit()
                
                # ส่งเมนูให้เลือกคณะ
                send_faculty_selection(event.reply_token)
            else:
                # ส่งข้อความตอบกลับทั่วไป
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="ขอบคุณสำหรับข้อความ กรุณาเลือกเมนูด้านล่างเพื่อใช้งานระบบ")
                )
    finally:
        db_pool.putconn(conn)

def send_faculty_selection(reply_token):
    # สร้าง Flex Message สำหรับเลือกคณะ
    bubble = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "เลือกคณะของคุณ",
                    "weight": "bold",
                    "size": "xl"
                }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": []
        }
    }
    
    # เพิ่มปุ่มสำหรับแต่ละคณะ
    for faculty in FACULTIES:
        bubble["footer"]["contents"].append({
            "type": "button",
            "style": "link",
            "height": "sm",
            "action": {
                "type": "postback",
                "label": faculty,
                "data": f"faculty={faculty}"
            }
        })
    
    flex_message = FlexSendMessage(
        alt_text="เลือกคณะของคุณ",
        contents=bubble
    )
    
    line_bot_api.reply_message(reply_token, flex_message)

def add_tag_to_user(user_id, faculty):
    # ตรวจสอบว่ามี tag นี้ในระบบหรือไม่
    tag_id = get_or_create_tag(faculty)
    
    # เพิ่ม tag ให้กับผู้ใช้
    url = f"https://api.line.me/v2/bot/user/{user_id}/tag/{tag_id}"
    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(url, headers=headers)
    
    if response.status_code != 200:
        app.logger.error(f"Error adding tag to user: {response.text}")

def get_or_create_tag(tag_name):
    # ดึงรายการ tag ทั้งหมด
    url = "https://api.line.me/v2/bot/audienceGroup/tag/list"
    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        tags = response.json().get("tags", [])
        
        # ค้นหา tag ที่มีอยู่แล้ว
        for tag in tags:
            if tag["name"] == tag_name:
                return tag["id"]
        
        # สร้าง tag ใหม่ถ้าไม่มี
        return create_tag(tag_name)
    else:
        app.logger.error(f"Error getting tag list: {response.text}")
        return None

def create_tag(tag_name):
    url = "https://api.line.me/v2/bot/audienceGroup/tag/create"
    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "name": tag_name
    }
    
    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code == 200:
        return response.json().get("tagId")
    else:
        app.logger.error(f"Error creating tag: {response.text}")
        return None

# ฟังก์ชันสำหรับส่งข่าวสารเฉพาะกลุ่มตาม tag
def send_message_to_faculty(faculty, message):
    # ดึง tag ID ของคณะนั้นๆ
    tag_id = get_or_create_tag(faculty)
    
    if tag_id is None:
        app.logger.error(f"Cannot find tag for faculty: {faculty}")
        return False
    
    # สร้าง Narrowcast Message
    url = "https://api.line.me/v2/bot/message/narrowcast"
    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    data = {
        "messages": [
            {
                "type": "text",
                "text": message
            }
        ],
        "recipient": {
            "type": "operator_id",
            "and": [
                {
                    "type": "audience_group_tag",
                    "id": tag_id
                }
            ]
        }
    }
    
    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code == 200:
        return True
    else:
        app.logger.error(f"Error sending narrowcast: {response.text}")
        return False

# ตัวอย่างการเรียกใช้งานส่งข่าวสารเฉพาะคณะ
# send_message_to_faculty("คณะวิศวกรรมศาสตร์", "ประกาศถึงนักศึกษาคณะวิศวกรรมศาสตร์: วันนี้มีการบรรยายพิเศษที่ห้อง EN101 เวลา 13.00 น.")

if __name__ == "__main__":
    # สร้างไฟล์ .env ที่มีค่าตัวแปรต่อไปนี้:
    # LINE_CHANNEL_ACCESS_TOKEN=your_line_channel_access_token
    # LINE_CHANNEL_SECRET=your_line_channel_secret
    # DB_HOST=your_db_host
    # DB_NAME=your_db_name
    # DB_USER=your_db_user
    # DB_PASSWORD=your_db_password
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
