################################################################################
# Guard Planner Rules:
# - Can't do 2 days in a row, can't do weekends if needs_weekends is False
# - Each person that needs_weekends will do 2 weekends
# - Each person that doesn't need_weekends will do 0 weekends
# - Space out duties as much as possible
# - Avoid assigning only 1 weekend (if possible)
# - Each person will do an equal number of total days as much as possible
# - People who did more duties last month should do fewer this month (if possible)
################################################################################

import json
from datetime import datetime, timedelta
from collections import defaultdict

with open("data.json", "r") as file:
    data = json.load(file)

people = []
for entry in data["people"]:
    unavailable_dates = [
        datetime.strptime(date, "%Y-%m-%d").date()
        for date in entry["unavailable_dates"]
    ]
    people.append({
        "name": entry["name"],
        "needs_weekends": entry["needs_weekends"],
        "unavailable_dates": set(unavailable_dates),
        "duties_last_month": entry["duties_last_month"],
    })

month = "November 2025"
month_start = datetime.strptime(f"1 {month}", "%d %B %Y").date()
if month_start.month == 12:
    month_end = month_start.replace(year=month_start.year + 1, month=1, day=1)
else:
    month_end = month_start.replace(month=month_start.month + 1, day=1)
num_days = (month_end - month_start).days
dates = [month_start.replace(day=i) for i in range(1, num_days + 1)]
weekends = {d for d in dates if d.weekday() >= 5}

# - QUOTA -
total_days = len(dates)
total_ppl = len(people)
base_quota = total_days // total_ppl
extra = total_days % total_ppl

# - SET INDIVIDUAL QUOTAS -
target_counts = {}
sorted_people = sorted(people, key=lambda p: p["duties_last_month"], reverse=True)
for i, person in enumerate(sorted_people):
    quota = base_quota + (1 if i < extra else 0)
    quota = max(0, quota - (person["duties_last_month"] > base_quota)) # 1 less if they did more last month
    target_counts[person["name"]] = quota

# - SET WEEKEND QUOTAS -
weekend_people = [p for p in people if p["needs_weekends"]]
for p in weekend_people:
    target_counts[p["name"]] = max(target_counts[p["name"]], 2)

schedule = {}
assigned_counts = defaultdict(int)
weekend_counts = defaultdict(int)

for date in dates:
    candidates = []
    for p in people:
        name = p["name"]

        if date in p["unavailable_dates"]:
            continue
        if date in weekends and not p["needs_weekends"]:
            continue
        prev_date = date - timedelta(days=1)
        if prev_date in schedule and schedule[prev_date] == name: # Prevent back-to-back duties
            continue
        if assigned_counts[name] >= target_counts[name]: # Prevent exceeding target
            continue
        if date in weekends and weekend_counts[name] >= 2:
            continue

        candidates.append(p)

    if candidates:
        chosen = sorted(
            candidates,
            key=lambda x: (assigned_counts[x["name"]], x["duties_last_month"])
        )[0] # Sort by least assigned this month, then by least last month
        schedule[date] = chosen["name"]
        assigned_counts[chosen["name"]] += 1
        if date in weekends:
            weekend_counts[chosen["name"]] += 1
    else:
        schedule[date] = "UNASSIGNED"

for d in dates:
    print(d, "->", schedule[d])

print("\nSummary:")
for p in people:
    name = p["name"]
    print(name, "duties:", assigned_counts[name], "weekends:", weekend_counts[name], "target:", target_counts[name])