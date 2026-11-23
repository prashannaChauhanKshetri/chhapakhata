"""Attendance and salary, as the client asked:

* attendance is marked by hand; an absent day takes off one day's pay;
* working on Saturday (the weekly holiday) pays one day extra ("double");
* one day's pay = monthly salary ÷ days in that Nepali month;
* advances come off the month's salary; a paid month is locked.

Shrawan 2083 has 31 days (17 Jul – 16 Aug 2026), so Rs 15,500 a month is Rs 500 a day.
"""

import datetime as dt
from decimal import Decimal as D

import pytest
from rest_framework.exceptions import ValidationError

from apps.core.dates import local_today
from apps.core.models import ActivityLog
from apps.staff import services
from apps.staff.models import Attendance, SalaryPayment, Staff, StaffAdvance

pytestmark = pytest.mark.django_db

YEAR, MONTH = 2083, 4  # Shrawan 2083
FIRST = dt.date(2026, 7, 17)
LAST = dt.date(2026, 8, 16)
TUESDAY = dt.date(2026, 7, 21)
WEDNESDAY = dt.date(2026, 7, 22)
SATURDAY = dt.date(2026, 7, 25)


@pytest.fixture
def ram(db) -> Staff:
    return Staff.objects.create(
        name="Ram Thapa",
        job_title="Fitter",
        monthly_salary=D("15500"),
        joined_on=dt.date(2026, 1, 1),
    )


def sheet(staff):
    return services.month_sheet(staff, YEAR, MONTH)


def mark(staff, day, status, user=None):
    return services.set_attendance(staff=staff, day=day, status=status, user=user)


def test_a_month_with_no_marks_pays_the_full_salary(ram):
    s = sheet(ram)
    assert (s.days_in_month, s.days_employed, s.day_rate) == (31, 31, D("500.00"))
    assert s.earned == s.net == D("15500")


def test_an_absent_day_takes_off_one_day_and_a_saturday_worked_adds_one(ram, owner):
    mark(ram, TUESDAY, "absent", owner)
    mark(ram, WEDNESDAY, "absent", owner)
    mark(ram, SATURDAY, "worked", owner)
    s = sheet(ram)
    assert s.absent_dates == [TUESDAY, WEDNESDAY]
    assert s.worked_dates == [SATURDAY]
    assert (s.absent_deduction, s.holiday_pay) == (D("1000.00"), D("500.00"))
    assert s.net == D("15000.00")

    # Marking present again (or off on Saturday) clears the mark.
    mark(ram, WEDNESDAY, "present", owner)
    mark(ram, SATURDAY, "off", owner)
    assert sheet(ram).net == D("15000.00")  # 15,500 − one absent day
    assert Attendance.objects.count() == 1


def test_one_day_pay_follows_the_length_of_the_nepali_month(ram):
    # Bhadra 2083 has 31 days too; Kartik 2083 has 30: the same salary, a different day rate.
    kartik = services.month_sheet(ram, 2083, 7)
    assert kartik.days_in_month == 30
    assert kartik.day_rate == D("516.67")


def test_saturday_is_off_or_worked_and_a_working_day_present_or_absent(ram, owner):
    with pytest.raises(ValidationError):
        mark(ram, SATURDAY, "absent", owner)
    with pytest.raises(ValidationError):
        mark(ram, TUESDAY, "worked", owner)


def test_days_to_come_and_days_before_joining_cannot_be_marked(ram, owner):
    with pytest.raises(ValidationError, match="still to come"):
        mark(ram, local_today() + dt.timedelta(days=1), "absent", owner)
    with pytest.raises(ValidationError, match="not working here"):
        mark(ram, dt.date(2025, 12, 30), "absent", owner)


def test_a_worker_who_joins_mid_month_is_paid_for_the_days_from_joining(owner):
    sita = Staff.objects.create(
        name="Sita", monthly_salary=D("15500"), joined_on=dt.date(2026, 8, 1)
    )
    s = sheet(sita)
    assert s.days_employed == 16  # 1 – 16 Aug
    assert s.base_pay == D("8000.00")


def test_advances_come_off_the_salary(ram, owner):
    services.give_advance(staff=ram, day=TUESDAY, amount=D("3000"), note="Festival", user=owner)
    s = sheet(ram)
    assert s.advances_total == D("3000")
    assert s.net == D("12500")


def test_paying_locks_the_month_and_undoing_unlocks_it(ram, owner):
    mark(ram, TUESDAY, "absent", owner)
    payment = services.pay_salary(
        staff=ram, bs_year=YEAR, bs_month=MONTH, paid_on=LAST, mode="cash", user=owner
    )
    assert payment.net_paid == D("15000.00")
    assert payment.absent_days == 1
    assert ActivityLog.objects.filter(action="staff.salary_paid").exists()

    with pytest.raises(ValidationError, match="already paid"):
        mark(ram, WEDNESDAY, "absent", owner)
    with pytest.raises(ValidationError, match="already paid"):
        services.give_advance(staff=ram, day=TUESDAY, amount=D("100"), note="", user=owner)
    with pytest.raises(ValidationError, match="already paid"):
        services.pay_salary(
            staff=ram, bs_year=YEAR, bs_month=MONTH, paid_on=LAST, mode="cash", user=owner
        )

    # A raise later does not change what was paid.
    ram.monthly_salary = D("20000")
    ram.save()
    assert sheet(ram).net == D("15000.00")

    services.undo_salary(payment=payment, user=owner, reason="Entered twice")
    assert not SalaryPayment.objects.exists()
    mark(ram, WEDNESDAY, "absent", owner)  # open again


def test_advances_more_than_the_pay_move_to_next_month(ram, owner):
    services.give_advance(staff=ram, day=TUESDAY, amount=D("16000"), note="", user=owner)
    payment = services.pay_salary(
        staff=ram, bs_year=YEAR, bs_month=MONTH, paid_on=LAST, mode="cash", user=owner
    )
    assert payment.net_paid == D("0")
    assert payment.carried_forward == D("500")
    carried = StaffAdvance.objects.get(carried_from=payment)
    assert carried.date == LAST + dt.timedelta(days=1)  # 1 Bhadra
    assert services.month_sheet(ram, 2083, 5).advances_total == D("500")

    # It goes away with the payment, and cannot be removed on its own.
    with pytest.raises(ValidationError, match="carried"):
        services.delete_advance(advance=carried, user=owner)
    services.undo_salary(payment=payment, user=owner, reason="Mistake")
    assert not StaffAdvance.objects.filter(pk=carried.pk).exists()


def test_a_worker_who_left_needs_a_last_day_and_drops_off_later_months(api, owner, ram):
    response = api(owner).patch(f"/api/v1/staff/{ram.pk}/", {"is_active": False}, format="json")
    assert response.status_code == 400
    assert "left_on" in response.json()["errors"][0]["attr"]

    response = api(owner).patch(
        f"/api/v1/staff/{ram.pk}/", {"is_active": False, "left_on": "2026-07-31"}, format="json"
    )
    assert response.status_code == 200
    assert services.month_sheet(Staff.objects.get(pk=ram.pk), YEAR, MONTH).days_employed == 15
    assert ram not in services.staff_for_month(2083, 6)


# -- The API ------------------------------------------------------------------------


def test_daily_register_and_marking_through_the_api(api, owner, ram):
    client = api(owner)
    register = client.get("/api/v1/attendance/", {"date": TUESDAY.isoformat()}).json()
    assert register["is_holiday"] is False
    assert register["rows"][0]["status"] == "present"

    response = client.post(
        "/api/v1/attendance/",
        {"staff": ram.pk, "date": TUESDAY.isoformat(), "status": "absent"},
        format="json",
    )
    assert response.status_code == 200, response.content
    register = client.get("/api/v1/attendance/", {"date": TUESDAY.isoformat()}).json()
    assert register["rows"][0]["status"] == "absent"

    saturday = client.get("/api/v1/attendance/", {"date": SATURDAY.isoformat()}).json()
    assert saturday["is_holiday"] is True
    assert saturday["rows"][0]["status"] == "off"


def test_salary_month_pay_and_slip_through_the_api(api, owner, ram, shop):
    client = api(owner)
    client.post(
        "/api/v1/staff-advances/",
        {"staff": ram.pk, "date": TUESDAY.isoformat(), "amount": "2000", "note": "Rent"},
        format="json",
    )
    month = client.get("/api/v1/salary/", {"month": "2083-04"}).json()
    assert month["label"] == "Shrawan 2083"
    row = month["rows"][0]
    assert (row["earned"], row["advances_total"], row["net"]) == ("15500.00", "2000.00", "13500.00")
    assert row["payment"] is None

    response = client.post(
        "/api/v1/salary/pay/",
        {"staff": ram.pk, "year": 2083, "month": 4, "paid_on": LAST.isoformat(), "mode": "cash"},
        format="json",
    )
    assert response.status_code == 201, response.content
    payment_id = response.json()["id"]
    assert client.get("/api/v1/salary/", {"month": "2083-04"}).json()["total_paid"] == "13500.00"

    slip = client.get(f"/api/v1/salary-payments/{payment_id}/slip/")
    assert slip.status_code == 200
    assert slip["Content-Type"] == "application/pdf"
    assert slip.content.startswith(b"%PDF")

    response = client.post(
        f"/api/v1/salary-payments/{payment_id}/undo/", {"reason": "Wrong month"}, format="json"
    )
    assert response.status_code == 204


def test_front_desk_and_operators_cannot_see_or_change_salaries(api, desk, operator, ram):
    for user in (desk, operator):
        client = api(user)
        assert client.get("/api/v1/salary/").status_code == 403
        assert (
            client.post(
                "/api/v1/attendance/",
                {"staff": ram.pk, "date": TUESDAY.isoformat(), "status": "absent"},
                format="json",
            ).status_code
            == 403
        )
        assert client.patch(f"/api/v1/staff/{ram.pk}/", {"monthly_salary": "1"}).status_code == 403


def test_a_bad_month_is_refused(api, owner):
    assert api(owner).get("/api/v1/salary/", {"month": "2083-13"}).status_code == 400
    assert api(owner).get("/api/v1/salary/", {"month": "june"}).status_code == 400


# -- Saturday pay chosen by the owner, and correcting past days -----------------------


def test_the_owner_can_set_a_worker_s_own_saturday_pay(ram, owner):
    ram.saturday_pay = D("800")
    ram.save()
    mark(ram, SATURDAY, "worked", owner)
    mark(ram, dt.date(2026, 8, 1), "worked", owner)
    s = sheet(ram)
    assert (s.holiday_rate, s.holiday_pay) == (D("800"), D("1600.00"))
    assert s.net == D("17100.00")  # 15,500 + 2 × 800

    payment = services.pay_salary(
        staff=ram, bs_year=YEAR, bs_month=MONTH, paid_on=LAST, mode="cash", user=owner
    )
    assert payment.holiday_rate == D("800")
    # Changing it later leaves the paid month as paid.
    ram.saturday_pay = None
    ram.save()
    assert sheet(ram).holiday_pay == D("1600.00")


def test_without_its_own_saturday_pay_a_saturday_is_one_day(ram, owner):
    mark(ram, SATURDAY, "worked", owner)
    assert sheet(ram).holiday_rate == D("500.00")


def test_saturday_pay_is_set_through_the_staff_form(api, owner, ram):
    response = api(owner).patch(f"/api/v1/staff/{ram.pk}/", {"saturday_pay": "750"}, format="json")
    assert response.status_code == 200
    assert response.json()["saturday_pay"] == "750.00"
    response = api(owner).patch(f"/api/v1/staff/{ram.pk}/", {"saturday_pay": None}, format="json")
    assert response.json()["saturday_pay"] is None


def test_the_month_calendar_lets_past_days_be_corrected(api, owner, ram):
    client = api(owner)
    month = client.get(f"/api/v1/staff/{ram.pk}/days/", {"month": "2083-04"}).json()
    assert month["label"] == "Shrawan 2083"
    assert len(month["days"]) == 31
    first = month["days"][0]
    assert (first["bs_day"], first["weekday"]) == (1, 5)  # 1 Shrawan 2083 was a Friday
    saturday = month["days"][1]
    assert (saturday["is_holiday"], saturday["status"], saturday["editable"]) == (True, "off", True)

    # A day weeks ago is corrected like any other.
    client.post(
        "/api/v1/attendance/",
        {"staff": ram.pk, "date": TUESDAY.isoformat(), "status": "absent"},
        format="json",
    )
    month = client.get(f"/api/v1/staff/{ram.pk}/days/", {"month": "2083-04"}).json()
    assert month["days"][4]["status"] == "absent"

    # Paid: nothing can be changed until the payment is undone.
    services.pay_salary(
        staff=ram, bs_year=YEAR, bs_month=MONTH, paid_on=LAST, mode="cash", user=owner
    )
    month = client.get(f"/api/v1/staff/{ram.pk}/days/", {"month": "2083-04"}).json()
    assert month["paid"] is True
    assert not any(day["editable"] for day in month["days"])


def test_days_before_joining_and_still_to_come_are_not_editable(api, owner):
    newcomer = Staff.objects.create(
        name="Gopal", monthly_salary=D("12000"), joined_on=dt.date(2026, 8, 10)
    )
    month = api(owner).get(f"/api/v1/staff/{newcomer.pk}/days/", {"month": "2083-04"}).json()
    before = [d for d in month["days"] if d["date"] < "2026-08-10"]
    assert all(d["status"] == "not_working" and not d["editable"] for d in before)
    this_month = api(owner).get(f"/api/v1/staff/{newcomer.pk}/days/").json()
    today = local_today().isoformat()
    assert all(not d["editable"] for d in this_month["days"] if d["date"] > today)


# -- Balance up to a month, entered when the shop starts using the app ---------------


def with_balance(staff, amount, year=2083, month=3):  # up to Asar 2083
    staff.balance_year, staff.balance_month, staff.opening_balance = year, month, D(amount)
    staff.save()
    return staff


def test_a_balance_owed_to_the_worker_is_paid_in_the_next_month(ram, owner):
    with_balance(ram, "5000")
    s = sheet(ram)
    assert (s.opening_balance, s.opening_label) == (D("5000"), "Asar 2083")
    assert s.net == D("20500")  # 15,500 + 5,000
    payment = services.pay_salary(
        staff=ram, bs_year=YEAR, bs_month=MONTH, paid_on=LAST, mode="cash", user=owner
    )
    assert (payment.opening_balance, payment.net_paid) == (D("5000"), D("20500"))
    # Only once: the month after has no balance.
    assert services.month_sheet(ram, 2083, 5).opening_balance == 0


def test_an_old_advance_owed_by_the_worker_is_taken_off(ram, owner):
    with_balance(ram, "-2000")
    assert sheet(ram).net == D("13500")
    with_balance(ram, "-20000")
    s = sheet(ram)
    assert (s.net, s.carry_forward) == (D("0"), D("4500"))


def test_months_up_to_the_balance_are_settled_and_locked(api, ram, owner):
    with_balance(ram, "0", year=2083, month=4)  # up to Shrawan: counting starts in Bhadra
    assert ram not in services.staff_for_month(YEAR, MONTH)
    assert ram in services.staff_for_month(2083, 5)
    with pytest.raises(ValidationError, match="settled by"):
        mark(ram, TUESDAY, "absent", owner)
    with pytest.raises(ValidationError, match="settled by"):
        services.give_advance(staff=ram, day=TUESDAY, amount=D("100"), note="", user=owner)
    days = api(owner).get(f"/api/v1/staff/{ram.pk}/days/", {"month": "2083-04"}).json()["days"]
    assert {d["status"] for d in days} == {"settled"}
    assert not any(d["editable"] for d in days)


def test_the_balance_is_set_through_the_staff_form(api, owner, ram):
    client = api(owner)
    response = client.patch(
        f"/api/v1/staff/{ram.pk}/",
        {"balance_year": 2083, "balance_month": 3, "opening_balance": "-1500"},
        format="json",
    )
    assert response.status_code == 200, response.content
    assert response.json()["balance_label"] == "Asar 2083"
    month = client.get("/api/v1/salary/", {"month": "2083-04"}).json()["rows"][0]
    assert (month["opening_balance"], month["net"]) == ("-1500.00", "14000.00")

    # An amount needs its month; a month still to come is refused.
    bad = client.patch(
        f"/api/v1/staff/{ram.pk}/",
        {"balance_year": None, "balance_month": None, "opening_balance": "100"},
        format="json",
    )
    assert bad.status_code == 400
    year, month = services.next_month(*services.month_of(local_today()))
    bad = client.patch(
        f"/api/v1/staff/{ram.pk}/", {"balance_year": year, "balance_month": month}, format="json"
    )
    assert bad.status_code == 400
    months = client.get("/api/v1/salary/months/").json()
    assert len(months) == 12 and months[0]["label"].endswith(
        str(services.month_of(local_today())[0])
    )


def test_the_balance_cannot_change_once_a_month_after_it_is_paid(api, owner, ram):
    with_balance(ram, "5000")
    services.pay_salary(
        staff=ram, bs_year=YEAR, bs_month=MONTH, paid_on=LAST, mode="cash", user=owner
    )
    response = api(owner).patch(
        f"/api/v1/staff/{ram.pk}/", {"opening_balance": "6000"}, format="json"
    )
    assert response.status_code == 400
    assert "already paid" in str(response.json())
    # Other details still change.
    assert api(owner).patch(f"/api/v1/staff/{ram.pk}/", {"phone": "9800000000"}).status_code == 200


# -- The month register and the Nepali calendar ---------------------------------------


def test_the_month_register_shows_everyone_day_by_day(api, owner, ram):
    mark(ram, TUESDAY, "absent", owner)
    mark(ram, SATURDAY, "worked", owner)
    data = api(owner).get("/api/v1/attendance/month/", {"month": "2083-04"}).json()
    assert data["label"] == "Shrawan 2083"
    assert len(data["days"]) == 31
    assert data["days"][1]["is_holiday"] is True  # 2 Shrawan was a Saturday
    row = data["rows"][0]
    assert row["staff"]["name"] == "Ram Thapa"
    assert (row["absent"], row["worked"]) == (1, 1)
    assert row["cells"][4] == {"status": "absent", "editable": True}  # 5 Shrawan
    assert row["cells"][8] == {"status": "worked", "editable": True}  # 9 Shrawan


def test_the_nepali_month_for_calendars(api, desk):
    data = api(desk).get("/api/v1/utils/bs-month/", {"month": "2083-04"}).json()
    assert data["label"] == "Shrawan 2083"
    assert data["previous"]["label"] == "Asar 2083" and data["next"]["label"] == "Bhadra 2083"
    assert data["days"][0] == {"date": "2026-07-17", "bs_day": 1, "weekday": 5}
    assert len(data["days"]) == 31
    chaitra = api(desk).get("/api/v1/utils/bs-month/", {"month": "2082-12"}).json()
    assert chaitra["next"]["label"] == "Baisakh 2083"
    by_ad = api(desk).get("/api/v1/utils/bs-month/", {"ad": "2026-07-20"}).json()
    assert by_ad["label"] == "Shrawan 2083"
    assert api(desk).get("/api/v1/utils/bs-month/", {"month": "nope"}).status_code == 400


# -- Dates entered by hand -------------------------------------------------------------


def test_a_joining_date_still_to_come_is_refused_with_its_miti(api, owner):
    later = local_today() + dt.timedelta(days=35)
    response = api(owner).post(
        "/api/v1/staff/",
        {"name": "Chinta", "monthly_salary": "13000", "joined_on": later.isoformat()},
        format="json",
    )
    assert response.status_code == 400
    error = response.json()["errors"][0]
    assert error["attr"] == "joined_on"
    assert "still to come" in error["detail"] and " BS (" in error["detail"]


def test_a_balance_needs_the_worker_to_have_joined_by_then(api, owner, ram):
    # Ram joined 1 Jan 2026 (Poush 2082): a balance up to Asar 2083 is fine.
    ok = api(owner).patch(
        f"/api/v1/staff/{ram.pk}/",
        {"balance_year": 2083, "balance_month": 3, "opening_balance": "3304"},
        format="json",
    )
    assert ok.status_code == 200
    # Joined after the balance month: nothing could be owed up to it.
    bad = api(owner).patch(f"/api/v1/staff/{ram.pk}/", {"joined_on": "2026-07-20"}, format="json")
    assert bad.status_code == 400
    assert "after Asar 2083" in bad.json()["errors"][0]["detail"]


def test_a_worker_who_left_still_shows_on_the_days_they_worked(api, owner, ram):
    ram.is_active, ram.left_on = False, dt.date(2026, 7, 31)
    ram.save()
    register = api(owner).get("/api/v1/attendance/", {"date": TUESDAY.isoformat()}).json()
    assert [r["staff"]["name"] for r in register["rows"]] == ["Ram Thapa"]
    after = api(owner).get("/api/v1/attendance/", {"date": "2026-08-05"}).json()
    assert after["rows"] == []


def test_already_working_here_starts_the_day_after_the_balance_month(api, owner):
    # The form for someone already working sends the 1st of the next month as joining.
    response = api(owner).post(
        "/api/v1/staff/",
        {
            "name": "Ratan",
            "monthly_salary": "15000",
            "joined_on": "2026-07-17",  # 1 Shrawan 2083
            "balance_year": 2083,
            "balance_month": 3,  # up to Asar 2083
            "opening_balance": "3304",
        },
        format="json",
    )
    assert response.status_code == 201, response.content


# -- Deleting a worker added by mistake -----------------------------------------------


def test_a_worker_with_no_money_records_can_be_deleted(api, owner, ram):
    mark(ram, TUESDAY, "absent", owner)
    listed = api(owner).get("/api/v1/staff/").json()
    assert listed[0]["can_delete"] is True
    assert api(owner).delete(f"/api/v1/staff/{ram.pk}/").status_code == 204
    assert not Staff.objects.filter(pk=ram.pk).exists()
    assert not Attendance.objects.exists()
    assert ActivityLog.objects.filter(action="staff.deleted").exists()


def test_a_worker_with_an_advance_or_salary_is_kept(api, owner, ram):
    services.give_advance(staff=ram, day=TUESDAY, amount=D("500"), note="", user=owner)
    assert api(owner).get("/api/v1/staff/").json()[0]["can_delete"] is False
    response = api(owner).delete(f"/api/v1/staff/{ram.pk}/")
    assert response.status_code == 400
    assert "Still working here" in response.json()["errors"][0]["detail"]
    assert Staff.objects.filter(pk=ram.pk).exists()


def test_only_the_owner_can_delete_a_worker(api, desk, ram):
    assert api(desk).delete(f"/api/v1/staff/{ram.pk}/").status_code == 403
