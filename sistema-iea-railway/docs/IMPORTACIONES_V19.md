# Versión 19: importaciones revisables y recuperables

Esta entrega continúa la configuración institucional del PR #1. Implementa un
circuito común para **horarios y designaciones, alumnos e inscripciones generales
y planes de carrera**. No fue desplegada en Railway ni aplicada a datos reales.

## Uso

1. En Importar Datos, elegir el tipo, la sede y el período. “Todas las sedes” es una
   elección explícita. El plan de carrera es un molde compartido y no tiene período.
2. Elegir **Actualizar** para conservar los registros ausentes, o **Reemplazar**
   para proponer sus bajas exclusivamente dentro del alcance seleccionado.
3. Cargar XLSX o CSV y pulsar **Analizar y ver diferencias**. La vista previa no
   guarda personas, alias, horarios ni respaldos y no consume IDs de las tablas.
4. Revisar altas, modificaciones, bajas, campos anteriores/nuevos, errores y
   advertencias. Los cambios en alumnos, docentes, enlaces y oferta se muestran
   como cambios relacionados porque pueden afectar información compartida.
5. Corregir todos los errores. Si cambian las columnas, usar “Relacionar columnas
   de mi archivo” y volver a analizar. Las bajas requieren una confirmación expresa
   en la interfaz. Solo se habilita aplicar una vista previa válida.
6. Confirmar. El servidor verifica otra vez archivo, opciones, perfil y datos,
   guarda el respaldo obligatorio y aplica todos los cambios en una transacción.
   Cualquier fallo revierte la operación. Repetir un archivo sin cambios no crea
   registros duplicados ni otro respaldo vacío.
7. Para deshacer, abrir **Importaciones y recuperación**, revisar las diferencias
   y confirmar. Si hubo ediciones posteriores incompatibles, se detiene y explica
   el conflicto. La recuperación también es atómica y genera una operación inversa.

Las vistas previas vencen a los 30 minutos. Cambiar el archivo, incluso guardándolo
otra vez, exige volver a analizarlo. Cambios en los datos académicos mientras se
revisa una planilla también invalidan la confirmación de forma conservadora.

## Formato común

Se descarga una plantilla vacía por tipo. Los adaptadores transforman todas las
entradas al mismo conjunto de campos antes de consultar o modificar la base.
El mapeo manual relaciona nombres de columnas; no traduce automáticamente los
valores de modalidades, días, sedes o documentos.

| Tipo | Campos principales | Identificación y alcance |
|---|---|---|
| Horarios | codigo_materia, sede, dia, hora_inicio, hora_fin, docente_id/docente/docente_dni, modalidad; opcionales asignacion_id, comision, carrera, turno, link_meet, recibe_alumnos_presenciales, periodo_id | ID de asignación existente; sin ID se compara materia, sede, modalidad, día, hora inicial y comisión. Limitado al período y sede elegidos. |
| Inscripciones | codigo_materia, dni, nombre, apellido, email, carrera, sede, turno, modalidad, es_edi, edi_materia, periodo_id | Alumno por DNI; inscripción por alumno, materia y período. Un reemplazo elimina inscripciones, conserva personas. |
| Plan | codigo_materia, materia, carrera, sede, anno, dia_tm, hora_tm, dia_tn, hora_tn | Sede, carrera, año y código. Compartido entre períodos. |

En tablas con encabezados, horarios requiere columnas de código, día y hora
inicial; una fila asincrónica puede dejar vacíos día y hora si indica explícitamente
`asincronica`. Inscripciones requiere código y DNI; una persona nueva necesita
nombre. Plan requiere código, carrera y año, y cada registro debe incluir nombre
de materia. La sede puede omitirse en una fila si se seleccionó una sede concreta.
Con “Todas las sedes”, cada fila debe indicar su sede; `Remoto` representa una
asignación sin sede. Un plan siempre necesita una sede identificada.

Las materias de horarios e inscripciones y las sedes deben existir previamente.
Los códigos alfanuméricos propios se conservan. Los números de materia del IEA
se convierten a `c.N`. Los DNI se normalizan, incluido el decimal `.0` de Excel.
Se admiten documentos numéricos de 6 a 12 dígitos; otros documentos internacionales
requerirán ampliar el adaptador. Las horas usan HH:MM dentro del mismo día, sin
franjas que crucen medianoche. Las fórmulas en campos importados deben pegarse
como valores. Límites actuales: 15 MB y 15.000 filas por archivo.

Un nombre de docente ambiguo se rechaza; se puede resolver con docente_id o DNI.
Se aceptan alias previamente registrados, sin aprender equivalencias en la vista
previa. Un nombre nuevo propone crear un docente y lo advierte para revisión.
Dejar docente vacío marca esa asignación como pendiente. Los campos vacíos que
se importan pueden limpiar sus valores: revisar siempre el detalle de diferencias.
Un enlace de clase vacío conserva el anterior; uno informado modifica el enlace
compartido de la materia y queda incluido en la recuperación.

## Compatibilidad con IEA

- Planilla de trabajo con encabezados, más el formato clásico posicional de
  horarios. La exportación incorpora ASIGNACION_ID, COMISION, CARRERA, TURNO,
  MODALIDAD, RECIBE_ALUMNOS_PRESENCIALES y PERIODO_ID.
- Conservar ASIGNACION_ID para cambiar el día u hora de una clase existente. Para
  agregar otra franja, usar una fila sin ID. Una misma comisión puede tener varias
  clases semanales: su nombre no identifica por sí solo una asignación.
- Sin ID, cambiar día u hora se interpreta como otra franja. En Actualizar se
  conserva la anterior; en Reemplazar se propone su baja si está dentro del alcance.
- Una exportación por sede conserva únicamente sus asignaciones y los renglones
  pendientes correspondientes a su demanda. Completar o quitar esos renglones
  pendientes antes de importar; un horario incompleto bloquea todo el archivo.
- Inscripciones del formato IEA con columna de alumno, documento, materia y curso.
  EDI sin código exige una única materia de referencia en la hoja; la ambigüedad
  se rechaza. El formato común permite informar es_edi y código explícitamente.
- Plan IEA por hoja de sede, bloques de carrera y año, con EDI y turnos mañana/noche.
  El molde sigue compartido entre períodos. Para otro diseño se ofrece la tabla
  común y el mapeo de encabezados.
- El archivo exportado y los adaptadores se verificaron con datos sintéticos que
  representan esos formatos. Falta validar con una copia anonimizada de todas las
  variantes reales de planilla usadas internamente por IEA.

Un archivo de otra sede no se filtra silenciosamente: se informa el error para
corregir la selección o el archivo. Inscripciones sin sede identificable se
preservan al reemplazar una sola sede. Un reemplazo de todas las sedes sí incluye
esos registros dentro del período seleccionado y muestra sus bajas.

## Recuperación e integridad

`importaciones_historial` guarda el estado anterior y posterior completo de cada
registro afectado, incluidos IDs, banderas y relaciones. También registra personas
creadas y cambios en enlaces/oferta. No es una copia completa de la base ni sustituye
los respaldos operativos de PostgreSQL. No se eliminan automáticamente respaldos.
La pantalla muestra las últimas 100 operaciones del filtro seleccionado.

Se comprueba que cada registro conserve el estado posterior guardado antes de
revertirlo. No se eliminan personas nuevas si luego recibieron referencias ajenas
a la importación, por ejemplo un alias o una asignación adicional. Los IDs que se
restauran conservan su valor; las secuencias de PostgreSQL pueden dejar huecos tras
un fallo y no se retroceden.

Las escrituras usan bloqueos PostgreSQL `SHARE ROW EXCLUSIVE` sobre las tablas
académicas relevantes durante la transacción. Es una solución conservadora que
puede demorar otras escrituras; no acredita escalabilidad ni resuelve toda la
edición simultánea. La lectura completa del estado y la comparación en memoria
requieren medición con el volumen real antes de ampliar a más instituciones.

## Cambios técnicos y actualización

- Nuevos módulos: import_adapters.py (conversión pura), import_service.py
  (conciliación, transacciones y recuperación) e import_routes.py (API).
- Migración aditiva: columnas comision/carrera/turno en asignaciones y tabla de
  historial. El arranque comprueba que existan los campos obligatorios; falla si
  no se puede completar el esquema necesario.
- Los endpoints anteriores de alumnos, plan-carrera, horarios-preview y
  horarios-aplicar devuelven 409 con indicaciones para actualizar la interfaz.
  Esto evita ejecutar la antigua sustitución directa sin vista previa.
- Los respaldos anteriores siguen en una sección separada. Su restauración ahora
  exige guardar el estado actual y opera en una transacción. Solo pueden recuperar
  los campos que contenían, y reemplazan las asignaciones del período completo.

Antes de desplegar, ensayar la migración y recuperación en una copia de pruebas
con la versión real de PostgreSQL/Python, un respaldo operativo verificable y
planillas representativas. Actualizar backend y frontend en una ventana coordinada;
los clientes antiguos no podrán usar los tres importadores sustituidos. Las reglas
de compatibilidad de la primera entrega no se aplican a esos endpoints en v19.

Configurar `IMPORT_PREVIEW_SECRET` con un valor aleatorio de al menos 32 bytes,
compartido por todas las réplicas/workers del backend y conservado entre reinicios.
Guardar el valor en variables del entorno, nunca en Git. Si falta, se usa una clave
aleatoria por proceso: reinicios o balanceo entre workers invalidarán vistas
previas y pedirán analizar otra vez. El token enlaza vista previa y confirmación;
**no autentica usuarios ni reemplaza la autorización de la API**.

Si se necesita revertir la versión, preservar primero base e historial y evaluar
los datos ya importados. Volver al código antiguo vuelve a habilitar sus importadores
destructivos. No borrar las nuevas columnas o el historial como parte del rollback.
Esta rama está preparada para revisión; no se modificó el despliegue productivo.

## Alcance pendiente

Los importadores auxiliares de docentes, catálogos, apertura masiva y módulos
BCE/BEA conservan sus rutas anteriores. La vista previa nueva valida integridad
estructural, alcance e identidades; no reemplaza los controles de superposiciones,
disponibilidad, carga horaria ni reglas de publicación. La siguiente etapa debe
unificar esas restricciones entre creación, edición e importación.

Continúan pendientes la autenticación y permisos en el servidor, sesiones,
aislamiento entre clientes, auditoría de autores, operación simultánea y definición
de experiencia multiusuario con ITOESTE/IEA. La configuración sigue siendo de una
institución por despliegue. Parte de los reportes, sedes y calendario siguen
específicos del IEA. Esta entrega no acredita preparación comercial integral.

## Pruebas reproducibles

Usar únicamente una base local descartable: cada prueba de integración borra las
tablas públicas. Los tests exigen `TEST_DATABASE_DISPOSABLE=yes` y una DATABASE_URL
con host localhost o 127.0.0.1. Desde backend, con requirements.txt y httpx==0.27.2:

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
```

Desde validation, con Node 24 o superior:

```bash
npm ci
npm test
```

Desde frontend:

```bash
npm ci
npm run build
```

Resultados locales del 12/09/2026: 26 pruebas nuevas de integración y 5 nuevas de
interfaz. Se conserva la batería anterior de 5 reglas, 6 integraciones y 5 pruebas
de interfaz. Compilación de producción React satisfactoria. Entorno: Python
3.12.14, PGlite 0.5.8/PostgreSQL 18.3 y Node 24.19.0. No se probó concurrencia real
entre conexiones PostgreSQL ni se realizó un recorrido visual en navegador real.

Casos cubiertos: vista previa sin efectos, alcance parcial, archivo inválido y
vacío, fórmulas, IDs estables, repetición sin duplicados, múltiples franjas por
comisión, token desactualizado, falla de respaldo, fallo durante escritura,
recuperación completa de altas/cambios/bajas, referencias posteriores, historial
inválido, adaptadores IEA y CSV de otra institución con sus códigos y sede propios;
en interfaz, confirmación de bajas, mapeo, errores, rol consulta y recuperación.
