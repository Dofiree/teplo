import socket
import threading
import os
import random
import time
import hashlib
from datetime import datetime
APP_NAME = "Teplo"
MAX_WARNS = 5
SERVERS_FILE = "servers.txt"

clients = {} 
banned_hashes = set()
groups = {} 

def hash_data(data):
    salt = "TEPLO_SALT_2026_SECURE"
    return hashlib.sha256((data + salt).encode('utf-8')).hexdigest()

def log_to_chat(message):
    timestamp = datetime.now().strftime("%d.%m %H:%M")
    if not os.path.exists('chat.txt'):
        open('chat.txt', 'w', encoding='utf-8').close()
    with open('chat.txt', 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] {message}\n")

def send_history(client_socket, enc):
    if os.path.exists('chat.txt'):
        try:
            client_socket.sendall(f"\r\n--- История ---\r\n".encode(enc, errors='replace'))
            with open('chat.txt', 'r', encoding='utf-8') as f:
                for line in f:
                    clean_line = line.strip()
                    if clean_line:
                        client_socket.sendall((clean_line + "\r\n").encode(enc, errors='replace'))
            client_socket.sendall(f"---------------\r\n".encode(enc, errors='replace'))
        except: pass

def load_data():
    global banned_hashes
    for file in ['bans_ip.txt', 'warns.txt', 'friends.txt', 'logins.txt', 'chat.txt', 'balances.txt', SERVERS_FILE]:
        if not os.path.exists(file):
            open(file, 'w', encoding='utf-8').close()

    with open('bans_ip.txt', 'r') as f:
        banned_hashes = set(line.strip() for line in f if line.strip())
        
    warns = {}
    with open('warns.txt', 'r') as f:
        for line in f:
            if ':' in line:
                u, count = line.strip().split(':')
                warns[u] = int(count)
    return warns

def save_warn(user, count):
    warns = load_data()
    warns[user] = count
    with open('warns.txt', 'w') as f:
        for u, c in warns.items():
            f.write(f"{u}:{c}\n")

def get_balance(user):
    if os.path.exists('balances.txt'):
        with open('balances.txt', 'r', encoding='utf-8') as f:
            for line in f:
                if ':' in line:
                    u, bal = line.strip().split(':')
                    if u.lower() == user.lower():
                        return int(bal)
    return 100

def set_balance(user, amount):
    balances = {}
    if os.path.exists('balances.txt'):
        with open('balances.txt', 'r', encoding='utf-8') as f:
            for line in f:
                if ':' in line:
                    u, bal = line.strip().split(':')
                    balances[u] = int(bal)
    balances[user] = amount
    with open('balances.txt', 'w', encoding='utf-8') as f:
        for u, b in balances.items():
            f.write(f"{u}:{b}\n")

def ip_ban(ip):
    ip_hash = hash_data(ip)
    banned_hashes.add(ip_hash)
    with open('bans_ip.txt', 'a') as f:
        f.write(f"{ip_hash}\n")

def load_accounts():
    accounts = {}
    if os.path.exists('logins.txt'):
        with open('logins.txt', 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                parts = line.strip().split(':')
                if len(parts) >= 3:
                    accounts[parts[0]] = {"pass_hash": parts[1], "role": parts[2]}
    return accounts

def get_friends():
    friends = []
    if os.path.exists('friends.txt'):
        with open('friends.txt', 'r', encoding='utf-8') as f:
            for line in f:
                if ':' in line:
                    friends.append(line.strip().split(':'))
    return friends

def add_friend_link(u1, u2):
    pair = sorted([u1, u2])
    friends = get_friends()
    if pair not in friends:
        with open('friends.txt', 'a', encoding='utf-8') as f:
            f.write(f"{pair[0]}:{pair[1]}\n")
        return True
    return False

def broadcast(msg, sender_socket=None, is_event=False):
    prefix = f"[{APP_NAME}]: " if sender_socket is None and not is_event else ""
    full_msg = f"\r\n{prefix}{msg}\r\n"
    
    print(f"{prefix}{msg}")
    log_to_chat(f"{prefix}{msg}")

    for sock, info in list(clients.items()):
        if sock == sender_socket and not is_event:
            continue
        try:
            sock.sendall(full_msg.encode(info['enc'], errors='replace'))
        except:
            remove_client(sock)

def send_group_msg(g_name, sender_name, msg_text):
    full_g_msg = f"\r\n[Группа {g_name}] {sender_name}: {msg_text}\r\n"
    print(f"[ГРУППА {g_name}] {sender_name}: {msg_text}")

    for s, i in clients.items():
        if i['name'] in groups[g_name]["members"]:
            try:
                s.sendall(full_g_msg.encode(i['enc'], errors='replace'))
            except: pass

def send_to(sock, text):
    try:
        info = clients.get(sock, {"enc": "utf-8", "name": "Guest"})
        sock.sendall(f"\r\n{text}\r\n".encode(info['enc'], errors='replace'))
    except: pass

def remove_client(sock, reason="вышел"):
    if sock in clients:
        name = clients[sock]['name']
        del clients[sock]
        broadcast(f"--- {name} {reason} ---", is_event=True)
    try: sock.close()
    except: pass

def handle_commands(sock, line):
    info = clients[sock]
    name, role, ip = info['name'], info['role'], info['ip']
    parts = line.split(' ')
    cmd = parts[0].lower()
    
    print(f"[КОМАНДА] {name}: {line}")

    if cmd == "/help":
        send_to(sock, "/list - онлайн\r\n"
                      "/w [ник] [текст] - ЛС\r\n"
                      "/slots [ставка] - казино\r\n"
                      "/balance - мой баланс\r\n"
                      "/group create [название] [open/private] - создать группу\r\n"
                      "/group join [название] - войти в группу\r\n"
                      "/group invite [название] [ник] - пригласить в группу\r\n"
                      "/g main - вернуться в общий чат\r\n"
                      "/g [название] - переключиться в группу\r\n"
                      "/friend add [ник] - добавить в друзья\r\n"
                      "/friends - список друзей\r\n"
                      "/me [текст] - действие\r\n"
                      "/roll [число] - кубик\r\n"
                      "/coin - орел или решка\r\n"
                      "/time - время сервера\r\n"
                      "/whois [ник] - профиль юзера\r\n"
                      "/stats - мой профиль\r\n"
                      "/clear - очистить экран\r\n"
                      "/exit - выйти\r\n"
                      + ("\r\n[АДМИН]: /warn [ник], /kick [ник], /ban [ник]" if role in ["admin", "op", "creator"] else ""))

    elif cmd == "/balance":
        bal = get_balance(name)
        send_to(sock, f"Ваш баланс: {bal} монет")

    elif cmd == "/slots":
        bal = get_balance(name)
        bet = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 10
        if bet <= 0 or bet > bal:
            send_to(sock, f"Неверная ставка! Ваш баланс: {bal}")
            return None

        symbols = ["🍒", "🍋", "777", "💎", "🔔"]
        r1, r2, r3 = random.choice(symbols), random.choice(symbols), random.choice(symbols)
        slot_str = f"[ {r1} | {r2} | {r3} ]"

        if r1 == r2 == r3 == "777":
            win = bet * 10
            set_balance(name, bal + win)
            broadcast(f"🎰 [СЛОТЫ] {name} сорвал ДЖЕКПОТ x10 ({win} монет)! {slot_str}", is_event=True)
        elif r1 == r2 == r3:
            win = bet * 5
            set_balance(name, bal + win)
            send_to(sock, f"🎰 {slot_str} Выиграл x5! (+{win} монет)")
        elif r1 == r2 or r2 == r3 or r1 == r3:
            win = bet * 2
            set_balance(name, bal + win)
            send_to(sock, f"🎰 {slot_str} Выиграл x2! (+{win} монет)")
        else:
            set_balance(name, bal - bet)
            send_to(sock, f"🎰 {slot_str} Проигрыш! (-{bet} монет)")

    elif cmd == "/g" and len(parts) >= 2:
        target_g = parts[1]
        if target_g.lower() in ["main", "global", "общее", "общий"]:
            info['active_group'] = None
            send_to(sock, "Вы переключились в Общий Чат.")
        elif target_g in groups:
            if groups[target_g]["type"] == "open" or name in groups[target_g]["members"]:
                groups[target_g]["members"].add(name)
                info['active_group'] = target_g
                send_to(sock, f"Вы переключились на группу '{target_g}'.")
            else: send_to(sock, "Вы не состоите в этой закрытой группе.")
        else: send_to(sock, "Группа не найдена.")

    elif cmd == "/group" and len(parts) >= 3:
        sub = parts[1].lower()
        g_name = parts[2]

        if sub == "create":
            g_type = parts[3].lower() if len(parts) > 3 and parts[3].lower() in ["open", "private"] else "open"
            if g_name in groups:
                send_to(sock, "Группа с таким именем уже есть!")
            else:
                groups[g_name] = {"type": g_type, "owner": name, "members": {name}}
                info['active_group'] = g_name
                send_to(sock, f"Группа '{g_name}' ({g_type}) создана! Вы вошли в неё.")

        elif sub == "join":
            if g_name in groups:
                if groups[g_name]["type"] == "open" or name in groups[g_name]["members"]:
                    groups[g_name]["members"].add(name)
                    info['active_group'] = g_name
                    send_to(sock, f"Вы вошли в группу '{g_name}'.")
                else: send_to(sock, "Это закрытая группа! Нужен инвайт.")
            else: send_to(sock, "Группа не найдена.")

        elif sub == "invite" and len(parts) >= 4:
            target = parts[3]
            if g_name in groups and name in groups[g_name]["members"]:
                groups[g_name]["members"].add(target)
                send_to(sock, f"{target} добавлен в группу '{g_name}'.")
                t_sock = next((s for s, i in clients.items() if i['name'].lower() == target.lower()), None)
                if t_sock:
                    send_to(t_sock, f"Вас пригласили в группу '{g_name}'! Переключитесь: '/g {g_name}'")
            else: send_to(sock, "Ошибка приглашения.")

    elif cmd == "/list":
        online = [f"{i['name']}({i['role']})" for i in clients.values()]
        send_to(sock, f"В сети: {', '.join(online)}")

    elif cmd == "/friend" and len(parts) >= 3 and parts[1].lower() == "add":
        target = parts[2]
        if target.lower() == name.lower(): return None
        accs = load_accounts()
        t_real = next((u for u in accs if u.lower() == target.lower()), None)
        if t_real:
            if add_friend_link(name, t_real):
                send_to(sock, f"Добавлен {t_real}!")
                t_sock = next((s for s, i in clients.items() if i['name'].lower() == target.lower()), None)
                if t_sock:
                    send_to(t_sock, f"[{APP_NAME}]: {name} добавил вас в друзья!")
            else: send_to(sock, "Уже в друзьях.")
        else: send_to(sock, "Юзер не найден.")

    elif cmd == "/friends":
        f_list = get_friends()
        my_f = [p[1] if p[0].lower() == name.lower() else p[0] for p in f_list if name.lower() in (p[0].lower(), p[1].lower())]
        online_n = [i['name'].lower() for i in clients.values()]
        res = ["--- Друзья ---"] + [f"- {f} [{'ОНЛАЙН' if f.lower() in online_n else 'ОФФЛАЙН'}]" for f in my_f]
        send_to(sock, "\r\n".join(res) if my_f else "Друзей нет.")

    elif cmd == "/me" and len(parts) > 1:
        broadcast(f"* {name} {' '.join(parts[1:])}", is_event=True)

    elif cmd == "/roll":
        mv = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 100
        broadcast(f"[КУБИК] {name}: {random.randint(1, mv)}/{mv}", is_event=True)

    elif cmd == "/coin":
        res = random.choice(["Орел", "Решка"])
        broadcast(f"[МОНЕТКА] {name} подбросил: {res}", is_event=True)

    elif cmd == "/time":
        send_to(sock, f"Время сервера: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")

    elif cmd in ["/stats", "/whois"]:
        target = parts[1] if cmd == "/whois" and len(parts) > 1 else name
        accs = load_accounts()
        target_real = next((u for u in accs if u.lower() == target.lower()), None)
        if not target_real:
            send_to(sock, "Юзер не найден.")
            return None
            
        warns = load_data().get(target_real, 0)
        bal = get_balance(target_real)
        f_count = sum(1 for p in get_friends() if target_real.lower() in (p[0].lower(), p[1].lower()))
        send_to(sock, f"--- Профиль: {target_real} ---\r\nРоль: {accs[target_real]['role']}\r\nБаланс: {bal} монет\r\nВарны: {warns}/{MAX_WARNS}\r\nДрузей: {f_count}")

    elif cmd == "/clear":
        try: sock.sendall(b"\x1b[2J\x1b[H")
        except: pass

    elif role in ["admin", "op", "creator"] and cmd == "/warn" and len(parts) > 1:
        t_name = parts[1]
        warns = load_data()
        c = warns.get(t_name, 0) + 1
        save_warn(t_name, c)
        broadcast(f"{t_name} получил варн [{c}/{MAX_WARNS}] от {name}!")
        if c >= MAX_WARNS:
            t_sock = next((s for s, i in clients.items() if i['name'] == t_name), None)
            if t_sock:
                ip_ban(clients[t_sock]['ip'])
                remove_client(t_sock, "ЗАБАНЕН АВТОМАТИЧЕСКИ")

    elif role in ["admin", "op", "creator"] and cmd == "/kick" and len(parts) > 1:
        t_name = parts[1]
        t_sock = next((s for s, i in clients.items() if i['name'] == t_name), None)
        if t_sock: remove_client(t_sock, "КИКНУТ")

    elif role in ["admin", "op", "creator"] and cmd == "/ban" and len(parts) > 1:
        t_name = parts[1]
        t_sock = next((s for s, i in clients.items() if i['name'] == t_name), None)
        if t_sock:
            ip_ban(clients[t_sock]['ip'])
            remove_client(t_sock, "ЗАБАНЕН")

    elif cmd == "/w" and len(parts) > 2:
        t_name, m = parts[1], " ".join(parts[2:])
        t_sock = next((s for s, i in clients.items() if i['name'].lower() == t_name.lower()), None)
        if t_sock:
            t_sock.sendall(f"\r\n(ЛС от {name}): {m}\r\n".encode(clients[t_sock]['enc'], errors='replace'))
            print(f"[ЛС] {name} -> {t_name}: {m}")
            
    elif cmd == "/exit":
        remove_client(sock)
        return "exit"
    return None

def handle_client(sock, addr):
    ip = addr[0]
    if hash_data(ip) in banned_hashes:
        sock.sendall(b"Banned.\r\n")
        sock.close()
        return

    buf = b""
    enc = 'utf-8'
    
    def get_line(prompt):
        nonlocal buf
        sock.sendall(prompt.encode(enc, errors='replace'))
        while True:
            try:
                data = sock.recv(1024)
                if not data: return None
                if data == b"SYNC_V1\n": return "SYNC_V1"
                buf += data
                if b"\n" in buf or b"\r" in buf:
                    line = buf.decode(enc, errors='ignore').strip()
                    buf = b""
                    if not line:
                        sock.sendall(prompt.encode(enc, errors='replace'))
                        continue
                    return line
            except: return None

    try:
        sock.sendall(f"--- {APP_NAME} ---\r\n1. Win CMD(CP866)\r\n2. Win Telnet(CP1251)\r\n3. Linux(UTF-8)\r\n> ".encode('utf-8'))
        choice = ""
        while choice not in ["1", "2", "3"]:
            d = sock.recv(1024)
            if d == b"SYNC_V1\n": return
            c_str = d.decode('utf-8', errors='ignore').strip()
            if c_str in ["1", "2", "3"]: choice = c_str
            
        enc = {'1': 'cp866', '2': 'cp1251', '3': 'utf-8'}[choice]
        name = ""
        
        while not name:
            act = get_line("1. Вход | 2. Рег\r\n> ")
            if not act: break
            accs = load_accounts()
            
            if act == "1":
                u, p = get_line("Логин: "), get_line("Пароль: ")
                if not u or not p: continue
                
                p_hash = hash_data(p)
                if u in accs and accs[u]["pass_hash"] == p_hash:
                    if any(i['name'].lower() == u.lower() for i in clients.values()):
                        send_to(sock, "Уже в сети!")
                    else:
                        name, role = u, accs[u]["role"]
                else: send_to(sock, "Ошибка входа.")
                    
            elif act == "2":
                u, p = get_line("Логин: "), get_line("Пароль: ")
                if u and u not in accs and p:
                    p_hash = hash_data(p)
                    with open('logins.txt', 'a', encoding='utf-8') as f:
                        f.write(f"{u}:{p_hash}:user\n")
                    send_to(sock, "Успешно! Теперь войдите (1).")
                    print(f"[+] Зарегистрирован новый юзер: {u}")
                else: send_to(sock, "Занято или некорректные данные.")

        if not name: return
        clients[sock] = {"name": name, "role": role, "enc": enc, "ip": ip, "active_group": None}
        send_history(sock, enc)
        broadcast(f"--- {name} вошел ---", is_event=True)

        while True:
            active_g = clients[sock].get('active_group')
            channel_name = active_g if active_g else "Общий"
            
            msg = get_line(f"[{name} ({channel_name})]: ")
            if msg is None: break
            if not msg: continue
            
            if msg.startswith("/"):
                if handle_commands(sock, msg) == "exit": break
            else: 
                if active_g and active_g in groups:
                    send_group_msg(active_g, name, msg)
                else:
                    broadcast(f"{name}: {msg}", sender_socket=sock)
    except: pass
    finally: remove_client(sock)

def start_server():
    load_data()
    
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind(('0.0.0.0', 2323))
        server.listen(10)
        print(f"[*] {APP_NAME} запущен на 2323.")
    except: return
    
    def console():
        while True:
            cmd = input().strip()
            if not cmd: continue
            if cmd in ["/stop", "/off"]:
                os._exit(0)
            elif cmd.startswith("/op "):
                target = cmd.split(" ")[1]
                accs = load_accounts()
                if target in accs:
                    accs[target]["role"] = "op"
                    with open('logins.txt', 'w', encoding='utf-8') as f:
                        for u, d in accs.items():
                            f.write(f"{u}:{d['pass_hash']}:{d['role']}\n")
                    for s, i in clients.items():
                        if i['name'] == target:
                            clients[s]['role'] = "op"
                            send_to(s, "Вы получили права администратора!")
                    print(f"[+] {target} теперь админ.")
                else: print("[-] Нет такого юзера.")
            elif cmd.startswith("/"): print("[-] Неизвестная команда.")
            else: broadcast(cmd)
    
    threading.Thread(target=console, daemon=True).start()
    
    while True:
        try:
            conn, addr = server.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
        except: break

if __name__ == "__main__":
    start_server()
