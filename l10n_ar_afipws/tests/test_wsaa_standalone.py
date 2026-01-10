#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test standalone para wsaa_client.py
Puede ejecutarse sin Odoo para verificar funcionalidad básica.

IMPORTANTE: Para probar contra AFIP real (homologación), necesitas
un certificado válido de AFIP.

Uso:
    # Solo tests unitarios (sin llamar a AFIP):
    python3 test_wsaa_standalone.py
    
    # Con certificado real (requiere archivos cert.pem y key.pem):
    python3 test_wsaa_standalone.py --with-afip
"""

import sys
import os
import argparse

# Agregar path del módulo
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import wsaa_client, crypto_utils


def test_init_client():
    """Test inicialización del cliente WSAA"""
    print("\n=== Test: Inicializar cliente WSAA ===")
    
    # Test homologación
    client_homo = wsaa_client.WSAAClient(environment='homologation')
    print(f"✓ Cliente homologación inicializado")
    print(f"  WSDL: {client_homo.wsdl_url}")
    assert client_homo.environment == 'homologation'
    
    # Test producción
    client_prod = wsaa_client.WSAAClient(environment='production')
    print(f"✓ Cliente producción inicializado")
    print(f"  WSDL: {client_prod.wsdl_url}")
    assert client_prod.environment == 'production'
    
    return client_homo


def test_create_tra(client):
    """Test creación de TRA XML"""
    print("\n=== Test: Crear TRA XML ===")
    
    tra_xml = client.create_tra(
        service='wsfe',
        ttl=43200,  # 12 horas
        cuit='20123456789'
    )
    
    assert isinstance(tra_xml, str), "TRA debe ser string"
    assert '<?xml version' in tra_xml, "TRA debe ser XML válido"
    assert '<loginTicketRequest' in tra_xml, "TRA debe tener elemento raíz correcto"
    assert '<service>wsfe</service>' in tra_xml, "TRA debe incluir servicio"
    assert '<uniqueId>' in tra_xml, "TRA debe tener uniqueId"
    assert '<generationTime>' in tra_xml, "TRA debe tener generationTime"
    assert '<expirationTime>' in tra_xml, "TRA debe tener expirationTime"
    
    print(f"✓ TRA generado correctamente ({len(tra_xml)} bytes)")
    print(f"✓ Estructura XML válida")
    
    # Mostrar TRA
    lines = tra_xml.split('\n')
    for line in lines[:8]:
        print(f"  {line}")
    
    return tra_xml


def test_sign_tra(client, tra_xml):
    """Test firma del TRA con certificado de testing"""
    print("\n=== Test: Firmar TRA ===")
    
    # Generar certificado de testing
    print("Generando certificado autofirmado para testing...")
    
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.x509.oid import NameOID
    from datetime import datetime, timedelta, timezone
    from cryptography.hazmat.backends import default_backend
    
    # Generar clave
    key_pem = crypto_utils.generate_rsa_key(2048)
    private_key = crypto_utils.load_private_key(key_pem)
    
    # Crear certificado autofirmado
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "AR"),
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
    
    print(f"✓ Certificado de testing creado")
    
    # Firmar TRA
    cms_signed = client.sign_tra(
        tra_xml=tra_xml,
        certificate_pem=cert_pem.decode('utf-8'),
        private_key_pem=key_pem.decode('utf-8')
    )
    
    assert isinstance(cms_signed, bytes), "CMS debe ser bytes"
    assert b'BEGIN PKCS7' in cms_signed or b'BEGIN CMS' in cms_signed, "CMS debe tener header"
    
    print(f"✓ TRA firmado con CMS/PKCS#7 ({len(cms_signed)} bytes)")
    
    # Mostrar primeras líneas
    cms_str = cms_signed.decode('utf-8')
    lines = cms_str.split('\n')[:3]
    for line in lines:
        print(f"  {line}")
    
    return cms_signed, cert_pem, key_pem


def test_parse_response():
    """Test parsing de respuesta XML de WSAA"""
    print("\n=== Test: Parsear respuesta WSAA ===")
    
    # Respuesta simulada (estructura real de AFIP)
    mock_response = """<?xml version="1.0" encoding="UTF-8"?>
<loginTicketResponse version="1.0">
<header>
    <source>CN=wsaa,O=AFIP,C=AR,SERIALNUMBER=CUIT 33693450239</source>
    <destination>SERIALNUMBER=CUIT 20123456789,CN=test</destination>
    <uniqueId>1234567890</uniqueId>
    <generationTime>2024-01-10T10:00:00.000-03:00</generationTime>
    <expirationTime>2024-01-10T22:00:00.000-03:00</expirationTime>
</header>
<credentials>
    <token>MOCK_TOKEN_ABC123XYZ</token>
    <sign>MOCK_SIGN_DEF456UVW</sign>
</credentials>
</loginTicketResponse>"""
    
    client = wsaa_client.WSAAClient(environment='homologation')
    result = client._parse_login_response(mock_response)
    
    assert 'token' in result, "Debe extraer token"
    assert 'sign' in result, "Debe extraer sign"
    assert result['token'] == 'MOCK_TOKEN_ABC123XYZ'
    assert result['sign'] == 'MOCK_SIGN_DEF456UVW'
    
    print(f"✓ Token extraído: {result['token']}")
    print(f"✓ Sign extraído: {result['sign'][:30]}...")
    
    if 'unique_id' in result:
        print(f"✓ Unique ID: {result['unique_id']}")
    if 'generation_time' in result:
        print(f"✓ Generation time: {result['generation_time']}")
    if 'expiration_time' in result:
        print(f"✓ Expiration time: {result['expiration_time']}")


def test_get_status(client):
    """Test verificación de estado del servicio"""
    print("\n=== Test: Verificar estado WSAA ===")
    
    try:
        status = client.get_status()
        
        print(f"✓ Estado: {status['status']}")
        print(f"  Ambiente: {status['environment']}")
        print(f"  WSDL: {status['wsdl']}")
        print(f"  Disponible: {status['available']}")
        
        if 'service_name' in status:
            print(f"  Servicio: {status['service_name']}")
        
        assert 'status' in status
        assert 'available' in status
        
    except Exception as e:
        print(f"⚠ No se pudo verificar estado (normal sin conexión): {e}")


def test_with_real_certificate(client, cert_file, key_file):
    """Test con certificado real de AFIP homologación"""
    print("\n=== Test: Autenticación con certificado real ===")
    
    try:
        # Leer certificado y clave
        with open(cert_file, 'r') as f:
            cert_pem = f.read()
        with open(key_file, 'r') as f:
            key_pem = f.read()
        
        print(f"✓ Certificado cargado: {cert_file}")
        print(f"✓ Clave privada cargada: {key_file}")
        
        # Autenticar contra WSAA de homologación
        result = client.authenticate(
            service='wsfe',
            certificate_pem=cert_pem,
            private_key_pem=key_pem,
            cuit='20123456789'  # Reemplazar con CUIT real
        )
        
        print(f"\n🎉 AUTENTICACIÓN EXITOSA!")
        print(f"✓ Token: {result['token'][:50]}...")
        print(f"✓ Sign: {result['sign'][:50]}...")
        
        if 'generation_time' in result:
            print(f"✓ Generado: {result['generation_time']}")
        if 'expiration_time' in result:
            print(f"✓ Expira: {result['expiration_time']}")
        
        return result
        
    except FileNotFoundError as e:
        print(f"❌ Archivos de certificado no encontrados: {e}")
        print(f"   Crea los archivos cert.pem y key.pem en el directorio actual")
        return None
    except Exception as e:
        print(f"❌ Error en autenticación real: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Ejecuta todos los tests"""
    parser = argparse.ArgumentParser(description='Test WSAA Client')
    parser.add_argument('--with-afip', action='store_true',
                       help='Probar contra AFIP homologación (requiere cert.pem y key.pem)')
    parser.add_argument('--cert', default='cert.pem',
                       help='Archivo de certificado (default: cert.pem)')
    parser.add_argument('--key', default='key.pem',
                       help='Archivo de clave privada (default: key.pem)')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("TEST STANDALONE - wsaa_client.py")
    print("=" * 60)
    
    try:
        # Test 1: Inicializar cliente
        client = test_init_client()
        
        # Test 2: Crear TRA
        tra_xml = test_create_tra(client)
        
        # Test 3: Firmar TRA
        cms_signed, cert_pem, key_pem = test_sign_tra(client, tra_xml)
        
        # Test 4: Parsear respuesta
        test_parse_response()
        
        # Test 5: Estado del servicio
        test_get_status(client)
        
        # Test 6: Con certificado real (opcional)
        if args.with_afip:
            test_with_real_certificate(client, args.cert, args.key)
        else:
            print("\n⚠ Para probar contra AFIP homologación, ejecuta:")
            print(f"  python3 {os.path.basename(__file__)} --with-afip --cert cert.pem --key key.pem")
        
        print("\n" + "=" * 60)
        print("✅ TODOS LOS TESTS BÁSICOS PASARON")
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
