import os, json, webbrowser, subprocess, time, socket, signal
from flask import Flask, render_template, request, jsonify
from git import Repo
import requests
from pathlib import Path

app = Flask(__name__)
CONFIG_FILE = os.path.expanduser("~/.gitmaster_config.json")
PROJECTS_DIR = os.path.expanduser("~/GitMaster_Projects")
RUNNING_PROCS = {}

def get_token():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f: return json.load(f).get("github_token", "")
    return ""

def save_token(token):
    with open(CONFIG_FILE, 'w') as f: json.dump({"github_token": token}, f)

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

@app.route('/')
def index(): return render_template('index.html')

@app.route('/api/config', methods=['POST'])
def set_config():
    save_token(request.json.get('token'))
    return jsonify({"msg": "توکن با موفقیت ذخیره شد."})

@app.route('/api/repos')
def get_repos():
    token = get_token()
    if not token: return jsonify({"error": "توکن تنظیم نشده است."})
    res = requests.get("https://api.github.com/user/repos?per_page=100", headers={"Authorization": f"token {token}"})
    return jsonify([r['name'] for r in res.json()] if res.status_code == 200 else {"error": "خطا در دریافت ریپوها."})

@app.route('/api/local_dirs')
def get_local_dirs():
    base_path = request.args.get('path')
    if not base_path:
        if os.path.exists('/sdcard'): base_path = '/sdcard'
        else: base_path = os.path.expanduser("~")
    target_dir = Path(base_path).expanduser()
    if not target_dir.exists() or not target_dir.is_dir():
        return jsonify({"error": "مسیر پیدا نشد."})
    try:
        dirs = [{"name": p.name, "path": str(p)} for p in target_dir.iterdir() if p.is_dir() and not p.name.startswith('.')]
        dirs.sort(key=lambda x: x["name"].lower())
        return jsonify({"current_path": str(target_dir), "dirs": dirs})
    except Exception as e: return jsonify({"error": str(e)})

@app.route('/api/git', methods=['POST'])
def git_action():
    data = request.json; action, repo_name = data.get('action'), data.get('repo')
    repo_path = os.path.join(PROJECTS_DIR, repo_name)
    try:
        if action == 'clone':
            os.makedirs(PROJECTS_DIR, exist_ok=True)
            if not os.path.exists(repo_path):
                username = requests.get("https://api.github.com/user", headers={"Authorization": f"token {get_token()}"}).json().get('login')
                Repo.clone_from(f"https://{get_token()}@github.com/{username}/{repo_name}.git", repo_path)
                return jsonify({"msg": f"ریپوی {repo_name} کلون شد."})
            return jsonify({"msg": "این ریپو از قبل وجود دارد."})
        elif action == 'pull':
            Repo(repo_path).remotes.origin.pull()
            return jsonify({"msg": "دریافت تغییرات (Pull) موفق بود."})
        elif action == 'push':
            repo = Repo(repo_path); repo.git.add(A=True)
            if repo.is_dirty(untracked_files=True): repo.index.commit("Auto commit via GitMaster")
            repo.remotes.origin.push()
            return jsonify({"msg": "ارسال تغییرات (Push) موفق بود."})
    except Exception as e: return jsonify({"error": str(e)})

@app.route('/api/run', methods=['POST'])
def run_project():
    path = request.json.get('path')
    if not path or not os.path.exists(path): return jsonify({"error": "مسیر نامعتبر است"})
    port = find_free_port(); cmd = ""
    if os.path.exists(os.path.join(path, "package.json")): cmd = f"npm start -- --port {port}"
    elif os.path.exists(os.path.join(path, "main.py")): cmd = "python main.py"
    elif os.path.exists(os.path.join(path, "app.py")): cmd = "python app.py"
    else: cmd = f"python -m http.server {port}"
    try:
        proc = subprocess.Popen(cmd, shell=True, cwd=path, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        RUNNING_PROCS[path] = proc; time.sleep(1.5)
        if cmd.startswith("python -m http.server") or cmd.startswith("npm"):
            return jsonify({"msg": "پروژه اجرا شد.", "url": f"http://127.0.0.1:{port}"})
        return jsonify({"msg": "پروژه در پس‌زمینه اجرا شد."})
    except Exception as e: return jsonify({"error": str(e)})

if __name__ == '__main__':
    print("✅ GitMaster OS اجرا شد. در حال باز کردن مرورگر...")
    webbrowser.open("http://127.0.0.1:5000")
    app.run(port=5000, debug=False)
