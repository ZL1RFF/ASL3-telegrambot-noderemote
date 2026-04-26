import socket
import requests
import os
import subprocess
import html
import json
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from telegram.error import BadRequest

# --- CONFIGURATION LOADING ---
def load_config():
    """Loads node and token from config.json created by setup.sh"""
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print("CRITICAL ERROR: config.json not found! Run setup.sh first.")
        exit(1)

config = load_config()
MY_NODE = config["node_number"]
TOKEN = config["bot_token"]
DB_FILE = os.path.join(os.path.dirname(__file__), "favorites.json")

def load_favs():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_favs(favs):
    with open(DB_FILE, "w") as f:
        json.dump(favs, f)

# --- SYSTEM UTILITIES ---

def get_cpu_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            temp = float(f.read()) / 1000.0
        return f"{temp:.1f}°C"
    except Exception: return "Unknown"

def get_private_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception: return "Unknown"

def get_public_ip():
    try: return requests.get('https://api.ipify.org', timeout=5).text
    except Exception: return "Unknown"

def get_asl_stats():
    try:
        cmd = f"asterisk -rx 'rpt stats {MY_NODE}'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            lines = result.stdout.strip().splitlines()
            for line in lines:
                if "Nodes currently connected to us" in line:
                    nodes = re.findall(r'\b\d{4,6}\b', line)
                    if nodes:
                        return ", ".join(nodes)
            return "&lt;NONE&gt;"
        return "OFFLINE"
    except Exception:
        return "ERROR"

# --- TELEGRAM HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    favs = load_favs()
    keyboard = [
        [
            InlineKeyboardButton("⬛ STATUS", callback_data='status'),
            InlineKeyboardButton("🌐 NETWORK", callback_data='ip_info')
        ],
        [InlineKeyboardButton("🔹 FAVORITE NODES 🔹", callback_data='ignore')]
    ]
    
    for name, node in favs.items():
        keyboard.append([
            InlineKeyboardButton(f"🟢 Link {name}", callback_data=f"conn_{node}"),
            InlineKeyboardButton(f"🔴 Drop {node}", callback_data=f"disc_{node}")
        ])

    keyboard.append([
        InlineKeyboardButton("⚠️ DISCONNECT ALL", callback_data='disc_all'),
        InlineKeyboardButton("🛠️ SETTINGS", callback_data='manage_favs')
    ])
    keyboard.append([InlineKeyboardButton("🔄 REFRESH DASHBOARD", callback_data='menu')])

    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        f"<b>🔳 ASL3 COMMAND CENTER</b>\n"
        f"<code>────────────────────</code>\n"
        f"<b>📡 NODE:</b> <code>{MY_NODE}</code>\n"
        f"<b>🚦 STATE:</b> <code>{get_asl_stats()}</code>\n"
        f"<code>────────────────────</code>"
    )
    
    try:
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
        else:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    except BadRequest as e:
        if "Message is not modified" not in str(e): raise e

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    back_btn = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BACK TO CONSOLE", callback_data='menu')]])

    if data == 'menu' or data == 'ignore':
        await start(update, context)
    
    elif data == 'status':
        await query.edit_message_text(text=f"📊 <b>DETAILED LOG:</b>\n<code>{get_asl_stats()}</code>", parse_mode='HTML', reply_markup=back_btn)
    
    elif data == 'ip_info':
        msg = f"🌐 <b>IP ADDRESSING</b>\n🏠 INT: <code>{get_private_ip()}</code>\n🌍 PUB: <code>{get_public_ip()}</code>"
        await query.edit_message_text(text=msg, parse_mode='HTML', reply_markup=back_btn)

    elif data == 'manage_favs':
        favs = load_favs()
        current_list = "\n".join([f"▪️ <b>{name}</b> (<code>{node}</code>)" for name, node in favs.items()])
        msg = (
            f"🛠️ <b>NODE MANAGEMENT</b>\n\n"
            f"<b>REGISTERED:</b>\n{current_list if current_list else 'None'}\n\n"
            f"➕ <b>ADD:</b> <code>/add Name Node</code>\n"
            f"➖ <b>DEL:</b> <code>/del Name</code>\n"
            f"🔗 <b>MANUAL:</b> <code>/connect Node</code>\n"
            f"✂️ <b>MANUAL:</b> <code>/disconnect Node</code>\n\n"
            f"🌡️ <b>SYSTEM TEMP:</b> <code>{get_cpu_temp()}</code>"
        )
        temp_kb = [[InlineKeyboardButton("🌡️ CHECK TEMPERATURE", callback_data='temp')], [InlineKeyboardButton("⬅️ BACK TO CONSOLE", callback_data='menu')]]
        await query.edit_message_text(msg, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(temp_kb))

    elif data == 'temp':
        await query.edit_message_text(text=f"🌡️ <b>CPU TEMPERATURE</b>\n<code>Current: {get_cpu_temp()}</code>", parse_mode='HTML', reply_markup=back_btn)

    elif data == 'disc_all':
        subprocess.run(f"asterisk -rx 'rpt fun {MY_NODE} *806'", shell=True)
        await query.edit_message_text(text="🔳 <b>GLOBAL DISCONNECT SENT (*806)</b>", parse_mode='HTML', reply_markup=back_btn)

    elif data.startswith('conn_'):
        node = data.split('_')[1]
        subprocess.run(f"asterisk -rx 'rpt fun {MY_NODE} *3{node}'", shell=True)
        await query.edit_message_text(text=f"🟢 <b>LINKING: {node}</b>", parse_mode='HTML', reply_markup=back_btn)

    elif data.startswith('disc_'):
        node = data.split('_')[1]
        subprocess.run(f"asterisk -rx 'rpt fun {MY_NODE} *811{node}'", shell=True)
        await query.edit_message_text(text=f"🔴 <b>DROPPING: {node}</b>", parse_mode='HTML', reply_markup=back_btn)

# --- TEXT COMMAND HANDLERS ---

async def connect_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Usage: <code>/connect 55553</code>", parse_mode='HTML')
        return
    node = context.args[0]
    subprocess.run(f"asterisk -rx 'rpt fun {MY_NODE} *3{node}'", shell=True)
    await update.message.reply_text(f"🚀 <b>Manual Link Sent:</b> <code>{node}</code>", parse_mode='HTML')

async def disconnect_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Usage: <code>/disconnect 55553</code>", parse_mode='HTML')
        return
    node = context.args[0]
    subprocess.run(f"asterisk -rx 'rpt fun {MY_NODE} *811{node}'", shell=True)
    await update.message.reply_text(f"✂️ <b>Manual Drop Sent to:</b> <code>{node}</code>", parse_mode='HTML')

async def add_fav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2: return
    name, node = context.args[0], context.args[1]
    favs = load_favs(); favs[name] = node; save_favs(favs)
    await update.message.reply_text(f"✅ <b>{name}</b> STORED")

async def del_fav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return
    name = context.args[0]
    favs = load_favs()
    if name in favs:
        del favs[name]; save_favs(favs)
        await update.message.reply_text(f"🗑️ <b>{name}</b> REMOVED")

async def temp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🌡️ <b>CPU TEMP:</b> <code>{get_cpu_temp()}</code>", parse_mode='HTML')

# --- MAIN ---

def main():
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("connect", connect_cmd))
    application.add_handler(CommandHandler("disconnect", disconnect_cmd))
    application.add_handler(CommandHandler("add", add_fav))
    application.add_handler(CommandHandler("del", del_fav))
    application.add_handler(CommandHandler("temp", temp_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    print(f"ZL1RFF Cockpit Online for Node {MY_NODE}")
    application.run_polling()

if __name__ == '__main__':
    main()