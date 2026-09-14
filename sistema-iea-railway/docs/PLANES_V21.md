# v21 — Carreras y planes de estudio

El archivo académico del IEA se incorpora como un catálogo consultable, separado
de los horarios de cada cuatrimestre. Una carrera conserva sus distintos planes,
resoluciones, modalidades y jurisdicciones. La consulta compara sus materias con
las cátedras que existen en la base, preservando sus códigos y nombres actuales.

## Uso

- General: **Personas y datos académicos → Carreras y planes de estudio → Planes de estudio**.
- IEA: **Carreras terciarias → Planes de estudio**, con filtro inicial terciario.
- IEA: **BCE y BEA → Planes de estudio de secundario**, con filtro inicial secundario.
- Se puede buscar por carrera o resolución y filtrar por nivel, modalidad,
  jurisdicción y situación informada en el archivo.
- Cada plan muestra materias por año y cuatrimestre académico, correlatividades,
  coincidencias con cátedras actuales y pendientes de revisión.
- **Dobles titulaciones** reúne las hojas de comparación y las combinaciones sin
  detalle. No aplica equivalencias automáticamente.
- La consulta no exige elegir un cuatrimestre de trabajo. Al volver a horarios,
  el sistema vuelve a exigir un único período operativo.

## Contenido de esta revisión

Fuente: `Carreras Vigentes y Materias.xlsx`, revisión de conversión 14/09/2026.
El catálogo privado conserva el SHA-256 del archivo y la hoja/fila de cada registro.
El archivo original no se modifica. Ni el Excel ni el catálogo convertido se incorporan al repositorio público.

| Contenido | Cantidad |
|---|---:|
| Carreras terciarias | 30 |
| Programas secundarios BEA/BCE | 2 |
| Planes o propuestas identificados | 104 |
| Materias dentro de esos planes o propuestas | 2.939 |
| Materias pendientes de asignar a un plan | 30 |
| Registros de dobles titulaciones para revisar | 15 |

Las cantidades de materias corresponden a apariciones en planes, no a cátedras
únicas. Los 104 registros incluyen planes anteriores, futuros, incompletos y una
propuesta a distancia sin resolución aprobatoria informada. No significan 104
planes vigentes. Las 15 entradas de dobles titulaciones son nueve hojas de
comparación y seis combinaciones enumeradas sin detalle; no son quince nuevas
carreras ni quince acuerdos de equivalencias aprobados.

## Criterios acordados con IEA

1. Cada resolución conserva su propio plan. No se reemplaza un plan anterior
   por la llegada de otro. La vigencia y la admisión no se deducen solamente
   del año de la resolución.
2. CABA/Capital y Provincia se distinguen. CIED identifica la modalidad a
   distancia; por sí solo no determina la jurisdicción aprobante.
3. El año y cuatrimestre académicos provienen de las columnas del plan. Los
   campos «en sistema» quedan como evidencia para revisión, incluso si el
   campo académico está vacío. En BANCARIA se usan F = año y G = cuatrimestre,
   según confirmación del usuario.
4. Los códigos existentes en la base son la autoridad. El código del Excel
   es una referencia y no se usa para recodificar, crear ni renombrar cátedras.
5. Una coincidencia requiere código y nombre compatibles con una única
   cátedra actual. Se normalizan mayúsculas, acentos y puntuación; se compara
   el nombre académico o el nombre de cátedra explícito del archivo. Una
   coincidencia solo de nombre o solo de código queda como candidata a revisar.
   Esta coincidencia es informativa: no persiste una asociación operativa.
6. Los campos vacíos quedan pendientes. No se convierten en materias anuales
   ni se completa su ubicación con los campos posiblemente incorrectos del
   sistema anterior. EDI sin código conserva su carácter de espacio curricular.
7. Las hojas de control interno se excluyen del catálogo. Las hojas de
   dobles titulaciones se consultan por separado.

## Inconsistencias visibles

| Caso | Tratamiento |
|---|---|
| Hotelería, filas 184–211 | Cabecera «Plan 6», filas «Plan 5»: 28 materias pendientes de asignación. Plan 5 conserva sus 28 materias originales y Plan 6 queda sin detalle confirmado. |
| Psicopedagogía | 41 materias en el plan presencial y 28 en una propuesta a distancia separada, sin asumir aprobación. |
| Publicidad, Plan 1 | La resolución está guardada como una fecha con año 3805. Se conserva el dato original y se muestra resolución pendiente. |
| Gastronomía | La hoja es un formulario sin completar: se conserva la carrera sin inventar un plan. |
| Despacho / Guía de Turismo | Una materia de cada hoja carece de plan identificable. Se puede consultar en pendientes. |
| Administración, Plan 1, Computación I | La referencia c.1 no basta para vincularla con la cátedra Administración. Se presenta para revisión. |

Las restantes observaciones se muestran junto a cada materia. Las diferencias
en cantidad de asociaciones respecto de pruebas locales dependen de las cátedras
que efectivamente existan en la base del despliegue.

## Alcance técnico

- `app/curriculum.py`: lectura y validación del catálogo, comparación con
  cátedras y resúmenes. No ejecuta escrituras.
- `app/curriculum_routes.py`: cuatro rutas GET bajo `/api/planes-estudio`.
  El catálogo no recibe ni aplica un filtro de cuatrimestre operativo.
- `app/profiles/iea_curriculum.json`: ubicación opcional del archivo privado del IEA, excluida de Git.
- `frontend/src/AcademicPlans.js` y su CSS: buscador, filtros, detalle,
  pendientes y dobles titulaciones.
- `tools/build_iea_curriculum.py`: adaptador del Excel particular del IEA.
  No accede a una base de datos.

No se requieren migraciones de base para esta entrega. No se escriben ni
reemplazan cátedras, inscripciones, asignaciones, cursos ni `plan_carrera`.
Los horarios y las sugerencias continúan usando el plan operativo existente.

Quedan para una entrega posterior: edición y aprobación de asociaciones,
asignación explícita de plan a sede/cohorte, historial de esas decisiones y uso
del plan aprobado en las sugerencias de horarios. Las equivalencias y la
admisión a planes antiguos necesitan reglas académicas confirmadas. Esta versión
permite consultar y revisar el catálogo; no implementa esas decisiones.

## Configuración para otras instituciones

La interfaz y las rutas son generales. El catálogo se entrega por separado
como archivo privado. El perfil `iea` puede leerlo de `app/profiles/iea_curriculum.json`
si se instala allí. Sin archivo ni configuración explícita se muestra un catálogo
vacío. Cada perfil puede configurar su archivo mediante `CURRICULUM_CATALOG_PATH`. Una ruta relativa se
resuelve desde `backend/app`; una absoluta se utiliza directamente.

El JSON debe usar `schema_version: 1`, un `institution_id` que coincida con el
perfil, `source`, `careers` y `articulations`. Cada carrera contiene `planes` y
`materias_sin_plan`; cada plan tiene un ID único, `carrera_id`, metadatos y
`materias`. Las materias tienen IDs únicos, nombre, código de referencia, año,
cuatrimestre, correlatividades y origen. Los campos sin confirmar son `null` o
cadenas vacías según su significado. Las observaciones son listas de texto.

Los IDs no pueden repetirse, y un plan no puede pertenecer a otra carrera.
Se validan también las listas de carreras, planes, materias y módulos, los
campos de texto y las ubicaciones académicas. Año y cuatrimestre pueden quedar
sin confirmar (`null`); si se informan, deben ser enteros positivos. Un archivo
mal formado se rechaza antes de generar las pantallas de consulta.
Un catálogo configurado inválido o de otra institución produce un error visible;
no se sustituye por el del IEA. La lectura se almacena en memoria: después de
cambiar el archivo debe reiniciarse el servicio. El perfil por despliegue no
constituye aislamiento multiinstitución dentro de una misma base.

## Regeneración y comprobación

Las pruebas sobre el contenido real requieren el catálogo privado en
`backend/app/profiles/iea_curriculum.json`. Sin ese archivo, las dos clases de
pruebas que dependen del contenido IEA se omiten explícitamente; las pruebas
de configuración con datos ficticios y las demás pruebas siguen disponibles.

Desde `sistema-iea-railway`, con las dependencias del backend instaladas:

```bash
python tools/build_iea_curriculum.py \
  '/ruta/Carreras Vigentes y Materias.xlsx' \
  backend/app/profiles/iea_curriculum.json
PYTHONPATH=backend python -m unittest discover -s backend/tests -p test_curriculum.py -v
```

Revisar el diff antes de incorporar una nueva fuente: los IDs se calculan de
forma determinista a partir del contenido y pueden cambiar si cambia la
identidad del plan o de la materia. El adaptador depende de la estructura de
este Excel, no es un importador universal de planillas académicas.

Para la integración se utiliza exclusivamente una base PostgreSQL local
descartable con `TEST_DATABASE_DISPOSABLE=yes`; ver los requisitos y comandos
de [ESTANDARIZACION.md](ESTANDARIZACION.md). No ejecutar esa suite contra
producción: sus fixtures vacían tablas entre casos.

Validación local del 14/09/2026:

- 78 pruebas de backend satisfactorias con el catálogo privado instalado: 18 nuevas del catálogo y 5 nuevas de
  sus rutas, 7 de configuración con datos ficticios, 4 de compatibilidad de las
  claves de arranque configurables y las
  44 de reglas, API e importaciones anteriores.
- 28 pruebas de interfaz satisfactorias, incluidas 8 del catálogo y una de
  acceso sin período y regreso a la selección de cuatrimestre.
- Se ejecutó la suite completa de interfaz recuperada (27 casos); después de
  la corrección final se repitieron los 8 casos del catálogo, incluido el nuevo
  caso de ubicaciones académicas pendientes. Los otros 20 casos no cambiaron.
- Build de producción de React satisfactorio.
- Reconversión del Excel original idéntica al JSON versionado; se verificó su
  SHA-256 y los totales de carreras, planes, materias y pendientes.
- La integración comprueba que consultar el catálogo no cambia las tablas
  operativas, que una institución distinta no recibe el catálogo IEA y que
  las respuestas tardías no sustituyen el detalle recién seleccionado.
- Los catálogos mal formados reciben un error explicativo en las cuatro rutas.
  El filtro de revisión incluye ubicaciones académicas incompletas aunque el
  código coincida. Un EDI sin código y con datos académicos completos no requiere
  por ese único motivo una asociación de cátedra.

Las pruebas de interfaz usan jsdom y no sustituyen una revisión visual con
navegador. En este entorno no hay un navegador instalado; queda pendiente esa
revisión con usuarios y el contraste de asociaciones contra la base de Railway.
No se verificó concurrencia ni se desplegó esta versión en producción.

## Incorporación y reversión

### Configuración de acceso antes del despliegue

Al preparar la publicación, la revisión automática detectó contraseñas iniciales
incluidas en el código heredado. Esta entrega las reemplaza por dos variables
privadas del backend, sin incorporar sus valores al repositorio:

- `BOOTSTRAP_EDITOR_PASSWORD`: acceso inicial de edición.
- `BOOTSTRAP_CONSULTA_PASSWORD`: acceso inicial de consulta.

Las contraseñas personalizadas guardadas en `configuracion` conservan prioridad
y siguen funcionando. Si un rol todavía usa su contraseña inicial, configurar
su variable **antes de desplegar** esta versión. Sin contraseña guardada ni
variable configurada, ese rol no puede iniciar sesión. Configurar valores
distintos para ambos roles y no incluirlos en el frontend ni en archivos públicos.
Si se venían usando las claves publicadas, reemplazarlas por nuevas claves.

No se migran contraseñas ni se cambia la base de producción desde esta entrega.
Las cuatro pruebas adicionales verifican ambos roles, prioridad de las claves
guardadas, cambio de contraseña y ausencia de un acceso vacío al faltar una
variable. Esto conserva el circuito existente; la autenticación integral,
permisos y operación multiusuario siguen pendientes con ITOESTE.

### Configuración privada mediante variables

Railway puede recibir el catálogo sin subir archivos a un volumen. Se comprime
el JSON con gzip, se codifica en base64 y se divide en fragmentos de hasta
48.000 caracteres. Solo el backend recibe estas variables privadas:

- `CURRICULUM_CATALOG_GZIP_PARTS`: cantidad de fragmentos, entre 1 y 64.
- `CURRICULUM_CATALOG_GZIP_PART_01`, `_02`, etc.: fragmentos consecutivos.
- `CURRICULUM_CATALOG_GZIP_SHA256`: SHA-256 del JSON original sin comprimir.

La carga comprueba integridad, tamaño descomprimido máximo de 16 MiB y esquema.
Una configuración incompleta produce un error visible. No escribe archivos.
Una ruta explícita `CURRICULUM_CATALOG_PATH` tiene prioridad sobre las variables;
sin ruta explícita se utilizan las variables y luego el archivo local opcional.
Cambiar las variables requiere desplegar el backend. Los valores no se guardan
en Git ni se incorporan al frontend. Las pruebas incluyen reconstrucción exacta,
fragmentos incompletos, integridad incorrecta y límites de descompresión.

### Instalación privada alternativa mediante archivo

La publicación del archivo académico fue rechazada por la herramienta sin una
explicación adicional. Por eso la entrega pública contiene el código y las
pruebas, y el catálogo se entrega por separado en `Catalogo_IEA_v21_privado.zip`.

1. Extraer `iea_curriculum.json` del ZIP y colocarlo en un volumen privado que
   pueda leer el backend, por ejemplo `/data/iea_curriculum.json`.
2. Configurar `CURRICULUM_CATALOG_PATH=/data/iea_curriculum.json` en ese backend.
3. Reiniciar el servicio y verificar las 32 carreras/programas y 104 planes o
   propuestas. Si se configura una ruta inexistente o un archivo inválido,
   el sistema muestra un error; no sustituye los datos por otro catálogo.

No se instala el archivo en el frontend ni se lo sirve como recurso estático.
La configuración privada del archivo no sustituye la protección de la API;
la autorización de sus consultas sigue dentro del trabajo pendiente con ITOESTE.

### Publicación

Esta entrega parte de `main` posterior a la PR #4, que ya incorpora las mejoras
de configuración, importaciones y panel. La rama de revisión es
`codex/catalogo-planes-v21-20260914` y apunta directamente a `main`.
No es necesario volver a integrar las ramas intermedias de v19 y v20.

Para desplegarla, actualizar
primero el backend y después el frontend: el nuevo catálogo usa una ruta nueva.
El frontend anterior sigue siendo compatible con el backend nuevo.
La reversión puede restaurar el frontend anterior y después el backend anterior,
sin restaurar datos de una base, porque esta funcionalidad no escribe en ella.
