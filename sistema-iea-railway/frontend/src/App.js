import React, { useState, useMemo } from 'react';

// ============ MODELO DE DATOS CORREGIDO ============
// Una cátedra puede tener MÚLTIPLES asignaciones (TM, TN, presencial) en el mismo cuatrimestre

const SEDES = [
  { id: 1, nombre: 'Online - Interior', color: 'bg-purple-500' },
  { id: 2, nombre: 'Avellaneda', color: 'bg-blue-500' },
  { id: 3, nombre: 'Caballito', color: 'bg-emerald-500' },
  { id: 4, nombre: 'Vicente López', color: 'bg-amber-500' },
  { id: 5, nombre: 'Liniers', color: 'bg-pink-500' },
  { id: 6, nombre: 'Monte Grande', color: 'bg-cyan-500' },
];

// Generar 50 cátedras de ejemplo (en producción serían 635)
const generarCatedras = () => {
  const nombres = [
    'Administración', 'Informática I', 'Derecho', 'Economía', 'Contabilidad',
    'Matemática I', 'Sociología', 'Metodología de la Investigación', 'Marketing', 'Inglés I',
    'Informática II', 'Derecho Laboral', 'Administración de Personal', 'Matemática II', 'Derecho Comercial',
    'Admin de la Producción', 'Inglés II', 'Técnica Impositiva', 'Derecho Tributario', 'Comercio Internacional',
    'Costos y Presupuestos', 'Administración Estratégica', 'Administración Financiera', 'Estadística', 'Dirección de las Organizaciones',
    'Administración de RRHH', 'Análisis de Sector Industrial', 'Intro a la Publicidad', 'Métodos Cuantitativos', 'Teoría de Sistemas',
    'Psicología Social', 'Comunicación', 'Ética Profesional', 'Geografía Turística', 'Historia del Arte',
    'Patrimonio Cultural', 'Hotelería I', 'Hotelería II', 'Turismo I', 'Turismo II',
    'Gastronomía', 'Eventos', 'Protocolo', 'Relaciones Públicas', 'Periodismo',
    'Redacción', 'Fotografía', 'Diseño Gráfico', 'Marketing Digital', 'E-Commerce'
  ];
  
  return nombres.map((nombre, i) => ({
    id: i + 1,
    codigo: `c.${i + 1}`,
    nombre,
    inscriptos: i === 1 ? 715 : 0 // Solo c.2 tiene inscriptos
  }));
};

const CATEDRAS_BASE = generarCatedras();

const DOCENTES = [
  { id: 1, nombre: 'María', apellido: 'García', dni: '20345678', sede: 'Caballito' },
  { id: 2, nombre: 'Juan', apellido: 'Pérez', dni: '21456789', sede: 'Online - Interior' },
  { id: 3, nombre: 'Ana', apellido: 'López', dni: '22567890', sede: 'Avellaneda' },
  { id: 4, nombre: 'Carlos', apellido: 'Ruiz', dni: '23678901', sede: 'Vicente López' },
  { id: 5, nombre: 'Diego', apellido: 'Torres', dni: '24789012', sede: 'Avellaneda' },
  { id: 6, nombre: 'Laura', apellido: 'Fernández', dni: '25890123', sede: 'Caballito' },
  { id: 7, nombre: 'Pedro', apellido: 'Martínez', dni: '26901234', sede: 'Liniers' },
  { id: 8, nombre: 'Sofía', apellido: 'Díaz', dni: '27012345', sede: 'Online - Interior' },
];

// Asignaciones iniciales de ejemplo
const ASIGNACIONES_INICIAL = [
  { id: 1, catedra_id: 2, cuatrimestre: 1, modalidad: 'virtual_tm', docente_id: 2, dia: 'Martes', hora: '08:00' },
  { id: 2, catedra_id: 2, cuatrimestre: 1, modalidad: 'virtual_tn', docente_id: 2, dia: 'Martes', hora: '20:00' },
  { id: 3, catedra_id: 9, cuatrimestre: 1, modalidad: 'virtual_tn', docente_id: 5, dia: 'Jueves', hora: '19:00' },
  { id: 4, catedra_id: 4, cuatrimestre: 1, modalidad: 'asincronica', docente_id: null, dia: null, hora: null },
  { id: 5, catedra_id: 16, cuatrimestre: 1, modalidad: 'presencial', docente_id: 1, dia: 'Miércoles', hora: '10:00' },
  { id: 6, catedra_id: 7, cuatrimestre: 2, modalidad: 'asincronica', docente_id: null, dia: null, hora: null },
];

const SEDE_COLORS = {
  'Online - Interior': 'bg-purple-500', 'Avellaneda': 'bg-blue-500', 'Caballito': 'bg-emerald-500',
  'Vicente López': 'bg-amber-500', 'Liniers': 'bg-pink-500', 'Monte Grande': 'bg-cyan-500',
};

const MODALIDAD_CONFIG = {
  'virtual_tm': { label: 'Virtual TM', icon: '🖥️☀️', color: 'text-blue-600', bg: 'bg-blue-50' },
  'virtual_tn': { label: 'Virtual TN', icon: '🖥️🌙', color: 'text-indigo-600', bg: 'bg-indigo-50' },
  'presencial': { label: 'Presencial', icon: '🏫', color: 'text-emerald-600', bg: 'bg-emerald-50' },
  'asincronica': { label: 'Asincrónica', icon: '🎥', color: 'text-purple-600', bg: 'bg-purple-50' },
};

const DIAS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado'];
const HORAS_MANANA = ['07:00', '08:00', '09:00', '10:00', '11:00', '12:00', '13:00'];
const HORAS_NOCHE = ['18:00', '19:00', '20:00', '21:00', '22:00', '23:00'];

// ============ COMPONENTES ============

function Sidebar({ activeView, setActiveView, cuatrimestre, setCuatrimestre, stats }) {
  const menuItems = [
    { id: 'catedras', icon: '📚', label: 'Cátedras' },
    { id: 'horarios', icon: '📅', label: 'Horarios' },
    { id: 'docentes', icon: '👨‍🏫', label: 'Docentes' },
    { id: 'importar', icon: '📥', label: 'Importar', highlight: true },
    { id: 'cambios', icon: '📝', label: 'Cambios', badge: stats.modificadas },
    { id: 'exportar', icon: '📤', label: 'Exportar' },
  ];

  return (
    <div className="w-64 bg-slate-900 min-h-screen p-4 flex flex-col">
      <div className="mb-6 px-2">
        <h1 className="text-xl font-bold text-white">IEA Horarios</h1>
        <p className="text-slate-500 text-sm">Sistema v2.0</p>
      </div>
      
      <div className="mb-6 px-2">
        <label className="text-xs text-slate-400 block mb-1">Ver cuatrimestre</label>
        <select className="w-full bg-slate-800 text-white rounded px-3 py-2 text-sm border border-slate-700" value={cuatrimestre} onChange={(e) => setCuatrimestre(e.target.value)}>
          <option value="todos">Todos</option>
          <option value="1">1er Cuatrimestre 2026</option>
          <option value="2">2do Cuatrimestre 2026</option>
        </select>
      </div>
      
      <nav className="flex-1 space-y-1">
        {menuItems.map(item => (
          <button key={item.id} onClick={() => setActiveView(item.id)} className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-all ${activeView === item.id ? 'bg-amber-500 text-slate-900 font-medium' : item.highlight ? 'text-amber-400 hover:bg-slate-800' : 'text-slate-400 hover:bg-slate-800'}`}>
            <span className="text-lg">{item.icon}</span>
            <span className="flex-1">{item.label}</span>
            {item.badge > 0 && <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-red-500 text-white">{item.badge}</span>}
          </button>
        ))}
      </nav>
      
      <div className="mt-4 p-3 bg-slate-800/50 rounded-lg">
        <p className="text-xs text-slate-400 mb-2">Sedes</p>
        {SEDES.map(s => (
          <div key={s.id} className="flex items-center gap-2 mb-1">
            <div className={`w-2 h-2 rounded-full ${s.color}`}></div>
            <span className="text-[10px] text-slate-300">{s.nombre}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ============ VISTA CÁTEDRAS ============
function CatedrasView({ catedras, asignaciones, setAsignaciones, filtroCuatrimestre }) {
  const [filtros, setFiltros] = useState({ buscar: '', soloSinAsignar: false });
  const [modalConfig, setModalConfig] = useState(null);
  const [paginaActual, setPaginaActual] = useState(1);
  const porPagina = 20;

  // Filtrar cátedras
  const catedrasFiltradas = useMemo(() => {
    return catedras.filter(c => {
      if (filtros.buscar && !c.nombre.toLowerCase().includes(filtros.buscar.toLowerCase()) && !c.codigo.toLowerCase().includes(filtros.buscar.toLowerCase())) return false;
      
      if (filtros.soloSinAsignar) {
        const tieneAsignacion = asignaciones.some(a => 
          a.catedra_id === c.id && 
          (filtroCuatrimestre === 'todos' || a.cuatrimestre === parseInt(filtroCuatrimestre))
        );
        if (tieneAsignacion) return false;
      }
      
      return true;
    });
  }, [catedras, filtros, asignaciones, filtroCuatrimestre]);

  // Paginación
  const totalPaginas = Math.ceil(catedrasFiltradas.length / porPagina);
  const catedrasPaginadas = catedrasFiltradas.slice((paginaActual - 1) * porPagina, paginaActual * porPagina);

  // Stats
  const getAsignacionesCatedra = (catedraId) => asignaciones.filter(a => a.catedra_id === catedraId);
  const totalAsignaciones = asignaciones.length;
  const asincronicas = asignaciones.filter(a => a.modalidad === 'asincronica').length;
  const conDocente = asignaciones.filter(a => a.docente_id && a.modalidad !== 'asincronica').length;
  const sinDocente = asignaciones.filter(a => !a.docente_id && a.modalidad !== 'asincronica').length;
  const totalInscriptos = catedras.reduce((a, c) => a + c.inscriptos, 0);

  // Agregar asignación
  const agregarAsignacion = (catedraId, modalidad, cuatri) => {
    const nuevaAsignacion = {
      id: Date.now(),
      catedra_id: catedraId,
      cuatrimestre: cuatri,
      modalidad,
      docente_id: null,
      dia: null,
      hora: null
    };
    setAsignaciones([...asignaciones, nuevaAsignacion]);
  };

  // Eliminar asignación
  const eliminarAsignacion = (asignacionId) => {
    setAsignaciones(asignaciones.filter(a => a.id !== asignacionId));
  };

  return (
    <div className="p-8">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-slate-800">Cátedras</h2>
        <p className="text-slate-500 text-sm">
          {filtroCuatrimestre === 'todos' ? 'Todas las cátedras' : `Viendo ${filtroCuatrimestre === '1' ? '1er' : '2do'} Cuatrimestre 2026`}
        </p>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-6 gap-3 mb-6">
        <div className="bg-white rounded-xl border p-4 text-center">
          <p className="text-slate-500 text-xs">Total Cátedras</p>
          <p className="text-2xl font-bold">{catedras.length}</p>
        </div>
        <div className="bg-white rounded-xl border p-4 text-center">
          <p className="text-slate-500 text-xs">📋 Asignaciones</p>
          <p className="text-2xl font-bold text-blue-600">{totalAsignaciones}</p>
        </div>
        <div className="bg-white rounded-xl border p-4 text-center">
          <p className="text-slate-500 text-xs">🎥 Asincrónicas</p>
          <p className="text-2xl font-bold text-purple-600">{asincronicas}</p>
        </div>
        <div className="bg-white rounded-xl border p-4 text-center">
          <p className="text-slate-500 text-xs">👨‍🏫 Con Docente</p>
          <p className="text-2xl font-bold text-emerald-600">{conDocente}</p>
        </div>
        <div className="bg-white rounded-xl border p-4 text-center">
          <p className="text-slate-500 text-xs">⚠️ Sin Docente</p>
          <p className="text-2xl font-bold text-red-600">{sinDocente}</p>
        </div>
        <div className="bg-white rounded-xl border p-4 text-center">
          <p className="text-slate-500 text-xs">👥 Inscriptos</p>
          <p className="text-2xl font-bold text-cyan-600">{totalInscriptos}</p>
        </div>
      </div>

      {/* Filtros */}
      <div className="flex gap-3 mb-4 bg-white p-4 rounded-xl border items-center">
        <input 
          type="text" 
          placeholder="Buscar por código o nombre..." 
          className="px-3 py-2 border rounded-lg text-sm flex-1"
          value={filtros.buscar}
          onChange={e => { setFiltros({...filtros, buscar: e.target.value}); setPaginaActual(1); }}
        />
        <label className="flex items-center gap-2 text-sm">
          <input 
            type="checkbox" 
            checked={filtros.soloSinAsignar}
            onChange={e => { setFiltros({...filtros, soloSinAsignar: e.target.checked}); setPaginaActual(1); }}
          />
          Solo sin asignación
        </label>
        <span className="text-sm text-slate-500">
          {catedrasFiltradas.length} cátedras | Página {paginaActual} de {totalPaginas}
        </span>
      </div>

      {/* Tabla */}
      <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="bg-slate-50 border-b">
              <th className="text-left p-4 text-sm font-semibold text-slate-600 w-1/3">Cátedra</th>
              <th className="text-left p-4 text-sm font-semibold text-slate-600">Asignaciones este cuatrimestre</th>
              <th className="text-center p-4 text-sm font-semibold text-slate-600 w-24">Inscriptos</th>
              <th className="text-center p-4 text-sm font-semibold text-slate-600 w-32">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {catedrasPaginadas.map(cat => {
              const asignacionesCat = getAsignacionesCatedra(cat.id).filter(a => 
                filtroCuatrimestre === 'todos' || a.cuatrimestre === parseInt(filtroCuatrimestre)
              );
              
              return (
                <tr key={cat.id} className="border-b hover:bg-slate-50">
                  <td className="p-4">
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-1 bg-slate-800 text-white rounded text-xs font-mono">{cat.codigo}</span>
                      <span className="font-medium">{cat.nombre}</span>
                    </div>
                  </td>
                  <td className="p-4">
                    {asignacionesCat.length > 0 ? (
                      <div className="flex flex-wrap gap-2">
                        {asignacionesCat.map(a => {
                          const docente = DOCENTES.find(d => d.id === a.docente_id);
                          const config = MODALIDAD_CONFIG[a.modalidad];
                          return (
                            <div key={a.id} className={`px-3 py-2 rounded-lg ${config.bg} text-sm flex items-center gap-2`}>
                              <span>{config.icon}</span>
                              <div>
                                <p className={`font-medium ${config.color}`}>{config.label}</p>
                                {a.modalidad !== 'asincronica' && (
                                  <p className="text-xs text-slate-500">
                                    {docente ? `${docente.nombre} ${docente.apellido}` : '⚠️ Sin docente'}
                                    {a.dia && ` • ${a.dia} ${a.hora}`}
                                  </p>
                                )}
                              </div>
                              <button onClick={() => eliminarAsignacion(a.id)} className="text-red-400 hover:text-red-600 ml-2">×</button>
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      <span className="text-slate-400 text-sm">Sin asignaciones</span>
                    )}
                  </td>
                  <td className="p-4 text-center">
                    <span className={`text-xl font-bold ${cat.inscriptos > 0 ? 'text-cyan-600' : 'text-slate-300'}`}>
                      {cat.inscriptos}
                    </span>
                  </td>
                  <td className="p-4 text-center">
                    <button 
                      onClick={() => setModalConfig(cat)}
                      className="px-3 py-1.5 bg-amber-500 text-slate-900 rounded text-sm font-medium hover:bg-amber-400"
                    >
                      + Asignar
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Paginación */}
      <div className="flex justify-center gap-2 mt-4">
        <button 
          onClick={() => setPaginaActual(Math.max(1, paginaActual - 1))}
          disabled={paginaActual === 1}
          className="px-3 py-1 bg-slate-200 rounded disabled:opacity-50"
        >
          ← Anterior
        </button>
        {[...Array(Math.min(5, totalPaginas))].map((_, i) => {
          const pageNum = Math.max(1, Math.min(paginaActual - 2, totalPaginas - 4)) + i;
          if (pageNum > totalPaginas) return null;
          return (
            <button
              key={pageNum}
              onClick={() => setPaginaActual(pageNum)}
              className={`px-3 py-1 rounded ${paginaActual === pageNum ? 'bg-amber-500 text-white' : 'bg-slate-200'}`}
            >
              {pageNum}
            </button>
          );
        })}
        <button 
          onClick={() => setPaginaActual(Math.min(totalPaginas, paginaActual + 1))}
          disabled={paginaActual === totalPaginas}
          className="px-3 py-1 bg-slate-200 rounded disabled:opacity-50"
        >
          Siguiente →
        </button>
      </div>

      {/* Modal agregar asignación */}
      {modalConfig && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-bold mb-2">Agregar Asignación</h3>
            <p className="text-slate-600 mb-4">{modalConfig.codigo} - {modalConfig.nombre}</p>
            
            <p className="text-sm text-slate-500 mb-3">Seleccionar cuatrimestre y modalidad:</p>
            
            {[1, 2].map(cuatri => (
              <div key={cuatri} className="mb-4">
                <p className="text-sm font-medium mb-2">{cuatri === 1 ? '1er' : '2do'} Cuatrimestre:</p>
                <div className="grid grid-cols-2 gap-2">
                  {Object.entries(MODALIDAD_CONFIG).map(([key, config]) => (
                    <button
                      key={key}
                      onClick={() => { agregarAsignacion(modalConfig.id, key, cuatri); setModalConfig(null); }}
                      className={`p-2 border rounded-lg hover:${config.bg} text-left text-sm flex items-center gap-2`}
                    >
                      <span>{config.icon}</span>
                      <span>{config.label}</span>
                    </button>
                  ))}
                </div>
              </div>
            ))}
            
            <button onClick={() => setModalConfig(null)} className="w-full mt-2 p-2 bg-slate-100 rounded-lg">Cancelar</button>
          </div>
        </div>
      )}
    </div>
  );
}

// ============ VISTA DOCENTES ============
function DocentesView({ catedras, asignaciones, setAsignaciones, filtroCuatrimestre }) {
  const [modalAsignar, setModalAsignar] = useState(null);
  const [filtroModal, setFiltroModal] = useState('');

  // Calcular stats por docente
  const docentesConStats = useMemo(() => {
    return DOCENTES.map(d => {
      const asignacionesDocente = asignaciones.filter(a => 
        a.docente_id === d.id &&
        (filtroCuatrimestre === 'todos' || a.cuatrimestre === parseInt(filtroCuatrimestre))
      );
      
      const detalles = asignacionesDocente.map(a => {
        const cat = catedras.find(c => c.id === a.catedra_id);
        return { ...a, catedra: cat };
      });
      
      const horas = asignacionesDocente.length * 2;
      const alumnos = detalles.reduce((acc, a) => acc + (a.catedra?.inscriptos || 0), 0);
      
      return { ...d, asignaciones: detalles, horas, alumnos };
    });
  }, [asignaciones, catedras, filtroCuatrimestre]);

  // Asignaciones sin docente (disponibles)
  const asignacionesSinDocente = useMemo(() => {
    return asignaciones.filter(a => 
      !a.docente_id && 
      a.modalidad !== 'asincronica' &&
      (filtroCuatrimestre === 'todos' || a.cuatrimestre === parseInt(filtroCuatrimestre))
    ).map(a => ({
      ...a,
      catedra: catedras.find(c => c.id === a.catedra_id)
    })).filter(a => 
      !filtroModal || 
      a.catedra?.nombre.toLowerCase().includes(filtroModal.toLowerCase()) ||
      a.catedra?.codigo.toLowerCase().includes(filtroModal.toLowerCase())
    );
  }, [asignaciones, catedras, filtroCuatrimestre, filtroModal]);

  // TODAS las cátedras para asignar (crear nueva asignación)
  const catedrasParaAsignar = useMemo(() => {
    return catedras.filter(c =>
      !filtroModal ||
      c.nombre.toLowerCase().includes(filtroModal.toLowerCase()) ||
      c.codigo.toLowerCase().includes(filtroModal.toLowerCase())
    );
  }, [catedras, filtroModal]);

  const asignarDocente = (asignacionId, docenteId) => {
    setAsignaciones(asignaciones.map(a => 
      a.id === asignacionId ? { ...a, docente_id: docenteId } : a
    ));
  };

  const crearYAsignar = (catedraId, modalidad, cuatri, docenteId) => {
    const nueva = {
      id: Date.now(),
      catedra_id: catedraId,
      cuatrimestre: cuatri,
      modalidad,
      docente_id: docenteId,
      dia: null,
      hora: null
    };
    setAsignaciones([...asignaciones, nueva]);
  };

  const desasignarDocente = (asignacionId) => {
    setAsignaciones(asignaciones.map(a => 
      a.id === asignacionId ? { ...a, docente_id: null } : a
    ));
  };

  const actualizarHorario = (asignacionId, dia, hora) => {
    setAsignaciones(asignaciones.map(a =>
      a.id === asignacionId ? { ...a, dia, hora } : a
    ));
  };

  const totalHoras = docentesConStats.reduce((a, d) => a + d.horas, 0);
  const totalAlumnos = docentesConStats.reduce((a, d) => a + d.alumnos, 0);

  return (
    <div className="p-8">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-slate-800">Docentes</h2>
        <p className="text-slate-500 text-sm">Asignación de cátedras y horarios por docente</p>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-5 gap-4 mb-6">
        <div className="bg-white rounded-xl border p-4"><p className="text-slate-500 text-sm">Total Docentes</p><p className="text-2xl font-bold">{DOCENTES.length}</p></div>
        <div className="bg-white rounded-xl border p-4"><p className="text-slate-500 text-sm">Horas/Sem</p><p className="text-2xl font-bold text-blue-600">{totalHoras}</p></div>
        <div className="bg-white rounded-xl border p-4"><p className="text-slate-500 text-sm">Promedio</p><p className="text-2xl font-bold text-emerald-600">{DOCENTES.length ? Math.round(totalHoras / DOCENTES.length) : 0}hs</p></div>
        <div className="bg-white rounded-xl border p-4"><p className="text-slate-500 text-sm">Alumnos</p><p className="text-2xl font-bold text-purple-600">{totalAlumnos}</p></div>
        <div className="bg-white rounded-xl border p-4"><p className="text-slate-500 text-sm">Asig. sin docente</p><p className="text-2xl font-bold text-orange-600">{asignacionesSinDocente.length}</p></div>
      </div>

      {/* Tabla */}
      <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="bg-slate-50 border-b">
              <th className="text-left p-4 text-sm font-semibold">Docente</th>
              <th className="text-center p-4 text-sm font-semibold">Sede</th>
              <th className="text-left p-4 text-sm font-semibold">Cátedras Asignadas (con día/horario)</th>
              <th className="text-center p-4 text-sm font-semibold">Hs</th>
              <th className="text-center p-4 text-sm font-semibold">Alum.</th>
              <th className="text-center p-4 text-sm font-semibold">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {docentesConStats.map(d => (
              <tr key={d.id} className="border-b hover:bg-slate-50">
                <td className="p-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-slate-800 text-white flex items-center justify-center font-bold text-sm">{d.nombre[0]}{d.apellido[0]}</div>
                    <div>
                      <p className="font-medium">{d.nombre} {d.apellido}</p>
                      <p className="text-xs text-slate-500">{d.dni}</p>
                    </div>
                  </div>
                </td>
                <td className="p-4 text-center">
                  <span className={`px-2 py-1 rounded text-white text-xs ${SEDE_COLORS[d.sede]}`}>{d.sede}</span>
                </td>
                <td className="p-4">
                  {d.asignaciones.length > 0 ? (
                    <div className="space-y-2">
                      {d.asignaciones.map(a => (
                        <div key={a.id} className="flex items-center gap-2 text-sm">
                          <span className={MODALIDAD_CONFIG[a.modalidad]?.color}>
                            {MODALIDAD_CONFIG[a.modalidad]?.icon}
                          </span>
                          <span className="font-mono bg-slate-100 px-1 rounded">{a.catedra?.codigo}</span>
                          <span className="truncate max-w-[150px]">{a.catedra?.nombre}</span>
                          <select 
                            className="text-xs border rounded px-1 py-0.5"
                            value={a.dia || ''}
                            onChange={e => actualizarHorario(a.id, e.target.value, a.hora)}
                          >
                            <option value="">Día</option>
                            {DIAS.map(dia => <option key={dia} value={dia}>{dia.slice(0,3)}</option>)}
                          </select>
                          <select
                            className="text-xs border rounded px-1 py-0.5"
                            value={a.hora || ''}
                            onChange={e => actualizarHorario(a.id, a.dia, e.target.value)}
                          >
                            <option value="">Hora</option>
                            {(a.modalidad === 'virtual_tm' ? HORAS_MANANA : HORAS_NOCHE).map(h => 
                              <option key={h} value={h}>{h}</option>
                            )}
                          </select>
                          <button onClick={() => desasignarDocente(a.id)} className="text-red-400 hover:text-red-600">×</button>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <span className="text-slate-400 text-sm">Sin cátedras</span>
                  )}
                </td>
                <td className="p-4 text-center"><span className="font-bold">{d.horas}</span></td>
                <td className="p-4 text-center"><span className="font-bold text-purple-600">{d.alumnos}</span></td>
                <td className="p-4 text-center">
                  <button 
                    onClick={() => { setModalAsignar(d); setFiltroModal(''); }}
                    className="px-3 py-1.5 bg-amber-500 text-slate-900 rounded text-sm font-medium hover:bg-amber-400"
                  >
                    + Asignar
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Modal asignar */}
      {modalAsignar && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 max-w-2xl w-full mx-4 max-h-[85vh] overflow-auto">
            <h3 className="text-lg font-bold mb-2">Asignar Cátedra</h3>
            <p className="text-slate-600 mb-4">Docente: <strong>{modalAsignar.nombre} {modalAsignar.apellido}</strong></p>
            
            <input
              type="text"
              placeholder="Buscar cátedra..."
              className="w-full px-3 py-2 border rounded-lg mb-4"
              value={filtroModal}
              onChange={e => setFiltroModal(e.target.value)}
            />

            {/* Asignaciones existentes sin docente */}
            {asignacionesSinDocente.length > 0 && (
              <div className="mb-6">
                <p className="text-sm font-medium text-orange-600 mb-2">⚠️ Asignaciones existentes sin docente ({asignacionesSinDocente.length}):</p>
                <div className="space-y-2 max-h-40 overflow-auto">
                  {asignacionesSinDocente.map(a => (
                    <button
                      key={a.id}
                      onClick={() => { asignarDocente(a.id, modalAsignar.id); setModalAsignar(null); }}
                      className="w-full p-2 border rounded-lg hover:bg-slate-50 text-left flex items-center justify-between"
                    >
                      <div className="flex items-center gap-2">
                        <span className={MODALIDAD_CONFIG[a.modalidad]?.color}>{MODALIDAD_CONFIG[a.modalidad]?.icon}</span>
                        <span className="font-mono text-sm">{a.catedra?.codigo}</span>
                        <span>{a.catedra?.nombre}</span>
                      </div>
                      <span className="text-xs bg-slate-100 px-2 py-1 rounded">{a.cuatrimestre === 1 ? '1er C' : '2do C'}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Crear nueva asignación */}
            <div>
              <p className="text-sm font-medium text-slate-600 mb-2">📚 O crear nueva asignación ({catedrasParaAsignar.length} cátedras):</p>
              <div className="space-y-1 max-h-60 overflow-auto border rounded-lg p-2">
                {catedrasParaAsignar.slice(0, 50).map(c => (
                  <div key={c.id} className="p-2 hover:bg-slate-50 rounded flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-sm bg-slate-100 px-2 py-0.5 rounded">{c.codigo}</span>
                      <span className="text-sm">{c.nombre}</span>
                    </div>
                    <div className="flex gap-1">
                      {Object.entries(MODALIDAD_CONFIG).filter(([k]) => k !== 'asincronica').map(([key, cfg]) => (
                        <button
                          key={key}
                          onClick={() => { 
                            crearYAsignar(c.id, key, parseInt(filtroCuatrimestre) || 1, modalAsignar.id); 
                            setModalAsignar(null); 
                          }}
                          className="px-2 py-1 text-xs border rounded hover:bg-slate-100"
                          title={cfg.label}
                        >
                          {cfg.icon}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
                {catedrasParaAsignar.length > 50 && (
                  <p className="text-center text-sm text-slate-400 py-2">Mostrando 50 de {catedrasParaAsignar.length}. Usá el buscador.</p>
                )}
              </div>
            </div>
            
            <button onClick={() => setModalAsignar(null)} className="w-full mt-4 p-2 bg-slate-100 rounded-lg">Cerrar</button>
          </div>
        </div>
      )}
    </div>
  );
}

// ============ VISTA HORARIOS ============
function HorariosView({ catedras, asignaciones, filtroCuatrimestre }) {
  const [vistaActiva, setVistaActiva] = useState('grilla');
  const [semanaActual, setSemanaActual] = useState(1);

  // Filtrar asignaciones con horario
  const asignacionesConHorario = useMemo(() => {
    return asignaciones.filter(a => 
      a.dia && a.hora && a.docente_id &&
      (filtroCuatrimestre === 'todos' || a.cuatrimestre === parseInt(filtroCuatrimestre))
    ).map(a => ({
      ...a,
      catedra: catedras.find(c => c.id === a.catedra_id),
      docente: DOCENTES.find(d => d.id === a.docente_id)
    }));
  }, [asignaciones, catedras, filtroCuatrimestre]);

  // Asincrónicas
  const asincronicas = asignaciones.filter(a => 
    a.modalidad === 'asincronica' &&
    (filtroCuatrimestre === 'todos' || a.cuatrimestre === parseInt(filtroCuatrimestre))
  ).map(a => ({
    ...a,
    catedra: catedras.find(c => c.id === a.catedra_id)
  }));

  // Detectar solapamientos
  const solapamientos = useMemo(() => {
    const conflictos = [];
    asignacionesConHorario.forEach((a1, i) => {
      asignacionesConHorario.slice(i + 1).forEach(a2 => {
        if (a1.docente_id === a2.docente_id && a1.dia === a2.dia && a1.hora === a2.hora) {
          conflictos.push({ docente: a1.docente, a1, a2 });
        }
      });
    });
    return conflictos;
  }, [asignacionesConHorario]);

  // Organizar por grilla
  const grilla = useMemo(() => {
    const g = { mañana: {}, noche: {} };
    DIAS.forEach(dia => {
      g.mañana[dia] = {};
      g.noche[dia] = {};
      HORAS_MANANA.forEach(h => g.mañana[dia][h] = []);
      HORAS_NOCHE.forEach(h => g.noche[dia][h] = []);
    });
    
    asignacionesConHorario.forEach(a => {
      const turno = a.modalidad === 'virtual_tm' || a.modalidad === 'presencial' ? 'mañana' : 'noche';
      if (g[turno][a.dia] && g[turno][a.dia][a.hora]) {
        g[turno][a.dia][a.hora].push(a);
      }
    });
    
    return g;
  }, [asignacionesConHorario]);

  const renderCelda = (clases) => {
    if (!clases || clases.length === 0) return <div className="h-16 border-2 border-dashed border-slate-200 rounded"></div>;
    return clases.map((a, i) => (
      <div key={i} className={`p-2 rounded text-white text-xs mb-1 ${SEDE_COLORS[a.docente?.sede] || 'bg-gray-400'}`}>
        <p className="font-bold">{a.catedra?.codigo}</p>
        <p className="opacity-90 truncate">{a.docente?.nombre}</p>
      </div>
    ));
  };

  // Calendario semanal
  const fechasSemanales = useMemo(() => {
    const inicio = new Date(2026, 2, 2 + (semanaActual - 1) * 7);
    return DIAS.slice(0, 6).map((dia, i) => {
      const fecha = new Date(inicio);
      fecha.setDate(inicio.getDate() + i);
      return { dia, fecha: fecha.toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit' }) };
    });
  }, [semanaActual]);

  return (
    <div className="p-8">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-800">Horarios</h2>
          <p className="text-slate-500 text-sm">
            {filtroCuatrimestre === 'todos' ? 'Todos los cuatrimestres' : `${filtroCuatrimestre === '1' ? '1er' : '2do'} Cuatrimestre 2026`}
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setVistaActiva('grilla')} className={`px-4 py-2 rounded-lg ${vistaActiva === 'grilla' ? 'bg-amber-500 text-slate-900' : 'bg-slate-200'}`}>
            📅 Grilla
          </button>
          <button onClick={() => setVistaActiva('calendario')} className={`px-4 py-2 rounded-lg ${vistaActiva === 'calendario' ? 'bg-amber-500 text-slate-900' : 'bg-slate-200'}`}>
            🗓️ Calendario
          </button>
          <button onClick={() => setVistaActiva('solapamientos')} className={`px-4 py-2 rounded-lg ${vistaActiva === 'solapamientos' ? 'bg-amber-500 text-slate-900' : 'bg-slate-200'}`}>
            ⚠️ Solapamientos {solapamientos.length > 0 && <span className="ml-1 px-1.5 bg-red-500 text-white rounded-full text-xs">{solapamientos.length}</span>}
          </button>
        </div>
      </div>

      {/* Vista Grilla */}
      {vistaActiva === 'grilla' && (
        <>
          <div className="bg-white rounded-xl border shadow-sm overflow-x-auto mb-6">
            <div className="bg-amber-100 px-4 py-2 font-semibold text-amber-800">☀️ TURNO MAÑANA</div>
            <table className="w-full min-w-[900px]">
              <thead><tr className="bg-slate-800 text-white"><th className="p-2 w-20">Hora</th>{DIAS.map(d => <th key={d} className="p-2 text-center">{d}</th>)}</tr></thead>
              <tbody>
                {HORAS_MANANA.map(hora => (
                  <tr key={hora} className="border-b">
                    <td className="p-2 font-mono text-sm bg-slate-50 font-semibold">{hora}</td>
                    {DIAS.map(dia => <td key={dia} className="p-1 border-l">{renderCelda(grilla.mañana[dia]?.[hora])}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="bg-white rounded-xl border shadow-sm overflow-x-auto mb-6">
            <div className="bg-indigo-100 px-4 py-2 font-semibold text-indigo-800">🌙 TURNO NOCHE</div>
            <table className="w-full min-w-[900px]">
              <thead><tr className="bg-slate-800 text-white"><th className="p-2 w-20">Hora</th>{DIAS.map(d => <th key={d} className="p-2 text-center">{d}</th>)}</tr></thead>
              <tbody>
                {HORAS_NOCHE.map(hora => (
                  <tr key={hora} className="border-b">
                    <td className="p-2 font-mono text-sm bg-slate-50 font-semibold">{hora}</td>
                    {DIAS.map(dia => <td key={dia} className="p-1 border-l">{renderCelda(grilla.noche[dia]?.[hora])}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {asincronicas.length > 0 && (
            <div className="bg-purple-50 rounded-xl border border-purple-200 p-4">
              <h3 className="font-semibold text-purple-800 mb-3">🎥 Cátedras Asincrónicas ({asincronicas.length})</h3>
              <div className="flex flex-wrap gap-2">
                {asincronicas.map(a => (
                  <span key={a.id} className="px-3 py-1 bg-purple-100 text-purple-700 rounded-full text-sm">
                    {a.catedra?.codigo} - {a.catedra?.nombre}
                  </span>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* Vista Calendario */}
      {vistaActiva === 'calendario' && (
        <div className="bg-white rounded-xl border shadow-sm p-4">
          <div className="flex justify-between items-center mb-4">
            <button onClick={() => setSemanaActual(Math.max(1, semanaActual - 1))} className="px-3 py-1 bg-slate-200 rounded">← Semana anterior</button>
            <h3 className="font-semibold">Semana {semanaActual} - Marzo 2026</h3>
            <button onClick={() => setSemanaActual(Math.min(16, semanaActual + 1))} className="px-3 py-1 bg-slate-200 rounded">Semana siguiente →</button>
          </div>
          
          <div className="grid grid-cols-6 gap-2">
            {fechasSemanales.map(({ dia, fecha }) => (
              <div key={dia} className="border rounded-lg overflow-hidden">
                <div className="bg-slate-800 text-white p-2 text-center text-sm font-medium">
                  {dia} <span className="text-slate-300">{fecha}</span>
                </div>
                <div className="p-2 min-h-[200px] space-y-1">
                  {asignacionesConHorario.filter(a => a.dia === dia).map(a => (
                    <div key={a.id} className={`p-2 rounded text-xs ${SEDE_COLORS[a.docente?.sede]} text-white`}>
                      <p className="font-bold">{a.hora} - {a.catedra?.codigo}</p>
                      <p>{a.catedra?.nombre}</p>
                      <p className="opacity-75">{a.docente?.nombre} {a.docente?.apellido}</p>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Vista Solapamientos */}
      {vistaActiva === 'solapamientos' && (
        <div className="bg-white rounded-xl border shadow-sm p-6">
          <h3 className="font-semibold mb-4">⚠️ Detector de Solapamientos</h3>
          
          {solapamientos.length === 0 ? (
            <div className="text-center py-8 text-green-600">
              <p className="text-4xl mb-2">✅</p>
              <p className="font-medium">No hay solapamientos detectados</p>
              <p className="text-sm text-slate-500">Todos los horarios están correctamente asignados</p>
            </div>
          ) : (
            <div className="space-y-4">
              {solapamientos.map((s, i) => (
                <div key={i} className="p-4 bg-red-50 border border-red-200 rounded-lg">
                  <p className="font-medium text-red-700 mb-2">
                    🚨 Conflicto: {s.docente?.nombre} {s.docente?.apellido} tiene 2 clases el mismo día/hora
                  </p>
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div className="p-2 bg-white rounded">
                      <p className="font-mono">{s.a1.catedra?.codigo}</p>
                      <p>{s.a1.catedra?.nombre}</p>
                      <p className="text-slate-500">{s.a1.dia} {s.a1.hora}</p>
                    </div>
                    <div className="p-2 bg-white rounded">
                      <p className="font-mono">{s.a2.catedra?.codigo}</p>
                      <p>{s.a2.catedra?.nombre}</p>
                      <p className="text-slate-500">{s.a2.dia} {s.a2.hora}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Lista unificada */}
      <div className="mt-6 bg-white rounded-xl border shadow-sm p-4">
        <h3 className="font-semibold mb-3">📋 Lista Unificada ({asignacionesConHorario.length} asignaciones con horario)</h3>
        <div className="overflow-auto max-h-60">
          <table className="w-full text-sm">
            <thead className="bg-slate-50">
              <tr><th className="p-2 text-left">Cátedra</th><th className="p-2 text-left">Docente</th><th className="p-2">Modalidad</th><th className="p-2">Día</th><th className="p-2">Hora</th><th className="p-2">Sede</th></tr>
            </thead>
            <tbody>
              {asignacionesConHorario.map(a => (
                <tr key={a.id} className="border-b">
                  <td className="p-2"><span className="font-mono">{a.catedra?.codigo}</span> {a.catedra?.nombre}</td>
                  <td className="p-2">{a.docente?.nombre} {a.docente?.apellido}</td>
                  <td className="p-2 text-center"><span className={MODALIDAD_CONFIG[a.modalidad]?.color}>{MODALIDAD_CONFIG[a.modalidad]?.icon}</span></td>
                  <td className="p-2 text-center">{a.dia}</td>
                  <td className="p-2 text-center">{a.hora}</td>
                  <td className="p-2 text-center"><span className={`px-2 py-0.5 rounded text-white text-xs ${SEDE_COLORS[a.docente?.sede]}`}>{a.docente?.sede}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ============ VISTAS SIMPLES ============
function ImportarView() {
  return (
    <div className="p-8">
      <h2 className="text-2xl font-bold text-slate-800 mb-6">Importar Datos</h2>
      <div className="bg-green-50 border-2 border-green-300 rounded-xl p-6 mb-6">
        <h3 className="text-green-800 font-bold text-lg mb-4">✅ Datos Importados</h3>
        <div className="grid grid-cols-4 gap-4">
          <div className="bg-white rounded-lg p-4 text-center"><p className="text-3xl font-bold text-blue-600">635</p><p className="text-sm">Cátedras</p></div>
          <div className="bg-white rounded-lg p-4 text-center"><p className="text-3xl font-bold text-emerald-600">930</p><p className="text-sm">Cursos</p></div>
          <div className="bg-white rounded-lg p-4 text-center"><p className="text-3xl font-bold text-purple-600">8</p><p className="text-sm">Docentes</p></div>
          <div className="bg-white rounded-lg p-4 text-center"><p className="text-3xl font-bold text-amber-600">715</p><p className="text-sm">Inscripciones (c.2)</p></div>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border p-6">
          <h3 className="font-semibold mb-3">📊 Subir más inscripciones</h3>
          <button className="w-full py-2 bg-amber-500 text-slate-900 rounded-lg font-medium">📤 Subir Excel</button>
        </div>
        <div className="bg-white rounded-xl border p-6">
          <h3 className="font-semibold mb-3">👨‍🏫 Subir docentes</h3>
          <button className="w-full py-2 bg-slate-800 text-white rounded-lg">📤 Subir Excel</button>
        </div>
      </div>
    </div>
  );
}

function CambiosView() {
  return (
    <div className="p-8">
      <h2 className="text-2xl font-bold text-slate-800 mb-6">Cambios Pendientes</h2>
      <div className="bg-white rounded-xl border p-8 text-center text-slate-500">
        <p className="text-4xl mb-2">✅</p>
        <p>No hay cambios pendientes para comunicar</p>
      </div>
    </div>
  );
}

function ExportarView() {
  return (
    <div className="p-8">
      <h2 className="text-2xl font-bold text-slate-800 mb-6">Exportar</h2>
      <div className="max-w-xl space-y-4">
        <div className="bg-white rounded-xl border p-5">
          <h3 className="font-semibold mb-3">📊 Horarios para Alumnos</h3>
          <button className="w-full py-2 bg-amber-500 text-slate-900 rounded-lg font-bold">📥 Descargar Excel</button>
        </div>
        <div className="bg-white rounded-xl border p-5">
          <h3 className="font-semibold mb-3">👨‍🏫 Docentes con carga horaria</h3>
          <button className="w-full py-2 bg-violet-500 text-white rounded-lg">📥 Descargar</button>
        </div>
      </div>
    </div>
  );
}

// ============ APP PRINCIPAL ============
export default function App() {
  const [activeView, setActiveView] = useState('catedras');
  const [cuatrimestre, setCuatrimestre] = useState('1');
  const [asignaciones, setAsignaciones] = useState(ASIGNACIONES_INICIAL);

  const stats = { modificadas: 0 };

  const renderView = () => {
    switch(activeView) {
      case 'catedras': return <CatedrasView catedras={CATEDRAS_BASE} asignaciones={asignaciones} setAsignaciones={setAsignaciones} filtroCuatrimestre={cuatrimestre} />;
      case 'horarios': return <HorariosView catedras={CATEDRAS_BASE} asignaciones={asignaciones} filtroCuatrimestre={cuatrimestre} />;
      case 'docentes': return <DocentesView catedras={CATEDRAS_BASE} asignaciones={asignaciones} setAsignaciones={setAsignaciones} filtroCuatrimestre={cuatrimestre} />;
      case 'importar': return <ImportarView />;
      case 'cambios': return <CambiosView />;
      case 'exportar': return <ExportarView />;
      default: return <CatedrasView catedras={CATEDRAS_BASE} asignaciones={asignaciones} setAsignaciones={setAsignaciones} filtroCuatrimestre={cuatrimestre} />;
    }
  };

  return (
    <div className="flex min-h-screen bg-slate-100">
      <Sidebar activeView={activeView} setActiveView={setActiveView} cuatrimestre={cuatrimestre} setCuatrimestre={setCuatrimestre} stats={stats} />
      <main className="flex-1 overflow-auto">{renderView()}</main>
    </div>
  );
}
