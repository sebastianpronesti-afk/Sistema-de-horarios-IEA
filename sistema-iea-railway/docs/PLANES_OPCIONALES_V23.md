# v23 — Carrera conocida y plan pendiente

## Criterio

En IEA la inscripción identifica una carrera o curso, pero no siempre la versión
del plan. Se conserva ese dato de origen. El plan es opcional para cualquier
institución: no se infiere por nombres, materias compartidas, edad ni período.
Publicar esta versión no confirma ningún alumno, carrera ni oferta real.

## Inscripciones y planes

En Planificación → Oferta y materias → Carreras y planes de inscriptos:

1. Elegir el curso/carrera informado en las inscripciones del cuatrimestre.
2. Si corresponde, vincularlo con una carrera del catálogo. Este vínculo requiere
   confirmación y no modifica los nombres importados ni asigna planes.
3. Dejar los alumnos con «Plan pendiente de validar» mientras no se disponga del
   dato. Cuando se conozca, seleccionar un plan de esa carrera y guardar.

Hay búsqueda por nombre/DNI, filtro de pendientes y paginación. Las
confirmaciones pertenecen al alumno, curso y período: no se propagan a otros
cuatrimestres. Una carrera puede estar representada por varios cursos de origen.
Se admite tanto el vínculo curso_id de otras integraciones como el texto
curso_nombre que conserva el importador IEA. Los nombres informados se agrupan
por su valor exacto sin crear cursos ni inferir una versión del plan. Los grupos
de origen tienen identificadores internos estables; no son IDs del catálogo.
Las inscripciones sin curso se muestran aparte y no pueden vincularse en bloque
a una carrera: requieren completar primero el dato en la carga.

Las instituciones que ya conozcan el plan pueden confirmarlo con el mismo
recorrido. La importación automática de confirmaciones desde archivos o sistemas
externos queda pendiente; esta entrega no supone que el Excel existente aporte
ese dato. Tampoco añade cohortes ni asigna alumnos a comisiones específicas.

## Conteos

La apertura mantiene su criterio por cátedra y período. No se excluye a quien no
tenga un plan confirmado y no se multiplican registros por cada plan posible.
Se muestra un desglose de vínculos confirmados con la carrera, plan confirmado,
plan pendiente dentro de esa carrera y registros sin carrera vinculada al
catálogo. Los pendientes no son una estimación de alumnos de cada plan.

El dato «0 con vínculo confirmado a esta carrera» no significa que la carrera
carezca de alumnos: los nombres originales siguen visibles en inscripciones.
Los desgloses cuentan alumnos distintos; no deben sumarse entre planes o
carreras como si fueran conjuntos exclusivos. Las clases compartidas siguen
teniendo un solo registro.

## Materias pendientes

En cada materia aparece «Asociar cátedra» o «Cambiar cátedra». El selector y el
buscador incluyen todas las cátedras existentes, no solo coincidencias sugeridas.
Una materia sin plan identificado puede guardar su cátedra, año y cuatrimestre
sin elegir un destino. Las correlatividades quedan para cuando se confirme el
plan; sus antecedentes se conservan.

## Oferta todavía sin configurar

Horarios por carrera muestra las materias y las clases existentes como referencia
cuando no se configuró la oferta del plan para el período. No escribe al abrir.
Las referencias llevan «no ofrecida» y requieren selección y guardado explícitos
antes de asignar o sugerir clases. La oferta puede guardarse vacía de forma
intencional y se distingue de una oferta que nunca se configuró.

En modo consulta se explica que una persona con clave de edición debe configurar
la oferta. Los planes completos se mantienen en el catálogo independiente del
período. Confirmar la oferta curricular no confirma el plan de ningún alumno.

## Persistencia y límites

Se reutiliza academic_documents con un documento por curso/período y otro por
alumno/curso/período, evitando reescribir todas las confirmaciones juntas. Cada
cambio exige la revisión vigente y conserva antecedentes en academic_changes.
Las nuevas escrituras verifican la clave de edición en el servidor.

Se comprueba la existencia de la inscripción y la pertenencia del plan a la
carrera. Huellas de los datos de origen evitan aplicar confirmaciones anteriores
a identificadores reutilizados. Cambiar la carrera asociada deja sus antiguas
confirmaciones de plan pendientes de revisión. No se modifica el catálogo
institucional original, ni las inscripciones, ni los horarios existentes.

Una importación que altere curso o identidad puede requerir revisar vínculos. Los
respaldos completos de PostgreSQL incluyen estos documentos; los respaldos de una
importación no son un mecanismo de recuperación de ediciones de confirmaciones.
La separación por perfil no sustituye aislamiento seguro entre instituciones ni
autenticación individual. Esos aspectos siguen dentro del trabajo con ITOESTE.

## Comprobaciones

Las pruebas cubren el dato de carrera conservado con todos los planes pendientes,
confirmación explícita, rechazo de planes de otra carrera, separación entre
períodos y cursos, revisiones antiguas, cambios de identidad/carrera, conteos sin
duplicados, perfil institucional alternativo, materias pendientes sin destino y
consulta de referencias sin escritura automática. Incluyen pruebas de interfaz
del modo consulta y de la selección explícita de oferta y plan.
