from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
import sqlite3
from datetime import datetime, timedelta
import os
import asyncio
import random

# ===== CONFIG =====
TOKEN = os.getenv("TOKEN")
ADMIN_ID = 8619503816

GROUP_IDS = [-1003663678808]
GROUP_LINKS = ["https://t.me/thanhall"]

BOT_USERNAME = "loclastk2026bot"
MIN_WITHDRAW = 12000

# ===== DB =====
conn = sqlite3.connect("bot.db", check_same_thread=False)

def query(q, args=()):
    cur = conn.cursor()
    cur.execute(q, args)
    conn.commit()
    return cur

query("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance INTEGER DEFAULT 0,
    refs INTEGER DEFAULT 0,
    refed INTEGER DEFAULT 0,
    bank TEXT,
    stk TEXT,
    name TEXT,
    last_checkin TEXT,
    last_withdraw TEXT
)
""")

query("CREATE TABLE IF NOT EXISTS history (user_id INTEGER, amount INTEGER, note TEXT, time TEXT)")
query("CREATE TABLE IF NOT EXISTS banned (user_id INTEGER PRIMARY KEY)")

# ===== USER =====
def get_user(uid):
    if not query("SELECT 1 FROM users WHERE user_id=?", (uid,)).fetchone():
        query("INSERT INTO users(user_id) VALUES(?)", (uid,))

def is_banned(uid):
    return query("SELECT 1 FROM banned WHERE user_id=?", (uid,)).fetchone() is not None

def add_money(uid, amt, note):
    get_user(uid)
    query("UPDATE users SET balance=balance+? WHERE user_id=?", (amt, uid))
    query("INSERT INTO history VALUES(?,?,?,?)", (uid, amt, note, str(datetime.now())))

def sub_money(uid, amt):
    get_user(uid)
    row = query("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()
    bal = row[0] if row else 0

    if bal < amt:
        return False

    query("UPDATE users SET balance=balance-? WHERE user_id=?", (amt, uid))
    query("INSERT INTO history VALUES(?,?,?,?)", (uid, -amt, "withdraw", str(datetime.now())))
    return True

def get_balance(uid):
    get_user(uid)
    row = query("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()
    return row[0] if row else 0

# ===== JOIN =====
async def joined(uid, bot):
    for gid in GROUP_IDS:
        try:
            m = await bot.get_chat_member(gid, uid)
            if m.status not in ["left", "kicked"]:
                return True
        except:
            pass
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

    if ctx.args:
        try:
            ref = int(ctx.args[0])
            if ref != uid:
                row = query("SELECT refed FROM users WHERE user_id=?", (uid,)).fetchone()
                if row and row[0] == 0:
                    if query("SELECT 1 FROM users WHERE user_id=?", (ref,)).fetchone():
                        add_money(ref, 2000, "ref")
                        query("UPDATE users SET refs=refs+1 WHERE user_id=?", (ref,))
                        query("UPDATE users SET refed=1 WHERE user_id=?", (uid,))
        except:
            pass

    if not await joined(uid, ctx.bot):
        await force_join(update)
        return

    menu = ReplyKeyboardMarkup([
        ["💰 Số dư", "🎲 Tài xỉu"],
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
        get_user(uid)
        today = str(datetime.now().date())
        row = query("SELECT last_checkin FROM users WHERE user_id=?", (uid,)).fetchone()
        last = row[0] if row else None

        if last == today:
            await update.message.reply_text("❌ Hôm nay nhận rồi")
            return

        add_money(uid, 1000, "checkin")
        query("UPDATE users SET last_checkin=? WHERE user_id=?", (today, uid))
        await update.message.reply_text("🎉 +1000đ")

    elif txt == "📮 Mời bạn":
        msg = (
            "🎁 KIẾM TIỀN CÙNG BẠN BÈ\n"
            "1F = 4,000đ\n"
            "💸 Mời bạn bè nhận ngay +4,000đ mỗi lượt\n"
            "🏦 Min rút: 20,000đ\n\n"
            f"https://t.me/{BOT_USERNAME}?start={uid}"
        )
        await update.message.reply_text(msg, disable_web_page_preview=False)

    elif txt == "🛒 Rút tiền":
        await update.message.reply_text("Dùng: /rut bank stk ten amount")

    elif txt == "📜 Lịch sử":
        data = query("SELECT * FROM history WHERE user_id=? ORDER BY rowid DESC LIMIT 5", (uid,)).fetchall()
        msg = "\n".join([f"{d[1]} | {d[2]}" for d in data])
        await update.message.reply_text(msg or "Không có")

    elif txt == "📞 Hỗ trợ":
        await update.message.reply_text("@RoGarden")

    elif txt == "🎲 Tài xỉu":
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Tài 1K", callback_data="tx_tai_1000"),
                InlineKeyboardButton("Xỉu 1K", callback_data="tx_xiu_1000"),
            ],
            [
                InlineKeyboardButton("Tài 5K", callback_data="tx_tai_5000"),
                InlineKeyboardButton("Xỉu 5K", callback_data="tx_xiu_5000"),
            ],
            [
                InlineKeyboardButton("Tài 10K", callback_data="tx_tai_10000"),
                InlineKeyboardButton("Xỉu 10K", callback_data="tx_xiu_10000"),
            ]
        ])
        await update.message.reply_text("🎲 Chọn cửa & tiền cược:", reply_markup=keyboard)

# ===== TAIXIU =====
async def taixiu_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query_btn = update.callback_query
    await query_btn.answer()

    data = query_btn.data

    if data.startswith("tx_"):
        uid = query_btn.from_user.id

        _, choice, amount = data.split("_")
        amount = int(amount)

        if get_balance(uid) < amount:
            await query_btn.edit_message_text("❌ Không đủ tiền")
            return

        sub_money(uid, amount)

        dice = [random.randint(1,6) for _ in range(3)]
        total = sum(dice)

        result = "tai" if total >= 11 else "xiu"

        if choice == result:
            add_money(uid, amount * 2, "taixiu_win")
            msg = f"🎲 {dice} = {total}\n👉 {'Tài' if result=='tai' else 'Xỉu'}\n\n✅ Bạn thắng +{amount}"
        else:
            msg = f"🎲 {dice} = {total}\n👉 {'Tài' if result=='tai' else 'Xỉu'}\n\n❌ Bạn thua -{amount}"

        await query_btn.edit_message_text(msg)

# ===== RÚT =====
async def rut(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if len(ctx.args) < 4:
        await update.message.reply_text("Sai cú pháp")
        return

    bank, stk, name = ctx.args[0], ctx.args[1], ctx.args[2]

    try:
        amount = int(ctx.args[3])
    except:
        await update.message.reply_text("Sai số tiền")
        return

    if amount < MIN_WITHDRAW:
        await update.message.reply_text("Min 12k")
        return

    now = datetime.now()
    last = query("SELECT last_withdraw FROM users WHERE user_id=?", (uid,)).fetchone()[0]

    if last:
        if (now - datetime.fromisoformat(last)) < timedelta(seconds=60):
            await update.message.reply_text("Đợi 60s")
            return

    if not sub_money(uid, amount):
        await update.message.reply_text("Không đủ tiền")
        return

    query("UPDATE users SET bank=?, stk=?, name=?, last_withdraw=? WHERE user_id=?",
          (bank, stk, name, now.isoformat(), uid))

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Duyệt", callback_data=f"ok_{uid}_{amount}"),
            InlineKeyboardButton("❌ Từ chối", callback_data=f"no_{uid}_{amount}")
        ]
    ])

    await ctx.bot.send_message(
        ADMIN_ID,
        f"💸 Yêu cầu rút tiền\n\n👤 ID: {uid}\n💰 {amount}\n🏦 {bank} | {stk} | {name}",
        reply_markup=keyboard
    )

    await update.message.reply_text("Đã gửi yêu cầu")

# ===== CALLBACK RÚT =====
async def handle_withdraw_action(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query_btn = update.callback_query
    await query_btn.answer()

    if query_btn.from_user.id != ADMIN_ID:
        return

    action, uid, amount = query_btn.data.split("_")
    uid = int(uid)
    amount = int(amount)

    if action == "ok":
        await ctx.bot.send_message(uid, f"✅ Rút {amount} thành công")
        await query_btn.edit_message_text("✅ ĐÃ DUYỆT")

    elif action == "no":
        add_money(uid, amount, "refund")
        await ctx.bot.send_message(uid, f"❌ Bị từ chối")
        await query_btn.edit_message_text("❌ ĐÃ TỪ CHỐI")

# ===== RUN =====
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("rut", rut))

app.add_handler(CommandHandler("add", add))
app.add_handler(CommandHandler("sub", sub))
app.add_handler(CommandHandler("ban", ban))
app.add_handler(CommandHandler("unban", unban))
app.add_handler(CommandHandler("stats", stats))
app.add_handler(CommandHandler("all", all_user))

app.add_handler(CallbackQueryHandler(taixiu_callback, pattern="^tx_"))
app.add_handler(CallbackQueryHandler(handle_withdraw_action))

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

print("BOT PRO RUNNING...")
app.run_polling()
