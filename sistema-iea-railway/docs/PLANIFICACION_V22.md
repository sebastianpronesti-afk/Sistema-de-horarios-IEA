# v22 — Edición curricular y planificación por planes

## Recorrido
1. Cátedras: catálogo común de códigos y nombres.
2. Planes de estudio: versiones completas por carrera; año y cuatrimestre académico separados.
3. Inscriptos: estudiantes registrados en una cátedra y un período operativo.
4. Planificación: elegir el plan, configurar sus materias ofrecidas en el período, revisar la demanda y asignar clases o consultar sugerencias.

El selector del período no aparece en las fichas docentes, el catálogo de cátedras, los cursos de inscripción ni los planes completos. Las inscripciones del período y la carga horaria se consultan en Planificación.

## Edición
- Editar datos del plan, agregar planes y materias.
- Asociar una materia a una cátedra existente por su ID, sin cambiar códigos ni nombres de cátedra.
- Completar año y cuatrimestre con campos independientes.
- Seleccionar correlatividades entre materias de la misma versión del plan. Se rechazan referencias a otra versión, autorreferencias y ciclos.
- Trasladar materias sin plan identificado a un plan de su misma carrera, conservando el ID.
- Conservar hoja y fila de origen en un detalle de antecedentes; no son campos académicos.
- Los textos originales de correlatividades se conservan como antecedentes. El selector registra materias requeridas; no comprueba la historia académica individual ni distingue todavía requisitos de cursada y aprobación.

Los cambios se guardan en PostgreSQL, separados del archivo institucional original. El documento tiene revisión y se rechaza una escritura con revisión antigua. Se guarda un historial técnico anterior a cada modificación; todavía no hay un panel de recuperación curricular ni auditoría por usuario individual.

## Oferta y clases
La oferta del período se configura explícitamente. No se deduce que el primer cuatrimestre calendario deba ofrecer solamente materias del primer cuatrimestre académico.

Las asociaciones inequívocas de código y nombre del catálogo original pueden utilizarse; las dudosas requieren una asociación manual. Una asociación manual tiene prioridad y un vínculo vacío explícito no se rellena automáticamente.

Las inscripciones actuales no identifican siempre plan, cohorte, sede y turno. La nueva pantalla muestra **demanda por cátedra y período**, no alumnos propios del plan o de la sede elegida. Se cuentan alumnos distintos por cátedra para evitar duplicados. La misma cátedra compartida por varios planes consulta las mismas asignaciones. No se crean copias por cada carrera.

La sede seleccionada en el formulario determina dónde se dicta la clase, no filtra retrospectivamente el origen de los inscriptos. El criterio de apertura sigue siendo el total por cátedra del período. Para cupos y aperturas independientes por sede/cohorte habrá que incorporar esa identificación a la carga de alumnos y definir grupos de dictado.

Las sugerencias utilizan mínimo de apertura, alumnos por docente y duración del perfil institucional, cátedras habilitadas, disponibilidad completa y asignaciones del período. Se ordenan por carga horaria derivada. Las franjas disponibles representan intervalos de 30 minutos. No se supone disponibilidad cuando no se informó.

La asignación manual y la sugerida comparten la validación del nuevo flujo. Se rechazan horarios inválidos, docentes no habilitados, franjas incompletas, sedes presenciales no habilitadas, cruces docentes y cruces de materias ofrecidas del mismo año/cuatrimestre del plan. Los cambios de catálogo y oferta posteriores a abrir el formulario exigen recargar.

Se conserva como valor inicial del corte de turnos virtuales las 15:00 del código existente; se configura mediante el campo opcional del perfil institucional corte_turno_minutos (900 minutos desde medianoche). El corte del manual previo requiere confirmación funcional del instituto.

La aplicación comprueba nuevamente al guardar, y edita por ID las clases existentes. Los horarios previos se conservan en sus tablas actuales. No se reconstruye un horario completo ni se garantiza una optimización global. No se implementan aulas, traslados entre sedes ni carga asíncrona de trabajo como restricciones nuevas.

## Docentes y carga
La ficha general muestra contacto, cátedras habilitadas y notas. Se retiran los campos manuales de horas, los contadores de materias de sedes específicas y las sociedades del IEA.

Las sedes disponibles siguen siendo configurables a partir del catálogo real de sedes; no se impone una lista de cuatro. La carga se consulta en Planificación y se calcula desde las asignaciones del período. Las clases sin horario válido se señalan como pendientes y las que no tienen fin informado usan la duración institucional como estimación. No se utiliza el antiguo valor de horas cargado manualmente. Los campos históricos se conservan en la base.

## Operación y límites
- Nuevas tablas: academic_documents y academic_changes, creadas por la inicialización de metadatos existente.
- La primera consulta no escribe el catálogo. La primera edición crea el documento privado de la institución.
- Las nuevas escrituras curriculares y de planificación requieren la clave de edición, verificada en el servidor. La interfaz la conserva solamente en memoria para la sesión de trabajo; no la escribe en localStorage ni en el catálogo.
- Los endpoints heredados de edición, importación y asignación mantienen su alcance previo. Unificar todos los accesos a esas operaciones y reemplazar la autenticación compartida sigue pendiente con ITOESTE.
- La exclusión de escrituras simultáneas de horarios cubre este nuevo flujo. Las rutas heredadas todavía necesitan control general de concurrencia.
- El catálogo usa un perfil por despliegue; no implementa separación segura de varias instituciones dentro de una base compartida.
- El plan molde antiguo sigue disponible en los archivos y las rutas heredadas por compatibilidad; Horarios por carrera y Sugerencias del menú utilizan el catálogo curricular nuevo. Otros controles heredados que leen ese molde no se migran silenciosamente.
- Un cambio académico no reescribe asignaciones ni inscripciones existentes. Hay que revisar la oferta cuando se cambian las asociaciones de un plan que ya se estaba utilizando.
- Revertir el código no elimina los documentos nuevos. Conservar un respaldo de la base antes de desplegar.

## Validación
El entorno local no pudo iniciarse. Se preparó GitHub Actions con PostgreSQL descartable y datos ficticios, sin credenciales ni catálogos de producción.

La suite comprueba edición persistente, recuperación de lectura, código de cátedra intacto, rechazo de revisiones antiguas, correlatividades inválidas, movimiento de pendientes, oferta independiente por período, conteo de alumnos distintos, cátedras compartidas, disponibilidad durante toda la clase, revalidación al asignar y horas calculadas desde horarios.

Las pruebas de contenido académico privado no se ejecutan en GitHub; se omiten expresamente. La aprobación de estos controles no sustituye una revisión visual con usuarios ni pruebas con una copia privada de datos reales.
