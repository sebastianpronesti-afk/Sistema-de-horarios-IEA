# v24 — Identidad permanente de docentes, planes y cátedras

## Problema y criterio

Tener una clave primaria distinta en cada fila no impide registrar dos veces a la misma persona o al mismo plan. Esta entrega conserva los ID existentes y agrega controles de identificación a las altas, ediciones e importaciones. No renumera ni fusiona registros académicos.

| Entidad | Identidad permanente | Control de repetición |
| --- | --- | --- |
| Docente | `docentes.id`, presentado como `DOC-000001` | Documento normalizado. Coincidencias de nombre sin documentos suficientes requieren revisión. |
| Plan | El `id` existente del catálogo; UUID para nuevos planes | Carrera + resolución + jurisdicción + modalidad + versión dentro de la resolución. |
| Cátedra | `catedras.id` y su código institucional existente | Código comparado sin diferencias de mayúsculas o espacios exteriores. Los signos y ceros iniciales se conservan. |

Los ID son únicos dentro de la instalación actual. `DOC-000001` es la presentación del ID 1, no un segundo identificador que haya que mantener. No se presenta esta reforma como aislamiento entre instituciones ni como una migración multiusuario completa.

El nombre, correo, sede, turno y cuatrimestre no identifican por sí solos a un docente. Dos homónimos con documentos distintos pueden tener fichas diferentes. Si no hay documento, el ID sigue existiendo pero no garantiza que otra ficha con un nombre diferente no sea la misma persona.

El ID del plan no depende de datos que puedan corregirse. Una etiqueta diferente no permite crear una copia con la misma identificación académica. Se agrega `version_plan`, cuyo valor inicial es `1`; debe cambiar únicamente cuando exista una versión académica diferente. La sede y el cuatrimestre de dictado no crean un plan nuevo. Los planes con resolución, jurisdicción o modalidad incompletas quedan identificados por ID y pendientes de completar, sin inferir sus datos. Los sinónimos no confirmados de jurisdicciones/resoluciones no se equiparan automáticamente.

## Comportamiento de las pantallas

- Docentes: ID visible y buscable, también en los selectores. Exportación de docentes con ID para editar/reimportar.
- Revisión de identidades: grupos por documento repetido, nombres coincidentes y documento pendiente/inválido. Cada ID permite abrir su ficha cuando se dispone de edición. No hay fusión ni borrado automático.
- Planes: ID visible, búsqueda por ID, versión editable, aviso de identificación incompleta o posible duplicado anterior. Las asociaciones, correlatividades, confirmaciones de alumnos y ofertas conservan sus claves.
- Un nuevo plan vacío reutiliza el mismo borrador si se vuelve a solicitar antes de configurarlo.
- Cátedras: ID y código se muestran por separado. Intentar cambiar ID o código se rechaza; cambiar el nombre conserva ambos.

## Importaciones y exportaciones

- Los importadores de docentes y CUIT utilizan las mismas reglas que la ficha. Un archivo inválido revierte su transacción completa.
- Columnas reconocidas: `docente_id`, `dni`, `nombre`, `apellido`, `email`; también los encabezados históricos de apellido y nombre separados por coma.
- `docente_id` acepta el número o `DOC-000001`. Si ID y documento no coinciden, la importación se detiene. Corregir un documento existente se hace en la ficha, no mediante una contradicción dentro del archivo.
- Los documentos con puntos, espacios o decimales de Excel se comparan de forma uniforme. No se inventan documentos. El formato admitido sigue siendo un documento numérico de 6 a 12 dígitos.
- En horarios, una nueva alta necesita documento y nombre. Un nombre desconocido por sí solo queda como error en la vista previa. Un nombre completo o alias que identifica sin ambigüedad una ficha existente sigue siendo compatible, con una advertencia para conservar su ID.
- La planilla de trabajo agrega `DOCENTE_ID` y conserva el código exacto de cátedra. Al cambiar de persona se debe cambiar ese ID y el nombre. Para dejarla sin docente se vacían ambos. Si el nombre identifica a otra persona que el ID, se rechaza.
- Los códigos `MAT-1` y `MAT1` permanecen distintos. La adaptación histórica de números de Excel a `c.N` se mantiene; el catálogo no se renumera.
- BCE/BEA requiere el código del archivo; se eliminó la generación de códigos mediante un hash del nombre y la sustitución silenciosa por una cátedra con nombre parecido.

## Migración y protección en PostgreSQL

`install_identity_guards` es aditiva e idempotente. Dentro de una transacción:

1. Bloquea las escrituras en las tablas de docentes y cátedras durante su instalación.
2. Construye `identity_keys`, una tabla auxiliar de reservas por documento/código normalizado.
3. Instala triggers que impiden cambiar los ID, renumerar cátedras o introducir nuevas identidades repetidas. La clave primaria de las reservas serializa intentos concurrentes sobre el mismo documento/código.
4. Conserva íntegramente los registros anteriores, incluso los duplicados; estos quedan visibles para revisión. Una modificación de datos ajenos a la identidad no los elimina ni los fusiona.

Las reservas se mantienen al cambiar un documento o borrar un registro; ante un duplicado anterior, se conserva la reserva para la ficha que permanece. La tabla se puede reconstruir desde los datos principales mediante la misma migración. No se deben truncar tablas aisladas ni editar manualmente las reservas en producción.

La aplicación debe poder crear funciones y triggers en su base. Si falla esta migración, el arranque falla de forma visible; no continúa afirmando que la protección está instalada.

## Validación y publicación

Pruebas de regresión: migración repetida, duplicados anteriores, conservación de relaciones, documento formateado, altas manuales y ambos endpoints de edición, homónimos, importación repetida/atómica, CUIT, exportación/reimportación con ID, nombres sin identidad, códigos con signos, ofertas conservadas tras renombrar un plan, versiones/jurisdicciones distintas y borradores repetidos. Pruebas de interfaz: ID permanente, versión editable y revisión sin fusiones.

La prueba de dos escrituras concurrentes se ejecuta en PostgreSQL nativo con `IDENTITY_CONCURRENCY_TESTS=yes`, configurado en GitHub Actions. En el motor local PGlite se omite porque no ofrece el mismo manejo de conexiones concurrentes. Ninguna de estas pruebas modifica producción.

Antes de publicar: respaldo de la base, ensayo de migración sobre una copia de la base institucional y revisión de sus coincidencias. No hay limpieza automática de duplicados reales. Para retirar las nuevas protecciones, un responsable puede quitar los triggers `identity_guard` y `identity_release` de ambas tablas; no hace falta renumerar datos ni eliminar catálogos. Esto vuelve a permitir las entradas antiguas y debe hacerse como una reversión controlada, no como reparación de datos.

## Límites

Esta entrega no permite certificar que dos fichas sin documento sean personas diferentes, no resuelve automáticamente identidades anteriores y no incorpora fusión de registros. Tampoco sustituye la autenticación integral, el historial atribuible a usuarios ni la separación entre clientes pendientes con ITOESTE. El registro de planes sigue en el documento académico versionado y conserva su control de revisión.
