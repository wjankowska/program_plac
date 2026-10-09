from datetime import date
from fastapi import FastAPI, Depends, Request, Form
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import engine, get_db, Base
from models import Employee, RfidEvent, Absence, PayrollRecord
from payroll_engine import calculate_payroll_for_month

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Payroll Core")
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    """Główny panel księgowej"""
    records = db.query(PayrollRecord).filter(
        PayrollRecord.year == 2026,
        PayrollRecord.month == 9
    ).all()

    total_gross = sum(r.gross_total for r in records) if records else 0.0
    total_net = sum(r.net_amount for r in records) if records else 0.0
    total_zus = sum(r.social_zus + r.health_zus for r in records) if records else 0.0

    stats = {
        "total_employees": db.query(Employee).count(),
        "total_gross": total_gross,
        "total_zus": total_zus,
        "total_net": total_net,
    }

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"records": records, "stats": stats}
    )

@app.post("/payroll/calculate-view")
def calculate_and_refresh(year: int = Form(2026), month: int = Form(9), db: Session = Depends(get_db)):
    """Naliczanie listy płac z poziomu panelu"""
    # Usuwamy ewentualne stare naliczenia za ten miesiąc
    db.query(PayrollRecord).filter(PayrollRecord.year == year, PayrollRecord.month == month).delete()

    employees = db.query(Employee).all()

    for emp in employees:
        # Zliczamy e-ZLA
        absences = db.query(Absence).filter(
            Absence.employee_id == emp.id,
            Absence.absence_type == "CHOROBA_80"
        ).all()
        
        sick_days_count = 0
        for ab in absences:
            if ab.date_from.month == month and ab.date_from.year == year:
                sick_days_count += (ab.date_to - ab.date_from).days + 1

        # Zliczamy godziny
        events = db.query(RfidEvent).filter(RfidEvent.employee_id == emp.id).all()
        total_hours = len(events) // 2 * 8.0

        calc = calculate_payroll_for_month(
            birth_date=emp.birth_date,
            base_salary=emp.base_salary,
            fixed_allowance=emp.fixed_allowance,
            sick_days=sick_days_count,
            worked_hours=total_hours,
            calculation_date=date(year, month, 28)
        )

        record = PayrollRecord(
            employee_id=emp.id,
            year=year,
            month=month,
            hours_worked=total_hours,
            sick_days=sick_days_count,
            gross_total=calc["gross_total"],
            social_zus=calc["social_zus"],
            health_zus=calc["health_zus"],
            pit_advance=calc["pit_advance"],
            net_amount=calc["net_amount"]
        )
        db.add(record)

    db.commit()
    return RedirectResponse(url="/", status_code=303)

@app.get("/payroll/export-elixir-file")
def export_elixir_file(year: int = 2026, month: int = 9, db: Session = Depends(get_db)):
    """Pobieranie pliku przelewów Elixir"""
    records = db.query(PayrollRecord).filter(
        PayrollRecord.year == year,
        PayrollRecord.month == month
    ).all()

    lines = []
    for r in records:
        emp = r.employee
        grosze = int(r.net_amount * 100)
        lines.append(f"110,{grosze},{emp.bank_account},{emp.first_name} {emp.last_name},,Wynagrodzenie {month:02d}/{year}")

    content = "\n".join(lines)
    return PlainTextResponse(
        content=content,
        headers={"Content-Disposition": f"attachment; filename=elixir_{year}_{month:02d}.txt"}
    )