#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test standalone del cliente WSFEv1.

Para ejecutar:
    cd /Volumes/Disk\ 1Tb/DesarrollosODOO/ODOO18_Desarrollo/extra-addons-odoo18/odoo-argentina-ce
    python3 l10n_ar_afipws_fe/tests/test_wsfev1_standalone.py
"""

import sys
import os
from datetime import datetime, timedelta

# Agregar path de los módulos
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from l10n_ar_afipws.lib.wsaa_client import WSAAClient
from l10n_ar_afipws_fe.lib.wsfev1_client import WSFEv1Client


def get_wsaa_credentials():
    """
    Obtiene credenciales de WSAA.
    
    NOTA: Debes tener configurados en Odoo:
    - Certificado AFIP (.crt)
    - Clave privada (.key)
    - CUIT de la empresa
    """
    # TODO: Reemplazar con tus datos reales
    CUIT = "20123456789"  # Tu CUIT
    CERT_PATH = "/path/to/cert.crt"  # Path a tu certificado
    KEY_PATH = "/path/to/key.key"  # Path a tu clave privada
    
    print("=" * 60)
    print("IMPORTANTE: Debes configurar tus credenciales reales")
    print("=" * 60)
    print(f"CUIT: {CUIT}")
    print(f"Certificado: {CERT_PATH}")
    print(f"Clave: {KEY_PATH}")
    print()
    
    if not os.path.exists(CERT_PATH) or not os.path.exists(KEY_PATH):
        print("ERROR: Los archivos de certificado/clave no existen.")
        print("Copia tus archivos .crt y .key desde Odoo y actualiza las rutas.")
        return None
    
    # Leer certificado y clave
    with open(CERT_PATH, 'rb') as f:
        cert_pem = f.read()
    
    with open(KEY_PATH, 'rb') as f:
        key_pem = f.read()
    
    # Autenticar con WSAA
    print("Autenticando con WSAA...")
    wsaa = WSAAClient(environment='homologation')
    
    try:
        credentials = wsaa.authenticate(
            service='wsfe',  # Servicio WSFEv1
            certificate_pem=cert_pem,
            private_key_pem=key_pem
        )
        
        print(f"✓ Token obtenido: {credentials['token'][:50]}...")
        print(f"✓ Sign obtenido: {credentials['sign'][:50]}...")
        print(f"✓ Expira: {credentials['expiration_time']}")
        print()
        
        return {
            'cuit': CUIT,
            'token': credentials['token'],
            'sign': credentials['sign'],
        }
        
    except Exception as e:
        print(f"✗ Error al autenticar: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_dummy(client):
    """Test de conectividad."""
    print("\n" + "=" * 60)
    print("TEST 1: Dummy (conectividad)")
    print("=" * 60)
    
    try:
        result = client.dummy()
        print(f"✓ AppServer: {result['AppServer']}")
        print(f"✓ DbServer: {result['DbServer']}")
        print(f"✓ AuthServer: {result['AuthServer']}")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_parametros(client):
    """Test de consulta de parámetros."""
    print("\n" + "=" * 60)
    print("TEST 2: Parámetros")
    print("=" * 60)
    
    try:
        # Tipos de comprobante
        print("\n--- Tipos de Comprobante ---")
        tipos_cbte = client.get_tipos_comprobantes()
        for tipo in tipos_cbte[:5]:  # Solo mostrar primeros 5
            print(f"  {tipo['Id']:3d} - {tipo['Desc']}")
        print(f"  ... (total: {len(tipos_cbte)})")
        
        # Tipos de documento
        print("\n--- Tipos de Documento ---")
        tipos_doc = client.get_tipos_documento()
        for tipo in tipos_doc:
            print(f"  {tipo['Id']:3d} - {tipo['Desc']}")
        
        # Tipos de IVA
        print("\n--- Tipos de IVA ---")
        tipos_iva = client.get_tipos_iva()
        for tipo in tipos_iva:
            print(f"  {tipo['Id']:3d} - {tipo['Desc']}")
        
        # Monedas
        print("\n--- Monedas ---")
        monedas = client.get_tipos_moneda()
        for mon in monedas:
            print(f"  {mon['Id']:3s} - {mon['Desc']}")
        
        # Cotización dólar
        print("\n--- Cotización USD ---")
        cotiz_usd = client.get_cotizacion('DOL')
        print(f"  USD: ${cotiz_usd:.2f}")
        
        # Puntos de venta
        print("\n--- Puntos de Venta ---")
        puntos = client.get_puntos_venta()
        for pto in puntos:
            print(f"  Punto: {pto['Nro']:04d}, EmisionTipo: {pto.get('EmisionTipo', 'N/A')}, "
                  f"Bloqueado: {pto.get('Bloqueado', 'N/A')}")
        
        print("\n✓ Todos los parámetros consultados correctamente")
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ultimo_comprobante(client):
    """Test de consulta de último comprobante."""
    print("\n" + "=" * 60)
    print("TEST 3: Último Comprobante Autorizado")
    print("=" * 60)
    
    try:
        # Probar con diferentes tipos de comprobante
        tipos_test = [
            (1, 'Factura A'),
            (6, 'Factura B'),
            (11, 'Factura C'),
            (3, 'Nota de Crédito A'),
        ]
        
        for tipo_id, tipo_desc in tipos_test:
            ultimo = client.consultar_ultimo_comprobante(pto_vta=1, tipo_cbte=tipo_id)
            print(f"  {tipo_desc} (Tipo {tipo_id:02d}): último nro = {ultimo}")
        
        print("\n✓ Consultas exitosas")
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_solicitar_cae_factura_c(client):
    """
    Test de solicitud de CAE para una Factura C (consumidor final).
    
    NOTA: Este test genera un comprobante REAL en AFIP Homologación.
    """
    print("\n" + "=" * 60)
    print("TEST 4: Solicitar CAE - Factura C")
    print("=" * 60)
    print("ADVERTENCIA: Este test generará un comprobante REAL en AFIP Homologación")
    
    respuesta = input("¿Deseas continuar? (s/n): ")
    if respuesta.lower() != 's':
        print("Test cancelado por el usuario")
        return False
    
    try:
        # Obtener próximo número
        pto_vta = 1
        tipo_cbte = 11  # Factura C
        ultimo_nro = client.consultar_ultimo_comprobante(pto_vta, tipo_cbte)
        proximo_nro = ultimo_nro + 1
        
        print(f"\nPunto de venta: {pto_vta}")
        print(f"Tipo comprobante: {tipo_cbte} (Factura C)")
        print(f"Último autorizado: {ultimo_nro}")
        print(f"Próximo número: {proximo_nro}")
        
        # Preparar datos de la factura
        fecha_hoy = datetime.now().strftime('%Y%m%d')
        
        factura_data = {
            'PtoVta': pto_vta,
            'CbteTipo': tipo_cbte,
            'Concepto': 1,  # Productos
            'DocTipo': 99,  # Consumidor Final
            'DocNro': 0,
            'CbteDesde': proximo_nro,
            'CbteHasta': proximo_nro,
            'CbteFch': fecha_hoy,
            'ImpTotal': 121.0,  # Total con IVA
            'ImpTotConc': 0.0,  # No gravado
            'ImpNeto': 100.0,  # Neto gravado
            'ImpOpEx': 0.0,  # Exento
            'ImpTrib': 0.0,  # Tributos
            'ImpIVA': 21.0,  # IVA 21%
            'MonId': 'PES',  # Pesos
            'MonCotiz': 1.0,
            # Alícuotas IVA
            'Iva': [{
                'Id': 5,  # 21%
                'BaseImp': 100.0,
                'Importe': 21.0
            }]
        }
        
        print("\nDatos del comprobante:")
        print(f"  Concepto: {factura_data['Concepto']} (Productos)")
        print(f"  Cliente: Consumidor Final")
        print(f"  Fecha: {factura_data['CbteFch']}")
        print(f"  Neto: ${factura_data['ImpNeto']:.2f}")
        print(f"  IVA: ${factura_data['ImpIVA']:.2f}")
        print(f"  Total: ${factura_data['ImpTotal']:.2f}")
        
        print("\nSolicitando CAE...")
        result = client.solicitar_cae(factura_data)
        
        print("\n--- RESULTADO ---")
        print(f"  Resultado: {result.get('Resultado')}")
        
        if result.get('CAE'):
            print(f"  ✓ CAE: {result['CAE']}")
            print(f"  ✓ Vencimiento CAE: {result['CAEFchVto']}")
            print(f"  ✓ Comprobante: {result['CbteDesde']}")
            print(f"  ✓ Fecha: {result['CbteFch']}")
            print("\n✓ CAE obtenido exitosamente")
            return True
        else:
            print(f"  ✗ No se obtuvo CAE")
            
            if result.get('Observaciones'):
                print("\n  Observaciones:")
                for obs in result['Observaciones']:
                    print(f"    - [{obs['Code']}] {obs['Msg']}")
            
            if result.get('Errors'):
                print("\n  Errores:")
                for err in result['Errors']:
                    print(f"    - [{err['Code']}] {err['Msg']}")
            
            return False
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Función principal."""
    print("\n" + "=" * 60)
    print("TEST STANDALONE - WSFEv1 Client")
    print("=" * 60)
    
    # Obtener credenciales
    credentials = get_wsaa_credentials()
    if not credentials:
        print("\n✗ No se pudieron obtener las credenciales")
        print("\nPara ejecutar estos tests necesitas:")
        print("1. Certificado AFIP (.crt)")
        print("2. Clave privada (.key)")
        print("3. CUIT de homologación")
        print("\nActualiza la función get_wsaa_credentials() con tus datos.")
        return
    
    # Crear cliente WSFEv1
    print("Creando cliente WSFEv1...")
    client = WSFEv1Client(
        cuit=credentials['cuit'],
        token=credentials['token'],
        sign=credentials['sign'],
        environment='homologation'
    )
    print("✓ Cliente creado\n")
    
    # Ejecutar tests
    tests_passed = 0
    tests_total = 0
    
    tests = [
        test_dummy,
        test_parametros,
        test_ultimo_comprobante,
        test_solicitar_cae_factura_c,
    ]
    
    for test_func in tests:
        tests_total += 1
        if test_func(client):
            tests_passed += 1
    
    # Resumen
    print("\n" + "=" * 60)
    print("RESUMEN")
    print("=" * 60)
    print(f"Tests ejecutados: {tests_total}")
    print(f"Tests exitosos: {tests_passed}")
    print(f"Tests fallidos: {tests_total - tests_passed}")
    
    if tests_passed == tests_total:
        print("\n✓ TODOS LOS TESTS PASARON")
    else:
        print(f"\n✗ {tests_total - tests_passed} TEST(S) FALLARON")


if __name__ == '__main__':
    main()
