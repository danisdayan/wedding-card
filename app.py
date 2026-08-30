from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import secrets
import os
import socket
import functools
import sys
import string
from user_agents import parse

# ========== تنظیم مسیر ==========
def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_path()

# ========== تنظیمات Flask ==========
app = Flask(__name__,
            template_folder=os.path.join(BASE_DIR, 'templates'),
            static_folder=os.path.join(BASE_DIR, 'static'))

app.config['SECRET_KEY'] = secrets.token_hex(32)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'invitations.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)

# ========== مدل دیتابیس ==========
class Member(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    companion_type = db.Column(db.String(50), default="به تنهایی")
    unique_id = db.Column(db.String(20), unique=True, nullable=False)
    photo = db.Column(db.String(200), nullable=True)
    
    seen = db.Column(db.Boolean, default=False)
    seen_at = db.Column(db.DateTime, nullable=True)
    ip_address = db.Column(db.String(50), nullable=True)
    device_info = db.Column(db.String(500), nullable=True)
    device_type = db.Column(db.String(50), nullable=True)
    device_brand = db.Column(db.String(100), nullable=True)
    device_model = db.Column(db.String(100), nullable=True)
    os_info = db.Column(db.String(100), nullable=True)
    os_version = db.Column(db.String(50), nullable=True)
    browser = db.Column(db.String(100), nullable=True)
    browser_version = db.Column(db.String(50), nullable=True)
    is_mobile = db.Column(db.Boolean, default=False)
    is_tablet = db.Column(db.Boolean, default=False)
    is_pc = db.Column(db.Boolean, default=False)
    is_bot = db.Column(db.Boolean, default=False)
    language = db.Column(db.String(20), nullable=True)
    referrer = db.Column(db.String(500), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def generate_unique_id(self):
        chars = string.ascii_letters + string.digits
        while True:
            uid = ''.join(secrets.choice(chars) for _ in range(10))
            if not Member.query.filter_by(unique_id=uid).first():
                return uid

# ========== تابع کمکی ==========
def get_device_details(user_agent_string):
    if not user_agent_string:
        return {
            'device_type': 'نامشخص', 'device_brand': 'نامشخص', 'device_model': 'نامشخص',
            'os_name': 'نامشخص', 'os_version': '', 'browser': 'نامشخص', 'browser_version': '',
            'is_mobile': False, 'is_tablet': False, 'is_pc': False, 'is_bot': False
        }
    try:
        user_agent = parse(user_agent_string)
        device_type = 'موبایل'
        if user_agent.is_tablet:
            device_type = 'تبلت'
        elif user_agent.is_pc:
            device_type = 'کامپیوتر'
        elif user_agent.is_bot:
            device_type = 'ربات'
        return {
            'device_type': device_type,
            'device_brand': user_agent.device.brand or 'نامشخص',
            'device_model': user_agent.device.model or 'نامشخص',
            'os_name': user_agent.os.family or 'نامشخص',
            'os_version': user_agent.os.version_string or '',
            'browser': user_agent.browser.family or 'نامشخص',
            'browser_version': user_agent.browser.version_string or '',
            'is_mobile': user_agent.is_mobile,
            'is_tablet': user_agent.is_tablet,
            'is_pc': user_agent.is_pc,
            'is_bot': user_agent.is_bot
        }
    except:
        return {
            'device_type': 'نامشخص', 'device_brand': 'نامشخص', 'device_model': 'نامشخص',
            'os_name': 'نامشخص', 'os_version': '', 'browser': 'نامشخص', 'browser_version': '',
            'is_mobile': False, 'is_tablet': False, 'is_pc': False, 'is_bot': False
        }

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ========== دکوراتور لاگین ==========
def login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# ========== مسیرها ==========

@app.route("/")
def home():
    return render_template("welcome.html")

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == "admin" and password == "admin":
            session['admin_logged_in'] = True
            return redirect(url_for("admin_panel"))
        else:
            return render_template("login.html", error="نام کاربری یا رمز عبور اشتباه است")
    return render_template("login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for("admin_login"))

@app.route("/admin")
@login_required
def admin_panel():
    members = Member.query.order_by(Member.created_at.desc()).all()
    total = len(members)
    seen_count = sum(1 for m in members if m.seen)
    unseen_count = total - seen_count
    return render_template("admin.html", members=members, total=total, seen_count=seen_count, unseen_count=unseen_count)

@app.route("/admin/add", methods=["POST"])
@login_required
def add_member():
    name = request.form.get("name")
    companion_type = request.form.get("companion_type", "به تنهایی")
    
    if not name:
        return jsonify({"success": False, "error": "نام الزامی است"}), 400
    
    member = Member(name=name, companion_type=companion_type)
    member.unique_id = member.generate_unique_id()
    
    if 'photo' in request.files:
        file = request.files['photo']
        if file and file.filename and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            filename = f"{member.unique_id}.{ext}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            member.photo = url_for('static', filename=f'uploads/{filename}')
    
    db.session.add(member)
    db.session.commit()
    
    return jsonify({
        "success": True,
        "member": {
            "id": member.id,
            "name": member.name,
            "unique_id": member.unique_id,
            "companion_type": member.companion_type,
            "photo": member.photo,
            "link": url_for('invite', unique_id=member.unique_id, _external=True)
        }
    })

@app.route("/admin/delete/<int:member_id>", methods=["POST"])
@login_required
def delete_member(member_id):
    member = Member.query.get(member_id)
    if member:
        if member.photo:
            photo_path = os.path.join(BASE_DIR, 'static', 'uploads', os.path.basename(member.photo))
            if os.path.exists(photo_path):
                os.remove(photo_path)
        db.session.delete(member)
        db.session.commit()
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "کاربر یافت نشد"}), 404

@app.route("/admin/bulk-delete", methods=["POST"])
@login_required
def bulk_delete():
    data = request.get_json()
    ids = data.get('ids', [])
    for mid in ids:
        member = Member.query.get(mid)
        if member:
            if member.photo:
                photo_path = os.path.join(BASE_DIR, 'static', 'uploads', os.path.basename(member.photo))
                if os.path.exists(photo_path):
                    os.remove(photo_path)
            db.session.delete(member)
    db.session.commit()
    return jsonify({"success": True, "deleted": len(ids)})

@app.route("/invite/<unique_id>")
def invite(unique_id):
    member = Member.query.filter_by(unique_id=unique_id).first()
    if not member:
        return "❌ لینک نامعتبر است!", 404
    
    user_agent_string = request.headers.get('User-Agent')
    details = get_device_details(user_agent_string)
    
    member.seen = True
    member.seen_at = datetime.utcnow()
    member.ip_address = request.remote_addr
    member.device_info = user_agent_string
    member.device_type = details['device_type']
    member.device_brand = details['device_brand']
    member.device_model = details['device_model']
    member.os_info = f"{details['os_name']} {details['os_version']}".strip()
    member.os_version = details['os_version']
    member.browser = details['browser']
    member.browser_version = details['browser_version']
    member.is_mobile = details['is_mobile']
    member.is_tablet = details['is_tablet']
    member.is_pc = details['is_pc']
    member.is_bot = details['is_bot']
    member.language = request.headers.get('Accept-Language', '')[:20]
    member.referrer = request.referrer or ''
    
    db.session.commit()
    
    return render_template("card.html", member=member)

@app.route("/admin/member/<int:member_id>", methods=["GET"])
@login_required
def get_member(member_id):
    member = Member.query.get(member_id)
    if member:
        return jsonify({
            "id": member.id,
            "name": member.name,
            "companion_type": member.companion_type,
            "unique_id": member.unique_id,
            "photo": member.photo,
            "seen": member.seen,
            "seen_at": member.seen_at.strftime("%Y-%m-%d %H:%M") if member.seen_at else None,
            "ip_address": member.ip_address,
            "device_type": member.device_type,
            "device_brand": member.device_brand,
            "device_model": member.device_model,
            "os_info": member.os_info,
            "browser": member.browser,
            "is_mobile": member.is_mobile,
            "is_tablet": member.is_tablet,
            "is_pc": member.is_pc,
            "created_at": member.created_at.strftime("%Y-%m-%d %H:%M"),
            "link": url_for('invite', unique_id=member.unique_id, _external=True)
        })
    return jsonify({"error": "یافت نشد"}), 404

@app.route("/setup")
def setup():
    db.create_all()
    return "✅ دیتابیس ساخته شد!"

# ========== اجرا ==========
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    
    ip = get_local_ip()
    port = int(os.environ.get('PORT', 5000))
    
    print("=" * 50)
    print("💍 سیستم کارت دعوت عروسی")
    print("=" * 50)
    print(f"🌐 آدرس: http://{ip}:{port}")
    print(f"🔐 پنل مدیر: http://{ip}:{port}/admin/login")
    print("👤 نام کاربری: admin")
    print("🔑 رمز عبور: admin")
    print("=" * 50)
    
    app.run(host='0.0.0.0', port=port, debug=True)
