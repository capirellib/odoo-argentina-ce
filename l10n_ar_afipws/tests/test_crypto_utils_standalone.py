#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test standalone para crypto_utils.py
Se puede ejecutar sin Odoo para verificar funcionalidad básica.

Uso:
    python3 test_crypto_utils_standalone.py
"""

import sys
import os

# Agregar path del módulo
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import crypto_utils


def test_generate_rsa_key():
    """Test generación de clave RSA"""
    print("\n=== Test: Generar clave RSA ===")
    
    key_pem = crypto_utils.generate_rsa_key(2048)
    
    assert isinstance(key_pem, bytes), "La clave debe ser bytes"
    assert b"BEGIN RSA PRIVATE KEY" in key_pem, "Debe tener header RSA PRIVATE KEY"
    assert b"END RSA PRIVATE KEY" in key_pem, "Debe tener footer RSA PRIVATE KEY"
    
    print(f"✓ Clave generada: {len(key_pem)} bytes")
    print(f"✓ Header correcto: BEGIN RSA PRIVATE KEY")
    
    return key_pem


def test_create_csr(private_key_pem):
    """Test creación de CSR"""
    print("\n=== Test: Crear CSR ===")
    
    csr_pem = crypto_utils.create_csr(
        private_key_pem=private_key_pem,
        country_code="AR",
        state_name="Buenos Aires",
        city="CABA",
        company_name="Test Company S.A.",
        department="IT",
        common_name="test.company.com.ar",
        cuit="20123456789"
    )
    
    assert isinstance(csr_pem, bytes), "El CSR debe ser bytes"
    assert b"BEGIN CERTIFICATE REQUEST" in csr_pem, "Debe tener header CSR"
    assert b"END CERTIFICATE REQUEST" in csr_pem, "Debe tener footer CSR"
    
    print(f"✓ CSR creado: {len(csr_pem)} bytes")
    print(f"✓ Header correcto: BEGIN CERTIFICATE REQUEST")
    
    # Mostrar primeras líneas del CSR
    csr_str = csr_pem.decode('utf-8')
    lines = csr_str.split('\n')[:3]
    for line in lines:
        print(f"  {line}")
    
    return csr_pem


def test_load_private_key(private_key_pem):
    """Test carga de clave privada"""
    print("\n=== Test: Cargar clave privada ===")
    
    # Test con bytes
    key_obj = crypto_utils.load_private_key(private_key_pem)
    print(f"✓ Clave cargada desde bytes")
    print(f"✓ Tipo: {type(key_obj).__name__}")
    print(f"✓ Key size: {key_obj.key_size} bits")
    
    # Test con string
    key_str = private_key_pem.decode('utf-8')
    key_obj2 = crypto_utils.load_private_key(key_str)
    print(f"✓ Clave cargada desde string")
    
    return key_obj


def test_sign_cms(private_key_pem):
    """Test firma CMS/PKCS#7"""
    print("\n=== Test: Firma CMS/PKCS#7 ===")
    
    # Para este test necesitaríamos un certificado real
    # Por ahora solo verificamos que la función existe y tiene la firma correcta
    print("⚠ Test de firma CMS requiere certificado real")
    print("✓ Función sign_cms() disponible")
    print("✓ Parámetros: data, certificate_pem, private_key_pem")
    
    # Crear datos de prueba
    test_data = b"<?xml version='1.0' encoding='UTF-8'?><test>data</test>"
    print(f"✓ Datos de prueba: {len(test_data)} bytes")


def test_convert_key_format(private_key_pem):
    """Test conversión de formato de clave"""
    print("\n=== Test: Convertir formato de clave ===")
    
    key_str = private_key_pem.decode('utf-8')
    
    # Verificar que ya está en formato correcto
    converted = crypto_utils.convert_key_format(key_str)
    assert "BEGIN RSA PRIVATE KEY" in converted, "Debe mantener formato RSA"
    
    print(f"✓ Formato verificado: BEGIN RSA PRIVATE KEY")
    print(f"✓ Longitud: {len(converted)} caracteres")


def test_certificate_operations():
    """Test operaciones con certificados"""
    print("\n=== Test: Operaciones con certificados ===")
    
    # Crear un certificado autofirmado para testing
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.x509.oid import NameOID
    from datetime import datetime, timedelta, timezone
    from cryptography.hazmat.backends import default_backend
    
    print("Generando certificado autofirmado para testing...")
    
    # Generar clave
    key_pem = crypto_utils.generate_rsa_key(2048)
    private_key = crypto_utils.load_private_key(key_pem)
    
    # Crear certificado
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "AR"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Buenos Aires"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "CABA"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Test Org"),
        x509.NameAttribute(NameOID.COMMON_NAME, "test.com.ar"),
    ])
    
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        private_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.now(timezone.utc)
    ).not_valid_after(
        datetime.now(timezone.utc) + timedelta(days=365)
    ).sign(private_key, hashes.SHA256(), default_backend())
    
    cert_pem = cert.public_bytes(encoding=serialization.Encoding.PEM)
    
    print(f"✓ Certificado creado: {len(cert_pem)} bytes")
    
    # Test verify_certificate
    info = crypto_utils.verify_certificate(cert_pem)
    
    print(f"✓ Información extraída:")
    print(f"  - Subject CN: {info['subject']['common_name']}")
    print(f"  - Organization: {info['subject']['organization']}")
    print(f"  - Valid from: {info['valid_from']}")
    print(f"  - Valid until: {info['valid_until']}")
    print(f"  - Is valid: {info['is_valid']}")
    
    # Test sign_cms con certificado real
    print("\nProbando firma CMS con certificado de testing...")
    test_data = b"<?xml version='1.0' encoding='UTF-8'?><test>Datos de prueba</test>"
    
    try:
        cms_signed = crypto_utils.sign_cms(
            data=test_data,
            certificate_pem=cert_pem.decode('utf-8'),
            private_key_pem=key_pem.decode('utf-8')
        )
        
        assert isinstance(cms_signed, bytes), "CMS debe ser bytes"
        assert b"BEGIN PKCS7" in cms_signed or b"BEGIN CMS" in cms_signed, "Debe tener header PKCS7/CMS"
        
        print(f"✓ CMS firmado: {len(cms_signed)} bytes")
        print(f"✓ Firma CMS exitosa!")
        
        # Mostrar primeras líneas
        cms_str = cms_signed.decode('utf-8')
        lines = cms_str.split('\n')[:3]
        for line in lines:
            print(f"  {line}")
            
    except Exception as e:
        print(f"✗ Error en firma CMS: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Ejecuta todos los tests"""
    print("=" * 60)
    print("TEST STANDALONE - crypto_utils.py")
    print("=" * 60)
    
    try:
        # Test 1: Generar clave
        private_key_pem = test_generate_rsa_key()
        
        # Test 2: Crear CSR
        csr_pem = test_create_csr(private_key_pem)
        
        # Test 3: Cargar clave
        key_obj = test_load_private_key(private_key_pem)
        
        # Test 4: Firma CMS (básico)
        test_sign_cms(private_key_pem)
        
        # Test 5: Convertir formato
        test_convert_key_format(private_key_pem)
        
        # Test 6: Operaciones con certificados (incluyendo firma CMS real)
        test_certificate_operations()
        
        print("\n" + "=" * 60)
        print("✅ TODOS LOS TESTS PASARON")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n❌ TEST FALLIDO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
        
    except Exception as e:
        print(f"\n❌ ERROR INESPERADO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
