# Documentación de Smart Home UI Manager

## Propósito

Smart Home UI Manager es una herramienta manual de mantenimiento para Home Assistant OS. Instala, valida, actualiza, repara, diagnostica, inventaría y restaura componentes personalizados aprobados por el instalador.

La aplicación está pensada para ejecutarse durante mantenimiento y detenerse al terminar. No está diseñada para permanecer ejecutándose de forma continua.

> **Fuente de verdad:** las versiones, URLs, SHA-256, rutas y requisitos mínimos aprobados de cada componente están en `ui_manager/components.json`. Esta documentación explica el procedimiento, pero si existe una diferencia con el catálogo, debe revisarse `components.json`.

---

# Ajustes recomendados

Mantén normalmente:

- **Iniciar al arrancar:** desactivado.
- **Watchdog:** desactivado.
- **Actualización automática:** desactivada.

Actualiza Smart Home UI Manager mientras esté detenida. Después guarda la configuración y presiona **Iniciar** una sola vez.

---

# Regla principal de rutas

Dentro del contenedor de Smart Home UI Manager, la carpeta de configuración de Home Assistant siempre se encuentra en:

```text
/config
```

Aunque File Editor, Studio Code Server u otra herramienta muestre la misma carpeta como `/homeassistant`, dentro de Smart Home UI Manager debes utilizar `/config`.

| Ruta vista en otras herramientas | Ruta en Smart Home UI Manager |
|---|---|
| `/homeassistant/www/...` | `/config/www/...` |
| `/homeassistant/custom_components/...` | `/config/custom_components/...` |
| `/homeassistant/configuration.yaml` | `/config/configuration.yaml` |

Ejemplo correcto para Mushroom instalada mediante HACS:

```text
/config/www/community/lovelace-mushroom/mushroom.js
```

Ejemplo incorrecto:

```text
/homeassistant/www/community/lovelace-mushroom/mushroom.js
```

---

# Prioridad de los modos de operación

Los modos especiales son exclusivos.

| Opción activa | Operación |
|---|---|
| `local_inventory_enabled: true` | Solo calcula SHA-256 local |
| `restore_backup_enabled: true` | Solo restaura un respaldo |
| `diagnostic_only_enabled: true` | Solo realiza diagnóstico |
| Todas las anteriores en `false` | Mantenimiento normal |

Después de usar un modo especial, vuelve a desactivarlo.

---

# Referencia de opciones

## `diagnostic_only_enabled`

Ejecuta únicamente el diagnóstico previo. No instala, actualiza, repara ni restaura componentes.

```yaml
diagnostic_only_enabled: true
local_inventory_enabled: false
restore_backup_enabled: false
```

Procedimiento:

1. Activa **Solo diagnóstico**.
2. Guarda la configuración.
3. Inicia la aplicación una vez.
4. Revisa:

```text
/config/ui-manager/diagnostics/latest.txt
```

5. Confirma que no existan fallos críticos.
6. Vuelve a configurar:

```yaml
diagnostic_only_enabled: false
```

Úsalo después de instalar o actualizar UI Manager, antes de un mantenimiento importante o cuando cambie Home Assistant OS/Core.

---

## `minimum_free_space_mb`

Espacio libre mínimo requerido en `/config` antes del mantenimiento.

```yaml
minimum_free_space_mb: 200
```

Rango permitido:

```text
50 a 5000 MB
```

Si no hay suficiente espacio, el mantenimiento se bloquea antes de modificar componentes.

---

## `local_inventory_enabled`

Activa el inventario local SHA-256 de un componente ya instalado.

```yaml
local_inventory_enabled: true
```

Mientras esté activo, no se ejecuta mantenimiento normal.

Reporte:

```text
/config/ui-manager/checksum-candidates/latest.txt
```

Al terminar:

```yaml
local_inventory_enabled: false
```

---

## `local_inventory_type`

Lista seleccionable con dos valores:

```text
frontend
integration
```

Usa `frontend` para tarjetas o archivos individuales, normalmente `.js`:

```yaml
local_inventory_type: frontend
```

Usa `integration` para carpetas completas de integraciones que contienen `manifest.json`:

```yaml
local_inventory_type: integration
```

---

## `local_inventory_name`

Nombre descriptivo para el reporte.

```yaml
local_inventory_name: Mushroom
```

```yaml
local_inventory_name: Smart Entity Timer
```

No determina la ruta ni el ID interno.

---

## `local_inventory_version`

Versión que estás evaluando.

```yaml
local_inventory_version: 5.2.2
```

También puede escribirse con `v` si así identificas la publicación:

```yaml
local_inventory_version: v0.3.0
```

Para integraciones, confirma que corresponda a la versión detectada en `manifest.json`.

---

## `local_inventory_path`

Debe estar dentro de `/config`.

Tarjeta:

```yaml
local_inventory_path: /config/www/community/lovelace-mushroom/mushroom.js
```

Integración:

```yaml
local_inventory_path: /config/custom_components/smart_entity_timer
```

Error frecuente:

```text
No such file or directory: '/homeassistant'
```

Solución: sustituye `/homeassistant` por `/config`.

---

# Inventario SHA-256 de una tarjeta

Ejemplo con Mushroom instalada mediante HACS:

```yaml
local_inventory_enabled: true
local_inventory_type: frontend
local_inventory_name: Mushroom
local_inventory_version: 5.2.2
local_inventory_path: /config/www/community/lovelace-mushroom/mushroom.js
```

1. Instala o actualiza la versión en un laboratorio mediante HACS.
2. Confirma que el archivo exista.
3. Usa la ruta equivalente comenzando en `/config`.
4. Guarda la configuración.
5. Inicia UI Manager una vez.
6. Abre:

```text
/config/ui-manager/checksum-candidates/latest.txt
```

7. Copia la SHA-256.
8. Cuando sea posible, repite la comprobación en una segunda instalación.
9. Desactiva `local_inventory_enabled`.

La huella corresponde al archivo JavaScript instalado.

---

# Inventario SHA-256 de una integración

Ejemplo con Smart Entity Timer:

```yaml
local_inventory_enabled: true
local_inventory_type: integration
local_inventory_name: Smart Entity Timer
local_inventory_version: v0.3.0
local_inventory_path: /config/custom_components/smart_entity_timer
```

1. Instala o actualiza la versión en un laboratorio.
2. Confirma que exista la carpeta.
3. Confirma que incluya `manifest.json`.
4. Comprueba la versión detectada.
5. Inicia UI Manager una vez.
6. Abre:

```text
/config/ui-manager/checksum-candidates/latest.txt
```

7. Copia la huella del árbol de archivos.
8. Cuando sea posible, repite la comprobación en otra instalación.
9. Desactiva `local_inventory_enabled`.

> Para integraciones, la SHA-256 aprobada por UI Manager corresponde al **árbol de archivos instalado**, no al SHA-256 del ZIP descargado.

---

# Cómo obtener la URL correcta de un componente

No todos los proyectos publican sus archivos de la misma forma. Antes de editar `components.json`, identifica cómo publica el desarrollador el artefacto que realmente se instala.

La regla principal es:

> Usa una URL fija asociada a una versión o tag. No uses `main`, `master`, `latest` ni otra referencia mutable.

Hay cuatro casos comunes.

---

## Caso A: archivo adjunto a un GitHub Release

Es el caso de proyectos que publican directamente el archivo instalable dentro de **Assets**.

### Ejemplo: Mushroom

En la release `v5.2.2` se publica:

```text
mushroom.js
```

Patrón:

```text
https://github.com/ORGANIZACION/REPOSITORIO/releases/download/TAG/ARCHIVO
```

Ejemplo:

```text
https://github.com/piitaya/lovelace-mushroom/releases/download/v5.2.2/mushroom.js
```

Para una futura `v5.2.3`, primero confirma que la release siga incluyendo `mushroom.js`. Si conserva el mismo nombre, normalmente será:

```text
https://github.com/piitaya/lovelace-mushroom/releases/download/v5.2.3/mushroom.js
```

### Cómo obtenerla manualmente

1. Abre el repositorio.
2. Entra a **Releases**.
3. Abre la versión exacta.
4. Busca el archivo en **Assets**.
5. Copia el enlace de descarga.
6. Comprueba que la URL contenga la versión exacta.

### Digest de GitHub

GitHub puede mostrar un `digest` SHA-256 del asset. Si está disponible, compáralo con la huella obtenida mediante el inventario local.

Para un archivo frontend idéntico, ambos valores deben coincidir.

---

## Caso B: archivo dentro de un tag

Algunos proyectos no adjuntan el JavaScript como asset, pero el archivo compilado forma parte del tag.

### Ejemplo: Smart Entity Timer Card

El archivo está en:

```text
dist/smart-entity-timer-card.js
```

La URL que GitHub puede entregar al pulsar **Raw** es:

```text
https://raw.githubusercontent.com/ORGANIZACION/REPOSITORIO/refs/tags/TAG/RUTA
```

Ejemplo:

```text
https://raw.githubusercontent.com/abel-smart-timer/smart-entity-timer-card/refs/tags/v0.3.0/dist/smart-entity-timer-card.js
```

GitHub también puede resolver la forma corta:

```text
https://raw.githubusercontent.com/abel-smart-timer/smart-entity-timer-card/v0.3.0/dist/smart-entity-timer-card.js
```

Para el catálogo se recomienda utilizar la URL que GitHub entregue directamente mediante **Raw**.

### Cómo obtenerla manualmente

1. Abre el repositorio.
2. Cambia de `main` al tag exacto.
3. Navega hasta el archivo instalable.
4. Abre el archivo.
5. Pulsa **Raw**.
6. Copia la URL.
7. Confirma que contenga el tag correcto.
8. Confirma que la ruta y el nombre del archivo no hayan cambiado.

No asumas que todas las versiones conservarán la misma ruta.

---

## Caso C: ZIP automático de un tag

Es útil para integraciones cuyo repositorio contiene:

```text
custom_components/<dominio>/
```

Patrón:

```text
https://github.com/ORGANIZACION/REPOSITORIO/archive/refs/tags/TAG.zip
```

Ejemplo:

```text
https://github.com/abel-smart-timer/smart-entity-timer/archive/refs/tags/v0.3.0.zip
```

En este caso:

- `url` apunta al ZIP del tag.
- `version` debe coincidir con `manifest.json`.
- `integration_id` identifica el destino en `/config/custom_components`.
- `source_folder` identifica la carpeta dentro del paquete.
- `sha256` debe ser la huella del **árbol instalado**, no la huella del ZIP.

---

## Caso D: ZIP o archivo adjunto a una release

Algunas integraciones publican un paquete preparado específicamente para instalación.

Patrón:

```text
https://github.com/ORGANIZACION/REPOSITORIO/releases/download/TAG/PAQUETE.zip
```

Si existe un paquete oficial de instalación y su estructura es compatible con UI Manager, normalmente debe preferirse sobre el ZIP automático del código fuente.

Antes de usarlo confirma:

1. Que corresponde exactamente a la versión.
2. Que contiene la integración correcta.
3. Que `manifest.json` declara la versión esperada.
4. Que UI Manager encuentra la carpeta de origen.
5. Que el árbol extraído produce la SHA-256 aprobada.

---

# URLs que no debes usar

Evita ramas mutables:

```text
.../main/...
.../master/...
```

Evita referencias ambiguas:

```text
.../latest/...
```

El objetivo es mantener siempre esta relación:

```text
versión aprobada
+
URL fija
+
SHA-256 aprobada
```

---

# Actualizar manualmente una tarjeta ya soportada

Este procedimiento aplica cuando la tarjeta:

- ya existe en `components.json`;
- sigue siendo un solo archivo frontend;
- conserva la misma ruta de instalación;
- conserva el mismo nombre de archivo;
- no introduce dependencias especiales nuevas.

Ejemplo: Smart Entity Timer Card `0.2.2` → `0.3.0`.

## 1. Probar en HACS

Actualiza primero la tarjeta en un laboratorio y confirma que funciona.

## 2. Obtener la SHA-256

```yaml
local_inventory_enabled: true
local_inventory_type: frontend
local_inventory_name: Smart Entity Timer Card
local_inventory_version: v0.3.0
local_inventory_path: /config/www/community/smart-entity-timer-card/smart-entity-timer-card.js
```

Ejecuta una vez y toma la huella desde:

```text
/config/ui-manager/checksum-candidates/latest.txt
```

Luego desactiva el inventario.

## 3. Obtener la URL exacta

Para Smart Entity Timer Card:

1. Abre el tag `v0.3.0`.
2. Abre:

```text
dist/smart-entity-timer-card.js
```

3. Pulsa **Raw**.
4. Copia la URL.

Ejemplo:

```text
https://raw.githubusercontent.com/abel-smart-timer/smart-entity-timer-card/refs/tags/v0.3.0/dist/smart-entity-timer-card.js
```

## 4. Modificar `components.json`

Normalmente debes cambiar:

```text
version
url
sha256
catalog_version
```

Ejemplo:

```json
{
  "id": "smart_entity_timer_card",
  "name": "Smart Entity Timer Card",
  "option": "smart_entity_timer_card",
  "type": "frontend",
  "version": "0.3.0",
  "url": "https://raw.githubusercontent.com/abel-smart-timer/smart-entity-timer-card/refs/tags/v0.3.0/dist/smart-entity-timer-card.js",
  "sha256": "SHA256_APROBADA_DE_0.3.0",
  "install_dir": "/config/www/ui-components/smart-entity-timer-card",
  "filename": "smart-entity-timer-card.js",
  "resource_url": "/local/ui-components/smart-entity-timer-card/smart-entity-timer-card.js",
  "resource_type": "module",
  "min_home_assistant": "2026.7.0"
}
```

No cambies los demás campos salvo que la nueva versión realmente cambie esos requisitos.

## 5. Incrementar `catalog_version`

Ejemplo:

```json
"catalog_version": "2026.08.08-2"
```

Cada catálogo publicado debe tener un identificador diferente.

## 6. Incrementar Smart Home UI Manager

Si la versión actual ya fue publicada, incrementa el patch:

```text
1.1.0 → 1.1.1
```

en:

```text
ui_manager/config.yaml
```

## 7. Actualizar `CHANGELOG.md`

Ejemplo:

```markdown
## 1.1.1

- Actualizada Smart Entity Timer Card de 0.2.2 a 0.3.0.
- Actualizada la URL fija del tag aprobado.
- Actualizada la huella SHA-256 aprobada.
- Sin cambios en la lógica de Smart Home UI Manager.
```

## 8. Compilar sin publicar

```text
publish: false
allow_overwrite: false
```

Confirma:

```text
Validate and initialize
Build amd64
Build aarch64
```

## 9. Publicar

```text
publish: true
allow_overwrite: false
```

Confirma:

```text
Validate and initialize
Build amd64
Build aarch64
Publish multi-architecture manifest
Verify public publication
```

## 10. Probar la actualización

Actualiza UI Manager en un laboratorio y ejecuta mantenimiento normal.

El reporte debería mostrar la tarjeta como `ACTUALIZADO` o `VERIFICADO`, según el estado previo.

Después comprueba el dashboard y recarga el navegador.

---

# Actualizar manualmente Mushroom

Mushroom utiliza normalmente un **asset de GitHub Release**, no una URL `raw`.

## 1. Abrir la nueva release

Abre la release exacta de Mushroom.

## 2. Confirmar el asset

Dentro de **Assets**, confirma que exista:

```text
mushroom.js
```

## 3. Copiar la URL

Patrón:

```text
https://github.com/piitaya/lovelace-mushroom/releases/download/vVERSION/mushroom.js
```

Ejemplo:

```text
https://github.com/piitaya/lovelace-mushroom/releases/download/v5.2.2/mushroom.js
```

## 4. Obtener y verificar SHA-256

Actualiza Mushroom mediante HACS y calcula:

```yaml
local_inventory_enabled: true
local_inventory_type: frontend
local_inventory_name: Mushroom
local_inventory_version: 5.2.2
local_inventory_path: /config/www/community/lovelace-mushroom/mushroom.js
```

Si GitHub muestra un digest SHA-256 del asset, compáralo con la huella local.

## 5. Actualizar el catálogo

Para una actualización rutinaria normalmente cambias:

```text
version
url
sha256
catalog_version
```

No necesitas modificar:

```text
install_dir
filename
resource_url
resource_type
```

mientras el proyecto conserve el mismo formato de distribución.

---

# Cuándo no basta con cambiar `version`, `url` y `sha256`

Detén el procedimiento rutinario si ocurre cualquiera de estos cambios:

- El archivo cambia de nombre.
- El archivo cambia de carpeta.
- La tarjeta deja de ser un archivo único.
- El proyecto cambia de asset de release a ZIP o viceversa.
- La integración cambia de dominio.
- Cambia `custom_components/<dominio>`.
- Cambia la estructura interna del ZIP.
- Aparece una dependencia obligatoria nueva.
- Cambia la versión mínima de Home Assistant.
- La actualización requiere una migración especial.
- El paquete ya no produce la misma estructura que HACS.
- El artefacto descargado no produce la huella esperada.

En esos casos revisa `component_manager.py`, `components.json`, la documentación y el procedimiento antes de publicar.

---

# Checklist antes de aprobar una actualización

```text
[ ] La versión funciona en laboratorio.
[ ] Existe un tag o release fijo.
[ ] La URL apunta exactamente a ese tag o release.
[ ] La URL descarga el artefacto esperado.
[ ] La SHA-256 local fue calculada.
[ ] La SHA-256 fue repetida en otra instalación cuando sea posible.
[ ] El nombre y ruta del archivo no cambiaron.
[ ] La versión mínima de Home Assistant fue revisada.
[ ] Las notas de la release fueron revisadas.
```

Después:

```text
[ ] components.json actualizado.
[ ] catalog_version incrementado.
[ ] config.yaml incrementado.
[ ] CHANGELOG.md actualizado.
[ ] Build amd64 correcto.
[ ] Build aarch64 correcto.
[ ] Publicación multi-arquitectura correcta.
[ ] Verificación pública correcta.
[ ] Actualización probada en laboratorio.
```

---

# Restauración de respaldos

## `restore_backup_enabled`

```yaml
restore_backup_enabled: true
restore_component: sonofflan
restore_backup: latest_good
```

Procedimiento:

1. Activa **Restaurar respaldo**.
2. Indica el componente.
3. Usa normalmente `latest_good`.
4. Inicia la aplicación una vez.
5. Revisa:

```text
/config/ui-manager/restore-reports/latest.txt
```

6. Reinicia Home Assistant Core cuando corresponda.
7. Comprueba la integración.
8. Desactiva:

```yaml
restore_backup_enabled: false
```

---

## `restore_component`

IDs actuales de integraciones administradas:

```text
sonofflan
spook
smart_entity_timer
```

Ejemplo:

```yaml
restore_component: smart_entity_timer
```

Debe utilizarse el ID interno del catálogo.

---

## `restore_backup`

Valor recomendado:

```yaml
restore_backup: latest_good
```

| Valor | Comportamiento |
|---|---|
| `latest_good` | Último respaldo `GOOD` |
| `latest` | Último respaldo sin filtrar clasificación |
| `AAAAmmdd-HHMMSS` | Respaldo específico |

Inventario:

```text
/config/ui-manager/backups/inventory/latest.txt
```

---

## `max_integration_backups`

```yaml
max_integration_backups: 5
```

Rango:

```text
1 a 20
```

Los respaldos se crean antes de actualizar, reparar o restaurar una integración existente.

La primera instalación no crea respaldo porque no existe una versión anterior.

---

# Opciones de componentes administrados

## `mini_graph_card`

```yaml
mini_graph_card: true
```

Instala, verifica, actualiza o repara Mini Graph Card y registra su recurso.

## `mushroom`

```yaml
mushroom: true
```

Instala, verifica, actualiza o repara Mushroom y registra su recurso.

## `modern_circular_gauge`

```yaml
modern_circular_gauge: true
```

Instala, verifica, actualiza o repara Modern Circular Gauge y registra su recurso.

## `sonofflan`

```yaml
sonofflan: true
```

Administra SonoffLAN. Puede requerir reiniciar Home Assistant Core.

## `spook`

```yaml
spook: true
```

Administra Spook. Puede requerir reiniciar Home Assistant Core.

## `smart_entity_timer`

```yaml
smart_entity_timer: false
```

Administra Smart Entity Timer. Permanece desactivado por defecto para una adopción controlada.

Instalación:

```text
/config/custom_components/smart_entity_timer
```

Después de instalarlo o actualizarlo, reinicia Home Assistant Core.

El respaldo de UI Manager protege los archivos de la integración, pero no sustituye un respaldo completo de Home Assistant cuando una release indique una migración estructural.

## `smart_entity_timer_card`

```yaml
smart_entity_timer_card: false
```

Administra Smart Entity Timer Card. Permanece desactivada por defecto.

Instalación:

```text
/config/www/ui-components/smart-entity-timer-card/smart-entity-timer-card.js
```

El recurso registrado usa la versión actualmente definida en `components.json`:

```text
/local/ui-components/smart-entity-timer-card/smart-entity-timer-card.js?v=<VERSION>
```

Para utilizar el conjunto completo:

```yaml
smart_entity_timer: true
smart_entity_timer_card: true
```

### Regla general

- `true`: UI Manager administra el componente.
- `false`: UI Manager lo omite.
- Cambiar a `false` no desinstala el componente.
- UI Manager no elimina configuraciones, cuentas ni dispositivos.

---

# Adopción desde HACS

HACS puede seguir utilizándose en laboratorios para probar versiones nuevas y obtener sus huellas.

Evita que HACS y UI Manager administren simultáneamente el mismo componente en un equipo de cliente.

## Tarjetas

HACS normalmente utiliza:

```text
/config/www/community/
```

UI Manager utiliza:

```text
/config/www/ui-components/
```

No mantengas dos recursos Lovelace activos para la misma tarjeta.

## Integraciones

Ambos pueden apuntar físicamente a:

```text
/config/custom_components/<dominio>
```

Una vez adoptada por UI Manager, evita actualizar esa integración mediante HACS en ese equipo.

---

# Mantenimiento normal

```yaml
diagnostic_only_enabled: false
local_inventory_enabled: false
restore_backup_enabled: false
```

Deja en `true` únicamente los componentes que deseas administrar.

La aplicación:

1. Ejecuta diagnóstico previo.
2. Valida `components.json`.
3. Comprueba Home Assistant Core.
4. Omite componentes incompatibles.
5. Instala componentes ausentes.
6. Actualiza versiones anteriores.
7. Repara componentes con huella incorrecta.
8. Registra recursos de dashboard.
9. Genera respaldos cuando corresponde.
10. Genera el reporte.
11. Actualiza el inventario de respaldos.
12. Se detiene.

Reporte:

```text
/config/ui-manager/reports/latest.txt
```

---

# Diagnóstico previo automático

Comprueba:

- Trazabilidad de imagen.
- Validez del catálogo.
- Python y `curl`.
- Módulos Python.
- Montaje y escritura de `/config`.
- Carpetas de frontend e integraciones.
- Espacio libre.
- Token de Supervisor.
- Home Assistant Core.
- DNS de GitHub.

Resultados:

- `PASS`: correcto.
- `WARN`: observación no bloqueante.
- `FAIL`: fallo crítico.

---

# Ubicación rápida de reportes

| Reporte | Ruta |
|---|---|
| Mantenimiento | `/config/ui-manager/reports/latest.txt` |
| Diagnóstico | `/config/ui-manager/diagnostics/latest.txt` |
| Inventario SHA-256 | `/config/ui-manager/checksum-candidates/latest.txt` |
| Restauración | `/config/ui-manager/restore-reports/latest.txt` |
| Inventario de respaldos | `/config/ui-manager/backups/inventory/latest.txt` |

---

# Solución rápida de problemas

## `/homeassistant` no existe

Usa la ruta equivalente bajo `/config`.

## La tarjeta no se encuentra

1. Abre `/config/www/community`.
2. Confirma la carpeta creada por HACS.
3. Busca el JavaScript exacto.
4. Usa la ruta completa iniciando con `/config`.

## La integración no contiene `manifest.json`

La ruta debe apuntar a la carpeta concreta de la integración.

Ejemplo:

```text
/config/custom_components/smart_entity_timer
```

## La versión indicada no coincide

Abre `manifest.json` y comprueba la versión real instalada.

## No existe `latest_good`

Revisa:

```text
/config/ui-manager/backups/inventory/latest.txt
```

## Componente incompatible

El componente se omite antes de descargarse. Actualiza Home Assistant Core o conserva una versión compatible en el catálogo.

## SHA-256 diferente

No apruebes la actualización hasta comprobar:

- versión correcta;
- tag o release correcto;
- URL fija correcta;
- artefacto oficial;
- archivo no modificado localmente;
- segunda comprobación cuando sea posible.

## La URL funciona pero la SHA no coincide

Comprueba si descargaste:

- el archivo del tag correcto;
- un asset de release diferente;
- código fuente en lugar del artefacto compilado;
- un ZIP cuyo SHA no debe compararse directamente con la huella de árbol de una integración.

## Recurso ya registrado

No es necesariamente un error. UI Manager puede estar confirmando que el recurso correcto ya existe.

## Cuándo reiniciar Home Assistant Core

Normalmente después de instalar, actualizar, reparar o restaurar una integración. Las tarjetas frontend suelen requerir recargar el navegador.

---

# Publicar una versión futura de Smart Home UI Manager

1. Prueba el componente mediante HACS en laboratorio.
2. Lee las notas de la nueva release.
3. Identifica el artefacto oficial.
4. Obtén una URL fija del tag o release.
5. Obtén y valida la SHA-256.
6. Modifica `components.json`.
7. Incrementa `catalog_version`.
8. Incrementa `version` en `ui_manager/config.yaml`.
9. Actualiza `CHANGELOG.md`.
10. Ejecuta:

```text
publish=false
allow_overwrite=false
```

11. Confirma `amd64` y `aarch64`.
12. Ejecuta:

```text
publish=true
allow_overwrite=false
```

13. Confirma los cinco trabajos.
14. Actualiza primero un laboratorio.
15. Ejecuta diagnóstico y mantenimiento.
16. Comprueba el componente actualizado.
17. Crea el GitHub Release de UI Manager.
18. Distribuye gradualmente.

Nunca sobrescribas una versión ya distribuida.

---

# Regla de versionado

Actualización rutinaria de un componente ya soportado:

```text
1.1.0 → 1.1.1
```

Nueva función compatible de UI Manager:

```text
1.1.x → 1.2.0
```

Cambio incompatible:

```text
1.x → 2.0.0
```

---

# Componentes de terceros

Las tarjetas e integraciones administradas pertenecen a sus respectivos autores y conservan sus propias licencias.

Smart Home UI Manager debe descargar publicaciones fijas configuradas en `components.json` y verificar el contenido mediante SHA-256 antes de instalarlo.
