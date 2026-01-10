##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
import base64

from odoo import api, fields, models


class L10nArAfipwsUploadCertificate(models.TransientModel):
    _name = "afipws.upload_certificate.wizard"
    _description = "afipws.upload_certificate.wizard"

    @api.model
    def get_certificate(self):
        return self.env["afipws.certificate"].browse(self._context.get("active_id"))

    certificate_id = fields.Many2one(
        "afipws.certificate",
        required=True,
        readonly=True,
        default=get_certificate,
        ondelete="cascade",
    )
    certificate_file = fields.Binary("Upload Certificate", required=True)

    def action_confirm(self):
        """Upload and confirm certificate."""
        self.ensure_one()
        
        # Decodificar el archivo del certificado
        try:
            # En Odoo, certificate_file es un campo Binary que puede venir como:
            # - bytes (directo)
            # - str en base64
            cert_data = self.certificate_file
            
            if isinstance(cert_data, str):
                # Si es string, decodificar de base64
                cert_pem = base64.decodebytes(cert_data.encode('utf-8'))
            else:
                # Si ya son bytes, decodificar de base64
                cert_pem = base64.decodebytes(cert_data)
            
            # Convertir a string para almacenar en campo Text
            if isinstance(cert_pem, bytes):
                cert_pem = cert_pem.decode('utf-8')
            
            # Validar que sea un certificado PEM válido
            if not cert_pem.strip().startswith('-----BEGIN CERTIFICATE-----'):
                raise ValueError("El archivo no parece ser un certificado PEM válido")
            
            self.certificate_id.write({"crt": cert_pem})
            self.certificate_id.action_confirm()
            
        except Exception as e:
            from odoo.exceptions import UserError
            raise UserError(f"Error al procesar el certificado: {e}")
        
        return True
