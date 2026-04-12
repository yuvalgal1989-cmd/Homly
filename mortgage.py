#!/usr/bin/env python3
from typing import Optional


def calculate_down_payment(price: float, ltv_percent: float) -> Optional[float]:
    """Return down payment given purchase price and loan-to-value percent (0–100)."""
    if not price or not ltv_percent:
        return None
    if price <= 0 or not (0 < ltv_percent <= 100):
        return None
    return round(price * (1 - ltv_percent / 100), 2)


def calculate_loan_amount(price: float, down_payment: float) -> Optional[float]:
    """Return loan amount = price - down payment."""
    if price is None or down_payment is None:
        return None
    if price <= 0 or down_payment < 0 or down_payment >= price:
        return None
    return round(price - down_payment, 2)


def calculate_monthly_payment(
    loan: float, annual_interest: float, years: int
) -> Optional[float]:
    """
    Standard fixed-rate annuity formula.
    annual_interest: percent (e.g. 4.5 for 4.5%)
    Returns None for invalid inputs or zero-interest loans.
    """
    if loan is None or annual_interest is None or years is None:
        return None
    if loan <= 0 or years <= 0:
        return None
    if annual_interest <= 0:
        # Zero-interest: equal instalments
        return round(loan / (years * 12), 2)
    r = annual_interest / 100 / 12
    n = years * 12
    payment = loan * r * (1 + r) ** n / ((1 + r) ** n - 1)
    return round(payment, 2)


def calculate_total_payment(monthly_payment: float, years: int) -> Optional[float]:
    """Total amount paid over the loan term."""
    if monthly_payment is None or years is None:
        return None
    if monthly_payment <= 0 or years <= 0:
        return None
    return round(monthly_payment * years * 12, 2)


def calculate_total_interest(total_payment: float, loan: float) -> Optional[float]:
    """Total interest paid = total payment - principal."""
    if total_payment is None or loan is None:
        return None
    if total_payment <= 0 or loan <= 0:
        return None
    return round(total_payment - loan, 2)


def calculate_cash_flow(
    monthly_rent: Optional[float], monthly_payment: Optional[float]
) -> Optional[float]:
    """
    Net monthly cash flow = rent - mortgage payment.
    Positive = property covers the mortgage.
    Negative = out-of-pocket each month.
    """
    if monthly_rent is None or monthly_payment is None:
        return None
    if monthly_payment <= 0:
        return None
    return round(monthly_rent - monthly_payment, 2)


def simulate_mortgage_scenarios(
    price: float,
    ltv_percent: float,
    annual_interest: float,
    years_list: list[int],
) -> list[dict]:
    """
    Return a list of scenario dicts for each loan duration in years_list.

    Each dict contains:
        years, down_payment, loan_amount, monthly_payment,
        total_payment, total_interest, interest_to_loan_ratio
    """
    if not price or not ltv_percent or not annual_interest or not years_list:
        return []
    if price <= 0 or not (0 < ltv_percent <= 100) or annual_interest < 0:
        return []

    down_payment = calculate_down_payment(price, ltv_percent)
    loan = calculate_loan_amount(price, down_payment)

    if loan is None:
        return []

    results = []
    for years in years_list:
        if not isinstance(years, int) or years <= 0:
            continue
        monthly = calculate_monthly_payment(loan, annual_interest, years)
        total = calculate_total_payment(monthly, years)
        interest = calculate_total_interest(total, loan)
        results.append({
            "years":                years,
            "down_payment":         down_payment,
            "loan_amount":          loan,
            "monthly_payment":      monthly,
            "total_payment":        total,
            "total_interest":       interest,
            "interest_to_loan_ratio": round(interest / loan, 4) if interest and loan else None,
        })

    return results
