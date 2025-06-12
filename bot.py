import requests
import time
import json
import random
import threading

TOKEN = "8007824197:AAFJ572tf2WSrG0KLtDPHj0YYdBUEN6INYo"
API_URL = f"https://api.telegram.org/bot{TOKEN}/"
CHOICES = ["👊", "✌️", "✋"]

user_data = {}
games = {}
waiting_players = []
rematch_requests = {}  # game_id: {"p1_ready": bool, "p2_ready": bool, "timer": threading.Timer}
search_timers = {}  # user_id: {"timer": threading.Timer, "message_id": int}
finished_games = {}  # Храним завершённые игры для реванша

def api_request(endpoint, data=None):
    try:
        if data:
            return requests.post(API_URL + endpoint, data=data, timeout=10).json()
        return requests.get(API_URL + endpoint, timeout=10).json()
    except:
        return {}

def send_message(chat_id, text, reply_markup=None, inline_markup=None):
    data = {"chat_id": chat_id, "text": text}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    elif inline_markup:
        data["reply_markup"] = json.dumps(inline_markup)
    response = api_request("sendMessage", data)
    return response.get("result", {}).get("message_id")

def delete_message(chat_id, message_id):
    try:
        api_request("deleteMessage", {"chat_id": chat_id, "message_id": message_id})
    except:
        pass

def get_keyboard():
    return {"keyboard": [[{"text": "👊"}, {"text": "✌️"}, {"text": "✋"}], 
                        [{"text": "💼 Профиль"}, {"text": "🎮 Найти игру"}]], 
            "resize_keyboard": True}

def get_game_keyboard():
    return {"keyboard": [[{"text": "👊"}, {"text": "✌️"}, {"text": "✋"}]], 
            "resize_keyboard": True}

def get_rematch_keyboard(game_id):
    return {"inline_keyboard": [[{"text": "🔄 Сыграть ещё", "callback_data": f"rematch_{game_id}"},
                               {"text": "❌ Выйти", "callback_data": f"exit_{game_id}"}]]}

def process_bot_game(user_id, choice):
    bot_choice = random.choice(CHOICES)
    if choice == bot_choice:
        result = "🤝 Ничья!"
    elif (choice == "👊" and bot_choice == "✌️") or \
         (choice == "✌️" and bot_choice == "✋") or \
         (choice == "✋" and bot_choice == "👊"):
        result = "🎉 Победа! +1 монета"
        user_data[user_id]["coins"] += 1
    else:
        result = "💀 Поражение! -1 монета"
        user_data[user_id]["coins"] -= 1
    return f"Ты: {choice}\nБот: {bot_choice}\n{result}"

def find_game(user_id, chat_id, name):
    global waiting_players
    waiting_players = [p for p in waiting_players if p["user_id"] != user_id]
    
    # Отменяем предыдущий таймер поиска если есть
    if user_id in search_timers:
        search_timers[user_id]["timer"].cancel()
        del search_timers[user_id]
    
    if waiting_players:
        opponent = waiting_players.pop(0)
        
        # Отменяем таймер противника если он искал игру
        if opponent["user_id"] in search_timers:
            search_timers[opponent["user_id"]]["timer"].cancel()
            delete_message(opponent["chat_id"], search_timers[opponent["user_id"]]["message_id"])
            del search_timers[opponent["user_id"]]
        
        game_id = f"{user_id}_{opponent['user_id']}"
        games[game_id] = {"p1": user_id, "p2": opponent["user_id"], "p1_choice": None, "p2_choice": None,
                         "p1_chat": chat_id, "p2_chat": opponent["chat_id"], 
                         "p1_name": name, "p2_name": opponent["name"]}
        
        send_message(chat_id, f"🎮 Игра найдена! Противник: {opponent['name']}\nВыбери ход:", get_game_keyboard())
        send_message(opponent["chat_id"], f"🎮 Игра найдена! Противник: {name}\nВыбери ход:", get_game_keyboard())
    else:
        waiting_players.append({"user_id": user_id, "chat_id": chat_id, "name": name})
        message_id = send_message(chat_id, "🔍 Ищем противника...")
        
        # Запускаем таймер на 25 секунд
        def search_timeout():
            if user_id in search_timers:
                # Удаляем из очереди ожидания
                global waiting_players
                waiting_players = [p for p in waiting_players if p["user_id"] != user_id]
                
                # Удаляем сообщение о поиске и отправляем новое
                delete_message(chat_id, search_timers[user_id]["message_id"])
                send_message(chat_id, "😔 Игра не найдена. Попробуй позже!", get_keyboard())
                del search_timers[user_id]
        
        timer = threading.Timer(25.0, search_timeout)
        timer.start()
        search_timers[user_id] = {"timer": timer, "message_id": message_id}

def process_multiplayer(user_id, choice):
    for game_id, game in games.items():
        if (game["p1"] == user_id and game["p1_choice"] is None) or \
           (game["p2"] == user_id and game["p2_choice"] is None):
            
            if game["p1"] == user_id:
                game["p1_choice"] = choice
                send_message(game["p1_chat"], f"Твой выбор: {choice}. Ждем противника...")
            else:
                game["p2_choice"] = choice
                send_message(game["p2_chat"], f"Твой выбор: {choice}. Ждем противника...")
            
            if game["p1_choice"] and game["p2_choice"]:
                finish_game(game_id)
            break

def finish_game(game_id):
    if game_id not in games:
        return
    
    game = games[game_id]
    p1_choice, p2_choice = game["p1_choice"], game["p2_choice"]
    
    if p1_choice == p2_choice:
        result = "🤝 Ничья!"
    elif (p1_choice == "👊" and p2_choice == "✌️") or \
         (p1_choice == "✌️" and p2_choice == "✋") or \
         (p1_choice == "✋" and p2_choice == "👊"):
        result = f"🎉 {game['p1_name']} победил! +2 монеты"
        user_data[game["p1"]]["coins"] += 2
        if user_data[game["p2"]]["coins"] > 0:
            user_data[game["p2"]]["coins"] -= 1
    else:
        result = f"🎉 {game['p2_name']} победил! +2 монеты"
        user_data[game["p2"]]["coins"] += 2
        if user_data[game["p1"]]["coins"] > 0:
            user_data[game["p1"]]["coins"] -= 1
    
    game_result = f"🎮 Результат игры:\n{game['p1_name']}: {p1_choice}\n{game['p2_name']}: {p2_choice}\n{result}"
    
    # Сохраняем игру для возможного реванша
    finished_games[game_id] = game.copy()
    
    # Отправляем результат с кнопкой реванша и выхода
    send_message(game["p1_chat"], game_result, inline_markup=get_rematch_keyboard(game_id))
    send_message(game["p2_chat"], game_result, inline_markup=get_rematch_keyboard(game_id))
    
    # Удаляем активную игру (игроки больше не могут продолжать играть)
    del games[game_id]

def handle_rematch(game_id, user_id):
    if game_id not in finished_games:
        return
    
    game = finished_games[game_id]
    
    # Инициализируем запрос на реванш если его нет
    if game_id not in rematch_requests:
        rematch_requests[game_id] = {"p1_ready": False, "p2_ready": False, "timer": None}
    
    req = rematch_requests[game_id]
    
    # Определяем кто нажал
    if game["p1"] == user_id:
        req["p1_ready"] = True
        send_message(game["p1_chat"], "✅ Ты готов к реваншу! Ждем противника...")
        send_message(game["p2_chat"], f"🔄 {game['p1_name']} хочет реванш!")
    else:
        req["p2_ready"] = True
        send_message(game["p2_chat"], "✅ Ты готов к реваншу! Ждем противника...")
        send_message(game["p1_chat"], f"🔄 {game['p2_name']} хочет реванш!")
    
    # Если оба готовы - начинаем новую игру
    if req["p1_ready"] and req["p2_ready"]:
        if req["timer"]:
            req["timer"].cancel()
        
        # Создаём новую активную игру
        new_game = game.copy()
        new_game["p1_choice"] = None
        new_game["p2_choice"] = None
        games[game_id] = new_game
        
        send_message(game["p1_chat"], "🎮 Реванш начался! Выбери ход:", get_game_keyboard())
        send_message(game["p2_chat"], "🎮 Реванш начался! Выбери ход:", get_game_keyboard())
        
        del rematch_requests[game_id]
        del finished_games[game_id]
    else:
        # Запускаем таймер на 10 секунд
        if req["timer"]:
            req["timer"].cancel()
        
        def timeout():
            if game_id in rematch_requests:
                send_message(game["p1_chat"], "⏰ Время ожидания реванша истекло", get_keyboard())
                send_message(game["p2_chat"], "⏰ Время ожидания реванша истекло", get_keyboard())
                del rematch_requests[game_id]
                if game_id in finished_games:
                    del finished_games[game_id]
        
        req["timer"] = threading.Timer(10.0, timeout)
        req["timer"].start()

def handle_exit_game(game_id, user_id):
    # Очищаем все данные связанные с игрой
    if game_id in games:
        game = games[game_id]
        send_message(game["p1_chat"], "❌ Игра завершена", get_keyboard())
        send_message(game["p2_chat"], "❌ Игра завершена", get_keyboard())
        del games[game_id]
    
    if game_id in finished_games:
        game = finished_games[game_id]
        send_message(game["p1_chat"], "❌ Вы вышли из игры", get_keyboard())
        send_message(game["p2_chat"], "❌ Оппонент вышел из игры", get_keyboard())
        del finished_games[game_id]
    
    if game_id in rematch_requests:
        if rematch_requests[game_id]["timer"]:
            rematch_requests[game_id]["timer"].cancel()
        del rematch_requests[game_id]

def is_in_game(user_id):
    return any(game["p1"] == user_id or game["p2"] == user_id for game in games.values())

def main():
    offset = None
    while True:
        try:
            updates = api_request("getUpdates" + (f"?offset={offset}" if offset else ""))
            
            if "result" in updates and updates["result"]:
                for update in updates["result"]:
                    try:
                        offset = update["update_id"] + 1
                        
                        # Обработка инлайн кнопок
                        if "callback_query" in update:
                            callback = update["callback_query"]
                            user_id = callback["from"]["id"]
                            data = callback["data"]
                            
                            if data.startswith("rematch_"):
                                game_id = data.replace("rematch_", "")
                                handle_rematch(game_id, user_id)
                            elif data.startswith("exit_"):
                                game_id = data.replace("exit_", "")
                                handle_exit_game(game_id, user_id)
                            
                            api_request("answerCallbackQuery", {"callback_query_id": callback["id"]})
                            continue
                        
                        # Обработка обычных сообщений
                        message = update.get("message")
                        if not message or "text" not in message:
                            continue

                        chat_id = message["chat"]["id"]
                        user_id = message["from"]["id"]
                        text = message.get("text", "")
                        name = message["from"].get("first_name", "Игрок")

                        if user_id not in user_data:
                            user_data[user_id] = {"coins": 10}

                        if text in CHOICES:
                            if is_in_game(user_id):
                                process_multiplayer(user_id, text)
                            else:
                                result = process_bot_game(user_id, text)
                                send_message(chat_id, result, get_keyboard())
                        
                        elif text == "💼 Профиль":
                            send_message(chat_id, f"💼 Профиль\nМонеты: {user_data[user_id]['coins']}", get_keyboard())
                        
                        elif text == "🎮 Найти игру":
                            if not is_in_game(user_id):
                                find_game(user_id, chat_id, name)
                            else:
                                send_message(chat_id, "Ты уже в игре!", get_keyboard())
                        
                        elif text == "/start":
                            send_message(chat_id, "Добро пожаловать! Выбери вариант для игры:", get_keyboard())
                        
                        else:
                            send_message(chat_id, "Выбери вариант для игры:", get_keyboard())
                    
                    except:
                        continue

        except:
            pass
        
        time.sleep(1)

if __name__ == "__main__":
    main()