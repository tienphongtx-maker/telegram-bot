from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import sqlite3
from datetime import datetime
import os
import asyncio

# ===== CONFIG =====
TOKEN = os.getenv("TOKEN")
ADMIN_ID = 8619503816

GROUP_IDS = [-1003663678808]
GROUP_LINKS = ["https://t.me/thanhall"]

BOT_USERNAME = "loclastk2026bot"
MIN_WITHDRAW = 12000

# ===== DB =====
conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance INTEGER DEFAULT 0,
    refs INTEGER DEFAULT 0,
    refed INTEGER DEFAULT 0,
    bank TEXT,
    stk TEXT,
    name TEXT,
    last_checkin TEXT
)
""")

cursor.execute("CREATE TABLE IF NOT EXISTS history (user_id INTEGER, amount INTEGER, note TEXT, time TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS banned (user_id INTEGER PRIMARY KEY)")
conn.commit()

# ===== DB FUNC =====
def get_user(uid):
    cursor.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users(user_id) VALUES(?)", (uid,))
        conn.commit()

def is_banned(uid):
    cursor.execute("SELECT 1 FROM banned WHERE user_id=?", (uid,))
    return cursor.fetchone() is not None

def add_money(uid, amt, note):
    get_user(uid)
    cursor.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amt, uid))
    cursor.execute("INSERT INTO history VALUES(?,?,?,?)", (uid, amt, note, str(datetime.now())))
    conn.commit()

def sub_money(uid, amt):
    get_user(uid)
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
    bal = cursor.fetchone()[0]
    if bal < amt:
        return False
    cursor.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (amt, uid))
    cursor.execute("INSERT INTO history VALUES(?,?,?,?)", (uid, -amt, "withdraw", str(datetime.now())))
    conn.commit()
    return True

def get_balance(uid):
    get_user(uid)
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
    return cursor.fetchone()[0]

# ===== JOIN =====
async def joined(uid, bot):
    for gid in GROUP_IDS:
        try:
            m = await bot.get_chat_member(gid, uid)
            if m.status in ["member", "administrator", "creator"]:
                return True
        except:
            continue
    return False

async def force_join(update):
    buttons = [[InlineKeyboardButton(f"📢 Nhóm {i+1}", url=link)] for i, link in enumerate(GROUP_LINKS)]
    await update.message.reply_text("❌ Tham gia nhóm để dùng bot!", reply_markup=InlineKeyboardMarkup(buttons))

# ===== START =====
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if is_banned(uid):
        await update.message.reply_text("🚫 Bạn đã bị ban")
        return

    get_user(uid)

    # REF
    if ctx.args:
        try:
            ref = int(ctx.args[0])
            if ref != uid:
                cursor.execute("SELECT refed FROM users WHERE user_id=?", (uid,))
                if cursor.fetchone()[0] == 0:
                    add_money(ref, 2000, "ref")
                    cursor.execute("UPDATE users SET refs=refs+1 WHERE user_id=?", (ref,))
                    cursor.execute("UPDATE users SET refed=1 WHERE user_id=?", (uid,))
                    conn.commit()
        except:
            pass

    if not await joined(uid, ctx.bot):
        await force_join(update)
        return

    menu = ReplyKeyboardMarkup([
        ["💰 Số dư"],
        ["🎁 Checkin", "📮 Mời bạn"],
        ["🛒 Rút tiền", "📜 Lịch sử"],
        ["📞 Hỗ trợ"]
    ], resize_keyboard=True)

    await update.message.reply_text("🤖 Bot đã sẵn sàng", reply_markup=menu)

# ===== CHECKIN =====
async def handle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    txt = update.message.text

    if is_banned(uid):
        await update.message.reply_text("🚫 Bạn bị cấm")
        return

    if not await joined(uid, ctx.bot):
        await force_join(update)
        return

    if txt == "💰 Số dư":
        await update.message.reply_text(f"{get_balance(uid)} VND")

    elif txt == "🎁 Checkin":
        today = str(datetime.now().date())
        cursor.execute("SELECT last_checkin FROM users WHERE user_id=?", (uid,))
        last = cursor.fetchone()[0]

        if last == today:
            await update.message.reply_text("❌ Hôm nay nhận rồi")
            return

        add_money(uid, 1000, "checkin")
        cursor.execute("UPDATE users SET last_checkin=? WHERE user_id=?", (today, uid))
        conn.commit()

        await update.message.reply_text("🎉 +1000đ")

    elif txt == "📮 Mời bạn":
        await update.message.reply_text(f"https://t.me/{BOT_USERNAME}?start={uid}")

    elif txt == "🛒 Rút tiền":
        await update.message.reply_text("Dùng: /rut bank stk ten 12000")

    elif txt == "📜 Lịch sử":
        cursor.execute("SELECT * FROM history WHERE user_id=? ORDER BY rowid DESC LIMIT 5", (uid,))
        data = cursor.fetchall()
        msg = "\n".join([f"{d[1]} | {d[2]}" for d in data])
        await update.message.reply_text(msg or "Không có")

    elif txt == "📞 Hỗ trợ":
        await update.message.reply_text("Liên hệ admin")

# ===== BROADCAST =====
async def all_user(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    msg = " ".join(ctx.args)
    cursor.execute("SELECT user_id FROM users")

    for u in cursor.fetchall():
        try:
            await ctx.bot.send_message(u[0], f"📢 {msg}")
            await asyncio.sleep(0.05)
        except:
            pass

# ===== STATS =====
async def stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    cursor.execute("SELECT COUNT(*) FROM users")
    u = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(balance) FROM users")
    m = cursor.fetchone()[0] or 0

    await update.message.reply_text(f"User: {u}\nMoney: {m}")

# ===== BAN =====
async def ban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    cursor.execute("INSERT OR IGNORE INTO banned VALUES(?)", (int(ctx.args[0]),))
    conn.commit()
    await update.message.reply_text("Đã ban")

async def unban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    cursor.execute("DELETE FROM banned WHERE user_id=?", (int(ctx.args[0]),))
    conn.commit()
    await update.message.reply_text("Đã unban")

# ===== RÚT =====
async def rut(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    try:
        amount = int(ctx.args[3])
    except:
        await update.message.reply_text("Sai lệnh")
        return

    if amount < MIN_WITHDRAW:
        await update.message.reply_text("Min 12k")
        return

    if not sub_money(uid, amount):
        await update.message.reply_text("Không đủ tiền")
        return

    await ctx.bot.send_message(ADMIN_ID, f"Rút {amount} từ {uid}")
    await update.message.reply_text("Đã gửi yêu cầu")

# ===== RUN =====
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("rut", rut))
app.add_handler(CommandHandler("all", all_user))
app.add_handler(CommandHandler("stats", stats))
app.add_handler(CommandHandler("ban", ban))
app.add_handler(CommandHandler("unban", unban))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

print("BOT PRO RUNNING...")
app.run_polling()
