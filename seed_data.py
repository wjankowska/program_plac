import random
from datetime import date, datetime, timedelta
from faker import Faker
from database import SessionLocal, engine, Base
from models import Employee, RfidEvent, Absence

fake = Faker("pl_PL")
Base.metadata.create_all(bind=engine)
db = SessionLocal()

def seed():
    print("Czyszczenie starych danych...")
    db.query(RfidEvent).delete()
    db.query(Absence).delete()
    db.query(Employee).delete()
    db.commit()

    print("Generowanie 50 pracowników...")
    employees = []
    for i in range(1, 51):
        # Część pracowników poniżej 26 lat, część powyżej
        is_young = random.random() < 0.3
        if is_young:
            b_date = fake.date_of_birth(minimum_age=20, maximum_age=25)
        else:
            b_date = fake.date_of_birth(minimum_age=27, maximum_age=60)

        emp = Employee(
            first_name=fake.first_name(),
            last_name=fake.last_name(),
            birth_date=b_date,
            card_uid=f"CARD_{1000 + i}",
            bank_account=fake.iban(),
            contract_type="UOP",
            base_salary=round(random.uniform(4300.0, 11000.0), 2),
            fixed_allowance=round(random.choice([0, 200, 500, 800]), 2)
        )
        db.add(emp)
        employees.append(emp)
    
    db.commit()

    print("Generowanie zdarzeń RCP i zwolnień lekarskich na okres 30 dni...")
    start_date = date(2026, 9, 1)
    
    for emp in employees:
        # Losowo przydzielmy niektórym pracownikom chorobowe z ZUS
        has_sick_leave = random.random() < 0.2
        sick_days_list = []
        if has_sick_leave:
            sick_start = start_date + timedelta(days=random.randint(5, 20))
            sick_len = random.randint(3, 7)
            sick_end = sick_start + timedelta(days=sick_len)
            absence = Absence(
                employee_id=emp.id,
                date_from=sick_start,
                date_to=sick_end,
                absence_type="CHOROBA_80"
            )
            db.add(absence)
            for d in range(sick_len + 1):
                sick_days_list.append(sick_start + timedelta(days=d))

        # Generowanie odbić wejść/wyjść w dni robocze
        for day_offset in range(30):
            current_day = start_date + timedelta(days=day_offset)
            
            # Pomiń weekendy (sobota=5, niedziela=6)
            if current_day.weekday() >= 5:
                continue

            # Pomiń dni choroby
            if current_day in sick_days_list:
                continue

            # Losowe wejście (ok. 7:45 - 8:15)
            in_minute = random.randint(45, 75)  # 7:45 do 8:15
            in_time = datetime(current_day.year, current_day.month, current_day.day, 7, 0) + timedelta(minutes=in_minute)
            
            # Losowe wyjście (ok. 15:55 - 16:20)
            out_time = in_time + timedelta(hours=8, minutes=random.randint(-5, 20))

            db.add(RfidEvent(employee_id=emp.id, timestamp=in_time, event_type="IN"))
            db.add(RfidEvent(employee_id=emp.id, timestamp=out_time, event_type="OUT"))

    db.commit()
    print("Baza została pomyślnie załadowana 50 pracownikami, odbiciami i e-ZLA!")
    db.close()

if __name__ == "__main__":
    seed()