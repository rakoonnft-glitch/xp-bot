import os
import sqlite3
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ==== 설정 ====
BOT_TOKEN = os.environ.get("BOT_TOKEN")  # Render 환경변수에서 가져옴
DB_PATH = os.environ.get("DB_PATH", "xp_bot.db")
XP_PER_MESSAGE = 10   # 메시지당 경험치


# ==== DB ====
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            username TEXT,
            xp INTEGER DEFAULT 0,
            messages INTEGER DEFAULT 0
        )
        """
    )
    conn.commit()
    conn.close()


def get_conn():
    return sqlite3.connect(DB_PATH)


# ==== 레벨 계산 ====
def calc_level(xp: int) -> int:
    return xp // 100 + 1   # 0~99: Lv1, 100~199: Lv2 ...


def xp_to_next_level(xp: int) -> int:
    level = calc_level(xp)
    next_total = level * 100
    return max(0, next_total - xp)


# ==== DB 함수 ====
def add_xp(user_id: int, username: str | None, xp: int):
    conn = get_conn()
    c = conn.cursor()

    c.execute("SELECT xp, messages FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()

    if row is None:
        c.execute(
            "INSERT INTO users (user_id, username, xp, messages) VALUES (?, ?, ?, ?)",
            (user_id, username, xp, 1),
        )
    else:
        current_xp, messages = row
        new_xp = current_xp + xp
        new_messages = messages + 1
        c.execute(
            "UPDATE users SET xp = ?, messages = ?, username = ? WHERE user_id = ?",
            (new_xp, new_messages, username, user_id),
        )

    conn.commit()
    conn.close()


def get_user(user_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT username, xp, messages FROM users WHERE user_id = ?",
        (user_id,),
    )
    row = c.fetchone()
    conn.close()
    return row


def get_top10():
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT username, xp FROM users ORDER BY xp DESC LIMIT 10"
    )
    rows = c.fetchall()
    conn.close()
    return rows


# ==== 핸들러 ====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "이 봇은 무엇을 할 수 있나요?\n"
        "- 채팅량을 측정하여 경험치로 환산합니다.\n"
        "- 경험치에 기반하여 유저의 레벨을 기록합니다.\n"
        "- /stats 명령어로 본인의 레벨 및 경험치를 확인하세요.\n"
        "- /ranking 명령어로 상위 10명의 명단을 확인하세요."
    )
    await update.message.reply_text(text)


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    row = get_user(user.id)

    if row is None:
        await update.message.reply_text("아직 기록된 정보가 없습니다. 먼저 채팅을 남겨주세요!")
        return

    username, xp, messages = row
    level = calc_level(xp)
    remain = xp_to_next_level(xp)

    display_name = user.full_name or "사용자"
    handle = f"@{user.username}" if user.username else username or ""
    if handle:
        title = f"{display_name}({handle})님의 통계"
    else:
        title = f"{display_name}님의 통계"

    text = (
        f"📊 {title}\n\n"
        f"🎯 레벨: {level}\n"
        f"⭐ 경험치: {xp} XP\n"
        f"📈 다음 레벨까지: {remain} XP\n"
        f"💬 총 메시지 수: {messages}"
    )

    await update.message.reply_text(text)


async def ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = get_top10()

    if not rows:
        await update.message.reply_text("아직 랭킹 데이터가 없습니다.")
        return

    lines = ["🏆 경험치 랭킹 TOP 10\n"]
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}

    for i, (username, xp) in enumerate(rows, start=1):
        level = calc_level(xp)
        handle = f"@{username}" if username else "이름없음"

        if i in medals:
            prefix = f"{medals[i]} "
        else:
            prefix = f"{i}. "

        line = f"{prefix}{handle} - Lv.{level} ({xp} XP)"
        lines.append(line)

    text = "\n".join(lines)
    await update.message.reply_text(text)


async def message_xp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    user = update.effective_user

    if user is None or user.is_bot:
        return

    username = user.username
    add_xp(user.id, username, XP_PER_MESSAGE)


# ==== 메인 ====
def main():
    init_db()

    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN 환경변수를 설정해주세요.")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("ranking", ranking))

    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS & (filters.TEXT | filters.STICKER | filters.PHOTO),
            message_xp,
        )
    )

    print("XP 봇 시작")
    app.run_polling()


if __name__ == "__main__":
    main()
