#importing fastAPI and setting it up

from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def home():
    return {"message": "API is running"}

######################setting up database usin sqlalchemy######################################

from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True)
    password = Column(String)

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True)
    title = Column(String)
    priority = Column(String)
    user_id = Column(Integer, ForeignKey("users.id"))

Base.metadata.create_all(bind=engine)


################################# AUTH Part #############################################

from fastapi import Depends, HTTPException
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta

SECRET_KEY = "secret"
ALGORITHM = "HS256"

pwd_context = CryptContext(schemes=["bcrypt"])

def hash_password(password):
    return pwd_context.hash(password)

def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)

def create_token(data: dict):
    data["exp"] = datetime.utcnow() + timedelta(hours=1)
    return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)


################################### sign up login apis #############################

from fastapi import Body

@app.post("/signup")
def signup(email: str = Body(...), password: str = Body(...)):
    db = SessionLocal()
    user = User(email=email, password=hash_password(password))
    db.add(user)
    db.commit()
    return {"message": "User created"}

@app.post("/login")
def login(email: str = Body(...), password: str = Body(...)):
    db = SessionLocal()
    user = db.query(User).filter(User.email == email).first()

    if not user or not verify_password(password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_token({"user_id": user.id})
    return {"token": token}

################################## protected route task #################################

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    return payload["user_id"]

@app.post("/tasks")
def create_task(title: str = Body(...), priority: str = Body(...), user_id: int = Depends(get_current_user)):
    db = SessionLocal()
    task = Task(title=title, priority=priority, user_id=user_id)
    db.add(task)
    db.commit()
    return {"message": "Task created"}



############################### Redis Rate Limiting for requests ######################################

import redis
import time

r = redis.Redis(host="localhost", port=6379, db=0)

def rate_limit(user_id):
    key = f"rate:{user_id}"
    count = r.get(key)

    if count and int(count) > 10:
        raise HTTPException(status_code=429, detail="Too many requests")

    pipe = r.pipeline()
    pipe.incr(key, 1)
    pipe.expire(key, 60)
    pipe.execute()

########################### using the API ############################################

@app.get("/tasks")
def get_tasks(user_id: int = Depends(get_current_user)):
    rate_limit(user_id)

    db = SessionLocal()
    tasks = db.query(Task).filter(Task.user_id == user_id).all()
    return tasks