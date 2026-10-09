from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Date, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    birth_date = Column(Date, nullable=False)
    card_uid = Column(String, unique=True, index=True, nullable=False)  # UID karty RFID
    bank_account = Column(String, nullable=False)
    contract_type = Column(String, default="UOP")  # UOP lub ZLECENIE
    base_salary = Column(Float, nullable=False)    # Stawka zasadnicza brutto
    fixed_allowance = Column(Float, default=0.0)   # Dodatki stałe (np. stażowy, funkcyjny)
    hourly_rate = Column(Float, default=0.0)       # Dla zleceń/rozliczeń godzinowych

    events = relationship("RfidEvent", back_populates="employee")
    absences = relationship("Absence", back_populates="employee")
    payrolls = relationship("PayrollRecord", back_populates="employee")

class RfidEvent(Base):
    __tablename__ = "rfid_events"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"))
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    event_type = Column(String, nullable=False)  # "IN" (wejście) lub "OUT" (wyjście)

    employee = relationship("Employee", back_populates="events")

class Absence(Base):
    __tablename__ = "absences"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"))
    date_from = Column(Date, nullable=False)
    date_to = Column(Date, nullable=False)
    absence_type = Column(String, nullable=False)  # "CHOROBA_80", "URLOP_WYPOCZYNKOWY", "BEZPLATNY"

    employee = relationship("Employee", back_populates="absences")

class PayrollRecord(Base):
    __tablename__ = "payroll_records"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"))
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    
    hours_worked = Column(Float, default=0.0)
    sick_days = Column(Integer, default=0)
    gross_total = Column(Float, nullable=False)
    social_zus = Column(Float, nullable=False)    # Emerytalne, rentowe, chorobowe
    health_zus = Column(Float, nullable=False)    # Zdrowotna 9%
    pit_advance = Column(Float, nullable=False)   # Zaliczka na PIT
    net_amount = Column(Float, nullable=False)    # Do wypłaty na konto
    created_at = Column(DateTime, default=datetime.utcnow)

    employee = relationship("Employee", back_populates="payrolls")