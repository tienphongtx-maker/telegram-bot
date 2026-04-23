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
    buttons = [
        [InlineKeyboardButton(f"📢 Nhóm {i+1}", url=link)]
        for i, link in enumerate(GROUP_LINKS)
    ]
    await update.message.reply_text(
        "❌ Bạn cần tham gia ít nhất 1 nhóm để dùng bot!",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ===== START =====
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if is_banned(uid):
        await update.message.reply_text("🚫 Bạn đã bị ban")
        return

    get_user(uid)

    if ctx.args:
        try:
            ref = int(ctx.args[0])
            if ref != uid:
                cursor.execute("SELECT refed FROM users WHERE user_id=?", (uid,))
                row = cursor.fetchone()
                if row and row[0] == 0:
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

# ===== HANDLE =====
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
        row = cursor.fetchone()
        last = row[0] if row else None

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
        await update.message.reply_text("@RoGarden")

# ===== RÚT TIỀN =====
async def rut(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    try:
        bank, stk, name, amount = ctx.args[0], ctx.args[1], ctx.args[2], int(ctx.args[3])
    except:
        await update.message.reply_text("❌ Dùng: /rut bank stk ten 12000")
        return

    if amount < MIN_WITHDRAW:
        await update.message.reply_text(f"❌ Tối thiểu {MIN_WITHDRAW}")
        return

    if get_balance(uid) < amount:
        await update.message.reply_text("❌ Không đủ tiền")
        return

    sub_money(uid, amount)

    cursor.execute("""
    INSERT INTO withdraw(user_id, amount, bank, stk, name, status, time)
    VALUES(?,?,?,?,?,?,?)
    """, (uid, amount, bank, stk, name, "pending", str(datetime.now())))
    wid = cursor.lastrowid
    conn.commit()

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Duyệt", callback_data=f"ok_{wid}"),
            InlineKeyboardButton("❌ Từ chối", callback_data=f"no_{wid}")
        ]
    ])

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
        await query.edit_message_text("❌ Không tồn tại")
        return

    uid, amount, status = row

    if status != "pending":
        await query.edit_message_text("⚠️ Đã xử lý")
        return

    if action == "ok":
        cursor.execute("UPDATE withdraw SET status='done' WHERE id=?", (wid,))
        conn.commit()
        await ctx.bot.send_message(uid, f"✅ Rút {amount} thành công")
        await query.edit_message_text("✅ Đã duyệt")

    else:
        add_money(uid, amount, "refund")
        cursor.execute("UPDATE withdraw SET status='reject' WHERE id=?", (wid,))
        conn.commit()
        await ctx.bot.send_message(uid, f"❌ Rút {amount} bị từ chối")
        await query.edit_message_text("❌ Đã từ chối")

# ===== ADMIN FULL =====
async def add(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        uid = int(ctx.args[0]); amt = int(ctx.args[1])
    except:
        await update.message.reply_text("Sai: /add id tiền")
        return
    add_money(uid, amt, "admin_add")
    await update.message.reply_text("✅ Đã cộng")

async def sub(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        uid = int(ctx.args[0]); amt = int(ctx.args[1])
    except:
        await update.message.reply_text("Sai: /sub id tiền")
        return
    if not sub_money(uid, amt):
        await update.message.reply_text("❌ Không đủ tiền")
        return
    await update.message.reply_text("✅ Đã trừ")

async def set_money(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        uid = int(ctx.args[0]); amt = int(ctx.args[1])
    except:
        await update.message.reply_text("Sai: /set id tiền")
        return
    cursor.execute("UPDATE users SET balance=? WHERE user_id=?", (amt, uid))
    conn.commit()
    await update.message.reply_text("✅ Đã set")

async def addall(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        amt = int(ctx.args[0])
    except:
        await update.message.reply_text("Sai: /addall tiền")
        return
    cursor.execute("SELECT user_id FROM users")
    for u in cursor.fetchall():
        add_money(u[0], amt, "admin_addall")
    await update.message.reply_text("✅ Đã cộng all")

async def ban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    uid = int(ctx.args[0])
    cursor.execute("INSERT OR IGNORE INTO banned(user_id) VALUES(?)", (uid,))
    conn.commit()
    await update.message.reply_text("🚫 Đã ban")

async def unban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    uid = int(ctx.args[0])
    cursor.execute("DELETE FROM banned WHERE user_id=?", (uid,))
    conn.commit()
    await update.message.reply_text("✅ Unban")

async def pending(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    cursor.execute("SELECT id,user_id,amount FROM withdraw WHERE status='pending'")
    rows = cursor.fetchall()
    if not rows:
        await update.message.reply_text("Không có lệnh rút")
        return
    msg = "\n".join([f"ID:{r[0]} | User:{r[1]} | 💰{r[2]}" for r in rows])
    await update.message.reply_text(msg)

async def stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    cursor.execute("SELECT COUNT(*) FROM users")
    u = cursor.fetchone()[0]
    await update.message.reply_text(f"User: {u}")

# ===== RUN =====
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("rut", rut))
app.add_handler(CommandHandler("stats", stats))

# 👉 ADMIN
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
