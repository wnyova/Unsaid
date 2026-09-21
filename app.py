import os, re, secrets, time
from datetime import datetime, timezone
from functools import wraps
import requests
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()
app=Flask(__name__)
app.config["SECRET_KEY"]=os.getenv("SECRET_KEY",secrets.token_hex(32))
app.config["SQLALCHEMY_DATABASE_URI"]=os.getenv("DATABASE_URL","sqlite:///unsaid.db").replace("postgres://","postgresql+psycopg://",1)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"]=False
db=SQLAlchemy(app)
login_manager=LoginManager(app); login_manager.login_view="login"

class User(UserMixin,db.Model):
 id=db.Column(db.Integer,primary_key=True); username=db.Column(db.String(32),unique=True,nullable=False,index=True)
 display_name=db.Column(db.String(60),nullable=False); password_hash=db.Column(db.String(255),nullable=False)
 created_at=db.Column(db.DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
 messages=db.relationship("Message",backref="recipient",lazy=True,cascade="all, delete-orphan")
class Message(db.Model):
 id=db.Column(db.Integer,primary_key=True); user_id=db.Column(db.Integer,db.ForeignKey("user.id"),nullable=False,index=True)
 body=db.Column(db.Text,nullable=False); song_id=db.Column(db.String(64)); song_name=db.Column(db.String(200)); song_artist=db.Column(db.String(200)); song_image=db.Column(db.Text); song_url=db.Column(db.Text)
 is_public=db.Column(db.Boolean,default=False,nullable=False); created_at=db.Column(db.DateTime(timezone=True),default=lambda:datetime.now(timezone.utc),index=True)

@login_manager.user_loader
def load_user(uid): return db.session.get(User,int(uid))
def clean_username(v): return re.sub(r"[^a-z0-9_.-]","",v.lower().strip())[:32]
def client_key(): return request.headers.get("CF-Connecting-IP") or request.headers.get("X-Forwarded-For","").split(",")[0].strip() or request.remote_addr or "unknown"
_rate={}
def rate_limit(limit=5,window=60):
 def deco(fn):
  @wraps(fn)
  def wrapped(*a,**k):
   key=f"{fn.__name__}:{client_key()}"; now=time.time(); arr=[t for t in _rate.get(key,[]) if now-t<window]
   if len(arr)>=limit: abort(429)
   arr.append(now); _rate[key]=arr
   return fn(*a,**k)
  return wrapped
 return deco

@app.route("/")
def index(): return render_template("index.html")
@app.route("/register",methods=["GET","POST"])
def register():
 if current_user.is_authenticated:return redirect(url_for("inbox"))
 if request.method=="POST":
  username=clean_username(request.form.get("username","")); name=request.form.get("display_name","").strip()[:60]; pw=request.form.get("password","")
  if len(username)<3 or len(name)<1 or len(pw)<8: flash("Username min. 3 chars and password min. 8 chars.","error")
  elif User.query.filter_by(username=username).first(): flash("That username is already taken.","error")
  else:
   u=User(username=username,display_name=name,password_hash=generate_password_hash(pw));db.session.add(u);db.session.commit();login_user(u);return redirect(url_for("inbox"))
 return render_template("auth.html",mode="register")
@app.route("/login",methods=["GET","POST"])
def login():
 if request.method=="POST":
  u=User.query.filter_by(username=clean_username(request.form.get("username",""))).first()
  if u and check_password_hash(u.password_hash,request.form.get("password","")):login_user(u);return redirect(url_for("inbox"))
  flash("Invalid username or password.","error")
 return render_template("auth.html",mode="login")
@app.route("/logout",methods=["POST"])
@login_required
def logout():logout_user();return redirect(url_for("index"))
@app.route("/to/<username>",methods=["GET","POST"])
@rate_limit(8,60)
def recipient_page(username):
 u=User.query.filter_by(username=clean_username(username)).first_or_404()
 if request.method=="POST":
  body=request.form.get("body","").strip()
  if request.form.get("website",""):return redirect(url_for("recipient_page",username=u.username))
  if not 1<=len(body)<=1500:flash("Message must be 1–1500 characters.","error")
  else:
   m=Message(user_id=u.id,body=body,song_id=request.form.get("song_id") or None,song_name=request.form.get("song_name") or None,song_artist=request.form.get("song_artist") or None,song_image=request.form.get("song_image") or None,song_url=request.form.get("song_url") or None)
   db.session.add(m);db.session.commit();flash("Sent anonymously. Your identity was not attached to the message.","success");return redirect(url_for("recipient_page",username=u.username))
 public=Message.query.filter_by(user_id=u.id,is_public=True).order_by(Message.created_at.desc()).limit(30).all()
 return render_template("recipient.html",user=u,public_messages=public)
@app.route("/inbox")
@login_required
def inbox():return render_template("inbox.html",messages=Message.query.filter_by(user_id=current_user.id).order_by(Message.created_at.desc()).all())
@app.route("/message/<int:mid>/toggle",methods=["POST"])
@login_required
def toggle(mid):
 m=Message.query.filter_by(id=mid,user_id=current_user.id).first_or_404();m.is_public=not m.is_public;db.session.commit();return redirect(url_for("inbox"))
@app.route("/message/<int:mid>/delete",methods=["POST"])
@login_required
def delete(mid):
 m=Message.query.filter_by(id=mid,user_id=current_user.id).first_or_404();db.session.delete(m);db.session.commit();return redirect(url_for("inbox"))

_spotify={"token":None,"expires":0}
def spotify_token():
 cid=os.getenv("SPOTIFY_CLIENT_ID");secret=os.getenv("SPOTIFY_CLIENT_SECRET")
 if not cid or not secret:return None
 if _spotify["token"] and time.time()<_spotify["expires"]-30:return _spotify["token"]
 r=requests.post("https://accounts.spotify.com/api/token",data={"grant_type":"client_credentials"},auth=(cid,secret),timeout=10);r.raise_for_status();d=r.json();_spotify.update(token=d["access_token"],expires=time.time()+d["expires_in"]);return d["access_token"]
@app.route("/api/spotify/search")
@rate_limit(20,60)
def spotify_search():
 q=request.args.get("q","").strip()[:100]
 if len(q)<2:return jsonify([])
 token=spotify_token()
 if not token:return jsonify({"error":"Spotify is not configured"}),503
 r=requests.get("https://api.spotify.com/v1/search",params={"q":q,"type":"track","limit":6},headers={"Authorization":f"Bearer {token}"},timeout=10);r.raise_for_status()
 return jsonify([{"id":t["id"],"name":t["name"],"artist":", ".join(a["name"] for a in t["artists"]),"image":(t["album"]["images"][-1]["url"] if t["album"]["images"] else ""),"url":t["external_urls"]["spotify"]} for t in r.json().get("tracks",{}).get("items",[])])
@app.errorhandler(429)
def too_many(e):return render_template("error.html",message="Too many requests. Try again in a minute."),429
with app.app_context():db.create_all()