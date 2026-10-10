from datetime import date, datetime
from typing import Optional
from fastapi import FastAPI, Depends, Request, Form, Query
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import engine, get_db, Base
from models import Employee, RfidEvent, Absence, PayrollRecord
from payroll_engine import calculate_payroll_for_month

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Payroll & Presence System")
templates = Jinja2Templates(directory="templates")

def get_current_presence_status(db: Session):
    """Wylicza kto aktualnie przebywa w budynku na podstawie ostatniego odbicia."""
    employees = db.query(Employee).all()
    in_building = []
    out_of_building = []

    for emp in employees:
        last_event = (
            db.query(RfidEvent)
            .filter(RfidEvent.employee_id == emp.id)
            .order_by(desc(RfidEvent.timestamp))
            .first()
        )
        status = "OUT"
        last_time = None
        if last_event:
            status = last_event.event_type
            last_time = last_event.timestamp.strftime("%Y-%m-%d %H:%M")

        emp_info = {
            "id": emp.id,
            "name": f"{emp.first_name} {emp.last_name}",
            "card_uid": emp.card_uid,
            "status": status,
            "last_time": last_time or "Brak odbić"
        }

        if status == "IN":
            in_building.append(emp_info)
        else:
            out_of_building.append(emp_info)

    return in_building, out_of_building

@app.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    tab: str = "presence",
    emp_filter: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Główny panel z zakładkami: Obecność, Płace, Historia odbić"""
    in_building, out_of_building = get_current_presence_status(db)

    # Pobieranie historii odbić (ostatnie 100 zdarzeń)
    events_query = db.query(RfidEvent).order_by(desc(RfidEvent.timestamp))
    if emp_filter:
        events_query = events_query.filter(RfidEvent.employee_id == emp_filter)
    recent_events = events_query.limit(100).all()

    # Dane płacowe
    records = db.query(PayrollRecord).filter(
        PayrollRecord.year == 2026,
        PayrollRecord.month == 9
    ).all()
    total_gross = sum(r.gross_total for r in records) if records else 0.0
    total_net = sum(r.net_amount for r in records) if records else 0.0
    total_zus = sum(r.social_zus + r.health_zus for r in records) if records else 0.0

    stats = {
        "total_employees": db.query(Employee).count(),
        "in_count": len(in_building),
        "out_count": len(out_of_building),
        "total_gross": total_gross,
        "total_zus": total_zus,
        "total_net": total_net,
    }

    all_employees = db.query(Employee).order_by(Employee.last_name).all()

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "tab": tab,
            "in_building": in_building,
            "out_of_building": out_of_building,
            "recent_events": recent_events,
            "records": records,
            "stats": stats,
            "all_employees": all_employees,
            "emp_filter": emp_filter
        }
    )

@app.get("/evacuation", response_class=HTMLResponse)
def evacuation_list(request: Request, db: Session = Depends(get_db)):
    """Widok listy ewakuacyjnej do natychmiastowego druku/BHP"""
    in_building, _ = get_current_presence_status(db)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return templates.TemplateResponse(
        request=request,
        name="evacuation.html",
        context={
            "in_building": in_building,
            "generated_at": generated_at,
            "count": len(in_building)
        }
    )

@app.post("/rfid/manual-swipe")
def manual_swipe(
    employee_id: int = Form(...),
    event_type: str = Form(...),
    tab: str = Form("presence"),
    db: Session = Depends(get_db)
):
    """Ręczna symulacja odbicia karty z panelu dla testów"""
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if emp:
        event = RfidEvent(
            employee_id=emp.id,
            timestamp=datetime.now(),
            event_type=event_type
        )
        db.add(event)
        db.commit()
    return RedirectResponse(url=f"/?tab={tab}", status_code=303)

@app.post("/payroll/calculate-view")
def calculate_and_refresh(year: int = Form(2026), month: int = Form(9), db: Session = Depends(get_db)):
    """Naliczanie listy płac"""
    db.query(PayrollRecord).filter(PayrollRecord.year == year, PayrollRecord.month == month).delete()
    employees = db.query(Employee).all()

    for emp in employees:
        absences = db.query(Absence).filter(
            Absence.employee_id == emp.id,
            Absence.absence_type == "CHOROBA_80"
        ).all()
        sick_days_count = sum(
            (ab.date_to - ab.date_from).days + 1
            for ab in absences
            if ab.date_from.month == month and ab.date_from.year == year
        )

        calc = calculate_payroll_for_month(
            birth_date=emp.birth_date,
            base_salary=emp.base_salary,
            fixed_allowance=emp.fixed_allowance,
            sick_days=sick_days_count,
            worked_hours=168.0,
            calculation_date=date(year, month, 28)
        )

        record = PayrollRecord(
            employee_id=emp.id,
            year=year,
            month=month,
            hours_worked=168.0,
            sick_days=sick_days_count,
            gross_total=calc["gross_total"],
            social_zus=calc["social_zus"],
            health_zus=calc["health_zus"],
            pit_advance=calc["pit_advance"],
            net_amount=calc["net_amount"]
        )
        db.add(record)

    db.commit()
    return RedirectResponse(url="/?tab=payroll", status_code=303)

@app.get("/payroll/export-elixir-file")
def export_elixir_file(year: int = 2026, month: int = 9, db: Session = Depends(get_db)):
    """Eksport pliku do banku"""
    records = db.query(PayrollRecord).filter(
        PayrollRecord.year == year,
        PayrollRecord.month == month
    ).all()
    lines = [
        f"110,{int(r.net_amount * 100)},{r.employee.bank_account},{r.employee.first_name} {r.employee.last_name},,Wynagrodzenie {month:02d}/{year}"
        for r in records
    ]
    return PlainTextResponse(
        content="\n".join(lines),
        headers={"Content-Disposition": f"attachment; filename=elixir_{year}_{month:02d}.txt"}
    )