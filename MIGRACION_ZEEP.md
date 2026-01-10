# Plan de Migración: pyafipws → zeep+cryptography

**Branch**: `18.0_Iicio_zeep_certificado`  
**Fecha inicio**: 10 de enero de 2026  
**Objetivo**: Migrar odoo-argentina-ce de pyafipws/pysimplesoap/M2Crypto a zeep+cryptography

---

## 📋 Resumen Ejecutivo

### Estado Actual
- **Módulos afectados**: 4 módulos (todos `installable: False` en v18)
  - `l10n_ar_afipws` (base)
  - `l10n_ar_afipws_fe` (facturación electrónica)
  - `l10n_ar_pos_afipws_fe` (POS)
  - `l10n_ar_reports` (NO requiere cambios)

### Dependencias Actuales (obsoletas)
```python
pyafipws
pysimplesoap~=1.8.22
M2Crypto
pyOpenSSL
```

### Dependencias Objetivo
```python
zeep
cryptography
lxml
```

### Web Services AFIP/ARCA
- **WSAA**: Autenticación (CRÍTICO - base de todo)
- **WSFEv1**: Facturación mercado interno (CRÍTICO)
- **WSFEXv1**: Facturación exportación (MEDIA)
- **WSBFE**: Bono fiscal (MEDIA)
- **WSCDC**: Constatación comprobantes (BAJA)
- **WS_SR_PADRON**: Consulta padrón A4/A5 (MEDIA)
- **WSFECred**: Facturas de crédito (BAJA)

---

## 🎯 Fases de Implementación

### ✅ FASE 0: Preparación [COMPLETADA]
- [x] Crear branch `18.0_Iicio_zeep_certificado`
- [x] Analizar código actual y dependencias
- [x] Documentar plan en `MIGRACION_ZEEP.md`
- [x] Instalar dependencias: zeep, cryptography, lxml
- [ ] Configurar ambiente de testing con certificados de homologación
- [ ] Documentar URLs y WSDLs de cada servicio

### 🔧 FASE 1: Cryptography - Certificados y Firma CMS [COMPLETADA]

**Objetivo**: Reemplazar OpenSSL/M2Crypto con cryptography

#### Archivos a crear:
- `l10n_ar_afipws/lib/__init__.py`
- `l10n_ar_afipws/lib/crypto_utils.py`

#### Funciones a implementar en `crypto_utils.py`:

```python
def generate_rsa_key(key_size=2048):
    """Genera clave RSA (reemplaza OpenSSL.crypto.PKey)"""
    
def create_csr(private_key, subject_data, cuit):
    """Crea Certificate Signing Request (reemplaza OpenSSL.crypto.X509Req)"""
    
def load_private_key(pem_data):
    """Carga clave privada desde PEM"""
    
def load_certificate(pem_data):
    """Carga certificado desde PEM"""
    
def sign_cms(data, certificate, private_key):
    """Firma datos con CMS/PKCS#7 (reemplaza M2Crypto)"""
    # DESAFÍO: Implementar firma CMS compatible con AFIP
```

#### Archivos a modificar:
- `l10n_ar_afipws/models/afipws_certificate_alias.py`
  - Método `generate_key()` (línea ~156)
  - Método `action_create_certificate_request()` (línea ~167)

#### Tests a crear:
- `l10n_ar_afipws/tests/test_crypto_utils.py`
  - Test generación de claves
  - Test creación de CSR
  - Test firma CMS con certificado demo

#### Criterios de aceptación:
- [x] Genera clave RSA 2048 bits en formato PEM
- [x] Crea CSR válido con DN correcto (incluyendo CUIT)
- [x] Firma CMS compatible con WSAA de AFIP
- [x] Tests unitarios pasan al 100%
- [x] Integrar con modelos existentes (afipws_certificate_alias)
- [x] Actualizar afipws_certificate.py para usar crypto_utils
- [x] Crear tests de Odoo para validar integración
- [ ] Probar en instancia Odoo real

**ESTADO**: ✅ Funciones crypto implementadas, testeadas e integradas con modelos Odoo

---

### 🔐 FASE 2: WSAA con zeep [PENDIENTE]

**Objetivo**: Reimplementar autenticación WSAA usando zeep

#### Archivos a crear:
- `l10n_ar_afipws/lib/wsaa_client.py`

#### Clase a implementar:

```python
class WSAAClient:
    """Cliente WSAA con zeep"""
    
    WSDL_PROD = "https://wsaa.afip.gov.ar/ws/services/LoginCms?wsdl"
    WSDL_HOMO = "https://wsaahomo.afip.gov.ar/ws/services/LoginCms?wsdl"
    
    def __init__(self, environment='homologation'):
        """Inicializa cliente zeep"""
        
    def create_tra(self, service, ttl=43200):
        """Crea Ticket de Requerimiento de Acceso (XML)"""
        
    def login(self, tra_signed_cms):
        """Llama LoginCms y obtiene token/sign"""
        
    def authenticate(self, service, certificate_pem, private_key_pem):
        """Flujo completo: TRA → Firma → Login → Token/Sign"""
```

#### Archivos a modificar:
- `l10n_ar_afipws/models/afipws_connection.py`
  - Método `get_auth()` (línea ~192-256)
  - Reemplazar uso de `pyafipws.wsaa.WSAA`

#### Tests a crear:
- `l10n_ar_afipws/tests/test_wsaa_client.py`
  - Test creación TRA XML
  - Test login con certificado demo (mock o homologación)
  - Test parsing de respuesta (token, sign, expirationTime)

#### Criterios de aceptación:
- [ ] Genera TRA XML válido según especificación AFIP
- [ ] Firma TRA con CMS correctamente
- [ ] LoginCms retorna token y sign válidos
- [ ] Se puede conectar a homologación AFIP
- [ ] Tests pasan con certificado demo
- [ ] `afipws.connection` guarda token/sign en BD correctamente

---

### 📄 FASE 3: WSFEv1 con zeep [PENDIENTE]

**Objetivo**: Migrar facturación electrónica mercado interno

#### Archivos a crear:
- `l10n_ar_afipws_fe/lib/__init__.py`
- `l10n_ar_afipws_fe/lib/wsfev1_client.py`

#### Métodos WSFEv1 a implementar:

```python
class WSFEv1Client:
    """Cliente WSFEv1 con zeep"""
    
    WSDL_PROD = "https://servicios1.afip.gov.ar/wsfev1/service.asmx?WSDL"
    WSDL_HOMO = "https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL"
    
    def __init__(self, cuit, token, sign, environment='homologation'):
        """Inicializa cliente zeep con credenciales"""
        
    # Métodos principales
    def dummy(self):
        """Test conectividad"""
        
    def solicitar_cae(self, invoice_data):
        """FECAESolicitar - Obtener CAE para factura"""
        
    def consultar_ultimo_comprobante(self, pto_vta, tipo_cbte):
        """FECompUltimoAutorizado"""
        
    # Métodos de parámetros
    def get_tipos_comprobantes(self):
        """FEParamGetTiposCbte"""
        
    def get_puntos_venta(self):
        """FEParamGetPtosVenta"""
        
    def get_tipos_concepto(self):
        """FEParamGetTiposConcepto"""
        
    def get_tipos_documento(self):
        """FEParamGetTiposDoc"""
        
    def get_tipos_iva(self):
        """FEParamGetTiposIva"""
        
    def get_tipos_moneda(self):
        """FEParamGetTiposMonedas"""
        
    def get_tipos_tributo(self):
        """FEParamGetTiposTributos"""
        
    def get_cotizacion(self, moneda_id):
        """FEParamGetCotizacion"""
```

#### Archivos a modificar:
- `l10n_ar_afipws_fe/models/account_move_ws.py`
  - Método `do_pyafipws_request_cae()` (línea ~250-500)
  - Reemplazar todo uso de `pyafipws.wsfev1.WSFEv1`
- `l10n_ar_afipws_fe/models/account_journal_ws.py`
  - Métodos de consulta (último número, tipos, etc.)

#### Tests a crear:
- `l10n_ar_afipws_fe/tests/test_wsfev1_client.py`
  - Test dummy (conectividad)
  - Test solicitar CAE con factura tipo A/B/C
  - Test consultar último comprobante
  - Test obtener parámetros

#### Criterios de aceptación:
- [ ] Dummy retorna estado OK
- [ ] Solicita CAE correctamente para tipos A, B, C
- [ ] Maneja notas de crédito y débito
- [ ] Maneja FCE (MiPyMEs)
- [ ] Consulta último número autorizado
- [ ] Obtiene todos los parámetros (tipos cbte, IVA, etc.)
- [ ] Guarda XML request/response en factura
- [ ] Tests pasan en homologación

---

### 🌍 FASE 4: Servicios Secundarios [PENDIENTE]

#### 4.1 WSFEXv1 (Exportación)

**Archivo**: `l10n_ar_afipws_fe/lib/wsfexv1_client.py`

```python
class WSFEXv1Client:
    """Cliente WSFEXv1 con zeep - Facturación Exportación"""
    
    WSDL_PROD = "https://servicios1.afip.gov.ar/wsfexv1/service.asmx?WSDL"
    WSDL_HOMO = "https://wswhomo.afip.gov.ar/wsfexv1/service.asmx?WSDL"
    
    def solicitar_cae(self, invoice_data):
        """FEXAuthorize"""
        
    def consultar_ultimo_comprobante(self, pto_vta, tipo_cbte):
        """FEXGetLast_CMP"""
```

#### 4.2 WSBFE (Bono Fiscal)

**Archivo**: `l10n_ar_afipws_fe/lib/wsbfev1_client.py`

```python
class WSBFEv1Client:
    """Cliente WSBFE con zeep - Bono Fiscal"""
    
    WSDL_PROD = "https://servicios1.afip.gov.ar/wsbfev1/service.asmx?WSDL"
    WSDL_HOMO = "https://wswhomo.afip.gov.ar/wsbfev1/service.asmx?WSDL"
```

#### 4.3 WSCDC (Constatación)

**Archivo**: `l10n_ar_afipws_fe/lib/wscdc_client.py`

```python
class WSCDCClient:
    """Cliente WSCDC con zeep - Constatación Comprobantes"""
    
    WSDL_PROD = "https://servicios1.afip.gov.ar/WSCDC/service.asmx?WSDL"
    WSDL_HOMO = "https://wswhomo.afip.gov.ar/WSCDC/service.asmx?WSDL"
```

#### Archivos a modificar:
- `l10n_ar_afipws_fe/models/account_move_ws.py`
  - Actualizar lógica de routing según `journal.afip_ws`

---

### 👥 FASE 5: Padrón AFIP [PENDIENTE]

**Objetivo**: Migrar consultas al padrón de contribuyentes

#### Archivo a crear:
- `l10n_ar_afipws/lib/padron_client.py`

```python
class PadronA4Client:
    """WS_SR_PADRON_A4 con zeep"""
    
    WSDL_PROD = "https://aws.afip.gov.ar/sr-padron/webservices/personaServiceA4?wsdl"
    WSDL_HOMO = "https://awshomo.afip.gov.ar/sr-padron/webservices/personaServiceA4?wsdl"

class PadronA5Client:
    """WS_SR_PADRON_A5 con zeep"""
    
    WSDL_PROD = "https://aws.afip.gov.ar/sr-padron/webservices/personaServiceA5?wsdl"
    WSDL_HOMO = "https://awshomo.afip.gov.ar/sr-padron/webservices/personaServiceA5?wsdl"
    
    def get_persona(self, cuit):
        """getPersona_v2 - Consulta datos contribuyente"""
```

#### Archivo a modificar:
- `l10n_ar_afipws/models/res_partner.py`
  - Método `update_partner_from_padron()` (línea ~91-165)

---

### 🧹 FASE 6: Limpieza y Activación [PENDIENTE]

#### 6.1 Actualizar requirements.txt

```python
# Eliminar
# pyafipws
# pysimplesoap~=1.8.22
# M2Crypto
# pyOpenSSL  # Opcional, se puede mantener

# Agregar
zeep>=4.2.0
cryptography>=41.0.0
lxml>=4.9.0
```

#### 6.2 Actualizar __manifest__.py

En cada módulo cambiar:
```python
# De:
"installable": False,
"external_dependencies": {
    "python": ["pyafipws", "OpenSSL", "pysimplesoap"]
}

# A:
"installable": True,
"external_dependencies": {
    "python": ["zeep", "cryptography", "lxml"]
}
```

#### 6.3 Eliminar imports obsoletos

- `l10n_ar_afipws_fe/afip_utils.py` (línea 5)
  - Eliminar: `from pysimplesoap.client import SimpleXMLElement`
  - Reemplazar con: `from lxml import etree`
  - Actualizar método `get_cbte_desde()` para usar lxml

---

### 🧪 FASE 7: Testing Integral [PENDIENTE]

#### Suite de tests a crear:

```
l10n_ar_afipws/tests/
  __init__.py
  test_crypto_utils.py
  test_wsaa_client.py
  test_padron_client.py
  test_certificate_alias.py
  test_connection.py

l10n_ar_afipws_fe/tests/
  __init__.py
  test_wsfev1_client.py
  test_wsfexv1_client.py
  test_wsbfev1_client.py
  test_wscdc_client.py
  test_account_move_fe.py
  test_account_journal.py
```

#### Casos de prueba críticos:

**Autenticación**:
- [ ] Generar certificado y CSR
- [ ] Obtener token/sign de WSAA homologación
- [ ] Manejo de token expirado
- [ ] Renovación automática

**Facturación WSFEv1**:
- [ ] Factura A (IVA Responsable Inscripto)
- [ ] Factura B (IVA Responsable Inscripto a Consumidor Final)
- [ ] Factura C (IVA Exento/Monotributo)
- [ ] Factura M (Exportación - código 51)
- [ ] Nota de crédito A/B/C
- [ ] Nota de débito A/B/C
- [ ] FCE (MiPyMEs) tipos 201, 206, 211
- [ ] Factura con múltiples impuestos/tributos
- [ ] Factura con comprobantes asociados

**Consultas**:
- [ ] Último número autorizado
- [ ] Tipos de comprobante
- [ ] Puntos de venta autorizados
- [ ] Cotización de moneda
- [ ] Consulta padrón por CUIT

**Manejo de errores**:
- [ ] Error de autenticación (token inválido)
- [ ] Error de validación AFIP (CAE rechazado)
- [ ] Error de conexión (timeout)
- [ ] Observaciones AFIP (warnings)

---

## 📊 Tracking de Progreso

### Checklist General

#### Preparación
- [x] Crear branch de trabajo
- [x] Documentar plan completo
- [ ] Configurar certificados demo homologación
- [ ] Descargar todos los WSDLs

#### Implementación Core
- [x] FASE 1: Cryptography (firma CMS)
- [ ] FASE 2: WSAA (autenticación)
- [ ] FASE 3: WSFEv1 (facturación)
- [ ] FASE 4: Servicios secundarios
- [ ] FASE 5: Padrón AFIP
- [ ] FASE 6: Limpieza y activación

#### Testing
- [ ] Tests unitarios crypto
- [ ] Tests unitarios WSAA
- [ ] Tests unitarios WSFEv1
- [ ] Tests integración facturación
- [ ] Tests con certificados reales homologación

#### Documentación
- [ ] Actualizar READMEs
- [ ] Documentar cambios en CHANGELOG.md
- [ ] Guía de migración para usuarios

---

## 🔍 Referencias Técnicas

### URLs AFIP/ARCA

#### Producción
- WSAA: `https://wsaa.afip.gov.ar/ws/services/LoginCms?wsdl`
- WSFEv1: `https://servicios1.afip.gov.ar/wsfev1/service.asmx?WSDL`
- WSFEXv1: `https://servicios1.afip.gov.ar/wsfexv1/service.asmx?WSDL`
- WSBFE: `https://servicios1.afip.gov.ar/wsbfev1/service.asmx?WSDL`
- WSCDC: `https://servicios1.afip.gov.ar/WSCDC/service.asmx?WSDL`
- Padrón A4: `https://aws.afip.gov.ar/sr-padron/webservices/personaServiceA4?wsdl`
- Padrón A5: `https://aws.afip.gov.ar/sr-padron/webservices/personaServiceA5?wsdl`
- WSFECred: `https://serviciosjava.afip.gob.ar/wsfecred/FECredService?wsdl`

#### Homologación
- WSAA: `https://wsaahomo.afip.gov.ar/ws/services/LoginCms?wsdl`
- WSFEv1: `https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL`
- WSFEXv1: `https://wswhomo.afip.gov.ar/wsfexv1/service.asmx?WSDL`
- WSBFE: `https://wswhomo.afip.gov.ar/wsbfev1/service.asmx?WSDL`
- WSCDC: `https://wswhomo.afip.gov.ar/WSCDC/service.asmx?WSDL`
- Padrón A4: `https://awshomo.afip.gov.ar/sr-padron/webservices/personaServiceA4?wsdl`
- Padrón A5: `https://awshomo.afip.gov.ar/sr-padron/webservices/personaServiceA5?wsdl`
- WSFECred: `https://fwshomo.afip.gov.ar/wsfecred/FECredService?wsdl`

### Documentación AFIP
- Manual WSFEv1: http://www.afip.gob.ar/ws/documentacion/ws-factura-electronica.asp
- Manual WSBFE: http://www.afip.gob.ar/fe/documentos/WSBFEv1%20-%20Manual%20para%20el%20desarrollador.pdf

### Repositorios
- Código actual: https://github.com/ingadhoc/odoo-argentina-ce
- pyafipws: https://github.com/filoquin/pyafipws (fork usado)
- Odoo Enterprise (referencia): https://github.com/odoo/enterprise (l10n_ar_edi)

---

## 🚨 Desafíos Conocidos

### 1. Firma CMS/PKCS#7
**Problema**: pyafipws usa M2Crypto para firma PKCS#7 del TRA  
**Complejidad**: ALTA  
**Solución propuesta**: Usar `cryptography.hazmat.primitives.serialization.pkcs7`  
**Referencia**: Ver implementación en Odoo Enterprise l10n_ar_edi

### 2. Formato de clave privada
**Problema**: Conversión "BEGIN PRIVATE KEY" ↔ "BEGIN RSA PRIVATE KEY"  
**Ubicación**: `res_company.py` línea 177  
**Solución**: cryptography maneja ambos, verificar necesidad de conversión

### 3. Parsing XML
**Problema**: Uso de pysimplesoap.SimpleXMLElement  
**Ubicación**: `afip_utils.py` línea 5  
**Solución**: Reemplazar con lxml.etree

### 4. Compatibilidad interfaz
**Problema**: Código asume objetos pyafipws (ws.CAE, ws.Resultado)  
**Solución**: Crear wrapper/adaptador que simule interfaz

### 5. Testing sin certificados
**Problema**: Tests requieren certificados AFIP válidos  
**Solución**: Certificados demo + mock de respuestas SOAP

---

## 📝 Notas de Desarrollo

### Convenciones de código
- Seguir PEP 8
- Type hints en todas las funciones nuevas
- Docstrings estilo Google
- Logging con `_logger = logging.getLogger(__name__)`

### Manejo de errores
- Capturar excepciones zeep específicas
- Traducir a excepciones Odoo (UserError, ValidationError)
- Logear errores con contexto completo
- Preservar XML request/response para debugging

### Compatibilidad
- Mantener campos existentes en modelos
- No romper API pública de métodos
- Mantener estructura de datos en BD
- Migración debe ser transparente para usuarios

---

## ✅ Próximos Pasos Inmediatos

1. **Instalar dependencias**:
   ```bash
   pip install zeep cryptography lxml
   ```

2. **Obtener certificado de homologación AFIP**:
   - Generar CSR con código actual
   - Solicitar certificado en portal AFIP homologación
   - Guardar en `l10n_ar_afipws/tests/fixtures/`

3. **Comenzar FASE 1**: Implementar `crypto_utils.py`
   - Función `generate_rsa_key()`
   - Función `create_csr()`
   - Función `sign_cms()` (desafío principal)
   - Tests unitarios

---

**Última actualización**: 10 de enero de 2026  
**Estado**: FASE 1 - COMPLETADA ✅ | Iniciando FASE 2
