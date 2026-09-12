# Método común con adaptación institucional

> Documento de la primera entrega. La implementación posterior de importaciones,
> sus cambios de compatibilidad y la validación de v19 están en
> [IMPORTACIONES_V19.md](IMPORTACIONES_V19.md). La reorganización posterior del panel
> y el cuatrimestre único están en [PANEL_V20.md](PANEL_V20.md).

## Decisión de producto

Mantener un solo producto y una misma base de código. El IEA será un perfil
institucional con sus reglas, catálogos y formatos. Cada nuevo requerimiento debe
clasificarse como regla general, parámetro institucional, adaptación de archivos
o módulo opcional. Evitar copias del código por cliente.

El primer segmento a validar es el de instituciones con organización semejante:
oferta por períodos, comisiones, docentes compartidos e intercambio de planillas.
Esta decisión no implica que el sistema ya sirva para cualquier escuela,
universidad o régimen académico.

## Método de trabajo propuesto

El siguiente es el proceso objetivo de producto. Esta entrega implementa la
configuración indicada más abajo; no implementa todavía todos estos pasos como
un asistente de interfaz ni como estados persistidos.

| Paso | Trabajo común | Resultado verificable | Adaptación institucional |
|---|---|---|---|
| 1. Preparar el período | Confirmar calendario, sedes, turnos y criterios | Marco de planificación identificado | Fechas, nombres, modalidades y reglas |
| 2. Preparar los datos | Incorporar materias, carreras, docentes y demanda | Datos válidos y reporte de filas rechazadas | Columnas y equivalencias de cada archivo |
| 3. Definir la oferta | Elegir qué se dicta y qué comisiones se necesitan | Oferta por período y sede; excepciones justificadas | Mínimos, cupos, modalidades permitidas |
| 4. Armar el borrador | Asignar docentes, franjas y recursos | Asignaciones editables con restricciones visibles | Disponibilidad, duración, horas máximas, sedes |
| 5. Validar | Revisar cruces, faltantes y excepciones | Errores bloqueantes y advertencias separados | Preferencias flexibles y excepciones permitidas |
| 6. Publicar una versión | Confirmar el horario aprobado y exportar | Versión identificada, recuperable y trazable | Formato de salida y destinatarios |
| 7. Gestionar cambios | Comparar una nueva propuesta con lo publicado | Diferencias y nueva validación antes de reemplazar | Circuito interno de aprobación |

La oferta y la demanda pueden iterarse durante la preparación. La publicación
debe exigir un período concreto y una validación del estado completo. “Exportar”
y “publicar” son operaciones distintas; hoy se dispone principalmente de la
primera. El usuario debe poder conservar sus planillas y su orden práctico de
preparación, cumpliendo las mismas condiciones antes del cierre.

## Primera mejora implementada

| Aspecto | Perfil IEA | Perfil de prueba |
|---|---|---|
| Mínimo para sugerir apertura con docente | 10 inscriptos | 15 inscriptos |
| Alumnos por docente sugerido | 100 | 40 |
| Duración sugerida cuando falta hora de fin | 90 minutos | 60 minutos |
| Nombre en acceso, menú y título del navegador | IEA Horarios | Planificación académica |
| Equivalencias de carreras | Catálogo original IEA | Catálogo propio del perfil |

Las reglas de apertura y cantidad de docentes se comparten entre catálogo,
pendientes, dictado, sugerencias, controles y exportaciones. La interfaz obtiene
el mismo perfil del servidor. La duración se utiliza para sugerir la hora final,
calcular cargas y comparar franjas que no tienen fin explícito. Un horario con
fin explícito conserva su duración.

El control académico toma el año y número del período seleccionado, tanto en
pantalla como en Excel. Los nombres de carreras que no requieren un alias ya
no se descartan automáticamente por no estar en una lista fija.

No se cambian registros existentes al seleccionar un perfil. Las sugerencias y
las duraciones estimadas sí pueden cambiar: todo cambio de criterio requiere
revisar sus consecuencias antes del siguiente cierre. El perfil se carga al
iniciar el proceso; requiere reiniciar el backend para aplicar cambios.

## Configuración y compatibilidad

El perfil por defecto es `backend/app/profiles/iea.json`. Conserva los criterios
y las equivalencias previas. Un archivo explícito se selecciona con la variable
de despliegue `INSTITUTION_CONFIG`, que puede usar una ruta absoluta o una ruta
relativa al directorio de inicio del backend. Por ejemplo, iniciando desde backend:

```bash
INSTITUTION_CONFIG=app/profiles/institucion-ejemplo.json uvicorn app.main:app
```

El archivo usa un esquema versionado y estricto: todos los campos son necesarios;
las claves desconocidas, los números inválidos o un archivo inexistente producen
un error de inicio. Un perfil inválido no se reemplaza silenciosamente por IEA.
El endpoint de lectura `GET /api/institucion` expone solamente el nombre y las
reglas necesarias para la interfaz. No se agregó una API para cambiar reglas.

El frontend requiere ese endpoint y muestra un error con reintento si no puede
cargarlo. Para revisar o desplegar esta versión, actualizar primero el backend y
después el frontend. El frontend anterior puede seguir usando el backend nuevo;
el frontend nuevo requiere el backend nuevo. Para revertir, restaurar primero el
frontend anterior y después el backend anterior. Esta entrega no fue desplegada.

Los perfiles con identificador distinto de `iea` omiten la carga automática de
personas y catálogos del IEA. Usar una base nueva y descartable para evaluar el
perfil de prueba; cambiar un perfil no borra ni separa datos de una base existente.
Se mantiene el arranque y el calendario heredados para compatibilidad.

## Qué todavía es específico del IEA

- Desgloses de sedes y turnos en tablas, estadísticas y exportaciones.
- Lectura de Excel por posiciones, nombres y convenciones institucionales.
- Normalización y búsqueda aproximada de carreras y sedes en el control académico.
- Calendario de dos períodos por año, ingresos marzo/agosto y cálculo limitado
  a tres años; el tratamiento de fechas inválidas sigue pendiente.
- Sugerencia asincrónica para grupos con alumnos por debajo del mínimo. Otras
  instituciones pueden requerir posponer, combinar o abrir una excepción.
- BCE/BEA, EDI, referencias a CIED y otras decisiones de la operación actual.

El perfil de prueba verifica la separación de algunos parámetros; no constituye
una implementación comercial completa para un segundo cliente.

## Próximas entregas técnicas

1. Hacer atómicas y recuperables las importaciones: validar antes de reemplazar,
   diferenciar actualización y reemplazo completo, respetar sede/período y detener
   cambios si no hay respaldo válido. Corregir la restauración incompleta.
2. Unificar las restricciones de docentes, comisiones y períodos en un servicio
   común; aplicar las mismas reglas al crear, editar, importar y publicar.
3. Definir un formato común de intercambio con campos separados para carrera,
   sede, modalidad y turno. Convertir los Excel del IEA a ese formato mediante un
   adaptador; incorporar mapeo de columnas para otros archivos. Usar identificadores
   estables en vez de depender de textos concatenados o coincidencias aproximadas.
4. Generalizar sedes, turnos, calendario, decisiones bajo el mínimo y reportes.
   Mantener BCE/BEA y EDI como módulos opcionales, según su necesidad real.
5. Incorporar borrador, validación, versión publicada y comparación de cambios.
   Validar el proceso con una segunda institución antes de ampliar el producto.

## Coordinación con IEA e ITOESTE

| Frente | Trabajo previsto |
|---|---|
| Desarrollo técnico de esta línea | Motor de reglas, integridad de datos, configuración, importadores, exportaciones y pruebas |
| IEA | Confirmar restricciones obligatorias, excepciones reales, entradas, salidas y criterios de aceptación |
| ITOESTE con IEA | Seguridad, identidades, permisos, sesiones, operación simultánea, experiencia de varios usuarios y despliegue |
| Acuerdo conjunto | Quién modifica reglas, cómo se aprueba una versión, qué ocurre con cambios simultáneos y cómo se recupera información |

La configuración institucional no representa aislamiento entre clientes. Se
carga un perfil por despliegue. ITOESTE deberá definir si cada cliente tendrá
instancia y base propias o si habrá una arquitectura compartida con aislamiento
explícito. Ese contrato afecta a los datos y debe acordarse antes de implementar
la publicación y edición simultánea.

Los problemas de seguridad y de integridad identificados en la auditoría siguen
siendo pendientes salvo las correcciones expresamente indicadas en esta entrega.
En particular, esta configuración no corrige la autenticación de la API ni hace
seguras las importaciones destructivas. La rama debe revisarse antes de integrar
y no acredita preparación comercial.

## Verificación reproducible

Pruebas de reglas sin base de datos, desde backend:

```bash
python -m unittest discover -s tests -p test_institution.py -v
```

Pruebas de integración: instalar requirements.txt y `httpx==0.27.2` en un entorno
local, usar PostgreSQL local descartable con DATABASE_URL y declarar
`TEST_DATABASE_DISPOSABLE=yes`. El archivo `tests/test_institution_api.py` borra
las tablas públicas al preparar cada caso y rechaza destinos distintos de
localhost o 127.0.0.1. Ejecutar exclusivamente contra una base de pruebas vacía:

```bash
python -m unittest discover -s tests -p test_institution_api.py -v
```

Pruebas de componentes, desde validation, con Node 24 o superior:

```bash
npm ci
npm test
```

Los fixtures de interfaz contienen respuestas con alumnos y docentes ficticios.
Las pruebas no acceden a Railway. El entorno usado para la integración fue
PGlite 0.5.8/PostgreSQL 18.3, Python 3.12.14 y las dependencias originales del
backend; queda pendiente verificarlo con la versión efectiva de PostgreSQL y
Python del despliegue.

Resultado local del 12/09/2026: 5 pruebas de reglas, 6 de integración y 5 de
componentes nuevas satisfactorias. Pasaron además 9 escenarios seleccionados de
la auditoría original: lecturas y exportaciones básicas, ficha docente,
disponibilidad, cruces, umbrales, conteos, excepciones y recorrido de planilla.
Se repitieron las 29 comprobaciones anteriores de componentes: 27 satisfactorias
y las mismas 2 fallas conocidas de permisos de consulta y aviso de carga de datos.
No se verificó un despliegue, un build de producción de React ni concurrencia.
