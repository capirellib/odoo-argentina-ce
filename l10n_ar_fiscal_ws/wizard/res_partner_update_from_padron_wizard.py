import logging
from ast import literal_eval

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResPartnerUpdateFromPadronField(models.TransientModel):
    _name = "res.partner.update.from.padron.field"
    _description = "ARCA A5 Census Field"

    wizard_id = fields.Many2one(
        "res.partner.update.from.padron.wizard",
    )
    field = fields.Char("Field Name", help="Technical field name")
    field_label = fields.Char(compute="_compute_field_label", store=False)
    old_value = fields.Char()
    new_value = fields.Char()
    real_value = fields.Char(help="Actual value to be written (ID for Many2one, etc)")

    @api.depends("field")
    def _compute_field_label(self):
        """Obtiene el label legible del campo técnico sin N+1 consultas."""
        field_names = {rec.field for rec in self if rec.field}
        descriptions_by_name = {}
        if field_names:
            fields_data = self.env["ir.model.fields"].search_read(
                [("model", "=", "res.partner"), ("name", "in", list(field_names))],
                ["name", "field_description"],
            )
            descriptions_by_name = {fd["name"]: fd["field_description"] for fd in fields_data if fd.get("name")}
        for rec in self:
            if rec.field:
                rec.field_label = descriptions_by_name.get(rec.field, rec.field)
            else:
                rec.field_label = ""


class ResPartnerUpdateFromPadronWizard(models.TransientModel):
    _name = "res.partner.update.from.padron.wizard"
    _description = "ARCA A5 Census Wizard"

    @api.model
    def get_partners(self):
        # TODO deberiamos buscar de otro manera estos partners
        domain = [
            ("vat", "!=", False),
            ("l10n_latam_identification_type_id.l10n_ar_afip_code", "=", 80),
        ]
        active_ids = self.env.context.get("active_ids", [])
        if active_ids:
            domain.append(("id", "in", active_ids))
        return self.env["res.partner"].search(domain)

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        context = self.env.context
        if context.get("active_model") == "res.partner" and context.get("active_ids"):
            partners = self.get_partners()
            if not partners:
                raise UserError(_("No se encontró ningún partner con CUIT para actualizar"))
            elif len(partners) == 1:
                res["state"] = "selection"
                res["partner_id"] = partners[0].id
        return res

    @api.model
    def _get_domain(self):
        fields_names = [
            "name",
            "street",
            "city",
            "zip",
            "state_id",
            "country_id",
            "l10n_ar_afip_responsibility_type_id",
            "imp_iva_padron",
            "imp_ganancias_padron",
            "last_update_census",
        ]
        return [
            ("model", "=", "res.partner"),
            ("name", "in", fields_names),
        ]

    @api.model
    def _get_default_title_case(self):
        parameter = (
            self.env["ir.config_parameter"]
            .sudo()  # OCA: Justificado. Requerido para acceso a parámetros globales multi-compañía.
            .get_param("use_title_case_on_padron_afip")
        )
        if parameter == "False" or parameter == "0":
            return False
        return True

    @api.model
    def get_fields(self):
        return self.env["ir.model.fields"].search(self._get_domain())

    state = fields.Selection(
        [("option", "Option"), ("selection", "Selection"), ("finished", "Finished")],
        readonly=True,
        required=True,
        default="option",
    )
    field_ids = fields.One2many(
        "res.partner.update.from.padron.field",
        "wizard_id",
        string="Fields",
    )
    partner_ids = fields.Many2many(
        "res.partner",
        "partner_update_from_padron_rel",
        "update_id",
        "partner_id",
        string="Partners",
        default=get_partners,
    )
    partner_id = fields.Many2one(
        "res.partner",
        readonly=True,
    )
    update_constancia = fields.Boolean(
        default=True,
    )
    title_case = fields.Boolean(
        help="Converts retreived text fields to Title Case.",
        default=_get_default_title_case,
    )
    field_to_update_ids = fields.Many2many(
        "ir.model.fields",
        "res_partner_update_fields",
        "update_id",
        "field_id",
        string="Fields To Update",
        help="Only this fields are going to be retrived and updated",
        default=get_fields,
        domain=_get_domain,
        required=True,
    )
    xml_request = fields.Text(string="XML Enviado", readonly=True, help="XML enviado a ARCA en la última consulta")
    xml_response = fields.Text(
        string="XML Recibido", readonly=True, help="XML recibido desde ARCA en la última consulta"
    )
    afip_error = fields.Text(string="Error de ARCA", readonly=True, help="Error devuelto por ARCA en la consulta")
    has_afip_error = fields.Boolean(
        string="Tiene Error ARCA", readonly=True, help="Indica si hubo un error específico de ARCA"
    )

    @api.onchange("partner_id")
    def change_partner(self):
        """Obtiene datos de ARCA y genera la comparación de campos"""
        self.ensure_one()
        self.field_ids = [(5, 0, 0)]  # Limpiar registros existentes

        # Limpiar errores previos
        self.afip_error = False
        self.has_afip_error = False
        self.xml_request = ""
        self.xml_response = ""

        partner = self.partner_id

        if not partner:
            return

        try:
            # Obtener datos desde AFIP
            partner_vals = partner.get_data_from_padron_arca_safe()

            # Verificar si hubo error de AFIP
            if partner_vals.get("afip_error"):
                self.afip_error = partner_vals["afip_error"]
                self.has_afip_error = True
                self.xml_request = partner_vals.get("xml_request", "")
                self.xml_response = partner_vals.get("xml_response", "")
                return

            # Guardar XMLs para debugging
            self.xml_request = partner_vals.get("xml_request", "")
            self.xml_response = partner_vals.get("xml_response", "")

            lines = []
            # Excluir campos XML y de metadatos internos
            excluded_fields = {"xml_request", "xml_response", "afip_error"}

            # Filtrar por campos seleccionados por el usuario
            selected_field_names = set(self.field_to_update_ids.mapped("name"))

            for key, new_value in partner_vals.items():
                # --- OCA: Solo mostrar y actualizar campos seleccionados por el usuario y definidos en el modelo ---
                if key in excluded_fields:
                    continue
                if selected_field_names and key not in selected_field_names:
                    continue
                if not hasattr(partner, key) or key not in partner._fields:
                    continue

                field_def = partner._fields[key]

                # Obtener valor actual del partner
                try:
                    old_value = partner[key]
                except Exception:
                    old_value = None

                # Aplicar title case si corresponde
                if self.title_case and key in ("name", "city", "street") and new_value:
                    if isinstance(new_value, str):
                        new_value = new_value.title()

                # --- COMPARACIÓN INTELIGENTE (OCA/Rendimiento) ---
                # Evitar mostrar cambios si el valor es el mismo
                is_changed = False
                if field_def.type == "many2one":
                    # Comparar IDs
                    old_id = old_value.id if old_value else None
                    try:
                        new_id = int(new_value) if new_value else None
                    except (ValueError, TypeError):
                        new_id = None
                    is_changed = old_id != new_id
                elif field_def.type in ("many2many", "one2many"):
                    # Comparar sets de IDs
                    old_ids = set(old_value.ids) if old_value else set()
                    try:
                        new_ids = set(literal_eval(new_value)) if new_value else set()
                    except Exception:
                        new_ids = set()
                    is_changed = old_ids != new_ids
                elif field_def.type == "boolean":
                    # Normalizar booleanos (S/N -> True/False)
                    norm_new = True if str(new_value).upper() in ("S", "AC", "1", "TRUE") else False
                    is_changed = bool(old_value) != norm_new
                else:
                    # Comparación genérica (como strings para visualización)
                    is_changed = str(old_value or "") != str(new_value or "")

                if not is_changed:
                    continue

                # Formatear valores para mostrar
                # OCA: Manejo explícito de valores falsy (0, False)
                def format_display(val, ftype):
                    if val is False:
                        return "False"
                    if val is None:
                        return ""
                    if ftype == "many2one":
                        return val.display_name if val else ""
                    return str(val)

                if field_def.type == "many2one":
                    old_value_display = format_display(old_value, "many2one")
                    if new_value:
                        try:
                            comodel = field_def.comodel_name
                            new_record = self.env[comodel].browse(int(new_value))
                            new_value_display = new_record.display_name if new_record.exists() else str(new_value)
                        except (ValueError, TypeError):
                            new_value_display = str(new_value)
                    else:
                        new_value_display = ""
                elif field_def.type in ("many2many", "one2many"):
                    old_value_display = str(old_value.ids) if old_value else "[]"
                    new_value_display = str(new_value) if new_value else "[]"
                else:
                    old_value_display = format_display(old_value, field_def.type)
                    new_value_display = format_display(new_value, field_def.type)

                # Agregar línea al wizard
                line_vals = {
                    "wizard_id": self.id,
                    "field": key,
                    "old_value": old_value_display,
                    "new_value": new_value_display,
                    "real_value": str(new_value) if new_value is not None else "",
                }
                lines.append((0, 0, line_vals))

            self.field_ids = lines

        except Exception as e:
            _logger.error("Error al obtener datos de AFIP para %s: %s", partner.name, e, exc_info=True)
            raise

    def _update(self):
        """Aplica los cambios seleccionados al partner"""
        self.ensure_one()

        if not self.field_ids:
            return {"type": "ir.actions.act_window_close"}

        # Construir diccionario de valores a actualizar desde los field_ids
        vals = {}

        for field_line in self.field_ids:
            # Obtener definición de campo en res.partner para casting de tipos
            partner_field = self.partner_id._fields.get(field_name)
            if not partner_field:
                _logger.warning("Campo '%s' no existe en res.partner, se omite", field_name)
                continue

            ftype = partner_field.type
            real_val = field_line.real_value

            # Aplicar casting de tipos y manejar relacionales
            if ftype in ("many2many", "one2many"):
                if real_val:
                    try:
                        ids_list = literal_eval(real_val)
                        vals[field_name] = [(6, 0, ids_list)]
                    except Exception:
                        vals[field_name] = [(6, 0, [])]
            elif ftype == "many2one":
                if real_val:
                    try:
                        vals[field_name] = int(real_val)
                    except (ValueError, TypeError):
                        # Fallback por nombre
                        comodel = partner_field.comodel_name
                        record = self.env[comodel].search([("display_name", "ilike", real_val)], limit=1)
                        vals[field_name] = record.id if record else False
                else:
                    vals[field_name] = False
            elif ftype == "boolean":
                # Normalizar booleanos (S, AC, True, TRUE -> True)
                vals[field_name] = str(real_val).upper() in ("S", "AC", "1", "TRUE") if real_val else False
            elif ftype in ("integer",):
                vals[field_name] = int(real_val) if real_val else 0
            elif ftype in ("float", "monetary"):
                vals[field_name] = float(real_val) if real_val else 0.0
            else:
                # Char, Text, Selection
                final_val = real_val if real_val is not None else new_val
                if self.title_case and field_name in ("name", "city", "street") and final_val:
                    final_val = final_val.title()
                vals[field_name] = final_val

        if vals:
            # Filtrar campos que no existen en res.partner para evitar KeyError
            partner_fields = self.env["res.partner"]._fields
            invalid_fields = [f for f in vals if f not in partner_fields]
            for f in invalid_fields:
                _logger.warning(
                    "Campo '%s' no existe en res.partner, se omite de la escritura",
                    f,
                )
            vals = {k: v for k, v in vals.items() if k in partner_fields}

        if vals:
            self.partner_id.write(vals)

            # Retornar acción para cerrar wizard y recargar el partner
            return {
                "type": "ir.actions.act_window_close",
                "infos": {"partner_updated": True, "partner_id": self.partner_id.id},
            }
        else:
            return {"type": "ir.actions.act_window_close"}

    def automatic_process_cb(self):
        """Actualiza todos los partners en un solo lote para evitar N+1 de red.
        Respeta la selección de campos del usuario en field_to_update_ids."""
        self.ensure_one()
        if self.partner_ids:
            # Usar el método masivo del modelo que procesa en lotes de 100
            # Pasamos field_to_update_ids para que solo actualice lo seleccionado
            return self.partner_ids.update_multiple_from_padron_arca(field_to_update_ids=self.field_to_update_ids)

        self.write({"state": "finished"})
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def update_selection(self):
        self.ensure_one()
        if not self.field_ids:
            self.write({"state": "finished"})
            return {
                "type": "ir.actions.act_window",
                "res_model": self._name,
                "res_id": self.id,
                "view_mode": "form",
                "target": "new",
            }
        self._update()
        return self.next_cb()

    def next_cb(self):
        """ """
        self.ensure_one()
        if self.partner_id:
            self.write({"partner_ids": [(3, self.partner_id.id, False)]})
        return self._next_screen()

    def _next_screen(self):
        self.ensure_one()
        values = {}
        if self.partner_ids:
            # in this case, we try to find the next record.
            partner = self.partner_ids[0]
            values.update(
                {
                    "partner_id": partner.id,
                    "state": "selection",
                }
            )
        else:
            values.update(
                {
                    "state": "finished",
                }
            )

        self.write(values)
        # because field is not changed, view is distroyed and reopen, on change
        # is not called an we call it manually
        self.change_partner()
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def start_process_cb(self):
        """
        Start the process.
        """
        self.ensure_one()
        return self._next_screen()
