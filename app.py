from datetime import time as dtime
from datetime import UTC, datetime
import json
from pathlib import Path

import streamlit as st
from ai_scheduler import AISchedulerAdapter, ScenarioInput, ScenarioTask
from pawpal_system import Owner, Pet, Task, Scheduler
from reliability_evaluator import evaluate_scenario_runs

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")
st.title("🐾 PawPal+")
st.caption("A daily pet care scheduler.")

APP_ROOT = Path(__file__).resolve().parent

# ── Session state initialisation ──────────────────────────────────────────────
if "owner" not in st.session_state:
    st.session_state["owner"] = None

if "scheduler" not in st.session_state:
    st.session_state["scheduler"] = None

if "reliability_results" not in st.session_state:
    st.session_state["reliability_results"] = None

# ── Section 1: Owner setup ─────────────────────────────────────────────────────
st.header("1. Owner Info")

with st.form("owner_form"):
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Your name", value="Jordan")
        email = st.text_input("Email", value="jordan@email.com")
    with col2:
        available_minutes = st.number_input(
            "Minutes available today", min_value=0, max_value=720, value=120, step=10
        )
    save_owner = st.form_submit_button("Save owner info")

if save_owner:
    if not name.strip():
        st.warning("Please enter your name.")
    elif st.session_state["owner"] is None:
        st.session_state["owner"] = Owner(name.strip(), email.strip(), int(available_minutes))
        st.success(f"Owner '{name}' created.")
    else:
        st.session_state["owner"].update_owner(name.strip(), email.strip(), int(available_minutes))
        st.success(f"Owner info updated.")

if st.session_state["owner"] is None:
    st.info("Save your owner info above to continue.")
    st.stop()

owner: Owner = st.session_state["owner"]

# ── Section 2: Pets ────────────────────────────────────────────────────────────
st.divider()
st.header("2. Your Pets")

with st.form("pet_form"):
    col1, col2, col3 = st.columns(3)
    with col1:
        pet_name = st.text_input("Pet name")
    with col2:
        species = st.selectbox("Species", ["dog", "cat", "other"])
    with col3:
        special_needs = st.text_input("Special needs (optional)")
    add_pet = st.form_submit_button("Add pet")

if add_pet:
    if not pet_name.strip():
        st.warning("Please enter a pet name.")
    else:
        new_pet = Pet(
            name=pet_name.strip(),
            species=species,
            special_needs=special_needs.strip() or None,
        )
        try:
            owner.add_pet(new_pet)
            st.success(f"Added **{pet_name}** ({species}).")
        except ValueError as exc:
            st.warning(str(exc))

if owner.pets:
    for pet in owner.pets:
        col_pn, col_ps = st.columns([3, 5])
        with col_pn:
            st.markdown(f"**{pet.name}** — {pet.species}")
        with col_ps:
            if pet.special_needs:
                st.caption(f"Special needs: {pet.special_needs}")
else:
    st.info("No pets added yet. Add one above.")

# ── Section 3: Tasks ───────────────────────────────────────────────────────────
st.divider()
st.header("3. Tasks")

if not owner.pets:
    st.info("Add a pet first before adding tasks.")
else:
    pet_names = [p.name for p in owner.pets]

    # Keep preferred-time controls outside the form so the checkbox can
    # immediately lock/unlock the time input on click.
    col_pt1, col_pt2 = st.columns([1, 3])
    with col_pt1:
        set_pref_time = st.checkbox("Set preferred time?", key="set_pref_time")
    with col_pt2:
        pref_time_input = st.time_input(
            "Preferred start time",
            value=dtime(8, 0),
            key="pref_time_input",
            disabled=not set_pref_time,
        )

    with st.form("task_form"):
        selected_pet_name = st.selectbox("Assign to pet", pet_names)
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            task_title = st.text_input("Task title", value="Morning walk")
        with col2:
            duration = st.number_input("Duration (min)", min_value=1, max_value=240, value=20)
        with col3:
            priority = st.selectbox("Priority", ["high", "medium", "low"])
        with col4:
            frequency = st.selectbox(
                "Frequency", ["daily", "weekly", "as_needed", "one_time_only"]
            )
        with col5:
            non_negotiable = st.checkbox("Non-negotiable task")

        add_task = st.form_submit_button("Add task")

    if add_task:
        if not task_title.strip():
            st.warning("Please enter a task title.")
        else:
            target_pet = owner.get_pet(selected_pet_name)
            preferred_time = (
                f"{pref_time_input.hour:02d}:{pref_time_input.minute:02d}"
                if set_pref_time
                else None
            )
            try:
                target_pet.add_task(
                    Task(
                        title=task_title.strip(),
                        duration_minutes=int(duration),
                        priority=priority,
                        frequency=frequency,
                        preferred_time=preferred_time,
                        non_negotiable=non_negotiable,
                    )
                )
                st.session_state["scheduler"] = None  # invalidate old schedule
                st.success(f"Added **{task_title}** to {selected_pet_name}.")
            except ValueError as exc:
                st.warning(str(exc))

    # ── Filter controls ───────────────────────────────────────────────────────
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        filter_pet = st.selectbox("Filter by pet", ["All"] + pet_names, key="filter_pet")
    with col_f2:
        filter_status = st.selectbox(
            "Filter by status", ["All", "Pending", "Completed"], key="filter_status"
        )

    # ── Task list with completion checkboxes ──────────────────────────────────
    PRIORITY_BADGE = {"high": "🔴 high", "medium": "🟡 medium", "low": "🟢 low"}

    task_changed = False
    any_shown = False
    total_pending = total_done = 0

    for pet in owner.pets:
        if filter_pet != "All" and pet.name != filter_pet:
            continue

        tasks_to_show = pet.tasks
        if filter_status == "Pending":
            tasks_to_show = [t for t in tasks_to_show if not t.completed]
        elif filter_status == "Completed":
            tasks_to_show = [t for t in tasks_to_show if t.completed]

        if not tasks_to_show:
            continue

        any_shown = True
        st.subheader(f"{pet.name}'s tasks", divider="gray")

        for t in tasks_to_show:
            col_chk, col_info, col_meta = st.columns([1, 5, 2])
            with col_chk:
                checkbox_key = f"done_{pet.name}_{t.title}_{id(t)}"
                new_val = st.checkbox(
                    "done",
                    value=t.completed,
                    key=checkbox_key,
                    label_visibility="collapsed",
                )
            with col_info:
                title_fmt = f"~~{t.title}~~" if t.completed else f"**{t.title}**"
                pref_label = f" | pref. `{t.preferred_time}`" if t.preferred_time else ""
                must_label = " | MUST" if t.non_negotiable else ""
                badge = PRIORITY_BADGE.get(t.priority, t.priority)
                st.markdown(
                    f"{title_fmt} — {t.duration_minutes} min"
                    f" | {badge} | _{t.frequency}_{pref_label}{must_label}"
                )
            with col_meta:
                if t.completed:
                    st.success("Done", icon="✅")
                elif t.frequency == "weekly":
                    last = t.last_done_date or "never"
                    st.caption(f"Last done: {last}")

            if new_val != t.completed:
                if new_val:
                    # complete_and_reschedule marks the task done AND
                    # appends a fresh next-occurrence instance for daily/weekly tasks.
                    pet.complete_and_reschedule(t.title)
                else:
                    t.mark_incomplete()
                task_changed = True

            if t.completed:
                total_done += 1
            else:
                total_pending += 1

    if not any_shown:
        st.info("No tasks match the current filter.")
    else:
        if total_done > 0 and total_pending == 0:
            st.success(f"All {total_done} task(s) completed — great job!")
        elif total_done > 0:
            st.info(f"{total_pending} task(s) pending · {total_done} completed")
        else:
            st.info(f"{total_pending} task(s) pending")

    if task_changed:
        st.session_state["scheduler"] = None
        st.rerun()

# ── Section 4: Generate schedule ──────────────────────────────────────────────
st.divider()
st.header("4. Today's Schedule")

col_time, col_gap = st.columns([2, 3])
with col_time:
    day_start = st.time_input("Schedule starts at", value=dtime(8, 0), key="day_start")
day_start_minutes = day_start.hour * 60 + day_start.minute

if st.button("Generate schedule", type="primary"):
    if not owner.get_all_tasks():
        st.warning("Add at least one task before generating a schedule.")
    else:
        scheduler = Scheduler(owner=owner, day_start_minutes=day_start_minutes)
        scheduler.build_schedule()
        st.session_state["scheduler"] = scheduler

if st.session_state["scheduler"] is not None:
    scheduler: Scheduler = st.session_state["scheduler"]

    if scheduler.scheduled_tasks:
        time_used = sum(t.duration_minutes for t in scheduler.scheduled_tasks)

        # ── Summary metrics ────────────────────────────────────────────────────
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.metric("Tasks scheduled", len(scheduler.scheduled_tasks))
        with col_m2:
            st.metric("Time used", f"{time_used} min")
        with col_m3:
            pct = int(time_used / owner.available_minutes * 100) if owner.available_minutes else 0
            st.metric("Budget used", f"{pct}%")

        budget_ratio = (time_used / owner.available_minutes) if owner.available_minutes else 0
        st.progress(min(budget_ratio, 1.0))

        # ── Sort control — uses Scheduler.sort_by_time() ───────────────────────
        sort_mode = st.radio(
            "Sort schedule by",
            ["Priority (default)", "Preferred time"],
            horizontal=True,
            key="sort_mode",
        )

        # ── Pet filter — uses Scheduler.filter_tasks() ─────────────────────────
        sched_pet_names = sorted({t.pet_name for t in scheduler.scheduled_tasks if t.pet_name})
        filter_sched_pet = st.selectbox(
            "Filter schedule by pet",
            ["All"] + sched_pet_names,
            key="filter_sched_pet",
        )

        # Build display list: start from scheduled tasks, apply pet filter,
        # then sort — both operations delegate to Scheduler methods.
        scheduled_ids = {id(t) for t in scheduler.scheduled_tasks}

        if filter_sched_pet != "All":
            # filter_tasks() searches scheduled_tasks + skipped_tasks;
            # intersect with scheduled_ids to keep only scheduled ones.
            pet_filtered = scheduler.filter_tasks(pet_name=filter_sched_pet)
            display_tasks = [t for t in pet_filtered if id(t) in scheduled_ids]
        else:
            display_tasks = list(scheduler.scheduled_tasks)

        if sort_mode == "Preferred time":
            # sort_by_time() returns all tasks ordered by preferred_time;
            # use its rank to re-order the already-filtered display_tasks.
            time_ranked = {id(t): i for i, t in enumerate(scheduler.sort_by_time())}
            display_tasks = sorted(display_tasks, key=lambda t: time_ranked.get(id(t), 9999))

        # ── Active-view banner ─────────────────────────────────────────────────
        sort_label = "preferred time" if sort_mode == "Preferred time" else "priority"
        filter_label = f"**{filter_sched_pet}**" if filter_sched_pet != "All" else "all pets"
        st.info(
            f"Showing **{len(display_tasks)}** task(s) · sorted by **{sort_label}**"
            f" · filtered to {filter_label}"
        )

        if not display_tasks:
            st.warning(f"No scheduled tasks found for **{filter_sched_pet}**.")
        else:
            # Show "Preferred Time" column only when at least one task has it set.
            has_pref_times = any(t.preferred_time for t in display_tasks)

            PRIORITY_BADGE = {"high": "🔴 high", "medium": "🟡 medium", "low": "🟢 low"}

            rows = []
            for t in display_tasks:
                row = {
                    "Task": t.title,
                    "Pet": t.pet_name or "—",
                    "Start": (
                        Scheduler._format_time(t.scheduled_start)
                        if t.scheduled_start is not None else "—"
                    ),
                    "End": (
                        Scheduler._format_time(t.scheduled_start + t.duration_minutes)
                        if t.scheduled_start is not None else "—"
                    ),
                    "Duration (min)": t.duration_minutes,
                    "Priority": PRIORITY_BADGE.get(t.priority, t.priority),
                    "Frequency": t.frequency,
                }
                if has_pref_times:
                    row["Preferred Time"] = t.preferred_time or "—"
                rows.append(row)

            col_cfg = {
                "Task": st.column_config.TextColumn("Task", width="medium"),
                "Pet": st.column_config.TextColumn("Pet", width="small"),
                "Start": st.column_config.TextColumn("Start", width="small"),
                "End": st.column_config.TextColumn("End", width="small"),
                "Duration (min)": st.column_config.NumberColumn("Duration (min)", width="small"),
                "Priority": st.column_config.TextColumn("Priority", width="small"),
                "Frequency": st.column_config.TextColumn("Frequency", width="small"),
            }
            if has_pref_times:
                col_cfg["Preferred Time"] = st.column_config.TextColumn(
                    "Preferred Time", width="small"
                )

            st.dataframe(rows, use_container_width=True, column_config=col_cfg, hide_index=True)

    else:
        st.error("No tasks could be scheduled within your available time.")

    # ── Conflict warnings — separated by type ─────────────────────────────────
    if scheduler.conflicts:
        # build_schedule() stores both priority inversions and
        # preferred_time window overlaps in scheduler.conflicts.
        priority_conflicts = [c for c in scheduler.conflicts if "was skipped while" in c]
        time_conflicts = [c for c in scheduler.conflicts if "Time conflict:" in c]

        if priority_conflicts:
            with st.expander(
                f"⚠️ {len(priority_conflicts)} priority conflict(s) detected", expanded=True
            ):
                st.caption(
                    "A higher-priority task was skipped while a lower-priority task fit. "
                    "Consider shortening the task or increasing available time."
                )
                for conflict in priority_conflicts:
                    st.warning(conflict)

        if time_conflicts:
            with st.expander(
                f"🕐 {len(time_conflicts)} preferred-time overlap(s) detected", expanded=True
            ):
                st.caption(
                    "These tasks have overlapping preferred time windows. "
                    "Adjust their preferred times to avoid scheduling clashes."
                )
                for conflict in time_conflicts:
                    st.info(conflict)

    if scheduler.skipped_tasks:
        with st.expander(f"⏭️ {len(scheduler.skipped_tasks)} task(s) skipped — not enough time"):
            st.caption("These tasks did not fit within your available time budget.")
            for task in scheduler.skipped_tasks:
                pet_label = f" [{task.pet_name}]" if task.pet_name else ""
                st.warning(
                    f"**{task.title}**{pet_label} — {task.duration_minutes} min"
                    f" ({task.priority} priority · {task.frequency})",
                    icon="⏭️",
                )

    with st.expander("Full plan explanation"):
        st.text(scheduler.explain_plan())

# ── Section 5: AI reliability check ───────────────────────────────────────────
st.divider()
st.header("5. AI Reliability Check")
st.caption("Run reliability checks against your current session's pending tasks.")

col_r1, col_r2 = st.columns(2)
with col_r1:
    repeat_runs = st.number_input(
        "Repeated runs per scenario",
        min_value=1,
        max_value=20,
        value=3,
        step=1,
        key="reliability_repeat_runs",
    )
with col_r2:
    compliance_threshold = st.slider(
        "Compliance threshold",
        min_value=0.0,
        max_value=1.0,
        value=0.95,
        step=0.01,
        key="reliability_threshold",
    )

pending_tasks_for_eval = [
    (pet, task)
    for pet in owner.pets
    for task in pet.tasks
    if not task.completed
]
if not pending_tasks_for_eval:
    st.info("Add at least one pending task in the app to run reliability checks.")

if st.button(
    "Run reliability check",
    key="run_reliability_button",
    disabled=not pending_tasks_for_eval,
):
    try:
        with st.spinner("Running reliability checks..."):
            scenario_tasks = []
            for idx, (pet, task) in enumerate(pending_tasks_for_eval, start=1):
                scenario_tasks.append(
                    ScenarioTask(
                        task_id=f"session_task_{idx}",
                        pet_name=pet.name,
                        title=task.title,
                        duration_minutes=task.duration_minutes,
                        priority=task.priority,
                        frequency=task.frequency,
                        preferred_time=task.preferred_time,
                    )
                )

            scenarios = [
                ScenarioInput(
                    scenario_id="current_session",
                    owner_name=owner.name,
                    owner_email=owner.email,
                    available_minutes=owner.available_minutes,
                    day_start_minutes=day_start_minutes,
                    tasks=scenario_tasks,
                )
            ]
            adapter = AISchedulerAdapter()
            rows = []
            for scenario in scenarios:
                outputs = [adapter.generate_schedule(scenario) for _ in range(int(repeat_runs))]
                evaluation = evaluate_scenario_runs(scenario, outputs)
                rows.append(evaluation.to_dict())

            agg_compliance = sum(float(r["compliance_rate"]) for r in rows) / len(rows)
            agg_consistency = sum(float(r["consistency_rate"]) for r in rows) / len(rows)
            overall_pass = all(bool(r["passed"]) for r in rows) and agg_compliance >= float(
                compliance_threshold
            )
            st.session_state["reliability_results"] = {
                "rows": rows,
                "aggregate_compliance": agg_compliance,
                "aggregate_consistency": agg_consistency,
                "overall_pass": overall_pass,
                "threshold": float(compliance_threshold),
                "last_run_utc": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%SZ"),
            }
        st.success("Reliability check completed.")
    except Exception as exc:
        st.error(f"Reliability check failed: {exc}")

results = st.session_state["reliability_results"]
if results:
    st.caption(f"Last run (UTC): {results.get('last_run_utc', 'unknown')}")
    if results["overall_pass"]:
        st.success(
            "PASS "
            f"(compliance={results['aggregate_compliance']:.2%}, "
            f"consistency={results['aggregate_consistency']:.2%})"
        )
    else:
        st.error(
            "FAIL "
            f"(compliance={results['aggregate_compliance']:.2%}, "
            f"threshold={results['threshold']:.2%})"
        )

    st.dataframe(
        [
            {
                "Scenario": row["scenario_id"],
                "Pass": row["passed"],
                "Compliance": f"{row['compliance_rate']:.2%}",
                "Consistency": f"{row['consistency_rate']:.2%}",
                "Scheduled": row["scheduled_count"],
                "Skipped": row["skipped_count"],
            }
            for row in results["rows"]
        ],
        use_container_width=True,
        hide_index=True,
    )

    with st.expander("Per-scenario rule checks"):
        for row in results["rows"]:
            st.markdown(f"**{row['scenario_id']}**")
            for check in row["checks"]:
                label = "PASS" if check["passed"] else "FAIL"
                st.write(f"- {check['name']}: {label} ({check['details']})")

    if st.button("Export latest reliability report", key="export_reliability_report_button"):
        try:
            timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            output_dir = APP_ROOT / "assets" / "curr_project_assets" / "reports"
            output_dir.mkdir(parents=True, exist_ok=True)
            json_path = output_dir / f"reliability_report_{timestamp}.json"
            md_path = output_dir / f"reliability_report_{timestamp}.md"

            payload = {
                "generated_at_utc": timestamp,
                "repeat_runs": int(repeat_runs),
                "compliance_threshold": float(results["threshold"]),
                "overall_pass": bool(results["overall_pass"]),
                "aggregate_compliance_rate": round(float(results["aggregate_compliance"]), 4),
                "aggregate_consistency_rate": round(float(results["aggregate_consistency"]), 4),
                "scenario_results": results["rows"],
            }
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)

            markdown_lines = [
                "# PawPal+ Reliability Report",
                "",
                f"- Overall pass: **{'PASS' if payload['overall_pass'] else 'FAIL'}**",
                f"- Aggregate compliance rate: **{payload['aggregate_compliance_rate']:.2%}**",
                f"- Aggregate consistency rate: **{payload['aggregate_consistency_rate']:.2%}**",
                "",
                "## Scenario Results",
                "",
            ]
            for row in results["rows"]:
                markdown_lines.extend(
                    [
                        f"### {row['scenario_id']}",
                        f"- Pass: {'PASS' if row['passed'] else 'FAIL'}",
                        f"- Compliance: {row['compliance_rate']:.2%}",
                        f"- Consistency: {row['consistency_rate']:.2%}",
                        f"- Scheduled: {row['scheduled_count']}, Skipped: {row['skipped_count']}",
                        "- Checks:",
                    ]
                )
                for check in row["checks"]:
                    check_label = "PASS" if check["passed"] else "FAIL"
                    markdown_lines.append(
                        f"  - {check['name']}: {check_label} ({check['details']})"
                    )
                markdown_lines.append("")

            with open(md_path, "w", encoding="utf-8") as f:
                f.write("\n".join(markdown_lines))

            st.success(f"Report exported to `{json_path}` and `{md_path}`")
        except Exception as exc:
            st.error(f"Export failed: {exc}")
