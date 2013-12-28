#!/usr/bin/python
# -*- coding: latin-1 -*-
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 3, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTIBILITY
# or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
# for more details.

"Módulo para obtener un ticket de autorización del web service WSAA de AFIP"

# Basado en wsaa-client.php de Gerardo Fisanotti - DvSHyS/DiOPIN/AFIP - 13-apr-07
# Definir WSDL, CERT, PRIVATEKEY, PASSPHRASE, SERVICE, WSAAURL
# Devuelve TA.xml (ticket de autorización de WSAA)

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2008-2011 Mariano Reingart"
__license__ = "GPL 3.0"
__version__ = "2.07a"

import hashlib, datetime, email, os, sys, time, traceback
from php import date
from pysimplesoap.client import SimpleXMLElement
from utils import inicializar_y_capturar_excepciones, BaseWS, get_install_dir
try:
    from M2Crypto import BIO, Rand, SMIME, SSL
except ImportError:
    BIO = Rand = SMIME = SSL = None
    from subprocess import Popen, PIPE
    from base64 import b64encode

# Constantes (si se usa el script de linea de comandos)
WSDL = "https://wsaahomo.afip.gov.ar/ws/services/LoginCms?wsdl"  # El WSDL correspondiente al WSAA 
CERT = "reingart.crt"        # El certificado X.509 obtenido de Seg. Inf.
PRIVATEKEY = "reingart.key"  # La clave privada del certificado CERT
PASSPHRASE = "xxxxxxx"  # La contraseña para firmar (si hay)
SERVICE = "wsfe"        # El nombre del web service al que se le pide el TA

# WSAAURL: la URL para acceder al WSAA, verificar http/https y wsaa/wsaahomo
#WSAAURL = "https://wsaa.afip.gov.ar/ws/services/LoginCms" # PRODUCCION!!!
WSAAURL = "https://wsaahomo.afip.gov.ar/ws/services/LoginCms" # homologacion (pruebas)
SOAP_ACTION = 'http://ar.gov.afip.dif.facturaelectronica/' # Revisar WSDL
SOAP_NS = "http://wsaa.view.sua.dvadac.desein.afip.gov"     # Revisar WSDL 

# Verificación del web server remoto
CACERT = "afip_ca_info.crt" # WSAA CA Cert

HOMO = True
TYPELIB = False
DEFAULT_TTL = 60*60*5       # five hours
DEBUG = False

# No debería ser necesario modificar nada despues de esta linea

def create_tra(service=SERVICE,ttl=2400):
    "Crear un Ticket de Requerimiento de Acceso (TRA)"
    tra = SimpleXMLElement(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<loginTicketRequest version="1.0">'
        '</loginTicketRequest>')
    tra.add_child('header')
    # El source es opcional. Si falta, toma la firma (recomendado).
    #tra.header.addChild('source','subject=...')
    #tra.header.addChild('destination','cn=wsaahomo,o=afip,c=ar,serialNumber=CUIT 33693450239')
    tra.header.add_child('uniqueId',date('U'))
    tra.header.add_child('generationTime',date('c',date('U')-ttl))
    tra.header.add_child('expirationTime',date('c',date('U')+ttl))
    tra.add_child('service',service)
    return tra.as_xml()

def sign_tra(tra,cert=CERT,privatekey=PRIVATEKEY):
    "Firmar PKCS#7 el TRA y devolver CMS (recortando los headers SMIME)"

    if BIO:
        # Firmar el texto (tra) usando m2crypto (openssl bindings para python)
        buf = BIO.MemoryBuffer(tra)             # Crear un buffer desde el texto
        #Rand.load_file('randpool.dat', -1)     # Alimentar el PRNG
        s = SMIME.SMIME()                       # Instanciar un SMIME
        if privatekey.startswith("-----BEGIN RSA PRIVATE KEY-----"):
            key_bio = BIO.MemoryBuffer(privatekey)
            crt_bio = BIO.MemoryBuffer(cert)
            s.load_key_bio(key_bio, crt_bio)        # Cargar certificados (buffer)
        elif os.path.exists(privatekey) and os.path.exists(cert):
            s.load_key(privatekey, cert)            # Cargar certificados (archivo)
        else:
            raise RuntimeError("Archivos no encontrados: %s, %s" % (privatekey, cert))
        p7 = s.sign(buf,0)                      # Firmar el buffer
        out = BIO.MemoryBuffer()                # Crear un buffer para la salida 
        s.write(out, p7)                        # Generar p7 en formato mail
        #Rand.save_file('randpool.dat')         # Guardar el estado del PRNG's

        # extraer el cuerpo del mensaje (parte firmada)
        msg = email.message_from_string(out.read())
        for part in msg.walk():
            filename = part.get_filename()
            if filename == "smime.p7m":                 # es la parte firmada?
                return part.get_payload(decode=False)   # devolver CMS
    else:
        # Firmar el texto (tra) usando OPENSSL directamente
        out = Popen(["openssl", "smime", "-sign", 
                     "-signer", cert, "-inkey", privatekey,
                     "-outform","DER", "-nodetach"], 
                    stdin=PIPE, stdout=PIPE, stderr=PIPE).communicate(tra)[0]
        return b64encode(out)

                
def call_wsaa(cms, location = WSAAURL, proxy=None, trace=False):
    "Llamar web service con CMS para obtener ticket de autorización (TA)"

    # creo la nueva clase
    wsaa = WSAA()
    try:
        wsaa.Conectar(proxy=proxy, wsdl=location, cache="")
        ta = wsaa.LoginCMS(cms)
        if not ta:
            raise RuntimeError(wsaa.Excepcion)
        else:
            return ta
    except:
        raise


class WSAA(BaseWS):
    "Interfaz para el WebService de Autenticación y Autorización"
    _public_methods_ = ['CreateTRA', 'SignTRA', 'CallWSAA', 'LoginCMS', 'Conectar',
                        'AnalizarXml', 'ObtenerTagXml', 'Expirado', 'Autenticar',
                        ]
    _public_attrs_ = ['Token', 'Sign', 'ExpirationTime', 'Version', 
                      'XmlRequest', 'XmlResponse', 
                      'InstallDir', 'Traceback', 'Excepcion',
                      'SoapFault', 'LanzarExcepciones',
                    ]
    _readonly_attrs_ = _public_attrs_[:-1]
    _reg_progid_ = "WSAA"
    _reg_clsid_ = "{6268820C-8900-4AE9-8A2D-F0A1EBD4CAC5}"

    if TYPELIB:
        _typelib_guid_ = '{30E9C94B-7385-4534-9A80-DF50FD169253}'
        _typelib_version_ = 2, 4
        _com_interfaces_ = ['IWSAA']

    # Variables globales para BaseWS:
    HOMO = HOMO
    WSDL = WSDL
    Version = "%s %s" % (__version__, HOMO and 'Homologación' or '')
    
    @inicializar_y_capturar_excepciones
    def CreateTRA(self, service="wsfe", ttl=2400):
        "Crear un Ticket de Requerimiento de Acceso (TRA)"
        return create_tra(service,ttl)
        
    @inicializar_y_capturar_excepciones
    def SignTRA(self, tra, cert, privatekey):
        "Firmar el TRA y devolver CMS"
        return sign_tra(str(tra),cert.encode('latin1'),privatekey.encode('latin1'))

    @inicializar_y_capturar_excepciones
    def LoginCMS(self, cms):
        "Obtener ticket de autorización (TA)"
        results = self.client.loginCms(in0=str(cms))
        ta_xml = results['loginCmsReturn'].encode("utf-8")
        self.xml = ta = SimpleXMLElement(ta_xml)
        self.Token = str(ta.credentials.token)
        self.Sign = str(ta.credentials.sign)
        self.ExpirationTime = str(ta.header.expirationTime)
        return ta_xml
            
    def CallWSAA(self, cms, url="", proxy=None):
        "Obtener ticket de autorización (TA) -version retrocompatible-"
        self.Conectar("", url, proxy)
        ta_xml = self.LoginCMS(cms)
        if not ta_xml:
            raise RuntimeError(self.Excepcion)
        return ta_xml

    @inicializar_y_capturar_excepciones
    def Expirado(self, fecha=None):
        "Comprueba la fecha de expiración, devuelve si ha expirado"
        if not fecha:
            fecha = self.ObtenerTagXml('expirationTime')
        now = datetime.datetime.now()
        d = datetime.datetime.strptime(fecha[:19], '%Y-%m-%dT%H:%M:%S')
        return now > d
        

    def Autenticar(self, service, crt, key, wsdl=None, proxy=None, cache=None):
        "Método unificado para obtener el ticket de acceso (cacheado)"

        self.LanzarExcepciones = True
        try:
            # sanity check: verificar las credenciales
            for filename in (crt, key):
                if not os.access(filename,os.R_OK):
                    raise RuntimeError("Imposible abrir %s\n" % filename)
            # creo el nombre para almacenar el TA ... 
            fn = "TA-%s.xml" % hashlib.md5(service + crt + key).hexdigest()
            if cache:
                fn = os.path.join(cache, fn)
            else:
                fn = os.path.join(self.InstallDir, "cache", fn)

            # leer el ticket de acceso (si fue previamente solicitado)
            if not os.path.exists(fn) or \
               os.path.getmtime(fn) + (DEFAULT_TTL) < time.time():    
                # ticket de acceso (TA) vencido, crear un nuevo req. (TRA) 
                if DEBUG: print "Creando TRA..."
                tra = self.CreateTRA(service=service, ttl=DEFAULT_TTL)
                # firmarlo criptográficamente
                if DEBUG: print "Frimando TRA..."
                cms = self.SignTRA(tra, crt, key)
                # concectar con el servicio web:
                if DEBUG: print "Conectando a WSAA..."
                self.Conectar(cache, wsdl, proxy)
                # llamar al método remoto para solicitar el TA
                if DEBUG: print "Llamando WSAA..."
                ta = self.LoginCMS(cms)
                if not ta:
                    raise RuntimeError("Ticket de acceso vacio")
                # grabar el ticket de acceso para poder reutilizarlo luego
                if DEBUG: print "Grabando TA en %s..." % fn
                open(fn, "w").write(ta)                   
            else:
                # leer el ticket de acceso del archivo en cache
                if DEBUG: print "Leyendo TA de %s..." % fn
                ta = open(fn, "r").read()
            # analizar el ticket de acceso y extraer los datos relevantes 
            self.AnalizarXml(xml=ta)
            self.Token = self.ObtenerTagXml("token")
            self.Sign = self.ObtenerTagXml("sign")
        except:
            ta = ""
            if not self.Excepcion:
                # avoid encoding problem when reporting exceptions to the user:
                self.Excepcion = traceback.format_exception_only(sys.exc_type, 
                                                          sys.exc_value)[0]
                self.Traceback = ""
            if DEBUG:
                raise
        return ta
    
        
# busco el directorio de instalación (global para que no cambie si usan otra dll)
INSTALL_DIR = WSAA.InstallDir = get_install_dir()


if __name__=="__main__":
    
    if '--register' in sys.argv or '--unregister' in sys.argv:
        import pythoncom
        if TYPELIB: 
            if '--register' in sys.argv:
                tlb = os.path.abspath(os.path.join(INSTALL_DIR, "wsaa.tlb"))
                print "Registering %s" % (tlb,)
                tli=pythoncom.LoadTypeLib(tlb)
                pythoncom.RegisterTypeLib(tli, tlb)
            elif '--unregister' in sys.argv:
                k = WSAA
                pythoncom.UnRegisterTypeLib(k._typelib_guid_, 
                                            k._typelib_version_[0], 
                                            k._typelib_version_[1], 
                                            0, 
                                            pythoncom.SYS_WIN32)
                print "Unregistered typelib"
        import win32com.server.register
        win32com.server.register.UseCommandLine(WSAA)
    elif "/Automate" in sys.argv:
        # MS seems to like /automate to run the class factories.
        import win32com.server.localserver
        #win32com.server.localserver.main()
        # start the server.
        win32com.server.localserver.serve([WSAA._reg_clsid_])
    else:
        
        # Leer argumentos desde la linea de comando (si no viene tomar default)
        args = [arg for arg in sys.argv if arg.startswith("--")]
        argv = [arg for arg in sys.argv if not arg.startswith("--")]
        crt = len(argv)>1 and argv[1] or CERT
        key = len(argv)>2 and argv[2] or PRIVATEKEY
        service = len(argv)>3 and argv[3] or "wsfe"
        ttl = len(argv)>4 and int(argv[4]) or 36000
        url = len(argv)>5 and argv[5] or WSAAURL
        wrapper = len(argv)>6 and argv[6] or None
        cacert = len(argv)>7 and argv[7] or CACERT
        DEBUG = "--debug" in args

        print >> sys.stderr, "Usando CRT=%s KEY=%s URL=%s SERVICE=%s TTL=%s" % (crt, key, url, service, ttl)

        # creo el objeto para comunicarme con el ws
        wsaa = WSAA()
        wsaa.LanzarExcepciones = True
        
        if '--proxy' in args:
            proxy = sys.argv[sys.argv.index("--proxy")+1]
            print >> sys.stderr, "Usando PROXY:", proxy
        else:
            proxy = None

        ta = wsaa.Autenticar(service, crt, key, url, proxy)
        if not ta:
            if DEBUG:
                print >> sys.stderr, wsaa.Traceback
            sys.exit(u"Excepcion: %s" % wsaa.Excepcion)
                
        else:
            print ta

        if DEBUG:
            print "Source:", wsaa.ObtenerTagXml('source')
            print "UniqueID Time:", wsaa.ObtenerTagXml('uniqueId')
            print "Generation Time:", wsaa.ObtenerTagXml('generationTime')
            print "Expiration Time:", wsaa.ObtenerTagXml('expirationTime')
            print "Expiro?", wsaa.Expirado()
            ##import time; time.sleep(10)
            ##print "Expiro?", wsaa.Expirado()
