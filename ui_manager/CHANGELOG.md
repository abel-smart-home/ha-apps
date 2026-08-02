# Changelog

## 0.2.3

- Activada la validación SHA-256 para todos los componentes administrados.
- Fijadas las huellas aprobadas después de validarlas en dos instalaciones.
- Las descargas con contenido diferente se rechazan antes de instalarse.
- Los componentes instalados con huella incorrecta se reparan usando el paquete aprobado.
- Agregado el estado REPARADO al reporte de mantenimiento.
- El reporte muestra la huella aprobada, la instalada y el resultado de integridad.
- Retirado el código de la prueba controlada de fallo.

## 0.2.2

- Retirada la opción visible de prueba controlada de fallo.
- Agregado inventario SHA-256 de los componentes instalados.
- Las tarjetas utilizan la huella del archivo JavaScript.
- Las integraciones utilizan una huella determinista de su árbol de archivos.
- Se ignoran cachés de Python y archivos temporales.
- Las huellas todavía son informativas y no bloquean actualizaciones.

## 0.2.1

- Agregada una prueba controlada de fallo de descarga.
- La prueba utiliza una carpeta aislada y no modifica componentes reales.
- Cambiado el arranque a manual_only.
- La app no puede configurarse para iniciar automáticamente.
- Confirmado que los errores individuales no detienen el mantenimiento.

## 0.2.0

- Agregado manejo independiente de errores por componente.
- Un fallo ya no detiene el mantenimiento de los demás componentes.
- Agregado reporte de versiones anterior, objetivo y final.
- Agregados estados VERIFICADO, INSTALADO, ACTUALIZADO, OMITIDO y ERROR.
- Agregada validación de la versión interna de integraciones.
- Las descargas o paquetes inválidos conservan la versión anterior.
- El reporte se genera incluso cuando existen errores.

## 0.1.15

- Limitado el historial a los 20 reportes más recientes.
- latest.txt no se incluye dentro del límite.
- Los reportes históricos más antiguos se eliminan automáticamente.
- Agregado al registro el número de reportes eliminados.

## 0.1.14

- Agregados reportes de mantenimiento.
- El reporte muestra componentes activados, omitidos y versiones instaladas.
- El reporte indica si es necesario reiniciar Home Assistant Core.
- Se conserva un reporte con fecha y un archivo latest.txt.

## 0.1.13

- Corregido el reinicio continuo después del mantenimiento.
- Permitido desactivar manualmente el inicio al arrancar.
- La aplicación continúa ejecutándose una sola vez y se detiene al finalizar.

## 0.1.12

- La aplicación ahora funciona únicamente bajo ejecución manual.
- Eliminado el inicio automático con Home Assistant.
- La aplicación se detiene al finalizar el mantenimiento.
- Agregado un mensaje indicando si es necesario reiniciar Home Assistant Core.

## 0.1.11

- Agregadas opciones para activar o desactivar componentes.
- Cada instalación puede elegir las tarjetas e integraciones administradas.
- Desactivar un componente no elimina sus archivos existentes.
- Agregados mensajes de registro para componentes desactivados.

## 0.1.10

- Corregida la instalación de Spook.
- Ahora se utiliza el paquete oficial spook.zip.
- Agregado soporte para integraciones cuyos archivos están en la raíz del ZIP.
- Corregido el problema de versión interna 0.0.0 de Spook.
- Forzada una nueva compilación de la aplicación.

## 0.1.9

- Primer intento de corrección de la instalación de Spook.

## 0.1.8

- Agregado Spook 5.0.0.
- Instalación automática de la integración Spook.
- Agregados respaldo y restauración de versiones anteriores de Spook.

## 0.1.7

- Agregado SonoffLAN 3.12.2.
- Instalación automática de la integración SonoffLAN.
- Agregados respaldo y rollback para integraciones personalizadas.
- Agregada validación de archivos ZIP.

## 0.1.6

- Agregado Modern Circular Gauge 0.14.1.
- Instalación y registro automático de Modern Circular Gauge.

## 0.1.5

- Corregido el metadato de versión de la aplicación.
- Agregado el historial de cambios.

## 0.1.4

- Agregado Mushroom 5.2.2.
- Instalación y registro automático de Mushroom.

## 0.1.3

- Agregado el registro automático de recursos de los dashboards.

## 0.1.2

- Agregado Mini Graph Card 0.13.0.
- Instalación automática dentro de la carpeta de configuración.
