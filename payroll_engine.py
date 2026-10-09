from datetime import date

def calculate_payroll_for_month(
    birth_date: date,
    base_salary: float,
    fixed_allowance: float,
    sick_days: int,
    worked_hours: float,
    calculation_date: date = date.today()
) -> dict:
    # 1. Ulga dla młodych (<26 lat)
    age = (calculation_date - birth_date).days // 365.25
    is_pit_exempt = age < 26

    # 2. Odliczenie za chorobę (1/30 za każdy dzień) + chorobowe 80%
    salary_deduction = (base_salary / 30.0) * sick_days
    earned_base = max(0.0, base_salary - salary_deduction)
    sick_pay = (base_salary * 0.8 / 30.0) * sick_days

    gross_total = round(earned_base + fixed_allowance + sick_pay, 2)

    # 3. ZUS Społeczne (od chorobowego NIE płaci się składek społecznych)
    social_base = round(earned_base + fixed_allowance, 2)
    skladka_emerytalna = round(social_base * 0.0976, 2)   # 9.76%
    skladka_rentowa = round(social_base * 0.015, 2)       # 1.50%
    skladka_chorobowa = round(social_base * 0.0245, 2)    # 2.45%
    social_zus = round(skladka_emerytalna + skladka_rentowa + skladka_chorobowa, 2)

    # 4. ZUS Zdrowotna (9% od brutto minus składki społeczne)
    health_base = round(gross_total - social_zus, 2)
    health_zus = round(health_base * 0.09, 2)

    # 5. Zaliczka PIT (12% minus kwota zmniejszająca 300 zł)
    if is_pit_exempt:
        pit_advance = 0.0
    else:
        kup = 250.0  # Zryczałtowane KUP
        tax_base = max(0.0, health_base - kup)
        raw_tax = (tax_base * 0.12) - 300.0
        pit_advance = round(max(0.0, raw_tax), 2)

    # 6. Wynagrodzenie Netto
    net_amount = round(gross_total - social_zus - health_zus - pit_advance, 2)

    return {
        "gross_total": gross_total,
        "social_zus": social_zus,
        "health_zus": health_zus,
        "pit_advance": pit_advance,
        "net_amount": net_amount
    }