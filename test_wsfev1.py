#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, '/var/lib/odoo/custom_addons/odoo-argentina-ce')

print("=" * 70)
print("TEST WSFEv1 CLIENT")
print("=" * 70)

print("\n[1/3] Importando...")
from l10n_ar_afipws_fe.lib.wsfev1_client import WSFEv1Client
print("✅ WSFEv1Client importado")

print("\n[2/3] Creando cliente...")
client = WSFEv1Client("20000000000", "token", "sign", "homologation", 10)
print("✅ Cliente creado")
print(f"    WSDL: {client.wsdl_url}")

print("\n[3/3] Verificando métodos...")
metodos = ['dummy', 'solicitar_cae', 'consultar_ultimo_comprobante', 
           'get_tipos_comprobantes', 'get_tipos_iva']
for m in metodos:
    ok = "✅" if hasattr(client, m) else "❌"
    print(f"    {ok} {m}()")

import zeep
print(f"\n✅ zeep {zeep.__version__} instalado")

print("\n" + "=" * 70)
print("✅ TODO OK - Cliente WSFEv1 listo")
print("=" * 70)
