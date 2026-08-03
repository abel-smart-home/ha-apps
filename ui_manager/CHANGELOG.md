# Changelog

## 0.5.0

- Agregada comprobación de compatibilidad mínima con Home Assistant Core.
- La versión actual se obtiene mediante el proxy interno oficial de Home Assistant.
- Agregado el campo opcional `min_home_assistant` al catálogo `components.json`.
- Los componentes incompatibles se omiten antes de descargar o modificar archivos.
- Agregado el estado `INCOMPATIBLE` al reporte de mantenimiento.
- El reporte muestra la versión actual de Home Assistant, el mínimo requerido y el resultado de compatibilidad.
- SonoffLAN 3.12.2 requiere Home Assistant 2023.2.0 o posterior.
- Spook 5.0.0 requiere Home Assistant 2026.3.0 o posterior.
- Si no es posible consultar Home Assistant, los componentes con requisito mínimo no se modifican.
- Agregada una prueba controlada de solo lectura con un catálogo ficticio incompatible.
- La prueba confirma que el componente incompatible no se descarga ni se instala.

## 0.4.1

- Agregada la selección segura `latest_good` para restauraciones.
- `latest_good` omite automáticamente respaldos SUSPECT, UNKNOWN e INVALID.
- Los respaldos se clasifican como GOOD, SUSPECT o UNKNOWN.
- Los respaldos previos a una actualización se marcan como GOOD.
- Los respaldos creados antes de reparar una huella incorrecta se marcan como SUSPECT.
- Los respaldos previos a una restauración se clasifican comparando su SHA-256 con el catálogo aprobado.
- Agregado inventario de respaldos con fecha, versión, motivo, clasificación y SHA-256.
- El inventario se actualiza después de cada mantenimiento y restauración.
- Se conserva al menos el respaldo GOOD más reciente dentro del límite configurado.
- Agregada una prueba controlada y aislada para validar `latest_good` y la restauración.
- La prueba controlada no modifica integraciones reales.

## 0.4.0

- Agregada restauración manual de respaldos para integraciones personalizadas.
- La restauración funciona como un modo exclusivo y no ejecuta el mantenimiento normal.
- Se puede restaurar el respaldo más reciente o seleccionar uno por fecha.
- Antes de restaurar se crea un respaldo de seguridad de la integración actual.
- Agregados metadatos con versión y SHA-256 para respaldos nuevos.
- Los respaldos antiguos sin metadatos siguen siendo compatibles.
- Limitados los respaldos a un valor configurable entre 1 y 20 por integración.
- El valor predeterminado conserva los últimos 5 respaldos.
- Agregados reportes de restauración y retención de los últimos 20 reportes.
- Agregada validación para impedir inventario y restauración simultáneos.

## 0.3.0

- Agregado components.json como catálogo único de componentes.
- Versiones, URL, rutas de instalación y huellas SHA-256 se administran en un solo archivo.
- Agregado component_manager.py para procesar dinámicamente el catálogo.
- Eliminadas del run.sh las definiciones repetidas de componentes.
- El reporte de mantenimiento ahora obtiene nombres, opciones, rutas y huellas desde el catálogo.
- Agregada validación del esquema, campos obligatorios, URL HTTPS y huellas SHA-256.
- El mantenimiento se cancela si components.json es inválido.
- Se conserva el modo de inventario local de solo lectura.
- Se conserva el manejo independiente de errores y la reparación por integridad.

## 0.2.4

- Agregado modo de inventario local SHA-256 en solo lectura.
- Permite calcular la huella de tarjetas ya instaladas por HACS.
- Permite calcular la huella de integraciones ya instaladas por HACS.
- El modo de inventario no instala, actualiza, repara ni elimina componentes.
- Las rutas se limitan a la carpeta /config.
- Las integraciones se validan mediante manifest.json.
- Se generan reportes en /config/ui-manager/checksum-candidates.
- Se conservan los últimos 20 inventarios y latest.txt.
- El inventario local es exclusivo y omite el mantenimiento normal.

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
