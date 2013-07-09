/* 
 * Ejemplo de Uso de Biblioteca LibPyAfipWs (.DLL / .so)
 * con Web Service Autenticaci�n / Factura Electr�nica AFIP
 * 2013 (C) Mariano Reingart <reingart@gmail.com>
 * Licencia: GPLv3
 * Requerimientos: scripts wsaa.py y libpyafipws.h / libpyafipws.c
 * Documentacion: 
 *  http://www.sistemasagiles.com.ar/trac/wiki/LibPyAfipWs
 *  http://www.sistemasagiles.com.ar/trac/wiki/ManualPyAfipWs
 */

#include "libpyafipws.h"

#if defined(__GNUC__)
#include <stdio.h>
#include <stdlib.h>
#endif

int main(int argc, char *argv[]) {
  char *tra, *cms, *ta;
  void *wsfev1;
  char *ret;
  bool ok;
  
  /* prueba generica */
  test();
  
  /* Generar ticket de requerimiento de acceso */
  tra = WSAA_CreateTRA("wsfe", 999);
  printf("TRA:\n%s\n", tra);
  /* Firmar criptograficamente el mensaje */
  cms = WSAA_SignTRA(tra, "reingart.crt", "reingart.key");
  printf("CMS:\n%s\n", cms);  
  /* Llamar al webservice y obtener el ticket de acceso */
  ta = WSAA_LoginCMS(cms);
  printf("TA:\n%s\n", ta);
  
  /* Crear una objeto WSFEv1 (interfaz webservice factura electronica) */
  wsfev1 = PYAFIPWS_CreateObject("wsfev1", "WSFEv1");
  printf("crear wsfev1: %p\n", wsfev1);    /* si funicon� ok, no debe ser NULL! */  
  /* conectar al webservice (para produccion cambiar URL) */
  ok = WSFEv1_Conectar(wsfev1, "", "", "");
  printf("concetar: %s", ok ? "true" : "false");
  
  /* obtener el estado de los servidores */
  ok = WSFEv1_Dummy(wsfev1);
  printf("llamar a dummy: %s\n", ok ? "true" : "false");
  /* obtener los atributos devueltos por AFIP */
  ret = PYAFIPWS_Get(wsfev1, "AppServerStatus");
  printf("dummy AppServerStatus: %s\n", ret);
  free(ret);
  ret = PYAFIPWS_Get(wsfev1, "DbServerStatus");
  printf("dummy DbServerStatus: %s\n", ret);
  free(ret);
  ret = PYAFIPWS_Get(wsfev1, "AuthServerStatus");
  printf("dummy AuthServerStatus: %s\n", ret);
  free(ret);
  
  /* establezco los datos para operar el webservice */
  ok = PYAFIPWS_Set(wsfev1, "Cuit", "267565393");
  ok = WSFEv1_SetTicketAcceso(wsfev1, ta);

  /* destruir el objeto */
  PYAFIPWS_DestroyObject(wsfev1);  


  /* liberar la memoria adquirida para los valores devueltos de WSAA */
  free(ta);
  free(cms);
  free(tra);

  return 0;
}

