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
weekends = [d for d in dates if d.weekday() >= 5]

# - SET BASE QUOTA -
total_days = len(dates)
total_ppl = len(people)
base_quota = total_days // total_ppl
extra = total_days % total_ppl

print(base_quota, extra)

# - SET INDIVIDUAL QUOTAS -
target_counts = {}
sorted_people = sorted(people, key=lambda p: p["duties_last_month"], reverse=True)
for i, person in enumerate(sorted_people):
    quota = base_quota + (1 if i < extra else 0)
    # Adjust quota down if they had more duties last month than base_quota
    if person["duties_last_month"] > base_quota:
        quota = max(quota - 1, base_quota)
    target_counts[person["name"]] = quota

# - SET WEEKEND QUOTAS -
weekend_people = [p for p in people if p["needs_weekends"]]
for p in weekend_people:
    target_counts[p["name"]] = max(target_counts[p["name"]], 2)

schedule = {}
assigned_counts = defaultdict(int)
weekend_counts = defaultdict(int)
last_assigned = {}  # Track last assigned date for each person

def days_since_last_duty(person_name, current_date):
    """Calculate days since last duty, returns large number if never assigned"""
    if person_name not in last_assigned:
        return 999
    return (current_date - last_assigned[person_name]).days

# - PRE-ASSIGN WEEKENDS FAIRLY -
# Balance weekends to ensure everyone gets exactly 2 (or as close as possible)
weekend_dates = list(weekends)
weekend_dates.sort()

# Assign weekends in rounds to ensure fairness
for date in weekend_dates:
    candidates = [p for p in weekend_people
                  if date not in p["unavailable_dates"]
                  and weekend_counts[p["name"]] < 2
                  and not (date - timedelta(days=1) in schedule and schedule[date - timedelta(days=1)] == p["name"])]
    
    if not candidates:
        # Relax the 2-weekend limit only if absolutely necessary
        candidates = [p for p in weekend_people
                      if date not in p["unavailable_dates"]
                      and not (date - timedelta(days=1) in schedule and schedule[date - timedelta(days=1)] == p["name"])]
    
    if candidates:
        # Prioritize: fewest weekends, then fewest total duties, then most days since last duty
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

# - ASSIGN WEEKDAYS -
for date in dates:
    if date in schedule:  # Already filled during pre-assignment
        continue

    candidates = []
    for p in people:
        name = p["name"]

        if date in p["unavailable_dates"]:
            continue
        if date in weekends and not p["needs_weekends"]:
            continue
        prev_date = date - timedelta(days=1)
        if prev_date in schedule and schedule[prev_date] == name:  # Prevent back-to-back duties
            continue
        if assigned_counts[name] >= target_counts[name]:  # Prevent exceeding target
            continue

        candidates.append(p)

    # If no candidates found, relax the target constraint
    if not candidates:
        for p in people:
            name = p["name"]
            if date in p["unavailable_dates"]:
                continue
            if date in weekends and not p["needs_weekends"]:
                continue
            prev_date = date - timedelta(days=1)
            if prev_date in schedule and schedule[prev_date] == name:
                continue
            candidates.append(p)

    if candidates:
        # Sort by: fewest duties, fewest last month, then longest time since last duty
        chosen = sorted(
            candidates,
            key=lambda x: (
                assigned_counts[x["name"]],
                x["duties_last_month"]
                -days_since_last_duty(x["name"], date),
            )
        )[0]
        schedule[date] = chosen["name"]
        assigned_counts[chosen["name"]] += 1
        last_assigned[chosen["name"]] = date
        if date in weekends:
            weekend_counts[chosen["name"]] += 1
    else:
        schedule[date] = "UNASSIGNED"

# - FIX SINGLE WEEKEND ASSIGNMENTS -
# Try to balance so everyone has 0 or 2 weekends, not 1
people_with_one_weekend = [p for p in weekend_people if weekend_counts[p["name"]] == 1]

for p in people_with_one_weekend:
    # Try to find an unassigned weekend or steal from someone with 3+
    assigned_second = False
    
    for date in weekend_dates:
        if assigned_second:
            break
            
        # Check if this weekend is unassigned
        if schedule.get(date) == "UNASSIGNED":
            if (date not in p["unavailable_dates"] and 
                not (date - timedelta(days=1) in schedule and schedule[date - timedelta(days=1)] == p["name"])):
                schedule[date] = p["name"]
                weekend_counts[p["name"]] += 1
                assigned_counts[p["name"]] += 1
                last_assigned[p["name"]] = date
                assigned_second = True
        # Check if we can swap with someone who has 3+ weekends
        elif (schedule.get(date) != p["name"] and 
              weekend_counts[schedule[date]] >= 3 and
              date not in p["unavailable_dates"] and
              not (date - timedelta(days=1) in schedule and schedule[date - timedelta(days=1)] == p["name"])):
            old = schedule[date]
            schedule[date] = p["name"]
            weekend_counts[p["name"]] += 1
            assigned_counts[p["name"]] += 1
            weekend_counts[old] -= 1
            assigned_counts[old] -= 1
            last_assigned[p["name"]] = date
            assigned_second = True

for d in dates:
    print(d, "->", schedule[d])

print("\nSummary:")
for p in people:
    name = p["name"]
    print(name, "Duties:", assigned_counts[name], "Weekends:", weekend_counts[name], "Target:", target_counts[name])

# --- CREATE NEXT MONTH DATA.JSON ---
next_month = (month_start + timedelta(days=num_days)).strftime("%B %Y")
next_data = {"people": []}

for p in people:
    next_data["people"].append({
        "name": p["name"],
        "needs_weekends": p["needs_weekends"],
        "unavailable_dates": [],  # reset
        "duties_last_month": assigned_counts[p["name"]]  # update with this month's duty count
    })

with open("next_month_data.json", "w") as f:
    json.dump(next_data, f, indent=4)

print(f"\nnext_month_data.json generated for {next_month}")