################################################################################
# Guard Planner Rules:
# - Can't do 2 days in a row, can't do weekends if needs_weekends is False
# - Each person that needs_weekends will do 2 weekends
# - Each person that doesn't need_weekends will do 0 weekends
# - Space out duties as much as possible
# - Assign either 2 or 0 weekends. Allow needs_weekends to do 0 if required, but assign 1 weekend only as a last resort.
# - Each person will do an equal number of total days as much as possible
# - People who did more duties last month should do fewer this month (if possible)
################################################################################

import json
import random
import argparse
from datetime import datetime, timedelta
from collections import defaultdict

parser = argparse.ArgumentParser(description="Guard Duty Planner")
parser.add_argument("--month", type=str, help="Month and Year (e.g., 'November 2025')", required=True)
args = parser.parse_args()
month = args.month

with open(f"{month.replace(' ', '_')}_data.json", "r") as file:
    data = json.load(file)

people = []
for entry in data["people"]:
    unavailable_dates = [
        datetime.strptime(date, "%Y-%m-%d").date()
        for date in entry["unavailable_dates"]
    ]
    preassigned_dates = [
        datetime.strptime(date, "%Y-%m-%d").date()
        for date in entry.get("preassigned_dates", [])
    ]
    people.append({
        "name": entry["name"],
        "needs_weekends": entry["needs_weekends"],
        "unavailable_dates": set(unavailable_dates),
        "duties_last_month": entry["duties_last_month"],
        "preassigned_dates": set(preassigned_dates)
    })

month_start = datetime.strptime(f"1 {month}", "%d %B %Y").date()
if month_start.month == 12:
    month_end = month_start.replace(year=month_start.year + 1, month=1, day=1)
else:
    month_end = month_start.replace(month=month_start.month + 1, day=1)
num_days = (month_end - month_start).days
dates = [month_start.replace(day=i) for i in range(1, num_days + 1)]
weekends = [d for d in dates if d.weekday() >= 5]

total_days = len(dates)
total_ppl = len(people)
base_quota = total_days // total_ppl
extra = total_days % total_ppl

print(base_quota, extra)

target_counts = {}
sorted_people = sorted(people, key=lambda p: p["duties_last_month"], reverse=True)
for i, person in enumerate(sorted_people):
    quota = base_quota + (1 if i < extra else 0)
    if person["duties_last_month"] > base_quota:
        quota = max(quota - 1, base_quota)
    target_counts[person["name"]] = quota

weekend_people = [p for p in people if p["needs_weekends"]]
for p in weekend_people:
    target_counts[p["name"]] = max(target_counts[p["name"]], 2)

schedule = {}
assigned_counts = defaultdict(int)
weekend_counts = defaultdict(int)
last_assigned = {}

def days_since_last_duty(person_name, current_date):
    if person_name not in last_assigned:
        return 999
    return (current_date - last_assigned[person_name]).days

def violates_back_to_back(name, date):
    prev_d = date - timedelta(days=1)
    next_d = date + timedelta(days=1)
    if prev_d in schedule and schedule[prev_d] == name:
        return True
    if next_d in schedule and schedule[next_d] == name:
        return True
    return False

# --- PREASSIGN DATES ---
preassigned_set = set()
for p in people:
    for d in p["preassigned_dates"]:
        if d < month_start or d >= month_end:
            continue
        if d in schedule:
            raise ValueError(f"duplicate preassignment on {d}")
        schedule[d] = p["name"]
        preassigned_set.add(d)
        assigned_counts[p["name"]] += 1
        last_assigned[p["name"]] = d
        if d.weekday() >= 5:
            weekend_counts[p["name"]] += 1

# --- WEEKEND ASSIGNMENT ---
weekend_dates = sorted(weekends)

for date in weekend_dates:
    if date in preassigned_set:
        continue

    candidates = [
        p for p in weekend_people
        if date not in p["unavailable_dates"]
        and not violates_back_to_back(p["name"], date)
        and weekend_counts[p["name"]] < 2
    ]

    if not candidates:
        candidates = [
            p for p in weekend_people
            if date not in p["unavailable_dates"]
            and not violates_back_to_back(p["name"], date)
        ]

    if candidates:
        chosen = sorted(
            candidates,
            key=lambda x: (
                weekend_counts[x["name"]],
                assigned_counts[x["name"]],
                -days_since_last_duty(x["name"], date),
                x["duties_last_month"]
            )
        )[0]
        schedule[date] = chosen["name"]
        weekend_counts[chosen["name"]] += 1
        assigned_counts[chosen["name"]] += 1
        last_assigned[chosen["name"]] = date

# --- WEEKDAY ASSIGNMENT ---
for date in dates:
    if date in schedule:
        continue

    candidates = []
    for p in people:
        name = p["name"]

        if date in p["preassigned_dates"] and schedule.get(date) != name:
            continue
        if date in p["unavailable_dates"]:
            continue
        if date in weekends and not p["needs_weekends"]:
            continue
        if violates_back_to_back(name, date):
            continue
        if assigned_counts[name] >= target_counts[name]:
            continue

        candidates.append(p)

    if not candidates:
        for p in people:
            name = p["name"]
            if date in p["preassigned_dates"] and schedule.get(date) != name:
                continue
            if date in p["unavailable_dates"]:
                continue
            if date in weekends and not p["needs_weekends"]:
                continue
            if violates_back_to_back(name, date):
                continue
            candidates.append(p)

    if candidates:
        chosen = sorted(
            candidates,
            key=lambda x: (
                assigned_counts[x["name"]],
                x["duties_last_month"],
                -days_since_last_duty(x["name"], date)
            )
        )[0]
        schedule[date] = chosen["name"]
        assigned_counts[chosen["name"]] += 1
        last_assigned[chosen["name"]] = date
        if date in weekends:
            weekend_counts[chosen["name"]] += 1
    else:
        schedule[date] = "UNASSIGNED"

# --- FIX SINGLE WEEKEND ASSIGNMENTS WHERE POSSIBLE ---
people_with_one = [p for p in weekend_people if weekend_counts[p["name"]] == 1]

for p in people_with_one:
    for date in weekend_dates:
        if date in preassigned_set:
            continue

        if schedule.get(date) == "UNASSIGNED":
            if (date not in p["unavailable_dates"]
                and not violates_back_to_back(p["name"], date)):
                schedule[date] = p["name"]
                weekend_counts[p["name"]] += 1
                assigned_counts[p["name"]] += 1
                last_assigned[p["name"]] = date
                break

        # Try swapping with someone who has 3 weekends
        elif (
            schedule.get(date) != p["name"]
            and weekend_counts[schedule[date]] >= 3
            and date not in p["unavailable_dates"]
            and not violates_back_to_back(p["name"], date)
        ):
            old = schedule[date]
            schedule[date] = p["name"]
            weekend_counts[p["name"]] += 1
            assigned_counts[p["name"]] += 1
            weekend_counts[old] -= 1
            assigned_counts[old] -= 1
            last_assigned[p["name"]] = date
            break

for d in dates:
    print(d, "->", schedule[d])

print("\nSummary:")
for p in people:
    name = p["name"]
    print(name, "Duties:", assigned_counts[name], "Weekends:", weekend_counts[name], "Target:", target_counts[name])

next_month = (month_start + timedelta(days=num_days)).strftime("%B %Y")
next_data = {"people": []}

random.shuffle(people)

for p in people:
    next_data["people"].append({
        "name": p["name"],
        "needs_weekends": weekend_counts[p["name"]] == 0,
        "unavailable_dates": [],
        "duties_last_month": assigned_counts[p["name"]]
    })

filename = f"{(month_start + timedelta(days=num_days)).strftime('%B_%Y')}_data.json"

with open(filename, "w") as f:
    json.dump(next_data, f, indent=4)

print(f"\n{filename} generated for {next_month}")