from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
import sqlite3
from datetime import datetime
import os
import asyncio

# ===== CONFIG =====
TOKEN = os.getenv("TOKEN")
ADMIN_ID = 8619503816

GROUP_IDS = [
    -1003663678808,
    -1001234567890
]

GROUP_LINKS = [
    "https://t.me/thanhall",
    "https://t.me/baonatnhacainhe"
]

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

cursor.execute("""
CREATE TABLE IF NOT EXISTS withdraw (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount INTEGER,
    bank TEXT,
    stk TEXT,
    name TEXT,
    status TEXT,
    time TEXT
)
""")

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
    cursor.execute("INSERT INTO history VALUES(?,?,?,?)", (uid, -amt, "withdraw_hold", str(datetime.now())))
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
    await update.message.reply_text(
        "❌ Bạn cần tham gia ít nhất 1 nhóm để dùng bot!",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ===== START =====
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if is_banned(uid):
        return await update.message.reply_text("🚫 Bạn đã bị ban")

    get_user(uid)

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
        return await force_join(update)

    menu = ReplyKeyboardMarkup([
        ["💰 Số dư"],
        ["🎁 Checkin", "📮 Mời bạn"],
        ["🛒 Rút tiền", "📜 Lịch sử"],
        ["📞 Hỗ trợ"]
    ], resize_keyboard=True)

    await update.message.reply_text("🤖 Bot đã sẵn sàng", reply_markup=menu)

# ===== HANDLE =====
async def handle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    txt = update.message.text

    if is_banned(uid):
        return await update.message.reply_text("🚫 Bạn bị cấm")

    if not await joined(uid, ctx.bot):
        return await force_join(update)

    if txt == "💰 Số dư":
        return await update.message.reply_text(f"{get_balance(uid)} VND")

    elif txt == "🎁 Checkin":
        today = str(datetime.now().date())
        cursor.execute("SELECT last_checkin FROM users WHERE user_id=?", (uid,))
        last = cursor.fetchone()[0]
        if last == today:
            return await update.message.reply_text("❌ Hôm nay nhận rồi")

        add_money(uid, 1000, "checkin")
        cursor.execute("UPDATE users SET last_checkin=? WHERE user_id=?", (today, uid))
        conn.commit()
        return await update.message.reply_text("🎉 +1000đ")

    elif txt == "📮 Mời bạn":
        return await update.message.reply_text(f"https://t.me/{BOT_USERNAME}?start={uid}")

    elif txt == "🛒 Rút tiền":
        return await update.message.reply_text("Dùng: /rut bank stk ten 12000")

    elif txt == "📜 Lịch sử":
        cursor.execute("SELECT * FROM history WHERE user_id=? ORDER BY rowid DESC LIMIT 5", (uid,))
        data = cursor.fetchall()
        msg = "\n".join([f"{d[1]} | {d[2]}" for d in data])
        return await update.message.reply_text(msg or "Không có")

    elif txt == "📞 Hỗ trợ":
        return await update.message.reply_text("@RoGarden")

# ===== RÚT TIỀN =====
async def rut(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    try:
        bank, stk, name, amount = ctx.args[0], ctx.args[1], ctx.args[2], int(ctx.args[3])
    except:
        return await update.message.reply_text("❌ Dùng: /rut bank stk ten 12000")

    if amount < MIN_WITHDRAW:
        return await update.message.reply_text(f"❌ Tối thiểu {MIN_WITHDRAW}")

    if get_balance(uid) < amount:
        return await update.message.reply_text("❌ Không đủ tiền")

    sub_money(uid, amount)

    cursor.execute("""
    INSERT INTO withdraw(user_id, amount, bank, stk, name, status, time)
    VALUES(?,?,?,?,?,?,?)
    """, (uid, amount, bank, stk, name, "pending", str(datetime.now())))
    wid = cursor.lastrowid
    conn.commit()

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Duyệt", callback_data=f"ok_{wid}"),
        InlineKeyboardButton("❌ Từ chối", callback_data=f"no_{wid}")
    ]])

    await ctx.bot.send_message(ADMIN_ID, f"RÚT TIỀN\nID:{uid}\n💰{amount}\n🏦{bank}\nSTK:{stk}\n👤{name}", reply_markup=keyboard)
    await update.message.reply_text("⏳ Đang chờ duyệt")

# ===== CALLBACK =====
async def handle_withdraw(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    action, wid = query.data.split("_")
    wid = int(wid)

    cursor.execute("SELECT user_id, amount, status FROM withdraw WHERE id=?", (wid,))
    row = cursor.fetchone()
    if not row:
        return await query.edit_message_text("❌ Không tồn tại")

    uid, amount, status = row

    if status != "pending":
        return await query.edit_message_text("⚠️ Đã xử lý")

    if action == "ok":
        cursor.execute("UPDATE withdraw SET status='done' WHERE id=?", (wid,))
        await ctx.bot.send_message(uid, f"✅ Rút {amount} thành công")
    else:
        add_money(uid, amount, "refund")
        cursor.execute("UPDATE withdraw SET status='reject' WHERE id=?", (wid,))
        await ctx.bot.send_message(uid, f"❌ Rút {amount} bị từ chối")

    conn.commit()
    await query.edit_message_text("✅ Đã xử lý")

# ===== ADMIN =====
async def add(update, ctx):
    if update.effective_user.id == ADMIN_ID:
        add_money(int(ctx.args[0]), int(ctx.args[1]), "admin_add")
        await update.message.reply_text("OK")

async def sub(update, ctx):
    if update.effective_user.id == ADMIN_ID:
        sub_money(int(ctx.args[0]), int(ctx.args[1]))
        await update.message.reply_text("OK")

async def set_money(update, ctx):
    if update.effective_user.id == ADMIN_ID:
        cursor.execute("UPDATE users SET balance=? WHERE user_id=?", (int(ctx.args[1]), int(ctx.args[0])))
        conn.commit()
        await update.message.reply_text("OK")

async def addall(update, ctx):
    if update.effective_user.id == ADMIN_ID:
        for u in cursor.execute("SELECT user_id FROM users"):
            add_money(u[0], int(ctx.args[0]), "addall")
        await update.message.reply_text("OK")

async def ban(update, ctx):
    if update.effective_user.id == ADMIN_ID:
        cursor.execute("INSERT INTO banned VALUES(?)", (int(ctx.args[0]),))
        conn.commit()
        await update.message.reply_text("BANNED")

async def unban(update, ctx):
    if update.effective_user.id == ADMIN_ID:
        cursor.execute("DELETE FROM banned WHERE user_id=?", (int(ctx.args[0]),))
        conn.commit()
        await update.message.reply_text("UNBANNED")

async def pending(update, ctx):
    if update.effective_user.id == ADMIN_ID:
        rows = cursor.execute("SELECT id,user_id,amount FROM withdraw WHERE status='pending'").fetchall()
        await update.message.reply_text("\n".join([str(r) for r in rows]) or "Không có")

async def stats(update, ctx):
    if update.effective_user.id == ADMIN_ID:
        u = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        await update.message.reply_text(f"User: {u}")

# ===== ALL USER =====
async def all_user(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    msg = " ".join(ctx.args)
    if not msg:
        return await update.message.reply_text("Dùng: /all nội dung")

    users = cursor.execute("SELECT user_id FROM users").fetchall()

    sent = 0
    for u in users:
        try:
            await ctx.bot.send_message(u[0], msg)
            sent += 1
            await asyncio.sleep(0.03)
        except:
            pass

    await update.message.reply_text(f"✅ Đã gửi: {sent} user")

# ===== RUN =====
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("rut", rut))
app.add_handler(CommandHandler("stats", stats))
app.add_handler(CommandHandler("all", all_user))

app.add_handler(CommandHandler("add", add))
app.add_handler(CommandHandler("sub", sub))
app.add_handler(CommandHandler("set", set_money))
app.add_handler(CommandHandler("addall", addall))
app.add_handler(CommandHandler("ban", ban))
app.add_handler(CommandHandler("unban", unban))
app.add_handler(CommandHandler("pending", pending))

app.add_handler(CallbackQueryHandler(handle_withdraw))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

print("BOT FULL PRO MAX RUNNING...")
app.run_polling()
