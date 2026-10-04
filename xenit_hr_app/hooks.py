import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

BACKUP_TABLE = "xenit_hr_app_menu_backup"
HR_ROOT_XMLID = "hr.menu_hr_root"

CATEGORY_XMLIDS = {
    "people": "xenit_hr_app.menu_hr_people",
    "time": "xenit_hr_app.menu_hr_time",
    "payroll": "xenit_hr_app.menu_hr_payroll_expenses",
    "talent": "xenit_hr_app.menu_hr_talent",
    "documents": "xenit_hr_app.menu_hr_documents_compliance",
    "reporting": "hr.hr_menu_hr_reports",
    "configuration": "hr.menu_human_resources_configuration",
    "other": "xenit_hr_app.menu_hr_other",
}

HR_KEYWORDS = (
    "hr",
    "employee",
    "payroll",
    "attendance",
    "timesheet",
    "time_off",
    "holiday",
    "holidays",
    "leave",
    "recruit",
    "shift",
    "appraisal",
    "resignation",
    "disciplinary",
    "orientation",
    "custody",
    "document_approval",
    "medical_examination",
)

MENU_CATEGORY_BY_XMLID = {
    # People
    "hr.menu_hr_main": "people",
    "hr.menu_hr_employee_payroll": "people",
    "hr.menu_hr_employee": "people",
    "hr.menu_hr_department_kanban": "people",
    "hr_contract.menu_hr_employee_contracts": "people",
    "hr_employee_transfer.employee_transfer_menu_create_transfer": "people",
    "hr_employee_updation.hr_management_menu": "people",
    "hr_custody.hr_management_menu": "people",
    # Time
    "hr_attendance.menu_hr_attendance_root": "time",
    "hr_holidays.menu_hr_holidays_root": "time",
    "hr_shift.shift_planning_root": "time",
    "hr_timesheet.timesheet_menu_root": "time",
    # Payroll and expenses
    "hr_expense.menu_hr_expense_root": "payroll",
    "hr_payroll_community.menu_hr_payroll_community_root": "payroll",
    "payroll.payroll_menu_root": "payroll",
    "hr_payroll_document.payrolls_management_wizard_menu_action": "payroll",
    "hr_payroll_document.payrolls_menu_action": "payroll",
    # Talent
    "hr_recruitment.menu_hr_recruitment_root": "talent",
    "oh_appraisal.hr_appraisal_menu_root": "talent",
    "hr_course.menu_hr_course": "talent",
    "hr_employee_language.menu_open_view_hr_employee_language_form": "talent",
    "employee_orientation.employee_orientation_menu_root": "talent",
    "employee_orientation.menu_employee_training_child": "talent",
    # Documents and compliance
    "document_approval.document_approval_menu_root": "documents",
    "oh_employee_documents_expiry.hr_document_menu": "documents",
    "hr_reward_warning.hr_announcement_menu_root": "documents",
    "hr_reminder.hr_reminder_menu": "documents",
    "hr_resignation.hr_resignation_menu_root": "documents",
    "hr_company_policy.hr_resignation_menu_root": "documents",
    "hr_personal_equipment_request.hr_personal_equipment_menu": "documents",
    "hr_disciplinary_tracking.disciplinary_action": "documents",
    "hr_employee_medical_examination.hr_employee_medical_examination_menu": "documents",
    "xenit_hr_forms_workflow.menu_xenit_hr_forms_root": "documents",
    # Reporting
    "hr_employee_updation.employee_report_menu": "reporting",
    "hr_custody.employee_report_menu": "reporting",
    "hr.menu_hr_reporting_timesheet": "reporting",
}


def post_init_hook(env):
    rebuild_unified_hr_app(env)


def uninstall_hook(env):
    restore_original_menu_tree(env)


def _ensure_backup_table(env):
    env.cr.execute(
        """
        CREATE TABLE IF NOT EXISTS xenit_hr_app_menu_backup (
            menu_id INTEGER PRIMARY KEY,
            original_parent_id INTEGER,
            original_sequence INTEGER,
            original_name VARCHAR,
            backup_date TIMESTAMP WITHOUT TIME ZONE DEFAULT now()
        )
        """
    )


def _backup_menu(env, menu):
    _ensure_backup_table(env)
    parent_id = menu.parent_id.id or None
    env.cr.execute(
        f"""
        INSERT INTO {BACKUP_TABLE}
            (menu_id, original_parent_id, original_sequence, original_name)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (menu_id) DO NOTHING
        """,
        (menu.id, parent_id, menu.sequence, menu.name),
    )


def _get_xmlids_by_menu(env, menu_ids):
    if not menu_ids:
        return {}
    data = env["ir.model.data"].sudo().search(
        [("model", "=", "ir.ui.menu"), ("res_id", "in", list(menu_ids))]
    )
    result = {menu_id: [] for menu_id in menu_ids}
    for row in data:
        result.setdefault(row.res_id, []).append(f"{row.module}.{row.name}")
    return result


def _is_hr_xmlid(xmlid):
    module = xmlid.split(".", 1)[0].lower()
    full = xmlid.lower()
    return (
        module == "payroll"
        or module.startswith("hr")
        or module.startswith("oh_")
        or module.startswith("ohrms_")
        or any(keyword in full for keyword in HR_KEYWORDS)
    )


def _category_from_xmlids(xmlids):
    for xmlid in xmlids:
        category = MENU_CATEGORY_BY_XMLID.get(xmlid)
        if category:
            return category
    text = " ".join(xmlids).lower()
    if any(word in text for word in ("attendance", "timesheet", "holiday", "holidays", "leave", "shift")):
        return "time"
    if any(word in text for word in ("payroll", "expense")):
        return "payroll"
    if any(word in text for word in ("recruit", "appraisal", "course", "orientation", "training", "language")):
        return "talent"
    if any(
        word in text
        for word in (
            "document",
            "approval",
            "resignation",
            "disciplinary",
            "reminder",
            "announcement",
            "medical",
            "equipment",
            "custody",
        )
    ):
        return "documents"
    if "report" in text:
        return "reporting"
    return "other"


def _category_menus(env):
    menus = {}
    for key, xmlid in CATEGORY_XMLIDS.items():
        menu = env.ref(xmlid, raise_if_not_found=False)
        if menu:
            menus[key] = menu.sudo()
    return menus


def _is_under(menu, ancestor):
    current = menu.parent_id
    while current:
        if current == ancestor:
            return True
        current = current.parent_id
    return False


def _candidate_menus(env, hr_root, category_ids):
    Menu = env["ir.ui.menu"].sudo()
    candidates = Menu.browse()

    for xmlid in MENU_CATEGORY_BY_XMLID:
        menu = env.ref(xmlid, raise_if_not_found=False)
        if menu and menu._name == "ir.ui.menu":
            candidates |= menu.sudo()

    menus = Menu.search([("active", "=", True)])
    xmlids_by_menu = _get_xmlids_by_menu(env, menus.ids)

    legacy_bucket_ids = Menu.search(
        [
            ("parent_id", "=", hr_root.id),
            ("name", "in", ("More", "Other HR")),
            ("id", "not in", list(category_ids)),
        ]
    ).ids

    for menu in menus:
        if menu.id == hr_root.id or menu.id in category_ids:
            continue
        xmlids = xmlids_by_menu.get(menu.id, [])
        if not any(_is_hr_xmlid(xmlid) for xmlid in xmlids):
            continue
        root_like = (
            not menu.parent_id
            or menu.parent_id == hr_root
            or menu.parent_id.id in legacy_bucket_ids
        )
        if root_like:
            candidates |= menu

    return candidates


def rebuild_unified_hr_app(env):
    env = env(su=True) if isinstance(env, api.Environment) else api.Environment(env, SUPERUSER_ID, {})
    Menu = env["ir.ui.menu"].sudo()
    hr_root = env.ref(HR_ROOT_XMLID).sudo()
    categories = _category_menus(env)
    category_ids = {menu.id for menu in categories.values()}

    _backup_menu(env, hr_root)
    hr_root.write({"name": "HR"})

    for key, menu in categories.items():
        _backup_menu(env, menu)
        menu.write({"parent_id": hr_root.id})
    categories["people"].write({"sequence": 10})
    categories["time"].write({"sequence": 20})
    categories["payroll"].write({"sequence": 30})
    categories["talent"].write({"sequence": 40})
    categories["documents"].write({"sequence": 50})
    categories["reporting"].write({"sequence": 80})
    categories["configuration"].write({"sequence": 90})
    categories["other"].write({"sequence": 100})

    candidates = _candidate_menus(env, hr_root, category_ids)
    xmlids_by_menu = _get_xmlids_by_menu(env, candidates.ids)
    moved = []
    skipped = []

    for menu in candidates.sorted(key=lambda item: (item.sequence, item.id)):
        if menu.id == hr_root.id or menu.id in category_ids:
            continue
        target_key = _category_from_xmlids(xmlids_by_menu.get(menu.id, []))
        target = categories.get(target_key) or categories["other"]
        if menu == target or _is_under(target, menu):
            skipped.append(menu.display_name)
            continue
        _backup_menu(env, menu)
        menu.write({"parent_id": target.id, "sequence": len(target.child_id) + 10})
        moved.append(menu.display_name)

    _deactivate_empty_legacy_buckets(env, hr_root, category_ids)
    env.cr.commit()
    report = validate_unified_hr_app(env)
    report.update({"moved": moved, "skipped": skipped})
    _logger.info("Unified HR app rebuild complete: %s", report)
    return report


def _deactivate_empty_legacy_buckets(env, hr_root, category_ids):
    legacy_buckets = env["ir.ui.menu"].sudo().search(
        [
            ("parent_id", "=", hr_root.id),
            ("name", "in", ("More", "Other HR")),
            ("id", "not in", list(category_ids)),
        ]
    )
    for menu in legacy_buckets:
        if not menu.child_id:
            _backup_menu(env, menu)
            menu.write({"active": False})


def validate_unified_hr_app(env):
    env = env(su=True) if isinstance(env, api.Environment) else api.Environment(env, SUPERUSER_ID, {})
    Menu = env["ir.ui.menu"].sudo()
    hr_root = env.ref(HR_ROOT_XMLID).sudo()
    top_menus = Menu.search([("parent_id", "=", False), ("active", "=", True)])
    xmlids_by_menu = _get_xmlids_by_menu(env, top_menus.ids)
    remaining = []
    for menu in top_menus:
        if menu == hr_root:
            continue
        xmlids = xmlids_by_menu.get(menu.id, [])
        if any(_is_hr_xmlid(xmlid) for xmlid in xmlids):
            remaining.append(f"{menu.display_name} ({', '.join(xmlids)})")
    return {"remaining_top_hr_like": remaining}


def restore_original_menu_tree(env):
    env = env(su=True) if isinstance(env, api.Environment) else api.Environment(env, SUPERUSER_ID, {})
    _ensure_backup_table(env)
    Menu = env["ir.ui.menu"].sudo()
    env.cr.execute(
        f"""
        SELECT menu_id, original_parent_id, original_sequence, original_name
          FROM {BACKUP_TABLE}
         ORDER BY menu_id
        """
    )
    rows = env.cr.fetchall()
    for menu_id, parent_id, sequence, name in rows:
        menu = Menu.browse(menu_id).exists()
        if not menu:
            continue
        values = {"sequence": sequence}
        if name:
            values["name"] = name
        if parent_id and Menu.browse(parent_id).exists():
            values["parent_id"] = parent_id
        else:
            values["parent_id"] = False
        menu.write(values)
    env.cr.execute(f"DROP TABLE IF EXISTS {BACKUP_TABLE}")
    env.cr.commit()

