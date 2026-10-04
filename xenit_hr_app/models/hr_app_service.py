from odoo import models

from ..hooks import rebuild_unified_hr_app, validate_unified_hr_app


class XenitHrAppService(models.AbstractModel):
    _name = "xenit.hr.app.service"
    _description = "Xenit HR App Menu Service"

    def rebuild_unified_hr_app(self):
        report = rebuild_unified_hr_app(self.env)
        message = "HR app menu rebuilt. Remaining HR-like top-level menus: %s" % (
            ", ".join(report["remaining_top_hr_like"]) or "none"
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "HR",
                "message": message,
                "type": "success" if not report["remaining_top_hr_like"] else "warning",
                "sticky": bool(report["remaining_top_hr_like"]),
            },
        }

    def validate_unified_hr_app(self):
        return validate_unified_hr_app(self.env)

