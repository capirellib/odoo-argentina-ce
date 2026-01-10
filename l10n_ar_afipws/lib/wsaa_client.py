# -*- coding: utf-8 -*-
"""
Cliente WSAA (Web Service de Autenticación y Autorización) usando zeep.
Reemplaza pyafipws.wsaa.WSAA con implementación moderna.
"""

import logging
from datetime import datetime, timedelta, timezone
from lxml import etree
from zeep import Client
from zeep.transports import Transport
from requests import Session

from . import crypto_utils

_logger = logging.getLogger(__name__)


class WSAAClient:
    """
    Cliente para el Web Service de Autenticación y Autorización (WSAA) de AFIP/ARCA.
    
    Este servicio permite autenticarse y obtener credenciales (token y sign)
    que son necesarias para acceder a otros web services de AFIP.
    """
    
    # URLs de WSAA
    WSDL_PROD = "https://wsaa.afip.gov.ar/ws/services/LoginCms?wsdl"
    WSDL_HOMO = "https://wsaahomo.afip.gov.ar/ws/services/LoginCms?wsdl"
    
    # TTL por defecto (12 horas)
    DEFAULT_TTL = 43200
    
    def __init__(self, environment='homologation', timeout=30):
        """
        Inicializa el cliente WSAA.
        
        Args:
            environment: 'production' o 'homologation'
            timeout: Timeout para requests en segundos
        """
        self.environment = environment
        self.timeout = timeout
        
        # Seleccionar WSDL según ambiente
        self.wsdl_url = self.WSDL_PROD if environment == 'production' else self.WSDL_HOMO
        
        # Configurar cliente zeep con timeout
        session = Session()
        session.timeout = timeout
        transport = Transport(session=session)
        
        try:
            self.client = Client(self.wsdl_url, transport=transport)
            _logger.info(f"Cliente WSAA inicializado: {environment} - {self.wsdl_url}")
        except Exception as e:
            _logger.error(f"Error al inicializar cliente WSAA: {e}")
            raise
    
    def create_tra(self, service, ttl=None, cuit=None):
        """
        Crea el TRA (Ticket de Requerimiento de Acceso) en formato XML.
        
        El TRA es el documento que se firma y se envía a WSAA para obtener
        las credenciales de acceso.
        
        Args:
            service: Nombre del servicio web (ej: 'wsfe', 'wsfex', 'wsbfe')
            ttl: Time To Live en segundos (default: 12 horas)
            cuit: CUIT del solicitante (opcional, para logging)
            
        Returns:
            String con el XML del TRA
        """
        if ttl is None:
            ttl = self.DEFAULT_TTL
        
        # Calcular tiempos
        now = datetime.now(timezone.utc)
        generation_time = now.strftime('%Y-%m-%dT%H:%M:%S-00:00')
        expiration_time = (now + timedelta(seconds=ttl)).strftime('%Y-%m-%dT%H:%M:%S-00:00')
        unique_id = int(now.timestamp())
        
        _logger.info(f"Creando TRA para servicio '{service}' (TTL: {ttl}s)")
        
        # Construir XML del TRA según especificación AFIP
        tra_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<loginTicketRequest version="1.0">
<header>
    <uniqueId>{unique_id}</uniqueId>
    <generationTime>{generation_time}</generationTime>
    <expirationTime>{expiration_time}</expirationTime>
</header>
<service>{service}</service>
</loginTicketRequest>"""
        
        _logger.debug(f"TRA generado: uniqueId={unique_id}")
        return tra_xml
    
    def sign_tra(self, tra_xml, certificate_pem, private_key_pem):
        """
        Firma el TRA con CMS/PKCS#7 usando el certificado.
        
        Args:
            tra_xml: XML del TRA a firmar
            certificate_pem: Certificado en formato PEM
            private_key_pem: Clave privada en formato PEM
            
        Returns:
            CMS firmado en formato PEM (bytes)
        """
        _logger.info("Firmando TRA con CMS/PKCS#7")
        
        try:
            cms_signed = crypto_utils.sign_cms(
                data=tra_xml.encode('utf-8') if isinstance(tra_xml, str) else tra_xml,
                certificate_pem=certificate_pem,
                private_key_pem=private_key_pem
            )
            
            _logger.info(f"TRA firmado exitosamente: {len(cms_signed)} bytes")
            return cms_signed
            
        except Exception as e:
            _logger.error(f"Error al firmar TRA: {e}")
            raise
    
    def login(self, cms_signed):
        """
        Llama al método LoginCms del WSAA para obtener credenciales.
        
        Args:
            cms_signed: TRA firmado en formato CMS/PKCS#7 (bytes)
            
        Returns:
            Diccionario con token, sign y metadatos
        """
        _logger.info("Llamando a LoginCms de WSAA")
        
        try:
            # Convertir CMS a string si es necesario
            if isinstance(cms_signed, bytes):
                cms_str = cms_signed.decode('utf-8')
            else:
                cms_str = cms_signed
            
            # Llamar al servicio LoginCms
            response = self.client.service.loginCms(cms_str)
            
            _logger.info("Respuesta recibida de LoginCms")
            
            # Parsear la respuesta XML
            result = self._parse_login_response(response)
            
            _logger.info(f"Autenticación exitosa - Token: {result['token'][:20]}...")
            return result
            
        except Exception as e:
            _logger.error(f"Error en LoginCms: {e}")
            raise
    
    def _parse_login_response(self, xml_response):
        """
        Parsea la respuesta XML de LoginCms.
        
        Args:
            xml_response: String con XML de respuesta
            
        Returns:
            Diccionario con campos parseados
        """
        try:
            # Parsear XML
            root = etree.fromstring(xml_response.encode('utf-8') if isinstance(xml_response, str) else xml_response)
            
            # Extraer campos del XML
            # Estructura esperada:
            # <loginTicketResponse>
            #   <header>
            #     <source>CN=wsaa,O=AFIP,C=AR,SERIALNUMBER=CUIT 33693450239</source>
            #     <destination>SERIALNUMBER=CUIT 20123456789,CN=nombre</destination>
            #     <uniqueId>1234567890</uniqueId>
            #     <generationTime>2024-01-10T10:00:00.000-03:00</generationTime>
            #     <expirationTime>2024-01-10T22:00:00.000-03:00</expirationTime>
            #   </header>
            #   <credentials>
            #     <token>PD94bWwgdmVyc2lvbj0iMS4...</token>
            #     <sign>Xy8P9P0T...</sign>
            #   </credentials>
            # </loginTicketResponse>
            
            credentials = root.find('credentials')
            header = root.find('header')
            
            if credentials is None:
                raise ValueError("No se encontró el elemento 'credentials' en la respuesta")
            
            token_elem = credentials.find('token')
            sign_elem = credentials.find('sign')
            
            if token_elem is None or sign_elem is None:
                raise ValueError("No se encontraron token o sign en la respuesta")
            
            result = {
                'token': token_elem.text,
                'sign': sign_elem.text,
            }
            
            # Extraer metadatos del header si están disponibles
            if header is not None:
                unique_id = header.find('uniqueId')
                generation_time = header.find('generationTime')
                expiration_time = header.find('expirationTime')
                
                if unique_id is not None:
                    result['unique_id'] = unique_id.text
                if generation_time is not None:
                    result['generation_time'] = self._parse_datetime(generation_time.text)
                if expiration_time is not None:
                    result['expiration_time'] = self._parse_datetime(expiration_time.text)
            
            return result
            
        except etree.XMLSyntaxError as e:
            _logger.error(f"Error al parsear XML de respuesta: {e}")
            raise ValueError(f"XML de respuesta inválido: {e}")
        except Exception as e:
            _logger.error(f"Error inesperado al parsear respuesta: {e}")
            raise
    
    def _parse_datetime(self, datetime_str):
        """
        Parsea string de fecha/hora de AFIP.
        
        Args:
            datetime_str: String con formato ISO 8601 (ej: '2024-01-10T10:00:00.000-03:00')
            
        Returns:
            datetime object
        """
        try:
            # Remover milisegundos y zona horaria para simplificar parsing
            # Formato típico: 2024-01-10T10:00:00.000-03:00
            dt_clean = datetime_str.split('.')[0]  # Remover milisegundos
            
            # Parsear
            dt = datetime.fromisoformat(dt_clean)
            return dt
            
        except Exception as e:
            _logger.warning(f"No se pudo parsear fecha '{datetime_str}': {e}")
            return datetime_str  # Retornar string original si falla
    
    def authenticate(self, service, certificate_pem, private_key_pem, cuit=None, ttl=None):
        """
        Flujo completo de autenticación: TRA → Firma → Login → Credenciales.
        
        Este es el método principal que debes usar para obtener token y sign.
        
        Args:
            service: Nombre del servicio web ('wsfe', 'wsfex', 'wsbfe', etc.)
            certificate_pem: Certificado X.509 en formato PEM
            private_key_pem: Clave privada en formato PEM
            cuit: CUIT del solicitante (opcional)
            ttl: Time To Live en segundos (opcional, default: 12 horas)
            
        Returns:
            Diccionario con:
                - token: Token de autenticación
                - sign: Firma digital
                - generation_time: Fecha de generación
                - expiration_time: Fecha de expiración
                - unique_id: ID único del ticket
                
        Raises:
            Exception: Si falla algún paso del proceso
        """
        _logger.info(f"Iniciando autenticación WSAA para servicio '{service}'")
        
        try:
            # 1. Crear TRA
            tra_xml = self.create_tra(service=service, ttl=ttl, cuit=cuit)
            
            # 2. Firmar TRA
            cms_signed = self.sign_tra(
                tra_xml=tra_xml,
                certificate_pem=certificate_pem,
                private_key_pem=private_key_pem
            )
            
            # 3. Login en WSAA
            credentials = self.login(cms_signed)
            
            _logger.info(f"Autenticación completada exitosamente para '{service}'")
            return credentials
            
        except Exception as e:
            _logger.error(f"Error en autenticación WSAA: {e}")
            raise
    
    def get_status(self):
        """
        Verifica el estado del servicio WSAA (disponibilidad).
        
        Nota: WSAA no tiene método de status dedicado, pero podemos
        verificar que el WSDL sea accesible.
        
        Returns:
            dict con información de estado
        """
        try:
            # Intentar acceder al WSDL
            services = list(self.client.wsdl.services.values())
            if services:
                service = services[0]
                return {
                    'status': 'OK',
                    'environment': self.environment,
                    'wsdl': self.wsdl_url,
                    'service_name': service.name,
                    'available': True,
                }
            else:
                return {
                    'status': 'ERROR',
                    'environment': self.environment,
                    'available': False,
                    'error': 'No se encontraron servicios en el WSDL'
                }
        except Exception as e:
            _logger.error(f"Error al verificar estado de WSAA: {e}")
            return {
                'status': 'ERROR',
                'environment': self.environment,
                'available': False,
                'error': str(e)
            }
