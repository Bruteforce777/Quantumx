from flask import Flask, render_template,request,redirect,session,url_for,abort
from werkzeug.security import generate_password_hash, check_password_hash
from flask import flash, get_flashed_messages
from flask_login import UserMixin,login_user, logout_user,LoginManager,login_required,current_user
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy import func
from flask import send_from_directory
import os
from werkzeug.utils import secure_filename
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time
from datetime import datetime, timedelta
from functools import lru_cache, wraps
import threading
from decimal import Decimal, InvalidOperation,getcontext
getcontext().prec = 28
import logging
from dataclasses import dataclass
from itsdangerous import URLSafeTimedSerializer 
from email.mime.text import MIMEText
import smtplib
import random
import uuid
from user_agents import parse
from dotenv import load_dotenv





@dataclass
class Asset:
    symbol: str
    quantity: float
    price: float
    value: float
    pnl: float


app = Flask(__name__)


basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv()

app.config["ADMIN_EMAIL"] = os.environ.get("ADMIN_EMAIL")
app.config["ADMIN_PASSWORD"] = os.environ.get("ADMIN_PASSWORD")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config["MAX_CONTENT_LENGHT"] = 5 * 1024 * 1024

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL.startswith("sqlite"):
    app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
else:
    # Fix for postgres on some hosts
    app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL.replace("postgres://", "postgresql://", 1)



db = SQLAlchemy(app)
migrate = Migrate(app,db)

#---------Login Manager-----------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))   


# -----Model Class-------


class User(UserMixin,db.Model):
    __tablename__ = 'clients'

    id = db.Column(db.Integer,primary_key=True) 
    name = db.Column(db.String(80),nullable=False)
    surname = db.Column(db.String(80),nullable=False)
    email = db.Column(db.String(120),unique=True,nullable=False)
    phonenumber = db.Column(db.String(25),nullable=False)
    password_hash = db.Column(db.String(255),nullable=False)
    total_balance = db.Column(db.Float, default=0.0)
    account_number =  db.Column(db.String(10),unique=True,nullable=False,index=True)
    security_code =  db.Column(db.String(10),unique=True,nullable=False,index=True)
    margin_type = db.Column(db.String(20), default="isolated") # isolated / cross
    margin_rate = db.Column(db.Integer, default=1)
    margin_level = db.Column(db.Integer, default=20)
    leverage = db.Column(db.Integer, default=3)
    last_seen = db.Column(db.DateTime, server_default=db.func.now())
    created = db.Column(db.DateTime, server_default=db.func.now())

    pagevisit = db.relationship("PageVisit", backref="user")
    personalinfo = db.relationship("PersonalInfo", backref="user")
    userfile = db.relationship("UserFile", backref="user")
    helpmessage = db.relationship("HelpMessage", backref="user")
    deposit = db.relationship("Deposit",backref="user",lazy=True)
    withdrawal = db.relationship("Withdrawal",backref="user",lazy=True)
    withdraw = db.relationship("Withdraw",backref="user",lazy=True)
    trade = db.relationship("Trade",backref="user",lazy=True)
    portfolio = db.relationship("Portfolio",backref="user",lazy=True)


    def set_password(self,password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)  

    


# -------Foreign Model Classes For Clients---------


class Portfolio(db.Model):
    __tablename__ = 'portfolio'
    id = db.Column(db.Integer,primary_key=True)
    user_id = db.Column(db.Integer,db.ForeignKey("clients.id"),nullable=False) 
    symbol = db.Column(db.String(50),nullable=False)
    side = db.Column(db.String(4),nullable=False) 
    quantity = db.Column(db.Float,nullable=False) 
    current_price = db.Column(db.Float,nullable=False)
    entry_price = db.Column(db.Float,nullable=False) 
    pnl = db.Column(db.Float,default=0.0)
    status = db.Column(db.String(10),default="open")
    created = db.Column(db.DateTime, server_default=db.func.now())



class PersonalInfo(db.Model):
    __tablename__ = 'personal_info'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=True)
    fullname = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(45), nullable=False)
    nationality = db.Column(db.String(80), nullable=False)
    city = db.Column(db.String(80), nullable=False)
    address = db.Column(db.String(100),nullable=False )
    zipcode = db.Column(db.String(100), nullable=False)
    date_of_birth = db.Column(db.String(255),nullable=False)
    timestamp = db.Column(db.DateTime, server_default=db.func.now())
    
    

class PageVisit(db.Model):
    __tablename__ = 'page_visit'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=True)
    path = db.Column(db.String(255), nullable=False)
    method = db.Column(db.String(10))
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(255))
    device_type = db.Column(db.String(20)) 
    timestamp = db.Column(db.DateTime, server_default=db.func.now())


class Trade(db.Model):
    __tablename__ = 'trade'
    id = db.Column(db.Integer,primary_key=True)
    user_id = db.Column(db.Integer,db.ForeignKey("clients.id"),nullable=False) 
    symbol = db.Column(db.String(50),nullable=False)
    side = db.Column(db.String(4),nullable=False) 
    quantity = db.Column(db.Float,nullable=False) 
    current_price = db.Column(db.Float,nullable=False)
    entry_price = db.Column(db.Float,nullable=False) 
    margin_rate = db.Column(db.Integer, nullable=False)
    margin_used = db.Column(db.Integer, nullable=False )
    pnl = db.Column(db.Float,default=0.0)
    status = db.Column(db.String(10),default="open")
    created = db.Column(db.DateTime, server_default=db.func.now())

   
class Deposit(db.Model):
    __tablename__ = 'deposit'
    id = db.Column(db.Integer,primary_key=True)
    user_id = db.Column(db.Integer,db.ForeignKey("clients.id"),nullable=False) 
    amount = db.Column(db.Float,nullable=False)
    type = db.Column(db.String(10),nullable=False)
    created = db.Column(db.DateTime,server_default=db.func.now())


class Withdraw(db.Model):
    __tablename__ = 'withdraw'
    id = db.Column(db.Integer,primary_key=True)
    user_id = db.Column(db.Integer,db.ForeignKey("clients.id"),nullable=False) 
    amount = db.Column(db.Float,nullable=False)
    type = db.Column(db.String(10),nullable=False)
    created = db.Column(db.DateTime,server_default=db.func.now())


class Withdrawal(db.Model):
    __tablename__ = 'withdrawal'
    id = db.Column(db.Integer,primary_key=True)
    user_id = db.Column(db.Integer,db.ForeignKey("clients.id"),nullable=False)
    method = db.Column(db.String(20),nullable=False)
    amount = db.Column(db.Float,nullable=False)
    destination = db.Column(db.String(255),nullable=False)
    note = db.Column(db.Text)
    status = db.Column(db.String(20),default="Pending")
    created = db.Column(db.DateTime,server_default=db.func.now())    

class HelpMessage(db.Model):
    __tablename__ = "help_messages"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created = db.Column(db.DateTime, server_default=db.func.now())


class UserFile(db.Model):
    __tablename__ = "user_files"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(50))
    uploaded = db.Column(db.DateTime, server_default=db.func.now())





#==========================
#  PNL FUNCTION 
#==========================

def calculate_pnl(trade):
    if not trade.current_price or not trade.entry_price:
        return 0.0
    
    if trade.side.lower() == "buy":
        pnl = (trade.current_price - trade.entry_price) * trade.quantity
    elif trade.side.lower() == "sell":
        pnl = (trade.entry_price - trade.current_price) * trade.quantity
    else:
        pnl = 0.0

    return round(pnl,2)            


#==========================
#  DASHBOARD ROUTE 
#==========================

@app.route('/dashboard')
@login_required
def dashboard():

    if isinstance(current_user, FakeAdmin):
        return redirect(url_for('admin_dashboard'))

    user = current_user
    trades = Trade.query.filter_by(user_id=user.id, status='open').all()
    closed_trades = Trade.query.filter_by(user_id=user.id, status='closed').all()

    total_pnl = 0

    for trade in trades:
        try:
            current_price = fetch_price(trade.symbol)
            if current_price:
                trade.current_price = current_price

                if trade.side.lower() == 'buy':
                    trade.pnl = (current_price - trade.entry_price) * trade.quantity
                elif trade.side.lower() == 'sell':
                    trade.pnl = (trade.entry_price - current_price) * trade.quantity
                total_pnl += trade.pnl
        except Exception as e:
            flash(f"Error Updating {trade.symbol}: {e}", "danger")

    total_balance = user.total_balance or 0 + total_pnl

    db.session.commit()

    return render_template("dashboard.html", 
                            user=user, 
                            trades=trades,
                            closed_trades=closed_trades, 
                            total_pnl=total_pnl, 
                            total_balance=total_balance)  
             
#==========================
#  UPDATE PRICES ROUTE 
#==========================

def update_price(symbol: str):
    url = f"https://api.twelvedata.com/price?symbol={symbol}&apikey={API_KEY}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        print(f"API RESPONSE FOR {symbol}: {data}")

        price = data.get("price")

        if price is not None and price != "":
            return float(price)
        else:
            print(f"NO VALID PRICE FOR {symbol}: (response: {data})")
            return None
    except Exception as e:
        print(f"ERROR FETCHING {symbol}: {e}")
        return None

#==========================
#  OPEN TRADE ROUTE 
#==========================

@app.route("/open_trade", methods=["POST"])
@login_required
def open_trade():

    user = current_user

    if request.method == "POST":
        symbol = request.form.get("symbol")
        side = request.form.get("side")
        quantity = float(request.form.get("quantity"))

    if not symbol or not side or not quantity:
        flash("All fields are required", "danger")
        return redirect(url_for("dashboard"))

    # Fetch price
    price = fetch_price(symbol)
    if not price:
        flash(f"Could not fetch price for {symbol}", "danger")
        return redirect(url_for("dashboard"))

    # Margin calculation
    MARGIN_COSTS = {1: 100, 2: 200, 5: 500, 10: 1000}
    margin_cost = MARGIN_COSTS.get(user.margin_rate)

    if not margin_cost:
        flash("Invalid margin rate", "danger")
        return redirect(url_for("dashboard"))

    required_margin = margin_cost * quantity

    # Balance validation
    if user.total_balance is None or user.total_balance <= 0:
        flash("Insufficient balance", "danger")
        return redirect(url_for("dashboard"))

    if user.total_balance < required_margin:
        flash("Insufficient margin balance", "danger")
        return redirect(url_for("dashboard"))

    # Deduct margin
    user.total_balance -= required_margin

    # Create trade (NO pnl calculation here)
    trade = Trade(
        user_id=user.id,
        symbol=symbol.upper(),
        side=side.lower(),
        quantity=quantity,
        entry_price=price,
        current_price=price,
        margin_rate=user.margin_rate,
        margin_used=required_margin,
        pnl=0,
        status="open")

    db.session.add(trade)
    db.session.commit()

    flash("Trade opened successfully", "success")
    return redirect(url_for("dashboard"))





# --------Get Forex price----------
API_KEY = "52e3083b0d7747f2b834fcf157aa7f07"
BASE_URL = "https://api.twelvedata.com"

price_cache = {}
CACHE_TTL = 300


def fetch_with_retry(url,max_retries=5, backoff=5):
    for attempt in range(max_retries):
        try: 
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if "price" in data:
                return data
        
        except Exception as e:
            wait_time = backoff * (2 ** attempt)
            print(f"API CALL FAILED (ATTEMPT {attempt+1}), RETRYING IN {wait_time}s...ERROR: {e}")
            time.sleep(wait_time)
    return None    


def get_price(symbol: str):
    key = f"stock:{symbol.upper()}"
    now = time.time()

    if key in price_cache and now - price_cache[key]["ts"] < CACHE_TTL:
        print(f"CACHE HIT FOR {key}")
        return price_cache[key]["price"]

    url = f"{BASE_URL}/price?symbol={symbol}&apikey={API_KEY}"
    data = fetch_with_retry(url)

    if data:
        price = float(data["price"])
        price_cache[key] = {"price": price, "ts": now}
        return price
    return None
 

def get_forex_price(symbol: str):
    key = f"forex:{symbol.upper()}"
    now = time.time()

    if key in price_cache and now - price_cache[key]["ts"] < CACHE_TTL:
        print(f"CACHE HIT FOR {key}")
        return price_cache[key]["price"]

    url = f"{BASE_URL}/price?symbol={symbol}&apikey={API_KEY}"
    data = fetch_with_retry(url)

    if data:
        price = float(data["price"])
        price_cache[key] = {"price": price, "ts": now}
        return price
    return None


def get_crypto_price(symbol: str):
    key = f"crypto:{symbol.upper()}"
    now = time.time()

    if key in price_cache and now - price_cache[key]["ts"] < CACHE_TTL:
        print(f"CACHE HIT FOR {key}")
        return price_cache[key]["price"]

    url = f"{BASE_URL}/price?symbol={symbol}&apikey={API_KEY}"
    data = fetch_with_retry(url)

    if data:
        price = float(data["price"])
        price_cache[key] = {"price": price, "ts": now}
        return price
    return None




PRICE_CACHE ={}
LAST_UPDATE = 0
UPDATE_INTERVAL = 300
CACHE_TTL = 300
       

def fetch_price(symbol: str):
    global PRICE_CACHE, LAST_UPDATE

    now = time.time()

    if symbol in PRICE_CACHE and now - LAST_UPDATE < CACHE_TTL:
        return PRICE_CACHE[symbol]

    try:
        url = f"https://api.twelvedata.com/price?symbol={symbol}&apikey={API_KEY}"
        response = requests.get(url, timeout=10)
        data = response.json()

        if "price" in data and data["price"]:
            price = float(data["price"])
            PRICE_CACHE[symbol] = price
            LAST_UPDATE = now
            print(f"CURRENT PRICE FOR {symbol}: {price}")
            return price
        else:
            print(f"No valid price for {symbol}: {data}")
            return None

    except Exception as e:
        print(f"ERROR FETCHING {symbol}: {e}")
        return None


def update_prices():
    global LAST_UPDATE
    symbols = ["BTC/USD","EUR/USD","AAPL"]   #---- "MSFT", "TSLA", "EUR/USD", "GBP/USD"
    while True:
        print("UPDATING MARKET PRICES...")
        for symbol in symbols:
            PRICE_CACHE[symbol] = fetch_price(symbol)
        LAST_UPDATE = time.time()
        time.sleep(UPDATE_INTERVAL)

threading.Thread(target=update_prices, daemon=True).start()            
  


DEFAULT_FOREX_LOT_SIZE = 1

def to_decimal(v):
    if v is None:
        return None

    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError, TypeError):
        return None   


#--------Asset Symbol Auto-Detection Function-------
def detect_asset_type(symbol: str) -> str:
    if not symbol:
        return "unknown"
    
    s = symbol.strip().upper()
    if "/" in s:
        base, quote = s.split("/", 1)
        if len(base) == 3 and len(quote) == 3 and base.isalpha() and quote.isalpha():
            return "forex"
        return "crypto"
    return "stock"   
    
    
def compute_pnl(side: str, entry_price, current_price, quantity,asset_type: str = None, forex_lot_size: int=DEFAULT_FOREX_LOT_SIZE):  
    side = (side or "").strip().lower()
    if side not in ("buy", "sell"):
        logging.warning("compute_pnl: unknown side '%s'", side)
        return None
    
    ep = to_decimal(entry_price)
    cp = to_decimal(current_price)
    q = to_decimal(quantity)

    if None in (ep, cp, q):
        logging.warning("compute_pnl: invalid numeric inputs: entry=%s current=%s qty=%s qty=%s", entry_price, current_price, quantity)
        return None
    
    if not asset_type:
        asset_type = detect_asset_type(str(getattr(quantity, 'symbol', '')))

    if asset_type == "forex" and forex_lot_size and forex_lot_size != 1:
        q = q * Decimal(forex_lot_size)

    if side == "buy":
        pnl = (ep - cp) * q
        return pnl





#==========================
#  HOMEPAGE ROUTE 
#==========================
@app.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template("index.html")


#==========================
#  LOG IN ROUTE 
#==========================
@app.route('/login',methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form.get('email','').strip().lower()
        password = request.form.get('password','')

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user)
            flash("SUCCESSFULLY LOGIN", 'success')
            return redirect(url_for('dashboard'))
        else:
            flash("INVALID CREDENTIALS", 'danger')
            return redirect(url_for('login'))
        
    return render_template("login.html")  
  


#==========================
#  SIGN UP ROUTE 
#==========================
@app.route('/signup', methods=["GET","POST"])
def signup():
    if request.method == "POST":
        name = request.form.get('name', '').capitalize()
        surname = request.form.get('surname', '').capitalize()
        email = request.form.get('email', '').strip().lower()
        phonenumber = request.form.get('phone_number','')
        password = request.form.get('password','')

        if not email or not password:
            flash("EMAIL AND PASSWORD ARE REQUIRED","danger")
            return redirect(url_for('signup'))
        
        if User.query.filter_by(email=email).first():
            flash("EMAIL ALREADY EXIST, PLEASE LOGIN","danger")
            return redirect(url_for('signup'))
        
        user = User(name=name,surname=surname,email=email,phonenumber=phonenumber,account_number=generate_account_number(),security_code=generate_security_code())
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("SUCCESSFULLY REGISTERED - PLEASE LOGIN",'success')
        return redirect(url_for('login'))
    
    return render_template("signup.html")



#==========================
#  LOG OUT ROUTE 
#==========================
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('YOU HAVE BEEN LOGGED OUT', "success")
    return redirect(url_for('login'))

            
#==========================
#  CLOSE TRADE ROUTE 
#==========================
@app.route('/close_trade/<int:trade_id>', methods=['POST', 'GET'])
@login_required
def close_trade(trade_id):
   
    trade = Trade.query.get_or_404(trade_id)

    if trade.status == 'closed':
        return redirect(url_for('dashboard'))
    
    current_price = fetch_price(trade.symbol)
    if current_price is None:
        return redirect(url_for('dashboard'))
    
    trade.current_price = current_price

         
    if trade.side.lower() == "buy":
        trade.pnl = (trade.current_price - trade.entry_price) * trade.quantity
    else:
        trade.pnl = (trade.entry_price - trade.current_price) * trade.quantity

    trade.status = 'closed'

    user = current_user
    if hasattr(user, 'total_balance'):
        user.total_balance += trade.pnl

    flash("closing trade", trade.id,trade.symbol, trade.status,"success")
    db.session.commit()

    flash(f"TRADE CLOSED. PNL: {trade.pnl:.2f}", "success")
    return redirect(url_for('dashboard'))        


#==========================
#  FORMAT MONEY FUNCTION
#==========================
def format_money(value):
    try:
        return f"${value:,.2f}"
    except (TypeError, ValueError):
        return "$0.00"
    
app.jinja_env.filters['money'] = format_money


#==========================
#  DASHBOARD TRADING CHART ROUTE 
#==========================
@app.route('/chart/<symbol>')
def chart(symbol):
    return render_template("chart.html", symbol=symbol)
  
             

#==========================
# USER SECURITY CODE GENERATOR
#==========================
def generate_security_code():
    while True:
        lenght = random.choice([6])
        security_code = ''.join(str(random.randint(0,5)) for _ in range(lenght))

        exists = User.query.filter_by(security_code=security_code).first()
        if not exists:
            return security_code 


#==========================
# ACCOUNT NUMBER GENERATOR
#==========================
def generate_account_number():
    while True:
        lenght = random.choice([8,9,10])
        account_number = ''.join(str(random.randint(0,9)) for _ in range(lenght))

        exists = User.query.filter_by(account_number=account_number).first()
        if not exists:
            return account_number 


#==========================
#  CLIENT WITHDRAWAL REQUEST ROUTE
#==========================
@app.route('/withdrawal',methods=["GET","POST"])
@login_required
def withdrawal():
    if request.method == "POST":
        method = request.form.get("method")
        amount = request.form.get("amount")
        destination = request.form.get("destination")
        note = request.form.get("note")

        if not method or not amount or not destination:
            flash("All Feilds Required Filled Out", "danger")
            return redirect(url_for('withdrawal'))
        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError
        except ValueError:
            flash("Invalid Withdrawal Amount", "danger")
            return redirect(url_for('withdrawal'))
        
        withdrawal = Withdrawal(user_id=current_user.id,method=method,amount=amount,destination=destination,note=note)
        db.session.add(withdrawal)
        db.session.commit()

        flash("Withdarawal Request Submitted Successfully", "success")
        return redirect(url_for('dashboard'))
    
    return render_template("withdrawal.html")


#==========================
#  HELPCENTER ROUTE
#==========================

@app.route("/helpcenter", methods=["GET", "POST"])
def helpcenter():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        message = request.form.get("message")

        if not name or not email or not message:
            flash("All fields are required", "danger")
            return redirect(url_for("helpcenter"))

        help_msg = HelpMessage(user_id=current_user.id,name=name,email=email,message=message)

        db.session.add(help_msg)
        db.session.commit()

        flash("Your message has been sent. Support will contact you.", "success")
        return redirect(url_for("dashboard"))

    return render_template("helpcenter.html")


#==========================
#  ALLOWED EXTENSIONS FILE UPLOAD
#==========================

def allowed_file(filename):
    return ("." in filename and filename.rsplit(".",1)[1].lower() in ALLOWED_EXTENSIONS )



#==========================
#  USER FILE UPLOAD ROUTE
#==========================

@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "POST":
        file = request.files.get("file")

        if not file or file.filename == "":
            flash("No file selected", "danger")
            return redirect(url_for("upload"))

        if not allowed_file(file.filename):
            flash("File type not allowed", "danger")
            return redirect(url_for("upload"))

        original_filename = secure_filename(file.filename)
        ext = original_filename.rsplit(".", 1)[1].lower()

        unique_name = f"{uuid.uuid4().hex}.{ext}"

        user_folder = os.path.join(app.config["UPLOAD_FOLDER"],str(current_user.id))

        os.makedirs(user_folder, exist_ok=True)

        file_path = os.path.join(user_folder, unique_name)
        file.save(file_path)

        new_file = UserFile(user_id=current_user.id,original_filename=original_filename,stored_filename=unique_name,file_type=ext)

        db.session.add(new_file)
        db.session.commit()

        flash("File uploaded successfully", "success")
        return redirect(url_for("upload"))

    return render_template("upload.html")



#==========================
#  FILE UPLOAD CONFIGURATION
#==========================
UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf", "doc", "docx"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


#==========================
#  SETTINGS ROUTE 
#==========================
@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":

        current_user.margin_type = request.form.get("margin_type")
        current_user.margin_rate = request.form.get("margin_rate")
        current_user.margin_level = request.form.get("margin_level")
        current_user.leverage = request.form.get("leverage")

       
        db.session.commit()
        flash("Settings updated successfully", "success")

        return redirect(url_for("settings"))

    return render_template("settings.html")


#==========================
#  ACCOUNT-OVERVIEW ROUTE * DATA FUNCTIONS
#==========================
@app.route('/account_overview')
@login_required
def account_overview():
    
    user = current_user
    
    open_trades = db.session.query(func.count(Trade.id)).filter_by(user_id=user.id, status="open").scalar() or 0
    closed_trades = db.session.query(func.count(Trade.id)).filter_by(user_id=user.id, status="closed").scalar() or 0
    total_deposit = db.session.query(db.func.coalesce(db.func.sum(Deposit.amount), 0)).filter(Deposit.user_id == user.id).scalar()
    total_withdraw = db.session.query(db.func.coalesce(db.func.sum(Withdraw.amount), 0)).filter(Withdraw.user_id == user.id).scalar()
    total_pnl = db.session.query(db.func.coalesce(db.func.sum(Trade.pnl), 0)).filter(Trade.user_id == user.id).scalar()

    latest_withdrawal = (Withdrawal.query.filter_by(user_id=current_user.id).order_by(Withdrawal.created.desc()).first())

    total_balance = user.total_balance 

    return render_template("account_overview.html",
                           latest_withdrawal=latest_withdrawal,
                           open_trades=open_trades,
                           closed_trades=closed_trades,
                           total_pnl=total_pnl,
                           total_deposit=total_deposit,
                           total_withdraw=total_withdraw,
                           total_balance=total_balance,
                           user=user)


#==========================
#  USER CHANGE PASSWORD ROUTE 
#==========================
@app.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current_password = request.form.get("current_password")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

       
        if not check_password_hash(current_user.password_hash, current_password):
            flash("Current password is incorrect", "danger")
            return redirect(url_for("change_password"))

        if new_password != confirm_password:
            flash("Passwords do not match","danger")
            return redirect(url_for("change_password"))

        if len(new_password) < 8:
            flash("Password must be at least 8 characters","danger")
            return redirect(url_for("change_password"))

        current_user.password_hash = generate_password_hash(new_password)
        
        db.session.commit()
        logout_user()

        flash("Password updated successfully","success")
        return redirect(url_for("login"))

    return render_template("change_password.html")


#==========================
#  USER ONLINE STATUS ROUTE 
#==========================
@app.route('/heartbeat', methods=["POST"])
@login_required
def heartbeat():
    current_user.last_seen =datetime.utcnow()
    db.session.commit()
    return "", 204

def is_user_online(user):
    if not user.last_seen:
        return False
    return datetime.utcnow() - user.last_seen < timedelta(minutes=5)

@app.context_processor
def inject_helpers():
    return dict(is_user_online=is_user_online)

@app.before_request
def update_last_seen():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        db.session.commit()



#==========================
#  USER DEVICE ROUTE 
#==========================
def get_device_type(user_agent_string):
    ua = parse(user_agent_string or "")

    if ua.is_mobile:
        return "MOBILE"
    if ua.is_tablet:
        return "TABLET"
    if ua.is_bot:
        return "Bot" 
    return "DESKTOP"



#==========================
#  PERSONAL INFOMATION ROUTE
#==========================
@app.route('/personalinfo',methods=["GET","POST"])
@login_required
def personalinfo():

    if request.method == "POST":
        fullname = request.form.get("fullname").capitalize()
        email = request.form.get("email")
        phone = request.form.get("phone")
        nationality = request.form.get("nationality")
        city = request.form.get("city")
        address = request.form.get("address")
        zipcode = request.form.get("zipcode")
        date_of_birth = request.form.get("date_of_birth")

        if not fullname or not email or not phone or not nationality or not city or not address or not zipcode or not date_of_birth :

            flash("All fields are required", "danger")
            return redirect(url_for("personalinfo"))

        new_info = PersonalInfo(user_id=current_user.id,fullname=fullname,email=email,phone=phone,nationality=nationality,city=city,address=address,zipcode=zipcode,date_of_birth=date_of_birth)

        db.session.add(new_info)
        db.session.commit()
        flash("Successfully submitted", "success")

        return redirect(url_for("dashboard"))

    return render_template("personalinfo.html")



#==========================
#  ADMIN WITHDRAWAL ROUTE approve/reject
#==========================



#==========================
#  ADMIN WITHDRAWAL ROUTE approve/reject
#==========================



#==========================
#  ADMIN WITHDRAWAL ROUTE approve/reject
#==========================
@app.route("/admin_withdrawal/<int:withdrawal_id>/update", methods=["POST"])
def update_withdrawal(withdrawal_id):
    

    withdrawal = Withdrawal.query.get_or_404(withdrawal_id)
    action = request.form.get("action") # approve / reject

    if withdrawal.status.lower() != "pending":
        flash("Withdrawal already processed", "danger")
        return redirect(url_for("admin_withdrawals"))

    if action == "approve":
        withdrawal.status = "approve"
        # later: deduct user balance here

    elif action == "reject":
        withdrawal.status = "reject"

    else:
        flash("Invalid Action", "danger")
        return redirect(url_for('admin_withdrawals'))    

    db.session.commit()

    flash("Withdrawal updated successfully", "success")

    return redirect(url_for("admin_withdrawals"))



#==========================
#  ADMIN WITHDRAWAL REQUEST VIEW ROUTE
#==========================
@app.route("/admin_withdrawals")
def admin_withdrawals():
    
    withdrawals = Withdrawal.query.order_by(Withdrawal.created.desc()).all()
    return render_template("admin_withdrawals.html",withdrawals=withdrawals)



#==========================
#  ADMIN HELPCENTER VIEW ROUTE
#==========================
@app.route('/admin_helpcenter')
def admin_helpcenter():
    messages = HelpMessage.query.order_by(HelpMessage.created.desc()).all()

    return render_template("admin_helpcenter.html", messages=messages)



#==========================
#  ADMIN ADD FUNDS ROUTE 
#==========================
@app.route('/funds', methods=["GET","POST"])
@login_required
def funds():
   
    if request.method == "POST":
        user_id =request.form.get('user_id')
        amount = request.form.get('amount')
        action = request.form.get('action')  

        if not user_id or not amount:
            flash("Invalid Amount", "danger")
            return redirect(url_for('funds'))
        
        try: 
            amount = float(amount)
            user = User.query.get(int(user_id))

            if not user:
                flash(f"Selected user not found","danger")
                return redirect(url_for('funds'))

            if action == 'deposit':
                deposit = Deposit(user_id=user.id, amount=amount, type='deposit')
                db.session.add(deposit)
                user.total_balance = (user.total_balance or 0) + amount

            elif action == 'withdraw':
                
                if (user.total_balance or 0) < amount:
                    flash("Insufficent Balance","danger")
                    return redirect(url_for('funds'))


                withdraw = Withdraw(user_id=user.id, amount=amount, type='withdraw')
                db.session.add(withdraw)
                user.total_balance = (user.total_balance or 0) - amount
                
            db.session.commit()
            flash(f"Transaction Successful", "success")
        
        except Exception as e:
            db.session.rollback()
            flash("Failed Transaction Try Again", "danger")  
        return redirect(url_for('funds'))
   
    users = User.query.all()      
    return render_template("funds.html", users=users)           
            


#==========================
#  ADMIN MANAGE TRADES ROUTE 
#==========================
@app.route('/manage_trades',methods=["GET","POST"])
@login_required
def manage_trades():

    selected_user_id = request.args.get("user_id",type=int)

    if selected_user_id:
        user_id = selected_user_id
    else:
        user_id = current_user.id    

    open_trades = Trade.query.filter_by(user_id=user_id, status='open').all()

    if request.method == 'POST':
        try:
            trade_id = int(request.form.get('trade_id'))
            new_quantity = float(request.form.get('quantity'))
            new_entry_price = float(request.form.get('entry_price'))

            trade = db.session.get(Trade, int(float(trade_id)))

            if not trade:
                flash("Trade not found", "danger")
                return redirect(url_for('manage_trades'))
            
            trade.quantity = new_quantity
            trade.entry_price = new_entry_price

            latest_price = fetch_price(trade.symbol)
            if latest_price is not None:
                trade.current_price = latest_price

            if (
                trade.entry_price is not None
                and trade.current_price is not None
                and trade.quantity is not None
            ):
                #Recalculate pnl values
                if trade.side.lower() == 'buy':
                    trade.pnl = (trade.current_price - trade.entry_price) * trade.quantity
                else:
                    trade.pnl = (trade.entry_price - trade.current_price) * trade.quantity    
            else:
                trade.pnl = 0.0

            db.session.commit()
            flash(f"Trade {trade.id} updated successfullly: New Pnl = {trade.pnl}, quantity= {trade.quantity}", "success")    
              
        except Exception as e:
            db.session.rollback()
            flash('Commit failed', "danger")

        return redirect(url_for('manage_trades', user_id=user_id))    

    open_trades = Trade.query.filter_by(user_id=user_id, status='open').all()
    total_pnl = sum(trade.pnl for trade in open_trades if trade.pnl is not None)      

    users = User.query.order_by(User.email).all()
    return render_template("manage_trades.html",trades=open_trades,total_pnl=total_pnl,users=users,selected_user_id=user_id) 



#==========================
#  ADMIN VIEW FILES ROUTE
#==========================
@app.route('/admin_files')
def admin_files():

    files = UserFile.query.order_by(UserFile.uploaded.desc()).all()

    return render_template("admin_files.html", files=files)



#==========================
#  SECURE ADMIN FILE DOWNLOAD ROUTE
#==========================
@app.route("/admin_files/<int:file_id>/download")
def download_file(file_id):

    file = UserFile.query.get_or_404(file_id)

    user_folder = os.path.join(app.config["UPLOAD_FOLDER"],str(file.user_id))

    return send_from_directory(user_folder,file.stored_filename,as_attachment=True,download_name=file.original_filename)




#==========================
#  ADMIN-DASHBOARD ROUTE 
#==========================
@app.route("/admin_dashboard")
@login_required
def admin_dashboard():
    if not getattr(current_user, "is_admin", False):
        abort(403)

    users = User.query.order_by(User.created.desc()).all()

    user_device = {}
    for user in users:
        last_visit = ( PageVisit.query.filter(PageVisit.user_id == user.id).order_by(PageVisit.timestamp.desc()).first())
        
        user_device[user.id] = last_visit.device_type if last_visit else "Unknown"

    return render_template("admin_dashboard.html", users=users,user_device=user_device)



#==========================
#  ADMIN-CHANGE PASSWORD ROUTE 
#==========================
@app.route("/admin/change_password/<int:user_id>", methods=["POST"])
def admin_change_password(user_id):

    new_password = request.form.get("new_password")

    if not new_password or len(new_password) < 8:
        flash("Password must be at least 8 characters","danger")
        return redirect(url_for("admin_dashboard"))

    user = User.query.get_or_404(user_id)

    user.password_hash = generate_password_hash(new_password)
    db.session.commit()

    flash(f"Password updated for {user.email}","success")
    return redirect(url_for("admin_dashboard"))



#==========================
#  VISITS ROUTE 
#==========================
@app.before_request
def log_page_visit():
    if request.endpoint == "static":
        return
    
    ua_string = request.user_agent.string or ""

    visit = PageVisit(
        user_id=current_user.id if current_user.is_authenticated else None,
        path=request.path,
        method=request.method,
        ip_address=request.headers.get("X-Forwarded-For", request.remote_addr),
        user_agent=ua_string,
        device_type=get_device_type(ua_string),
        timestamp=datetime.utcnow()
    )   
    db.session.add(visit)
    db.session.commit()               
        


@app.route('/admin_page_visits')
def admin_page_visits():
    
    visits = PageVisit.query.order_by(PageVisit.timestamp.desc()).limit(500).all()
    return render_template("admin_navigation.html", visits=visits)
                                      


#==========================
#  ADMIN PERSONAL INFORMATION ROUTE 
#==========================
@app.route("/admin_personalinfo")
def admin_personalinfo():
    infos = PersonalInfo.query.order_by(PersonalInfo.id.desc()).all()

    return render_template("admin_personalinfo.html",infos=infos)



#==========================
#  ADMIN LOGIN ROUTE 
#==========================
@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        if (email == os.getenv("ADMIN_EMAIL") and password == os.getenv("ADMIN_PASSWORD")):
            admin = FakeAdmin()
            login_user(admin)
            flash("Welcome Admin", "success")
            return redirect(url_for('admin_dashboard'))

        flash("Invalid admin credentials", "danger")

    return render_template("admin_login.html")



#==========================
#  ADMIN LOGOUT ROUTE 
#==========================

@app.route("/admin_logout")
@login_required
def admin_logout():
    logout_user()
    flash("Admin Logged Out successfully","success")
    return redirect(url_for('admin_login'))



#==========================
#  CLIENT IMPERSONATE LOGOUT ROUTE 
#==========================
class FakeAdmin(UserMixin):
    def __init__(self):
        self.id = "admin"
        self.email = os.getenv("ADMIN_EMAIL")
        self.is_admin = True


@login_manager.user_loader
def load_user(user_id):
    if user_id == "admin":
        return FakeAdmin()
    return User.query.get(int(user_id))        




#==========================
#  CLIENT IMPERSONATE LOGOUT ROUTE 
#=========================
@app.route("/admin/stop-impersonate")
@login_required
def stop_impersonate():
    if session.get("admin_id") != "admin":
        abort(403)

    session.pop("admin_id", None)
    login_user(FakeAdmin())

    flash("Returned to admin account", "success")
    return redirect(url_for("admin_dashboard"))

#==========================
#  CLIENT IMPERSONATE ROUTE 
#==========================  

@app.route("/admin/impersonate/<int:user_id>")
@login_required
def admin_impersonate(user_id):
    if not current_user.is_admin:
        abort(403)

  
    user = User.query.get_or_404(user_id)

    # Save admin ID so we can return later
    session["admin_id"] = "admin"
    login_user(user)

    flash(f"You are now viewing {user.name} {user.surname} 's dashboard","success")
    return redirect(url_for("dashboard"))


#Route For viewing open and closed trades
@app.route('/change_pass',methods=["GET","POST"])
def change_pass():
    return render_template("change_pass.html")


@app.route('/admin_deposit',methods=["GET","POST"])
def admin_deposit():
    return render_template("admin_deposit.html")


#Route For Analytic
@app.route('/analytic',methods=["GET","POST"])
def analytic():
    return render_template("analytic.html")


#Route For Markets
@app.route('/markets',methods=["GET","POST"])
def markets():
    return render_template("markets.html")


#Route For Futures
@app.route('/futures',methods=["GET","POST"])
def futures():
    return render_template("futures.html")


#Route For Contacts
@app.route('/contact',methods=["GET","POST"])
def contact():
    return render_template("contact.html")


#Route For Accounts
@app.route('/account',methods=["GET","POST"])
def account():
    return render_template("account.html")


#Route For Withdrawals
@app.route('/submit',methods=["GET","POST"])
def submit():
    return render_template("clientprofile.html")


#Route For Withdrawals
@app.route('/deposit',methods=["GET","POST"])
def deposit():
    return render_template("deposit.html")


#Route For Withdrawals
@app.route('/livemarket',methods=["GET","POST"])
def livemarket():
    return render_template("livemarket.html")


# User/Agreement Page route
@app.route("/useragreement")
def useragreement():
    return render_template("useragreement.html")


# Policy Page route
@app.route("/privacypolicy")
def privacypolicy():
    return render_template("privacypolicy.html")

if __name__ == "__main__":
    app.run()    




