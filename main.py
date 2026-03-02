from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from jose import JWTError, jwt
from passlib.context import CryptContext
import os
from datetime import datetime, timedelta

# ==========================
# Environment Variables
# ==========================
DATABASE_URL = os.environ.get("DATABASE_URL")
SECRET_KEY = "uR8x!fG2kL1zAq9P"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

if not DATABASE_URL:
    raise Exception("DATABASE_URL is not set")

# ==========================
# Database Setup
# ==========================
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ==========================
# Models
# ==========================
class Company(Base):
    __tablename__ = "companies"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String)
    company = relationship("Company")

class Employee(Base):
    __tablename__ = "employees"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    name = Column(String)
    role = Column(String)
    base_salary = Column(Float)
    experience = Column(Float)
    company = relationship("Company")

class CompensationSettings(Base):
    __tablename__ = "compensation_settings"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    strategic_weight = Column(Float, default=0)
    financial_weight = Column(Float, default=0)
    performance_weight = Column(Float, default=0)
    skills_weight = Column(Float, default=0)
    company = relationship("Company")

class Sale(Base):
    __tablename__ = "sales"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    product = Column(String)
    quantity = Column(Integer)
    price = Column(Float)
    date = Column(String)
    company = relationship("Company")

Base.metadata.create_all(bind=engine)

# ==========================
# App Setup
# ==========================
app = FastAPI(title="Smart Business SaaS API")

# ==========================
# Auth Setup
# ==========================
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_user(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()

def authenticate_user(db: Session, email: str, password: str):
    user = get_user(db, email)
    if not user or not verify_password(password, user.hashed_password):
        return False
    return user

# ==========================
# Auth Endpoints
# ==========================
@app.post("/token")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    access_token = create_access_token(data={"sub": user.email, "company_id": user.company_id, "role": user.role})
    return {"access_token": access_token, "token_type": "bearer"}

# ==========================
# Company Endpoint
# ==========================
@app.post("/company/")
def create_company(name: str, db: Session = Depends(get_db)):
    company = Company(name=name)
    db.add(company)
    db.commit()
    db.refresh(company)
    return {"id": company.id, "name": company.name}

# ==========================
# Employees Endpoint
# ==========================
@app.post("/employee/")
def create_employee(name: str, role: str, base_salary: float, experience: float, company_id: int, db: Session = Depends(get_db)):
    employee = Employee(name=name, role=role, base_salary=base_salary, experience=experience, company_id=company_id)
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return {"id": employee.id, "name": employee.name, "company_id": employee.company_id}

# ==========================
# Smart Compensation Endpoint
# ==========================
@app.get("/compensation/{employee_id}")
def calculate_compensation(employee_id: int, db: Session = Depends(get_db)):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    settings = db.query(CompensationSettings).filter(CompensationSettings.company_id == employee.company_id).first()
    if not settings:
        # default weights if none set
        settings = CompensationSettings(strategic_weight=10, financial_weight=15, performance_weight=10, skills_weight=5)
    total = employee.base_salary + \
            (employee.base_salary * settings.strategic_weight / 100) + \
            (employee.base_salary * settings.financial_weight / 100) + \
            (employee.base_salary * settings.performance_weight / 100) + \
            (employee.base_salary * settings.skills_weight / 100)
    return {"employee_id": employee.id, "total_compensation": total}

# ==========================
# Sales Endpoint
# ==========================
@app.post("/sale/")
def create_sale(product: str, quantity: int, price: float, company_id: int, db: Session = Depends(get_db)):
    sale = Sale(product=product, quantity=quantity, price=price, company_id=company_id, date=str(datetime.utcnow().date()))
    db.add(sale)
    db.commit()
    db.refresh(sale)
    return {"id": sale.id, "product": sale.product, "company_id": sale.company_id}

@app.get("/sales/{company_id}")
def get_sales(company_id: int, db: Session = Depends(get_db)):
    sales = db.query(Sale).filter(Sale.company_id == company_id).all()
    return [{"product": s.product, "quantity": s.quantity, "price": s.price, "date": s.date} for s in sales]

# ==========================
# Test Root
# ==========================
@app.get("/")
def root():
    return {"message":"Smart Business SaaS API Running"}
