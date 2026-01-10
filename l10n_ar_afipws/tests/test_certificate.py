# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
import base64


class TestAfipwsCertificate(TransactionCase):
    """Test certificate generation with crypto_utils integration."""
    
    def setUp(self):
        super(TestAfipwsCertificate, self).setUp()
        
        # Create a company if needed
        self.company = self.env['res.company'].search([], limit=1)
        if not self.company:
            self.company = self.env['res.company'].create({
                'name': 'Test Company',
                'vat': '30714295698',
            })
        
        # Get or create Argentina country
        self.country_ar = self.env.ref('base.ar', raise_if_not_found=False)
        if not self.country_ar:
            self.country_ar = self.env['res.country'].search([('code', '=', 'AR')], limit=1)
        
        # Get or create a state
        self.state = self.env['res.country.state'].search([
            ('country_id', '=', self.country_ar.id)
        ], limit=1)
    
    def test_01_generate_key(self):
        """Test RSA key generation using crypto_utils."""
        alias = self.env['afipws.certificate_alias'].create({
            'common_name': 'Test AFIP WS',
            'company_id': self.company.id,
            'country_id': self.country_ar.id,
            'state_id': self.state.id if self.state else False,
            'city': 'Buenos Aires',
            'department': 'IT',
            'company_cuit': '30714295698',
        })
        
        # Confirm alias to generate key
        alias.action_confirm()
        
        # Check key was generated
        self.assertTrue(alias.key, "Private key should be generated")
        self.assertIn('BEGIN RSA PRIVATE KEY', alias.key, 
                     "Key should be in RSA PRIVATE KEY format")
        self.assertIn('END RSA PRIVATE KEY', alias.key,
                     "Key should have proper footer")
        
        return alias
    
    def test_02_create_csr(self):
        """Test CSR creation using crypto_utils."""
        # First generate key
        alias = self.test_01_generate_key()
        
        # Create CSR
        alias.action_create_certificate_request()
        
        # Check certificate was created
        self.assertTrue(alias.certificate_ids, "Certificate should be created")
        certificate = alias.certificate_ids[0]
        
        # Check CSR content
        self.assertTrue(certificate.csr, "CSR should be generated")
        self.assertIn('BEGIN CERTIFICATE REQUEST', certificate.csr,
                     "CSR should have proper header")
        self.assertIn('END CERTIFICATE REQUEST', certificate.csr,
                     "CSR should have proper footer")
        
        # Check CSR can be downloaded
        self.assertTrue(certificate.request_file, "CSR file should be available")
        
        # Verify CSR contains CUIT
        csr_content = base64.b64decode(certificate.request_file).decode('utf-8')
        self.assertIn('BEGIN CERTIFICATE REQUEST', csr_content)
    
    def test_03_common_name_length(self):
        """Test common name validation."""
        with self.assertRaises(ValidationError):
            self.env['afipws.certificate_alias'].create({
                'common_name': 'A' * 51,  # More than 50 chars
                'company_id': self.company.id,
                'country_id': self.country_ar.id,
                'city': 'Buenos Aires',
                'department': 'IT',
                'company_cuit': '30714295698',
            })
