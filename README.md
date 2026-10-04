# Xenit HR App

`xenit_hr_app` is an Odoo 18 umbrella addon named **HR**.

It does two things:

1. Installs the validated HR module set through manifest dependencies.
2. Consolidates HR app roots and HR add-on menus under one top-level **HR** app.

The addon only changes `ir.ui.menu` placement and the HR root menu label. It does
not change models, fields, views, access rules, record rules, workflows, or
business logic.

## Expected Top-Level App

After installation, the only HR top-level app should be:

- `HR`

Inside `HR`, menus are grouped as:

- `People`
- `Time`
- `Payroll & Expenses`
- `Talent`
- `Documents & Compliance`
- `Reporting`
- `Configuration`
- `Other HR`

## Safety

On install or rebuild, the addon stores original menu parent/sequence/name data
in a SQL backup table before moving any menu. Rebuilding is idempotent.

On uninstall, it restores backed-up menu locations and names.

## Compatibility Plan

This addon is intentionally a meta/umbrella app:

- `__manifest__.py` lists the validated HR dependency stack, including the OCA,
  Open HRMS, Odoo, and Xenit HR addons currently present in the Odoo module
  registry.
- Odoo's native dependency resolver installs those modules in dependency order.
- The post-init hook only updates `ir.ui.menu` records. It does not modify HR
  models, fields, views, record rules, security groups, workflows, or reports.
- Every moved menu is backed up before the first write, so the original tree can
  be restored on uninstall.
- Uninstallable modules are deliberately excluded. Extra uninstalled HR addons
  should be added to `depends` only after they install cleanly on a test database.

The practical guarantee is that this addon will not introduce business-logic
incompatibilities of its own. Any incompatibility between HR addons remains under
Odoo's normal module installation checks, which run before the unified menu is
rebuilt.

## Install

Put this repository, or just the `xenit_hr_app` directory, on the Odoo
`addons_path`, update the apps list, and install **HR**.

All dependencies listed in `__manifest__.py` must also be available on the
server's `addons_path`.

## Maintenance

After installing new HR addons later, go to:

`HR -> Configuration -> Rebuild HR App Menu`

That reruns the consolidation and validation.
