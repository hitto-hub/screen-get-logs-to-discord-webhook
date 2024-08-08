import subprocess
import requests
import os
from dotenv import load_dotenv
import difflib
import schedule
import time

# .envファイルを読み込む
load_dotenv()

# 環境変数から値を取得
webhook_url = os.getenv("WEBHOOK_URL")
screen_name = os.getenv("SCREEN_NAME")
log_file_path = os.path.expanduser(os.getenv("LOG_FILE_PATH"))
previous_log_file = os.path.join(log_file_path, "previous_logs.txt")
send_log_file = os.path.join(log_file_path, "sent_logs.txt")

# screenのログを取得
def get_screen_logs():
    try:
        result = subprocess.run(
            ['screen', '-S', screen_name, '-X', 'hardcopy', '-h', '/tmp/screen_logs.txt'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode != 0: # エラーが発生した場合
            print(f"エラー: {result.stderr}")
            return "error 1"
        # ログファイルを読み込む
        with open('/tmp/screen_logs.txt', 'r') as file:
            logs = file.read()
        return logs
    except Exception as e:
        print(f"例外が発生しました: {e}")
        return "error 2"

def send_to_discord(message):
    try:
        max_length = 2000
        message_lines = message.split('\n')
        current_chunk = ""

        for line in message_lines:
            if len(current_chunk) + len(line) + 1 > max_length:
                data = {"content": current_chunk}
                response = requests.post(webhook_url, json=data)
                if response.status_code != 204:
                    print(f"メッセージの送信に失敗しました: {response.status_code}, {response.text}")
                current_chunk = line
            else:
                if current_chunk:
                    current_chunk += "\n"
                current_chunk += line

        if current_chunk:
            data = {"content": current_chunk}
            response = requests.post(webhook_url, json=data)
            if response.status_code == 204:
                print("メッセージが正常に送信されました")
            else:
                print(f"メッセージの送信に失敗しました: {response.status_code}, {response.text}")

    except Exception as e:
        print(f"Discordへのメッセージ送信中に例外が発生しました: {e}")

def get_previous_logs():
    if not os.path.exists(previous_log_file):
        return ""
    with open(previous_log_file, 'r') as file:
        return file.read()

def get_sent_logs():
    if not os.path.exists(send_log_file):
        return ""
    with open(send_log_file, 'r') as file:
        return file.read()

def save_current_logs(logs):
    with open(previous_log_file, 'w') as file:
        file.write(logs)

def save_sent_logs(logs):
    with open(send_log_file, 'w') as file:
        file.write(logs)

# ログの差分を確認して、Discordに送信する/5秒ごとに
def check_and_send_logs():
    current_logs = get_screen_logs()
    if current_logs.startswith("error"): # エラーが発生した場合
        print("screenログの取得に失敗しました。")
        return
    if not current_logs:
        print("送信するログがありません。")
        return

    previous_logs = get_previous_logs()
    sent_logs = get_sent_logs()

    if current_logs == previous_logs:
        print("ログに変更はありません。")
        return

    diff = list(difflib.unified_diff(previous_logs.splitlines(), current_logs.splitlines(), lineterm=''))
    diff = [line[1:] for line in diff if line.startswith('+') and not line.startswith('+++')]

    if not diff:
        print("ログに差分はありません。")
        return

    new_diff_message = "\n".join(diff)
    if new_diff_message in sent_logs:
        print("新しい差分はありません。")
        return

    save_current_logs(current_logs)
    send_to_discord(new_diff_message)
    save_sent_logs(new_diff_message)

if __name__ == "__main__":
    # 5秒ごとにcheck_and_send_logs関数を実行するスケジュールを設定
    schedule.every(5).seconds.do(check_and_send_logs)

    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("プログラムを終了します...")
