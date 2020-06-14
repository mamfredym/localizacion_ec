import OpenSSL.crypto
from OpenSSL.crypto import load_pkcs12, dump_certificate, sign
from Crypto.PublicKey import RSA
from Crypto.Util.asn1 import (DerSequence)
from datetime import datetime
import codecs
import random
import base64
import hashlib


def get_random():
    return '%s%s%s%s%s%s' % (
        random.randint(1, 9),
        random.randint(1, 9),
        random.randint(1, 9),
        random.randint(1, 9),
        random.randint(1, 9),
        random.randint(1, 9),
    )


def main():
    p12 = load_pkcs12(open('key.p12', 'rb').read(), b'CXGV2412')
    pkey = p12.get_privatekey()
    cert = p12.get_certificate().to_cryptography()
    x509_cert = p12.get_certificate()
    certificado = dump_certificate(OpenSSL.crypto.FILETYPE_PEM, cert).decode().replace(
        '-----BEGIN CERTIFICATE-----', '').replace('-----END CERTIFICATE-----', '').replace('\n', '')
    pub_key = x509_cert.get_pubkey()
    pub_key_asn1 = OpenSSL.crypto.dump_privatekey(
        OpenSSL.crypto.FILETYPE_ASN1, pub_key)
    pub_der = DerSequence()
    pub_der.decode(pub_key_asn1)
    x509_data = RSA.construct((int(pub_der._seq[1]), int(pub_der._seq[2])))
    e = hex(x509_data.e).replace('0x', '0')
    exponent = codecs.encode(codecs.decode(
        e, 'hex_codec'), 'base64').decode().replace('\n', '')
    n = hex(x509_data.n).replace('0x', '')
    modulus = codecs.encode(codecs.decode(n, 'hex_codec'), 'base64').decode()
    certificateX509_der_hash = base64.b64encode(
        x509_cert.digest("sha1")).decode().replace('\n', '')
    X509SerialNumber = str(cert.serial_number)
    issuer = x509_cert.get_issuer()
    issuer_name = 'CN=%s,L=%s,OU=%s,O=%s,C=%s' % (
        issuer.CN, issuer.L, issuer.OU, issuer.O, issuer.C
    )
    xml_content = open('invoice.xml').read()
    to_sign = xml_content.replace(
        "<?xml version='1.0' encoding='UTF-8'?>\n", '')
    firma_SignedInfo = base64.b64encode(
        sign(pkey, to_sign.encode(), "sha1")).decode()

    sha1_factura = hashlib.sha1(to_sign.encode()).hexdigest()

    xmlns = 'xmlns:ds="http://www.w3.org/2000/09/xmldsig#" xmlns:etsi="http://uri.etsi.org/01903/v1.3.2#"'
    Certificate_number = get_random()
    Signature_number = get_random()
    SignedProperties_number = get_random()
    SignedInfo_number = get_random()
    SignedPropertiesID_number = get_random()
    Reference_ID_number = get_random()
    SignatureValue_number = get_random()
    Object_number = get_random()
    SignedProperties = ''
    SignedProperties += '<etsi:SignedProperties Id="Signature' + \
        Signature_number + '-SignedProperties' + SignedProperties_number + '">'
    SignedProperties += '<etsi:SignedSignatureProperties>'
    SignedProperties += '<etsi:SigningTime>'

    SignedProperties += datetime.now().strftime('%Y-%m-%dT%H:%M:%S%z')

    SignedProperties += '</etsi:SigningTime>'
    SignedProperties += '<etsi:SigningCertificate>'
    SignedProperties += '<etsi:Cert>'
    SignedProperties += '<etsi:CertDigest>'
    SignedProperties += '<ds:DigestMethod Algorithm="http://www.w3.org/2000/09/xmldsig#sha1">'
    SignedProperties += '</ds:DigestMethod>'
    SignedProperties += '<ds:DigestValue>'

    SignedProperties += certificateX509_der_hash

    SignedProperties += '</ds:DigestValue>'
    SignedProperties += '</etsi:CertDigest>'
    SignedProperties += '<etsi:IssuerSerial>'
    SignedProperties += '<ds:X509IssuerName>'
    SignedProperties += issuer_name
    SignedProperties += '</ds:X509IssuerName>'
    SignedProperties += '<ds:X509SerialNumber>'

    SignedProperties += X509SerialNumber

    SignedProperties += '</ds:X509SerialNumber>'
    SignedProperties += '</etsi:IssuerSerial>'
    SignedProperties += '</etsi:Cert>'
    SignedProperties += '</etsi:SigningCertificate>'
    SignedProperties += '</etsi:SignedSignatureProperties>'
    SignedProperties += '<etsi:SignedDataObjectProperties>'
    SignedProperties += '<etsi:DataObjectFormat ObjectReference="#Reference-ID-' + \
        Reference_ID_number + '">'
    SignedProperties += '<etsi:Description>'

    SignedProperties += 'contenido comprobante'

    SignedProperties += '</etsi:Description>'
    SignedProperties += '<etsi:MimeType>'
    SignedProperties += 'text/xml'
    SignedProperties += '</etsi:MimeType>'
    SignedProperties += '</etsi:DataObjectFormat>'
    SignedProperties += '</etsi:SignedDataObjectProperties>'
    SignedProperties += '</etsi:SignedProperties>'
    SignedProperties

    SignedProperties_para_hash = SignedProperties.replace(
        '<etsi:SignedProperties', '<etsi:SignedProperties ' + xmlns).encode()
    sha1_SignedProperties = hashlib.sha1(SignedProperties_para_hash).hexdigest()

    KeyInfo = ''

    KeyInfo += '<ds:KeyInfo Id="Certificate' + Certificate_number + '">'
    KeyInfo += '\n<ds:X509Data>'
    KeyInfo += '\n<ds:X509Certificate>\n'

    KeyInfo += certificado

    KeyInfo += '\n</ds:X509Certificate>'
    KeyInfo += '\n</ds:X509Data>'
    KeyInfo += '\n<ds:KeyValue>'
    KeyInfo += '\n<ds:RSAKeyValue>'
    KeyInfo += '\n<ds:Modulus>\n'

    KeyInfo += modulus

    KeyInfo += '</ds:Modulus>'
    KeyInfo += '\n<ds:Exponent>'

    KeyInfo += exponent

    KeyInfo += '</ds:Exponent>'
    KeyInfo += '\n</ds:RSAKeyValue>'
    KeyInfo += '\n</ds:KeyValue>'
    KeyInfo += '\n</ds:KeyInfo>'

    KeyInfo_para_hash = KeyInfo.replace('<ds:KeyInfo', '<ds:KeyInfo ' + xmlns)
    sha1_certificado = hashlib.sha1(KeyInfo_para_hash.encode()).hexdigest()

    SignedInfo = ''

    SignedInfo += '<ds:SignedInfo Id="Signature-SignedInfo' + SignedInfo_number + '">'
    SignedInfo += '\n<ds:CanonicalizationMethod Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315">'
    SignedInfo += '</ds:CanonicalizationMethod>'
    SignedInfo += '\n<ds:SignatureMethod Algorithm="http://www.w3.org/2000/09/xmldsig#rsa-sha1">'
    SignedInfo += '</ds:SignatureMethod>'
    SignedInfo += '\n<ds:Reference Id="SignedPropertiesID' + SignedPropertiesID_number + \
        '" Type="http://uri.etsi.org/01903#SignedProperties" URI="#Signature' + \
        Signature_number + '-SignedProperties' + SignedProperties_number + '">'
    SignedInfo += '\n<ds:DigestMethod Algorithm="http://www.w3.org/2000/09/xmldsig#sha1">'
    SignedInfo += '</ds:DigestMethod>'
    SignedInfo += '\n<ds:DigestValue>'

    SignedInfo += sha1_SignedProperties

    SignedInfo += '</ds:DigestValue>'
    SignedInfo += '\n</ds:Reference>'
    SignedInfo += '\n<ds:Reference URI="#Certificate' + Certificate_number + '">'
    SignedInfo += '\n<ds:DigestMethod Algorithm="http://www.w3.org/2000/09/xmldsig#sha1">'
    SignedInfo += '</ds:DigestMethod>'
    SignedInfo += '\n<ds:DigestValue>'

    SignedInfo += sha1_certificado

    SignedInfo += '</ds:DigestValue>'
    SignedInfo += '\n</ds:Reference>'
    SignedInfo += '\n<ds:Reference Id="Reference-ID-' + \
        Reference_ID_number + '" URI="#comprobante">'
    SignedInfo += '\n<ds:Transforms>'
    SignedInfo += '\n<ds:Transform Algorithm="http://www.w3.org/2000/09/xmldsig#enveloped-signature">'
    SignedInfo += '</ds:Transform>'
    SignedInfo += '\n</ds:Transforms>'
    SignedInfo += '\n<ds:DigestMethod Algorithm="http://www.w3.org/2000/09/xmldsig#sha1">'
    SignedInfo += '</ds:DigestMethod>'
    SignedInfo += '\n<ds:DigestValue>'

    SignedInfo += sha1_factura

    SignedInfo += '</ds:DigestValue>'
    SignedInfo += '\n</ds:Reference>'
    SignedInfo += '\n</ds:SignedInfo>'

    SignedInfo_para_firma = SignedInfo.replace(
        '<ds:SignedInfo', '<ds:SignedInfo ' + xmlns)

    xades_bes = ''

    xades_bes += '<ds:Signature ' + xmlns + \
        ' Id="Signature' + Signature_number + '">'
    xades_bes += '\n' + SignedInfo

    xades_bes += '\n<ds:SignatureValue Id="SignatureValue' + \
        SignatureValue_number + '">\n'

    xades_bes += firma_SignedInfo

    xades_bes += '\n</ds:SignatureValue>'

    xades_bes += '\n' + KeyInfo

    xades_bes += '\n<ds:Object Id="Signature' + \
        Signature_number + '-Object' + Object_number + '">'
    xades_bes += '<etsi:QualifyingProperties Target="#Signature' + Signature_number + '">'

    xades_bes += SignedProperties

    xades_bes += '</etsi:QualifyingProperties>'
    xades_bes += '</ds:Object>'
    xades_bes += '</ds:Signature>'
    xml_signed = xml_content.replace("</factura>", xades_bes + "</factura>")

    print(xml_signed)
    myfile = open("invoice_test_sign2.xml", "w")
    myfile.write(xml_signed)
    myfile.close()


if __name__ == '__main__':
    main()
