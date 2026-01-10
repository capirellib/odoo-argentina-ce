##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import _, api, fields, models
from odoo.exceptions import UserError

import base64
import logging
from ..lib import crypto_utils

_logger = logging.getLogger(__name__)


class AfipwsCertificate(models.Model):
    _name = "afipws.certificate"
    _description = "afipws.certificate"
    _rec_name = "alias_id"

    alias_id = fields.Many2one(
        "afipws.certificate_alias",
        ondelete="cascade",
        string="Certificate Alias",
        required=True,
        auto_join=True,
        index=True,
    )
    csr = fields.Text(
        "Request Certificate",
        readonly=True,
        help="Certificate Request in PEM format.",
    )
    crt = fields.Text(
        "Certificate",
        readonly=True,
        help="Certificate in PEM format.",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("cancel", "Cancelled"),
        ],
        index=True,
        readonly=True,
        default="draft",
        help="* The 'Draft' state is used when a user is creating a new pair "
        "key. Warning: everybody can see the key."
        "\n* The 'Confirmed' state is used when a certificate is valid."
        "\n* The 'Canceled' state is used when the key is not more used. You "
        "cant use this key again.",
    )
    request_file = fields.Binary(
        "Download Signed Certificate Request",
        compute="_compute_request_file",
        readonly=True,
    )
    request_filename = fields.Char(
        "Filename",
        readonly=True,
        compute="_compute_request_file",
    )
    
    # Campos informativos del certificado
    cert_valid_from = fields.Datetime(
        string="Válido desde",
        compute="_compute_cert_info",
        store=False,
        help="Fecha desde la cual el certificado es válido"
    )
    cert_valid_to = fields.Datetime(
        string="Válido hasta",
        compute="_compute_cert_info",
        store=False,
        help="Fecha de vencimiento del certificado"
    )
    cert_subject = fields.Char(
        string="Subject (DN)",
        compute="_compute_cert_info",
        store=False,
        help="Distinguished Name del sujeto del certificado"
    )
    cert_issuer = fields.Char(
        string="Emisor",
        compute="_compute_cert_info",
        store=False,
        help="Entidad que emitió el certificado"
    )
    cert_serial_number = fields.Char(
        string="Número de Serie",
        compute="_compute_cert_info",
        store=False,
        help="Número de serie del certificado"
    )
    cert_is_expired = fields.Boolean(
        string="Certificado Vencido",
        compute="_compute_cert_info",
        store=False,
        help="Indica si el certificado está vencido"
    )
    cert_days_to_expire = fields.Integer(
        string="Días para vencer",
        compute="_compute_cert_info",
        store=False,
        help="Cantidad de días hasta que expire el certificado"
    )

    @api.depends("csr")
    def _compute_request_file(self):
        for rec in self:
            rec.request_filename = "request.csr"
            if rec.csr:
                rec.request_file = base64.encodebytes(self.csr.encode("utf-8"))
            else:
                rec.request_file = False

    @api.depends('crt')
    def _compute_cert_info(self):
        """Extraer información del certificado X.509"""
        from datetime import datetime, timezone
        
        for record in self:
            if not record.crt:
                record.cert_valid_from = False
                record.cert_valid_to = False
                record.cert_subject = False
                record.cert_issuer = False
                record.cert_serial_number = False
                record.cert_is_expired = False
                record.cert_days_to_expire = 0
                continue
            
            try:
                cert = record.get_certificate()
                
                if not cert:
                    record.cert_valid_from = False
                    record.cert_valid_to = False
                    record.cert_subject = False
                    record.cert_issuer = False
                    record.cert_serial_number = False
                    record.cert_is_expired = False
                    record.cert_days_to_expire = 0
                    continue
                
                # Fechas de validez
                try:
                    record.cert_valid_from = cert.not_valid_before_utc
                    record.cert_valid_to = cert.not_valid_after_utc
                    now = datetime.now(timezone.utc)
                    record.cert_is_expired = cert.not_valid_after_utc < now
                    days_diff = (cert.not_valid_after_utc - now).days
                    record.cert_days_to_expire = days_diff if days_diff > 0 else 0
                except AttributeError:
                    # Versiones antiguas de cryptography
                    record.cert_valid_from = cert.not_valid_before.replace(tzinfo=timezone.utc)
                    record.cert_valid_to = cert.not_valid_after.replace(tzinfo=timezone.utc)
                    now = datetime.now(timezone.utc)
                    record.cert_is_expired = cert.not_valid_after.replace(tzinfo=timezone.utc) < now
                    days_diff = (cert.not_valid_after.replace(tzinfo=timezone.utc) - now).days
                    record.cert_days_to_expire = days_diff if days_diff > 0 else 0
                
                # Subject (DN)
                subject_parts = []
                for attr in cert.subject:
                    subject_parts.append(f"{attr.oid._name}={attr.value}")
                record.cert_subject = ", ".join(subject_parts)
                
                # Issuer
                issuer_parts = []
                for attr in cert.issuer:
                    issuer_parts.append(f"{attr.oid._name}={attr.value}")
                record.cert_issuer = ", ".join(issuer_parts)
                
                # Número de serie
                record.cert_serial_number = str(cert.serial_number)
                
            except Exception as e:
                _logger.warning(f"Error al extraer información del certificado: {e}")
                record.cert_valid_from = False
                record.cert_valid_to = False
                record.cert_subject = False
                record.cert_issuer = False
                record.cert_serial_number = False
                record.cert_is_expired = False
                record.cert_days_to_expire = 0

    def action_to_draft(self):
        if self.alias_id.state != "confirmed":
            raise UserError(_("Certificate Alias must be confirmed first!"))
        self.write({"state": "draft"})
        return True

    def action_cancel(self):
        self.write({"state": "cancel"})
        return True

    def action_confirm(self):
        self.verify_crt()
        self.write({"state": "confirmed"})
        return True

    def verify_crt(self):
        """
        Verify if certificate is well formed
        """
        for rec in self:
            crt = rec.crt
            msg = False

            if not crt:
                msg = _("Invalid action! Please, set the certification string to " "continue.")
            certificate = rec.get_certificate()
            if certificate is None:
                msg = _(
                    "Invalid action! Your certificate string is invalid. "
                    "Check if you forgot the header CERTIFICATE or forgot/ "
                    "append end of lines."
                )
            if msg:
                raise UserError(msg)
        return True

    def get_certificate(self):
        """
        Return Certificate object.
        """
        self.ensure_one()
        if self.crt:
            try:
                certificate = crypto_utils.load_certificate(self.crt)
            except ValueError as e:
                error_msg = str(e)
                if "CERTIFICATE" in error_msg:
                    raise UserError(
                        _(
                            "Wrong Certificate file format.\nBe sure you have "
                            "BEGIN CERTIFICATE string in your first line."
                        )
                    )
                else:
                    raise UserError(_("Unknown error.\nCertificate validation failed:\n %s") % error_msg)
            except Exception as e:
                raise UserError(_("Error loading certificate:\n %s") % str(e))
        else:
            certificate = None
        return certificate
