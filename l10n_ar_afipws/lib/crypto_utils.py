# -*- coding: utf-8 -*-
"""
Utilidades criptográficas para certificados AFIP/ARCA.
Reemplaza OpenSSL y M2Crypto con cryptography.
"""

import logging
from datetime import datetime, timezone
from typing import Tuple

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography.x509.oid import NameOID

_logger = logging.getLogger(__name__)


def generate_rsa_key(key_size: int = 2048) -> bytes:
    """
    Genera una clave privada RSA.
    
    Reemplaza: OpenSSL.crypto.PKey().generate_key()
    
    Args:
        key_size: Tamaño de la clave en bits (default: 2048)
        
    Returns:
        Clave privada en formato PEM (bytes)
    """
    _logger.info(f"Generando clave RSA de {key_size} bits")
    
    # Generar clave privada
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
        backend=default_backend()
    )
    
    # Serializar a PEM
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,  # BEGIN RSA PRIVATE KEY
        encryption_algorithm=serialization.NoEncryption()
    )
    
    _logger.info("Clave RSA generada exitosamente")
    return pem


def create_csr(
    private_key_pem: bytes,
    country_code: str,
    state_name: str,
    city: str,
    company_name: str,
    department: str,
    common_name: str,
    cuit: str
) -> bytes:
    """
    Crea un Certificate Signing Request (CSR).
    
    Reemplaza: OpenSSL.crypto.X509Req()
    
    Args:
        private_key_pem: Clave privada en formato PEM
        country_code: Código de país (ej: "AR")
        state_name: Provincia (ej: "Buenos Aires")
        city: Ciudad
        company_name: Razón social
        department: Departamento
        common_name: Nombre común
        cuit: CUIT sin guiones
        
    Returns:
        CSR en formato PEM (bytes)
    """
    _logger.info(f"Creando CSR para CUIT {cuit}")
    
    # Cargar clave privada
    private_key = serialization.load_pem_private_key(
        private_key_pem,
        password=None,
        backend=default_backend()
    )
    
    # Construir subject del certificado
    subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, country_code),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, state_name),
        x509.NameAttribute(NameOID.LOCALITY_NAME, city),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, company_name),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, department),
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        x509.NameAttribute(NameOID.SERIAL_NUMBER, f"CUIT {cuit}"),
    ])
    
    # Crear CSR
    csr = x509.CertificateSigningRequestBuilder().subject_name(
        subject
    ).sign(private_key, hashes.SHA256(), backend=default_backend())
    
    # Serializar a PEM
    pem = csr.public_bytes(serialization.Encoding.PEM)
    
    _logger.info("CSR creado exitosamente")
    return pem


def load_private_key(pem_data: str) -> rsa.RSAPrivateKey:
    """
    Carga una clave privada desde formato PEM.
    
    Soporta tanto "BEGIN RSA PRIVATE KEY" como "BEGIN PRIVATE KEY".
    
    Args:
        pem_data: Clave en formato PEM (str o bytes)
        
    Returns:
        Objeto RSAPrivateKey
    """
    if isinstance(pem_data, str):
        pem_data = pem_data.encode('utf-8')
    
    # Intentar cargar como PKCS#8 (BEGIN PRIVATE KEY)
    try:
        private_key = serialization.load_pem_private_key(
            pem_data,
            password=None,
            backend=default_backend()
        )
        return private_key
    except Exception as e:
        _logger.error(f"Error al cargar clave privada: {e}")
        raise ValueError(f"No se pudo cargar la clave privada: {e}")


def load_certificate(pem_data: str) -> x509.Certificate:
    """
    Carga un certificado desde formato PEM.
    
    Args:
        pem_data: Certificado en formato PEM (str o bytes)
        
    Returns:
        Objeto Certificate
    """
    if isinstance(pem_data, str):
        pem_data = pem_data.encode('utf-8')
    
    try:
        certificate = x509.load_pem_x509_certificate(
            pem_data,
            backend=default_backend()
        )
        return certificate
    except Exception as e:
        _logger.error(f"Error al cargar certificado: {e}")
        raise ValueError(f"No se pudo cargar el certificado: {e}")


def sign_cms(
    data: bytes,
    certificate_pem: str,
    private_key_pem: str
) -> bytes:
    """
    Firma datos usando CMS/PKCS#7 (Cryptographic Message Syntax).
    
    Reemplaza: M2Crypto firma PKCS#7
    
    Este es el método crítico para firmar el TRA (Ticket de Requerimiento
    de Acceso) que se envía a WSAA de AFIP.
    
    Args:
        data: Datos a firmar (XML TRA)
        certificate_pem: Certificado en formato PEM
        private_key_pem: Clave privada en formato PEM
        
    Returns:
        CMS firmado en formato PEM (bytes)
        
    Raises:
        ValueError: Si hay error en la firma
    """
    _logger.info("Firmando datos con CMS/PKCS#7")
    
    try:
        # Cargar certificado y clave
        certificate = load_certificate(certificate_pem)
        private_key = load_private_key(private_key_pem)
        
        # Asegurar que data es bytes
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        # Crear firma PKCS#7
        # Nota: AFIP requiere firma "detached" (sin incluir el contenido)
        options = [pkcs7.PKCS7Options.DetachedSignature]
        
        cms_signed = (
            pkcs7.PKCS7SignatureBuilder()
            .set_data(data)
            .add_signer(certificate, private_key, hashes.SHA256())
            .sign(serialization.Encoding.PEM, options)
        )
        
        _logger.info("Datos firmados exitosamente con CMS/PKCS#7")
        return cms_signed
        
    except Exception as e:
        _logger.error(f"Error al firmar con CMS: {e}")
        raise ValueError(f"Error al firmar datos con CMS: {e}")


def convert_key_format(private_key_pem: str) -> str:
    """
    Convierte formato de clave privada si es necesario.
    
    Conversión: "BEGIN PRIVATE KEY" → "BEGIN RSA PRIVATE KEY"
    (Para compatibilidad con código legacy si fuera necesario)
    
    Args:
        private_key_pem: Clave en formato PEM
        
    Returns:
        Clave convertida al formato requerido
    """
    if isinstance(private_key_pem, bytes):
        private_key_pem = private_key_pem.decode('utf-8')
    
    # Si ya está en formato RSA PRIVATE KEY, retornar
    if "BEGIN RSA PRIVATE KEY" in private_key_pem:
        return private_key_pem
    
    # Si está en formato PKCS#8, convertir a Traditional OpenSSL
    if "BEGIN PRIVATE KEY" in private_key_pem:
        _logger.info("Convirtiendo clave de PKCS#8 a Traditional OpenSSL")
        
        private_key = load_private_key(private_key_pem)
        
        # Re-serializar en formato Traditional
        pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        return pem.decode('utf-8')
    
    # Si no tiene ningún header conocido, retornar tal cual
    return private_key_pem


def verify_certificate(certificate_pem: str) -> dict:
    """
    Verifica y extrae información de un certificado.
    
    Args:
        certificate_pem: Certificado en formato PEM
        
    Returns:
        Diccionario con información del certificado
    """
    certificate = load_certificate(certificate_pem)
    
    # Extraer información
    subject = certificate.subject
    issuer = certificate.issuer
    
    info = {
        'subject': {
            'common_name': subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value if subject.get_attributes_for_oid(NameOID.COMMON_NAME) else None,
            'organization': subject.get_attributes_for_oid(NameOID.ORGANIZATION_NAME)[0].value if subject.get_attributes_for_oid(NameOID.ORGANIZATION_NAME) else None,
            'country': subject.get_attributes_for_oid(NameOID.COUNTRY_NAME)[0].value if subject.get_attributes_for_oid(NameOID.COUNTRY_NAME) else None,
        },
        'issuer': {
            'common_name': issuer.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value if issuer.get_attributes_for_oid(NameOID.COMMON_NAME) else None,
            'organization': issuer.get_attributes_for_oid(NameOID.ORGANIZATION_NAME)[0].value if issuer.get_attributes_for_oid(NameOID.ORGANIZATION_NAME) else None,
        },
        'valid_from': certificate.not_valid_before_utc,
        'valid_until': certificate.not_valid_after_utc,
        'serial_number': certificate.serial_number,
        'is_valid': datetime.now(timezone.utc) <= certificate.not_valid_after_utc,
    }
    
    return info
