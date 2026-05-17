import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import sqlite3
import random
import string
import qrcode
from io import BytesIO
import threading
import time
from datetime import datetime, timedelta
import json
import os
import hashlib
import re

# ====== CẤU HÌNH ======
TOKEN = "8844310824:AAGsTlTEsomkyU_fVJZ4rMCEsLu-TWdIJIc"
ADMIN_ID = [8619503816] # Thêm nhiều admin: [123456789, 987654321]

bot = telebot.TeleBot(TOKEN)

# ====== CÀI ĐẶT HỆ THỐNG ======
COMMISSION_RATE = 20 # Hoa hồng 20%
DAILY_BONUS = 5000 # Quà tặng hàng ngày 5k

# ====== KHỞI TẠO DATABASE NÂNG CAO ======
def init_db():
conn = sqlite3.connect('bot_data.db', check_same_thread=False)
c = conn.cursor()

# Bảng users mở rộng
c.execute('''CREATE TABLE IF NOT EXISTS users
(user_id INTEGER PRIMARY KEY,
username TEXT,
balance INTEGER DEFAULT 0,
total_recharge INTEGER DEFAULT 0,
total_spent INTEGER DEFAULT 0,
referral_count INTEGER DEFAULT 0,
referred_by INTEGER DEFAULT 0,
is_banned INTEGER DEFAULT 0,
daily_bonus_date TEXT,
transaction_password TEXT,
two_factor_enabled INTEGER DEFAULT 0,
created_at TEXT)''')

# Bảng sản phẩm (có thể thêm/xóa/sửa)
c.execute('''CREATE TABLE IF NOT EXISTS products
(id INTEGER PRIMARY KEY AUTOINCREMENT,
product_key TEXT UNIQUE,
product_name TEXT,
price INTEGER,
category TEXT,
is_active INTEGER DEFAULT 1,
created_at TEXT)''')

# Bảng mã giảm giá
c.execute('''CREATE TABLE IF NOT EXISTS discount_codes
(id INTEGER PRIMARY KEY AUTOINCREMENT,
code TEXT UNIQUE,
discount_percent INTEGER,
max_use INTEGER,
used_count INTEGER DEFAULT 0,
expires_at TEXT,
created_by INTEGER)''')

# Bảng đánh giá sản phẩm
c.execute('''CREATE TABLE IF NOT EXISTS product_reviews
(id INTEGER PRIMARY KEY AUTOINCREMENT,
user_id INTEGER,
product_name TEXT,
rating INTEGER,
comment TEXT,
created_at TEXT)''')

# Bảng thông báo hệ thống
c.execute('''CREATE TABLE IF NOT EXISTS notifications
(id INTEGER PRIMARY KEY AUTOINCREMENT,
user_id INTEGER,
title TEXT,
message TEXT,
is_read INTEGER DEFAULT 0,
created_at TEXT)''')

# Bảng lịch sử mua hàng
c.execute('''CREATE TABLE IF NOT EXISTS purchase_history
(id INTEGER PRIMARY KEY AUTOINCREMENT,
user_id INTEGER,
product_name TEXT,
quantity INTEGER,
price INTEGER,
total_amount INTEGER,
code TEXT,
discount_code TEXT,
discount_amount INTEGER DEFAULT 0,
status TEXT DEFAULT 'success',
created_at TEXT)''')

# Bảng lịch sử nạp tiền
c.execute('''CREATE TABLE IF NOT EXISTS deposit_history
(id INTEGER PRIMARY KEY AUTOINCREMENT,
user_id INTEGER,
amount INTEGER,
status TEXT,
transaction_id TEXT,
method TEXT DEFAULT 'bank',
created_at TEXT)''')

# Bảng cài đặt hệ thống
c.execute('''CREATE TABLE IF NOT EXISTS settings
(key TEXT PRIMARY KEY,
value TEXT)''')

# Bảng QR codes
c.execute('''CREATE TABLE IF NOT EXISTS qr_codes
(user_id INTEGER PRIMARY KEY,
qr_data TEXT,
created_at TEXT)''')

# Bảng chat với admin
c.execute('''CREATE TABLE IF NOT EXISTS admin_chats
(id INTEGER PRIMARY KEY AUTOINCREMENT,
user_id INTEGER,
message TEXT,
reply TEXT,
status TEXT DEFAULT 'pending',
created_at TEXT)''')

# Thêm sản phẩm mặc định nếu chưa có
default_products = [
('Fly88_1', 'Fly88 (88-388k-60k)', 60000, 'basic'),
('F168_1', 'F168 (88-388k-60k)', 60000, 'basic'),
('C168_1', 'C168 (88-388k-60k)', 60000, 'basic'),
('Sc88_1', 'Sc88 (88-388k-60k)', 60000, 'basic'),
('Qq88_1', 'Qq88 (88-388k-60k)', 60000, 'basic'),
('Fly88_2', 'Fly88 (388-888k-180k)', 180000, 'vip'),
('F168_2', 'F168 (388-888k-180k)', 180000, 'vip'),
('C168_2', 'C168 (388-888k-180k)', 180000, 'vip'),
('Sc88_2', 'Sc88 (388-888k-180k)', 180000, 'vip'),
('Qq88_2', 'Qq88 (388-888k-180k)', 180000, 'vip'),
('Lc79_1', 'Lc79 (50k-15k)', 15000, 'basic'),
('Betvip_1', 'Betvip (50-10k)', 10000, 'basic'),
('Mb66_1', 'Mb66 (88-388k-60k)', 60000, 'basic'),
('Shbet_1', 'Shbet (88-388k-60k)', 60000, 'basic'),
('New88_1', 'New88 (88-388k-60k)', 60000, 'basic'),
('Jun88v1_1', 'Jun88v1 (88k-388k-60k)', 60000, 'basic'),
('Mb66_2', 'Mb66 (388-888k-180k)', 180000, 'vip'),
('Shbet_2', 'Shbet (388-888k-180k)', 180000, 'vip'),
('New88_2', 'New88 (388-888k-180k)', 180000, 'vip'),
('Jun88v1_2', 'Jun88v1 (388-888k-180k)', 180000, 'vip'),
]

for product in default_products:
c.execute("INSERT OR IGNORE INTO products (product_key, product_name, price, category, created_at) VALUES (?, ?, ?, ?, ?)",
(product[0], product[1], product[2], product[3], datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

# Khởi tạo settings
settings = [
('maintenance', 'off'),
('shopping', 'on'),
('deposit', 'on'),
('profile', 'on'),
('referral', 'on'),
('history', 'on'),
('support', 'on'),
('daily_bonus', 'on'),
('commission_rate', str(COMMISSION_RATE)),
('daily_bonus_amount', str(DAILY_BONUS)),
]

for key, value in settings:
c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))

conn.commit()
conn.close()

init_db()

# ====== HÀM TIỆN ÍCH NÂNG CAO ======
def get_setting(key):
conn = sqlite3.connect('bot_data.db', check_same_thread=False)
c = conn.cursor()
c.execute("SELECT value FROM settings WHERE key = ?", (key,))
result = c.fetchone()
conn.close()
return result[0] if result else 'off'

def update_setting(key, value):
conn = sqlite3.connect('bot_data.db', check_same_thread=False)
c = conn.cursor()
c.execute("UPDATE settings SET value = ? WHERE key = ?", (value, key))
conn.commit()
conn.close()

def check_maintenance():
return get_setting('maintenance') == 'on'

def check_user_banned(user_id):
conn = sqlite3.connect('bot_data.db', check_same_thread=False)
c = conn.cursor()
c.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
result = c.fetchone()
conn.close()
return result and result[0] == 1

def generate_code():
return ''.join(random.choices(string.ascii_letters + string.digits, k=15))

def generate_transaction_id():
return f"TX{int(time.time())}{random.randint(1000, 9999)}"

def get_balance(user_id):
conn = sqlite3.connect('bot_data.db', check_same_thread=False)
c = conn.cursor()
c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
result = c.fetchone()
conn.close()
return result[0] if result else 0

def add_notification(user_id, title, message):
conn = sqlite3.connect('bot_data.db', check_same_thread=False)
c = conn.cursor()
c.execute("INSERT INTO notifications (user_id, title, message, created_at) VALUES (?, ?, ?, ?)",
(user_id, title, message, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
conn.commit()
conn.close()

# ====== MENU CHÍNH NÂNG CẤP ======
def create_main_menu():
markup = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
btn1 = KeyboardButton('🛍️ Mua hàng')
btn2 = KeyboardButton('👤 Tài khoản')
btn3 = KeyboardButton('💰 Nạp tiền')
btn4 = KeyboardButton('🤝 Giới thiệu')
btn5 = KeyboardButton('📜 Lịch sử mua hàng')
btn6 = KeyboardButton('🎁 Nhận quà ngay')
btn7 = KeyboardButton('⭐ Đánh giá sản phẩm')
btn8 = KeyboardButton('🔍 Tra cứu mã code')
btn9 = KeyboardButton('📊 Bảng xếp hạng')
btn10 = KeyboardButton('🎧 Hỗ trợ')
markup.add(btn1, btn2, btn3, btn4, btn5, btn6, btn7, btn8, btn9, btn10)
return markup

def create_products_menu():
markup = InlineKeyboardMarkup(row_width=2)

# Lấy sản phẩm từ database
conn = sqlite3.connect('bot_data.db', check_same_thread=False)
c = conn.cursor()
c.execute("SELECT product_key, product_name, price FROM products WHERE is_active = 1 ORDER BY category, price")
products = c.fetchall()
conn.close()

for product in products:
btn = InlineKeyboardButton(f'🎲 {product[1]} - {product[2]:,}đ', callback_data=f'product_{product[0]}')
markup.add(btn)

btn_discount = InlineKeyboardButton('🎟️ Mã giảm giá', callback_data='show_discounts')
btn_back = InlineKeyboardButton('🔙 Quay lại menu', callback_data='back_to_menu')
markup.add(btn_discount, btn_back)

return markup

def create_quantity_menu(product_key):
markup = InlineKeyboardMarkup(row_width=5)
for i in range(1, 11):
markup.add(InlineKeyboardButton(str(i), callback_data=f'qty_{product_key}_{i}'))

btn_custom = InlineKeyboardButton('🔢 Nhập số lượng', callback_data=f'custom_qty_{product_key}')
btn_back = InlineKeyboardButton('🔙 Quay lại', callback_data='back_to_products')
markup.add(btn_custom, btn_back)

return markup

def create_confirm_menu(product_key, quantity, total_price, discount=0):
markup = InlineKeyboardMarkup(row_width=2)
markup.add(InlineKeyboardButton('✅ Xác nhận mua', callback_data=f'confirm_{product_key}_{quantity}'))

if discount > 0:
markup.add(InlineKeyboardButton('🎟️ Áp dụng mã giảm giá', callback_data=f'apply_discount_{product_key}_{quantity}'))

markup.add(InlineKeyboardButton('❌ Hủy', callback_data='back_to_products'))
return markup

def create_rating_menu(product_name):
markup = InlineKeyboardMarkup(row_width=5)
for i in range(1, 6):
markup.add(InlineKeyboardButton(f'⭐' * i, callback_data=f'rate_{product_name}_{i}'))
return markup

# ====== MENU ADMIN NÂNG CẤP ======
def create_admin_menu():
markup = InlineKeyboardMarkup(row_width=2)
markup.add(InlineKeyboardButton('📊 Thống kê', callback_data='admin_stats'))
markup.add(InlineKeyboardButton('👥 Quản lý user', callback_data='admin_users'))
markup.add(InlineKeyboardButton('🛍️ Quản lý sản phẩm', callback_data='admin_products'))
markup.add(InlineKeyboardButton('🎟️ Quản lý mã code', callback_data='admin_codes'))
markup.add(InlineKeyboardButton('🔧 Bảo trì', callback_data='admin_maintenance'))
markup.add(InlineKeyboardButton('📢 Gửi thông báo', callback_data='admin_broadcast'))
markup.add(InlineKeyboardButton('💬 Tin nhắn hỗ trợ', callback_data='admin_support_messages'))
markup.add(InlineKeyboardButton('⚙️ Cài đặt hệ thống', callback_data='admin_settings'))
return markup

def create_maintenance_menu():
markup = InlineKeyboardMarkup(row_width=2)

features = ['maintenance', 'shopping', 'deposit', 'profile', 'referral', 'history', 'support', 'daily_bonus']
names = ['🔧 Bảo trì tổng', '🛍️ Mua hàng', '💰 Nạp tiền', '👤 Tài khoản', '🤝 Giới thiệu', '📜 Lịch sử', '🎧 Hỗ trợ', '🎁 Quà hàng ngày']

for i, feature in enumerate(features):
status = get_setting(feature)
btn = InlineKeyboardButton(f'{names[i]}: {"✅ ON" if status == "on" else "❌ OFF"}', callback_data=f'toggle_{feature}')
markup.add(btn)

btn_back = InlineKeyboardButton('🔙 Quay lại', callback_data='back_to_admin')
markup.add(btn_back)

return markup

# ====== LỆNH ADMIN MỚI ======
@bot.message_handler(commands=['start'])
def start(message):
user_id = message.from_user.id
username = message.from_user.username or message.from_user.first_name

# Xử lý referral
referred_by = None
if len(message.text.split()) > 1:
try:
referred_by = int(message.text.split()[1])
except:
pass

get_or_create_user(user_id, username, referred_by)

if check_user_banned(user_id):
bot.reply_to(message, "⚠️ Tài khoản của quý khách đã bị khóa! Vui lòng liên hệ CSKH để được hỗ trợ.\n🎧 Hỗ trợ: @RoGarden")
return

# Kiểm tra daily bonus
check_and_send_daily_bonus(user_id)

welcome_msg = """
🎊 **CHÀO MỪNG ĐẾN VỚI HỆ THỐNG** 🎊
━━━━━━━━━━━━━━━━━━━━━
✨ **SIÊU THỊ GAME UY TÍN #1** ✨
✅ Giao dịch nhanh chóng - Bảo mật tuyệt đối
✅ Mã code tự động - Nhận hàng ngay sau khi mua
✅ Hoa hồng 20% cho người giới thiệu
✅ Nhận quà mỗi ngày - Lên đến 5,000đ

📌 **Hãy sử dụng menu bên dưới để trải nghiệm!**
━━━━━━━━━━━━━━━━━━━━━
"""
bot.send_message(message.chat.id, welcome_msg, parse_mode='Markdown', reply_markup=create_main_menu())

def get_or_create_user(user_id, username, referred_by=None):
conn = sqlite3.connect('bot_data.db', check_same_thread=False)
c = conn.cursor()

c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
user = c.fetchone()

if not user:
c.execute("INSERT INTO users (user_id, username, balance, referral_count, referred_by, created_at) VALUES (?, ?, ?, ?, ?, ?)",
(user_id, username, 0, 0, referred_by or 0, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

if referred_by:
c.execute("UPDATE users SET referral_count = referral_count + 1 WHERE user_id = ?", (referred_by,))
add_notification(referred_by, "🎉 Có người mới!", f"@{username} đã đăng ký qua link giới thiệu của bạn!")

conn.commit()
conn.close()

def check_and_send_daily_bonus(user_id):
conn = sqlite3.connect('bot_data.db', check_same_thread=False)
c = conn.cursor()

today = datetime.now().strftime('%Y-%m-%d')
c.execute("SELECT daily_bonus_date FROM users WHERE user_id = ?", (user_id,))
result = c.fetchone()

if not result or result[0] != today:
if get_setting('daily_bonus') == 'on':
bonus = int(get_setting('daily_bonus_amount'))
c.execute("UPDATE users SET balance = balance + ?, daily_bonus_date = ? WHERE user_id = ?", (bonus, today, user_id))
conn.commit()
conn.close()

try:
bot.send_message(user_id, f"🎁 **QUÀ TẶNG HÀNG NGÀY!**\n━━━━━━━━━━━━━━━━━━━━━\n✅ Bạn đã nhận {bonus:,}đ\n💰 Số dư hiện tại: {get_balance(user_id):,}đ\n━━━━━━━━━━━━━━━━━━━━━\n🎊 Hẹn gặp lại bạn vào ngày mai!", parse_mode='Markdown')
except:
pass
return True

conn.close()
return False

# ====== LỆNH ADMIN NÂNG CAO ======
@bot.message_handler(commands=['stats'])
def admin_stats(message):
if message.from_user.id not in ADMIN_ID:
return

conn = sqlite3.connect('bot_data.db', check_same_thread=False)
c = conn.cursor()

c.execute("SELECT COUNT(*) FROM users")
total_users = c.fetchone()[0]

c.execute("SELECT SUM(balance) FROM users")
total_balance = c.fetchone()[0] or 0

c.execute("SELECT SUM(total_recharge) FROM users")
total_recharge = c.fetchone()[0] or 0

c.execute("SELECT COUNT(*) FROM purchase_history WHERE DATE(created_at) = DATE('now')")
today_sales = c.fetchone()[0]

c.execute("SELECT SUM(total_amount) FROM purchase_history WHERE DATE(created_at) = DATE('now')")
today_revenue = c.fetchone()[0] or 0

stats_msg = f"""
📊 **THỐNG KÊ HỆ THỐNG**
━━━━━━━━━━━━━━━━━━━━━
👥 **Tổng người dùng:** {total_users}
💰 **Tổng số dư:** {total_balance:,}đ
💳 **Tổng nạp:** {total_recharge:,}đ

📈 **HÔM NAY:**
🛍️ **Số đơn:** {today_sales}
💵 **Doanh thu:** {today_revenue:,}đ
━━━━━━━━━━━━━━━━━━━━━
"""
bot.reply_to(message, stats_msg, parse_mode='Markdown')
conn.close()

@bot.message_handler(commands=['themsp'])
def add_product(message):
if message.from_user.id not in ADMIN_ID:
return

try:
parts = message.text.split('|')
product_key = parts[0].replace('/themsp', '').strip()
product_name = parts[1].strip()
price = int(parts[2].strip())
category = parts[3].strip() if len(parts) > 3 else 'basic'

conn = sqlite3.connect('bot_data.db', check_same_thread=False)
c = conn.cursor()
c.execute("INSERT INTO products (product_key, product_name, price, category, created_at) VALUES (?, ?, ?, ?, ?)",
(product_key, product_name, price, category, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
conn.commit()
conn.close()

bot.reply_to(message, f"✅ Đã thêm sản phẩm:\n{product_name}\n💰 Giá: {price:,}đ")
except:
bot.reply_to(message, "⚠️ Sai cú pháp!\nDùng: /themsp [mã] | [tên] | [giá] | [danh mục]\nVí dụ: /themsp SP001 | Sản phẩm A | 100000 | vip")

@bot.message_handler(commands=['suasp'])
def edit_product(message):
if message.from_user.id not in ADMIN_ID:
return

try:
parts = message.text.split('|')
product_key = parts[0].replace('/suasp', '').strip()
new_price = int(parts[1].strip())

conn = sqlite3.connect('bot_data.db', check_same_thread=False)
c = conn.cursor()
c.execute("UPDATE products SET price = ? WHERE product_key = ?", (new_price, product_key))
conn.commit()

if c.rowcount > 0:
bot.reply_to(message, f"✅ Đã cập nhật giá sản phẩm {product_key} thành {new_price:,}đ")
else:
bot.reply_to(message, "❌ Không tìm thấy sản phẩm!")
conn.close()
except:
bot.reply_to(message, "⚠️ Sai cú pháp!\nDùng: /suasp [mã_sản_phẩm] | [giá_mới]")

@bot.message_handler(commands=['xoasp'])
def delete_product(message):
if message.from_user.id not in ADMIN_ID:
return

try:
product_key = message.text.replace('/xoasp', '').strip()

conn = sqlite3.connect('bot_data.db', check_same_thread=False)
c = conn.cursor()
c.execute("DELETE FROM products WHERE product_key = ?", (product_key,))
conn.commit()

if c.rowcount > 0:
bot.reply_to(message, f"✅ Đã xóa sản phẩm {product_key}")
else:
bot.reply_to(message, "❌ Không tìm thấy sản phẩm!")
conn.close()
except:
bot.reply_to(message, "⚠️ Sai cú pháp!\nDùng: /xoasp [mã_sản_phẩm]")

@bot.message_handler(commands=['taicode'])
def create_discount_code(message):
if message.from_user.id not in ADMIN_ID:
return

try:
parts = message.text.split()
discount_percent = int(parts[1])
max_use = int(parts[2])
days_valid = int(parts[3])

code = generate_code()[:10].upper()
expires_at = (datetime.now() + timedelta(days=days_valid)).strftime('%Y-%m-%d %H:%M:%S')

conn = sqlite3.connect('bot_data.db', check_same_thread=False)
c = conn.cursor()
c.execute("INSERT INTO discount_codes (code, discount_percent, max_use, expires_at, created_by) VALUES (?, ?, ?, ?, ?)",
(code, discount_percent, max_use, expires_at, message.from_user.id))
conn.commit()
conn.close()

bot.reply_to(message, f"✅ Đã tạo mã giảm giá:\n🎟️ Mã: `{code}`\n📉 Giảm: {discount_percent}%\n🔢 Số lần: {max_use}\n📅 Hết hạn: {days_valid} ngày", parse_mode='Markdown')
except:
bot.reply_to(message, "⚠️ Sai cú pháp!\nDùng: /taicode [%_giảm] [số_lần] [số_ngày]")

@bot.message_handler(commands=['sendcode'])
def send_code_to_user(message):
if message.from_user.id not in ADMIN_ID:
return

try:
parts = message.text.split()
user_id = int(parts[1])
code = ' '.join(parts[2:])

bot.send_message(user_id, f"🎁 **BẠN NHẬN ĐƯỢC MÃ KHUYẾN MÃI!**\n━━━━━━━━━━━━━━━━━━━━━\n🎫 **Mã code:** `{code}`\n💝 Sử dụng khi mua hàng để nhận ưu đãi!\n━━━━━━━━━━━━━━━━━━━━━", parse_mode='Markdown')
bot.reply_to(message, f"✅ Đã gửi mã code đến user {user_id}")
except:
bot.reply_to(message, "⚠️ Sai cú pháp!\nDùng: /sendcode [id] [mã_code]")

@bot.message_handler(commands=['resetdaily'])
def reset_daily_bonus(message):
if message.from_user.id not in ADMIN_ID:
return

conn = sqlite3.connect('bot_data.db', check_same_thread=False)
c = conn.cursor()
c.execute("UPDATE users SET daily_bonus_date = NULL")
conn.commit()
conn.close()

bot.reply_to(message, "✅ Đã reset daily bonus cho tất cả người dùng!")

@bot.message_handler(commands=['setbonus'])
def set_bonus(message):
if message.from_user.id not in ADMIN_ID:
return

try:
amount = int(message.text.replace('/setbonus', '').strip())
update_setting('daily_bonus_amount', str(amount))
bot.reply_to(message, f"✅ Đã cài đặt quà tặng hàng ngày thành {amount:,}đ")
except:
bot.reply_to(message, "⚠️ Sai cú pháp!\nDùng: /setbonus [số_tiền]")

# ====== TÍNH NĂNG NGƯỜI DÙNG MỚI ======
@bot.message_handler(func=lambda message: message.text == '🎁 Nhận quà ngay')
def daily_bonus_command(message):
user_id = message.from_user.id

if check_user_banned(user_id):
bot.reply_to(message, "⚠️ Tài khoản của bạn đã bị khóa!")
return

if check_and_send_daily_bonus(user_id):
return
else:
bot.reply_to(message, "🎁 **QUÀ TẶNG HÀNG NGÀY**\n━━━━━━━━━━━━━━━━━━━━━\n⚠️ Bạn đã nhận quà hôm nay rồi!\n🔄 Hãy quay lại vào ngày mai!\n━━━━━━━━━━━━━━━━━━━━━", parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == '⭐ Đánh giá sản phẩm')
def rate_product(message):
if check_user_banned(message.from_user.id):
return

# Lấy danh sách sản phẩm đã mua
conn = sqlite3.connect('bot_data.db', check_same_thread=False)
c = conn.cursor()
c.execute("SELECT DISTINCT product_name FROM purchase_history WHERE user_id = ? ORDER BY created_at DESC LIMIT 10", (message.from_user.id,))
products = c.fetchall()
conn.close()

if not products:
bot.reply_to(message, "❌ Bạn chưa mua sản phẩm nào để đánh giá!")
return

markup = InlineKeyboardMarkup(row_width=1)
for product in products:
markup.add(InlineKeyboardButton(f'⭐ {product[0]}', callback_data=f'rate_product_{product[0]}'))

bot.send_message(message.chat.id, "⭐ **ĐÁNH GIÁ SẢN PHẨM**\n━━━━━━━━━━━━━━━━━━━━━\nChọn sản phẩm bạn muốn đánh giá:", parse_mode='Markdown', reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == '🔍 Tra cứu mã code')
def check_code(message):
msg = bot.send_message(message.chat.id, "🔍 **TRA CỨU MÃ CODE**\n━━━━━━━━━━━━━━━━━━━━━\nVui lòng nhập mã code cần tra cứu:", parse_mode='Markdown')
bot.register_next_step_handler(msg, process_che
