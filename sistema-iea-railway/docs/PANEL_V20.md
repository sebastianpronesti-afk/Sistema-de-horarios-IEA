# Versión 20: navegación y cuatrimestre de trabajo

Continuación de la versión 19 (PR #2). Esta entrega reorganiza el panel general,
agrega búsqueda de funciones y separa los accesos institucionales. Se mantiene
una institución por despliegue; no incorpora usuarios ni aislamiento entre clientes.

## Organización

| Menú | Funciones reunidas |
|---|---|
| Inicio → Panel general | Estado y pasos de preparación del cuatrimestre |
| Planificación → Oferta y materias | Oferta del cuatrimestre, materias/asignaciones y decisiones de apertura |
| Planificación → Horarios | Calendario y horarios por día |
| Planificación → Horarios por carrera | Horarios y sugerencias por carrera, en pestañas |
| Planificación → Validación y cierre | Revisión de cierre, cruces de horarios y cruces entre carreras |
| Personas y datos académicos → Docentes | Fichas, disponibilidad, carga horaria, asignaciones pendientes y equivalencias de nombres |
| Personas y datos académicos → Carreras e inscripciones | Carreras/cursos e inscripciones por curso |
| Archivos y seguimiento | Importar, exportar, respaldos/recuperación y comparación de cuatrimestres |
| IEA → Carreras terciarias | Horarios y sugerencias, EDI por cátedra y control de inscripciones |
| IEA → BCE y BEA | Materias BCE/BEA e importación específica de sus inscripciones |
| IEA → Materias asincrónicas | Panel institucional de materias asincrónicas |

Los apartados generales e IEA de horarios por carrera abren los mismos componentes
con los mismos datos. El acceso IEA aporta ubicación y contexto de trabajo; no crea
una segunda copia del horario. Las funciones IEA no aparecen en el menú ni en los
resultados del buscador de perfiles cuyo identificador sea distinto de `iea`.
Esta clasificación visual no es una restricción de acceso en el servidor.

Las secciones relacionadas comparten pestañas y dejan de competir como entradas
sueltas en un menú de más de veinte opciones. Se conservan las funciones existentes.
La búsqueda considera nombre, grupo y equivalencias, sin exigir tildes ni mayúsculas;
permite localizar también una pestaña interna. Enter abre el primer resultado y
Escape limpia la búsqueda. El resultado muestra su ubicación y abre sus grupos.

## Cuatrimestre único

El selector se trasladó a una cabecera persistente, con etiqueta, borde destacado
y texto mayor. En pantallas angostas se adapta al ancho disponible. No existe una
opción para mostrar todos los cuatrimestres. La elección se conserva por perfil en
el navegador y se valida contra el catálogo al iniciar.

Si no hay una elección previa válida, se usa el único cuatrimestre marcado activo;
si hay ambigüedad, se intenta el correspondiente al año/semestre actual. Si tampoco
existe, se pide una selección concreta. No se consulta información de horarios,
demanda o carga docente sin tener primero un cuatrimestre elegido.

Al cambiar, se oculta el contenido anterior hasta completar la nueva carga. Si
falla, se muestra el error y Reintentar. Las respuestas tardías de otra selección
se descartan. Los formularios y vistas dependientes se vuelven a montar con el
nuevo período para no arrastrar IDs, filtros o vistas previas del anterior.

La importación general, apertura masiva, creación de asignaciones y destino de
replicación usan el cuatrimestre de la cabecera. Replicar sigue permitiendo elegir
un origen. Comparar conserva dos períodos concretos por tratarse de una comparación;
ninguna de esas funciones habilita una vista combinada de todos los períodos.

El plan/molde de carreras, las fichas de personas, cursos, sedes, equivalencias y
algunas configuraciones siguen siendo datos compartidos entre períodos. Cambiar el
cuatrimestre cambia las asignaciones, inscripciones y cargas consultadas; no crea
catálogos independientes. El molde muestra expresamente que es compartido.

## Legibilidad y correcciones asociadas

- Menú de 16 px, campos principales de 16 px y selector de cuatrimestre de 20 px.
- Texto normal de 17 px y texto auxiliar/tablas con un mínimo de 14 px en el área
  principal. Se eliminó la dependencia visual de etiquetas de 9–11 px en esas vistas.
- Mayor contraste, espacios, foco visible para teclado y navegación adaptable.
- Los pasos del panel general son botones accesibles por teclado.
- El estado sin faltantes de docente ni cruces no afirma que todo el sistema esté
  validado: identifica los dos controles a los que se refiere.
- Los estilos de Tailwind se compilan y sirven con el frontend. Se retiró el script
  de CDN del HTML productivo; la apariencia no necesita descargarlo al abrir la app.
- Las sedes de los selectores generales provienen del catálogo de la institución.
- Horarios por carrera mantiene visibles todas las sedes al cambiar de pestaña.
- Importar plan desde ese panel dirige al circuito recuperable de v19 y selecciona
  Plan de carrera. Se retiró la importación directa antigua de esa pantalla.
- Exportar describe correctamente actualización/reemplazo por alcance y docentes
  pendientes; ya no promete una sustitución global ni validaciones no implementadas.

## Servicios por carrera

Los dos servicios de horarios y sugerencias exigen ahora un cuatrimestre existente.
Los filtros de sede usan parámetros SQL y admiten nombres con apóstrofes. Los códigos
propios y los nombres de carrera provienen del plan institucional. Una asignación
presencial de una sede no se presenta como horario de otra; las sesiones sin sede
se conservan como compartidas, conforme al tratamiento previo del sistema.

Las sugerencias leen las materias de referencia guardadas en la base y excluyen
docentes inactivos. Con perfil IEA se conserva la sugerencia asincrónica bajo el
mínimo de alumnos. En los dos paneles por carrera de otros perfiles, ese caso se
presenta como Revisar apertura, sin asumir que debe resolverse con una pregrabación.
Esto no generaliza todavía todas las reglas de apertura de los demás servicios.

Las sugerencias continúan siendo candidatos orientativos, no un generador de
horarios completos. Se mantiene pendiente unificar duración, disponibilidad,
traslados, sedes autorizadas, comisiones, carga máxima y asignación simultánea de
candidatos. Los conteos por materia siguen agregando la demanda del cuatrimestre;
no representan una nueva separación de demanda por sede/comisión.

## Validación y despliegue

Pruebas locales: 44 de backend (7 nuevas de paneles por carrera, 26 de importación,
6 de integración institucional y 5 de reglas) y 19 de interfaz (9 nuevas de
navegación, 5 de importación y 5 anteriores). Compilación de producción de React
con estilos locales. Los datos de prueba son ficticios.

Se verifican búsqueda, agrupación IEA, acceso general/institucional a los mismos
servicios, período único, error de carga y reintento, respuestas tardías, importación
con período fijado y conservación de pestañas de sede. En backend se verifican
períodos, sedes, códigos propios, reglas IEA/otro perfil, referencias e inactividad.

Reproducción: desde backend, con base local descartable y las condiciones de
seguridad de los tests de v19, ejecutar `python -m unittest discover -s tests -v`.
Desde validation, `npm ci` y `npm test`. Desde frontend, `npm ci` y `npm run build`.
Entorno: Python 3.12.14, PGlite 0.5.8/PostgreSQL 18.3 y Node 24.19.0.

La revisión visual con un navegador real queda pendiente: el entorno no pudo
descargar Chromium. Las comprobaciones de interfaz usan jsdom. También quedan
pendientes las pruebas con PostgreSQL y planillas reales anonimizadas del IEA.

La rama continúa la PR #2 y contiene las entregas previas. No fue desplegada en
Railway. Revisar los cambios y ensayar backend/frontend juntos antes de integrar.
No se realizaron migraciones nuevas de datos en v20 ni se modificó producción.

## Sugerencias para la próxima entrega

1. Aviso de cambios sin guardar y confirmación al salir de una edición o cambiar
   de cuatrimestre, con conservación del borrador cuando sea posible.
2. Estados Borrador / Revisado / Publicado, con comparación contra la versión
   publicada y una lista clara de pendientes antes de distribuir horarios.
3. Una ficha institucional para configurar módulos, calendario, sedes, turnos y
   reglas de apertura, con validación previa del impacto de cada cambio.
4. Unificar las restricciones de horarios entre edición manual, importación y
   sugerencias para que las tres vías comprueben las mismas condiciones.

Seguridad, permisos reales, sesiones, aislamiento comercial y experiencia de
operación simultánea continúan en el frente acordado con ITOESTE e IEA.
