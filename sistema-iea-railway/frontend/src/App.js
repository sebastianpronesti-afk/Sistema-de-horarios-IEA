import React, { useState, useEffect, useMemo, useCallback } from 'react';

// ============ CONFIGURACIÓN API ============
const API_URL = 'https://sistema-de-horarios-iea-production.up.railway.app';

// ============ CONSTANTES ============
const SEDE_COLORS = {
  'Online - Interior': 'bg-purple-500', 'Online - Exterior': 'bg-violet-500', 
  'Online - Cursos': 'bg-fuchsia-500', 'Online': 'bg-purple-400',
  'Avellaneda': 'bg-blue-500', 'Caballito': 'bg-emerald-500',
  'Vicente Lopez': 'bg-amber-500', 'Liniers': 'bg-pink-500', 'Monte Grande': 'bg-cyan-500',
  'La Plata': 'bg-indigo-500', 'Pilar': 'bg-rose-500',
  'BCE': 'bg-lime-500', 'BEA': 'bg-teal-500', 'Remoto': 'bg-gray-500',
};

const MODALIDAD_CONFIG = {
  'virtual_tm': { label: 'Virtual TM', icon: '🖥️☀️', color: 'text-blue-600', bg: 'bg-blue-50', border: 'border-blue-200' },
  'virtual_tn': { label: 'Virtual TN', icon: '🖥️🌙', color: 'text-indigo-600', bg: 'bg-indigo-50', border: 'border-indigo-200' },
  'presencial': { label: 'Presencial', icon: '🏫', color: 'text-emerald-600', bg: 'bg-emerald-50', border: 'border-emerald-200' },
  'asincronica': { label: 'Asincrónica', icon: '🎥', color: 'text-purple-600', bg: 'bg-purple-50', border: 'border-purple-200' },
};

const TIPO_DOCENTE_CONFIG = {
  'PRESENCIAL_VIRTUAL': { label: 'Presencial + Virtual', icon: '🏫🖥️', color: 'text-emerald-600', bg: 'bg-emerald-100' },
  'SEDE_VIRTUAL': { label: 'Sede Virtual', icon: '🖥️📍', color: 'text-blue-600', bg: 'bg-blue-100' },
  'REMOTO': { label: 'Remoto', icon: '🏠', color: 'text-gray-600', bg: 'bg-gray-100' },
  'SIN_ASIGNACIONES': { label: 'Sin asignar', icon: '⏳', color: 'text-orange-600', bg: 'bg-orange-100' },
};

const DIAS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado'];
const HORAS = ['07:00','08:00','09:00','10:00','11:00','12:00','13:00','18:00','19:00','20:00','21:00','22:00'];

// ============ FETCH HELPER ============
async function apiFetch(endpoint, options = {}) {
  const res = await fetch(`${API_URL}${endpoint}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Error de servidor' }));
    throw new Error(err.detail || 'Error');
  }
  return res.json();
}

// ============ SIDEBAR ============
function Sidebar({ activeView, setActiveView, cuatrimestre, setCuatrimestre, sedes, solapamientosCount }) {
  const menuItems = [
    { id: 'catedras', icon: '📚', label: 'Cátedras' },
    { id: 'docentes', icon: '👨‍🏫', label: 'Docentes' },
    { id: 'calendario', icon: '📅', label: 'Calendario' },
    { id: 'solapamientos', icon: '⚠️', label: 'Solapamientos', badge: solapamientosCount },
    { id: 'importar', icon: '📥', label: 'Importar', highlight: true },
    { id: 'exportar', icon: '📤', label: 'Exportar' },
  ];

  return (
    <div className="w-64 bg-slate-900 min-h-screen p-4 flex flex-col">
      <div className="mb-6 px-2">
        <h1 className="text-xl font-bold text-white">IEA Horarios</h1>
        <p className="text-slate-500 text-sm">Sistema v3.1</p>
      </div>
      <div className="mb-6 px-2">
        <label className="text-xs text-slate-400 block mb-1">Ver cuatrimestre</label>
        <select className="w-full bg-slate-800 text-white rounded px-3 py-2 text-sm border border-slate-700"
          value={cuatrimestre} onChange={e => setCuatrimestre(e.target.value)}>
          <option value="todos">Todos</option>
          <option value="1">1er Cuatrimestre 2026</option>
          <option value="2">2do Cuatrimestre 2026</option>
        </select>
      </div>
      <nav className="flex-1 space-y-1">
        {menuItems.map(item => (
          <button key={item.id} onClick={() => setActiveView(item.id)}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-all ${
              activeView === item.id ? 'bg-amber-500 text-slate-900 font-medium'
              : item.highlight ? 'text-amber-400 hover:bg-slate-800' : 'text-slate-400 hover:bg-slate-800'}`}>
            <span className="text-lg">{item.icon}</span>
            <span className="flex-1">{item.label}</span>
            {item.badge > 0 && <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-red-500 text-white">{item.badge}</span>}
          </button>
        ))}
      </nav>
      <div className="mt-4 p-3 bg-slate-800/50 rounded-lg">
        <p className="text-xs text-slate-400 mb-2">Sedes</p>
        {sedes.map(s => (
          <div key={s.id} className="flex items-center gap-2 mb-1">
            <div className={`w-2 h-2 rounded-full ${s.color || SEDE_COLORS[s.nombre] || 'bg-gray-500'}`}></div>
            <span className="text-[10px] text-slate-300">{s.nombre}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ============ VISTA CÁTEDRAS ============
function CatedrasView({ catedras, docentes, sedes, cuatrimestre, recargar }) {
  const [filtros, setFiltros] = useState({ buscar: '', soloSinAsignar: false });
  const [modalCatedra, setModalCatedra] = useState(null);
  const [paginaActual, setPaginaActual] = useState(1);
  const porPagina = 20;

  const catedrasFiltradas = useMemo(() => {
    return catedras.filter(c => {
      if (filtros.buscar && !c.nombre.toLowerCase().includes(filtros.buscar.toLowerCase()) &&
          !c.codigo.toLowerCase().includes(filtros.buscar.toLowerCase())) return false;
      if (filtros.soloSinAsignar && c.asignaciones?.length > 0) return false;
      return true;
    });
  }, [catedras, filtros]);

  const totalPaginas = Math.ceil(catedrasFiltradas.length / porPagina);
  const catedrasPag = catedrasFiltradas.slice((paginaActual - 1) * porPagina, paginaActual * porPagina);

  const stats = useMemo(() => {
    const allAsig = catedras.flatMap(c => c.asignaciones || []);
    return {
      total: catedras.length,
      asignaciones: allAsig.length,
      asincronicas: allAsig.filter(a => a.modalidad === 'asincronica').length,
      conDocente: allAsig.filter(a => a.docente && a.modalidad !== 'asincronica').length,
      sinDocente: allAsig.filter(a => !a.docente && a.modalidad !== 'asincronica').length,
      inscriptos: catedras.reduce((s, c) => s + (c.inscriptos || 0), 0),
    };
  }, [catedras]);

  const eliminarAsig = async (id) => {
    if (!window.confirm('¿Eliminar esta asignación?')) return;
    try { await apiFetch(`/api/asignaciones/${id}`, { method: 'DELETE' }); recargar(); } catch (e) { alert(e.message); }
  };

  return (
    <div className="p-8">
      <div className="mb-6"><h2 className="text-2xl font-bold text-slate-800">Cátedras</h2></div>
      {/* KPIs */}
      <div className="grid grid-cols-6 gap-3 mb-6">
        {[
          { label: 'Total Cátedras', val: stats.total, color: '' },
          { label: '📋 Asignaciones', val: stats.asignaciones, color: 'text-blue-600' },
          { label: '🎥 Asincrónicas', val: stats.asincronicas, color: 'text-purple-600' },
          { label: '👨‍🏫 Con Docente', val: stats.conDocente, color: 'text-emerald-600' },
          { label: '⚠️ Sin Docente', val: stats.sinDocente, color: 'text-red-600' },
          { label: '👥 Inscriptos', val: stats.inscriptos, color: 'text-cyan-600' },
        ].map((s, i) => (
          <div key={i} className="bg-white rounded-xl border p-4 text-center">
            <p className="text-slate-500 text-xs">{s.label}</p>
            <p className={`text-2xl font-bold ${s.color}`}>{s.val}</p>
          </div>
        ))}
      </div>
      {/* Filtros */}
      <div className="flex gap-3 mb-4 bg-white p-4 rounded-xl border items-center">
        <input type="text" placeholder="Buscar por código o nombre..." className="px-3 py-2 border rounded-lg text-sm flex-1"
          value={filtros.buscar} onChange={e => { setFiltros({...filtros, buscar: e.target.value}); setPaginaActual(1); }} />
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={filtros.soloSinAsignar}
            onChange={e => { setFiltros({...filtros, soloSinAsignar: e.target.checked}); setPaginaActual(1); }} />
          Solo sin asignación
        </label>
        <span className="text-sm text-slate-500">{catedrasFiltradas.length} cátedras | Pág {paginaActual}/{totalPaginas||1}</span>
      </div>
      {/* Tabla */}
      <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
        <table className="w-full">
          <thead><tr className="bg-slate-50 border-b">
            <th className="text-left p-4 text-sm font-semibold w-1/3">Cátedra</th>
            <th className="text-left p-4 text-sm font-semibold">Asignaciones</th>
            <th className="text-center p-4 text-sm font-semibold w-24">Inscriptos</th>
            <th className="text-center p-4 text-sm font-semibold w-32">Acciones</th>
          </tr></thead>
          <tbody>
            {catedrasPag.map(cat => (
              <tr key={cat.id} className="border-b hover:bg-slate-50">
                <td className="p-4">
                  <span className="px-2 py-1 bg-slate-800 text-white rounded text-xs font-mono mr-2">{cat.codigo}</span>
                  <span className="font-medium">{cat.nombre}</span>
                </td>
                <td className="p-4">
                  {cat.asignaciones?.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      {cat.asignaciones.map(a => {
                        const mod = MODALIDAD_CONFIG[a.modalidad] || {};
                        return (
                          <div key={a.id} className={`px-3 py-2 rounded-lg ${mod.bg} border ${mod.border} text-sm`}>
                            <div className="flex items-center gap-2">
                              <span>{mod.icon}</span>
                              <div>
                                <p className={`font-medium ${mod.color}`}>{mod.label}</p>
                                {a.modalidad !== 'asincronica' && (
                                  <p className="text-xs text-slate-500">
                                    {a.docente ? a.docente.nombre : '⚠️ Sin docente'}
                                    {a.dia && ` • ${a.dia} ${a.hora_inicio}`}
                                    {a.sede_nombre && ` • ${a.sede_nombre}`}
                                  </p>
                                )}
                              </div>
                              <button onClick={() => eliminarAsig(a.id)} className="text-red-400 hover:text-red-600 ml-2">×</button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : <span className="text-slate-400 text-sm">Sin asignaciones</span>}
                </td>
                <td className="p-4 text-center">
                  <span className={`text-xl font-bold ${cat.inscriptos > 0 ? 'text-cyan-600' : 'text-slate-300'}`}>{cat.inscriptos || 0}</span>
                </td>
                <td className="p-4 text-center">
                  <button onClick={() => setModalCatedra(cat)} className="px-3 py-1.5 bg-amber-500 text-slate-900 rounded text-sm font-medium hover:bg-amber-400">+ Asignar</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {/* Paginación */}
      <div className="flex justify-center gap-2 mt-4">
        <button onClick={() => setPaginaActual(Math.max(1, paginaActual - 1))} disabled={paginaActual === 1} className="px-3 py-1 bg-slate-200 rounded disabled:opacity-50">← Anterior</button>
        <button onClick={() => setPaginaActual(Math.min(totalPaginas, paginaActual + 1))} disabled={paginaActual >= totalPaginas} className="px-3 py-1 bg-slate-200 rounded disabled:opacity-50">Siguiente →</button>
      </div>
      {/* Modal */}
      {modalCatedra && <ModalAsignarCatedra catedra={modalCatedra} docentes={docentes} sedes={sedes} cuatrimestre={cuatrimestre} onClose={() => setModalCatedra(null)} recargar={recargar} />}
    </div>
  );
}

// ============ MODAL ASIGNAR DESDE CÁTEDRA ============
function ModalAsignarCatedra({ catedra, docentes, sedes, cuatrimestre, onClose, recargar }) {
  const [form, setForm] = useState({ docente_id: '', modalidad: 'virtual_tm', sede_id: '', dia: '', hora_inicio: '', recibe_alumnos_presenciales: false });
  const [error, setError] = useState('');

  const crear = async () => {
    setError('');
    try {
      await apiFetch('/api/asignaciones', {
        method: 'POST',
        body: JSON.stringify({
          catedra_id: catedra.id,
          cuatrimestre_id: parseInt(cuatrimestre) || 1,
          docente_id: form.docente_id ? parseInt(form.docente_id) : null,
          modalidad: form.modalidad,
          sede_id: form.sede_id ? parseInt(form.sede_id) : null,
          dia: form.dia || null,
          hora_inicio: form.hora_inicio || null,
          recibe_alumnos_presenciales: form.recibe_alumnos_presenciales,
        }),
      });
      recargar(); onClose();
    } catch (e) { setError(e.message); }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl p-6 max-w-lg w-full mx-4">
        <h3 className="text-lg font-bold mb-2">Agregar Asignación</h3>
        <p className="text-slate-600 mb-4">{catedra.codigo} - {catedra.nombre}</p>
        <div className="space-y-3">
          <div><label className="text-sm text-slate-600">Docente:</label>
            <select className="w-full border rounded-lg px-3 py-2 mt-1" value={form.docente_id} onChange={e => setForm({...form, docente_id: e.target.value})}>
              <option value="">Sin asignar</option>
              {docentes.map(d => <option key={d.id} value={d.id}>{d.nombre} {d.apellido}</option>)}
            </select></div>
          <div className="grid grid-cols-2 gap-3">
            <div><label className="text-sm text-slate-600">Modalidad:</label>
              <select className="w-full border rounded-lg px-3 py-2 mt-1" value={form.modalidad} onChange={e => setForm({...form, modalidad: e.target.value})}>
                {Object.entries(MODALIDAD_CONFIG).map(([k, v]) => <option key={k} value={k}>{v.icon} {v.label}</option>)}
              </select></div>
            <div><label className="text-sm text-slate-600">Sede física:</label>
              <select className="w-full border rounded-lg px-3 py-2 mt-1" value={form.sede_id} onChange={e => setForm({...form, sede_id: e.target.value})}>
                <option value="">🏠 Remoto</option>
                {sedes.filter(s => s.nombre !== 'Remoto').map(s => <option key={s.id} value={s.id}>{s.nombre}</option>)}
              </select></div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div><label className="text-sm text-slate-600">Día:</label>
              <select className="w-full border rounded-lg px-3 py-2 mt-1" value={form.dia} onChange={e => setForm({...form, dia: e.target.value})}>
                <option value="">Sin definir</option>
                {DIAS.map(d => <option key={d} value={d}>{d}</option>)}
              </select></div>
            <div><label className="text-sm text-slate-600">Hora:</label>
              <select className="w-full border rounded-lg px-3 py-2 mt-1" value={form.hora_inicio} onChange={e => setForm({...form, hora_inicio: e.target.value})}>
                <option value="">Sin definir</option>
                {HORAS.map(h => <option key={h} value={h}>{h}</option>)}
              </select></div>
          </div>
          {form.sede_id && (
            <label className="flex items-center gap-2 p-3 bg-emerald-50 rounded-lg cursor-pointer">
              <input type="checkbox" checked={form.recibe_alumnos_presenciales} onChange={e => setForm({...form, recibe_alumnos_presenciales: e.target.checked})} />
              <span className="text-sm">👥 Recibe alumnos presenciales</span>
            </label>
          )}
          {error && <div className="p-3 bg-red-50 border border-red-300 rounded-lg text-red-700 text-sm">⛔ {error}</div>}
        </div>
        <div className="flex gap-2 mt-4">
          <button onClick={crear} className="flex-1 py-2 bg-amber-500 text-slate-900 rounded-lg font-medium">Crear</button>
          <button onClick={onClose} className="flex-1 py-2 bg-slate-100 rounded-lg">Cancelar</button>
        </div>
      </div>
    </div>
  );
}

// ============ VISTA DOCENTES ============
function DocentesView({ docentes, sedes, cuatrimestre, recargar }) {
  const [modalSedes, setModalSedes] = useState(null);

  const stats = useMemo(() => {
    const s = { PRESENCIAL_VIRTUAL: 0, SEDE_VIRTUAL: 0, REMOTO: 0, SIN_ASIGNACIONES: 0 };
    docentes.forEach(d => { if (s[d.tipo_modalidad] !== undefined) s[d.tipo_modalidad]++; });
    return s;
  }, [docentes]);

  const guardarSedes = async (docenteId, sedeIds) => {
    try {
      await apiFetch(`/api/docentes/${docenteId}/sedes`, { method: 'PUT', body: JSON.stringify({ sede_ids: sedeIds }) });
      recargar(); setModalSedes(null);
    } catch (e) { alert(e.message); }
  };

  return (
    <div className="p-8">
      <div className="mb-6"><h2 className="text-2xl font-bold text-slate-800">Docentes</h2>
        <p className="text-slate-500 text-sm">Tipo deducido automáticamente de las asignaciones</p></div>
      <div className="grid grid-cols-4 gap-4 mb-6">
        {Object.entries(TIPO_DOCENTE_CONFIG).map(([key, cfg]) => (
          <div key={key} className={`p-4 rounded-xl border ${cfg.bg}`}>
            <p className={`font-medium ${cfg.color}`}>{cfg.icon} {cfg.label}</p>
            <p className={`text-3xl font-bold ${cfg.color}`}>{stats[key] || 0}</p>
          </div>
        ))}
      </div>
      <div className="bg-white rounded-xl border shadow-sm">
        <table className="w-full">
          <thead><tr className="bg-slate-50 border-b">
            <th className="text-left p-4 text-sm font-semibold">Docente</th>
            <th className="text-center p-4 text-sm font-semibold">Tipo</th>
            <th className="text-center p-4 text-sm font-semibold">Sedes</th>
            <th className="text-left p-4 text-sm font-semibold">Asignaciones</th>
          </tr></thead>
          <tbody>
            {docentes.map(d => {
              const tipoCfg = TIPO_DOCENTE_CONFIG[d.tipo_modalidad] || TIPO_DOCENTE_CONFIG.SIN_ASIGNACIONES;
              return (
                <tr key={d.id} className="border-b hover:bg-slate-50">
                  <td className="p-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-slate-800 text-white flex items-center justify-center font-bold">{d.nombre[0]}{d.apellido[0]}</div>
                      <div><p className="font-medium">{d.nombre} {d.apellido}</p><p className="text-xs text-slate-500">DNI: {d.dni}</p></div>
                    </div>
                  </td>
                  <td className="p-4 text-center"><span className={`px-3 py-1 rounded-full text-xs font-medium ${tipoCfg.bg} ${tipoCfg.color}`}>{tipoCfg.icon} {tipoCfg.label}</span></td>
                  <td className="p-4 text-center">
                    <div className="flex flex-wrap justify-center gap-1">
                      {d.sedes?.length > 0 ? d.sedes.map(s => <span key={s.id} className={`px-2 py-0.5 rounded text-white text-xs ${SEDE_COLORS[s.nombre]||'bg-gray-500'}`}>{s.nombre}</span>)
                        : <span className="text-slate-400 text-xs">Sin sedes</span>}
                    </div>
                    <button onClick={() => setModalSedes(d)} className="text-xs text-blue-600 hover:underline mt-1">Editar</button>
                  </td>
                  <td className="p-4">
                    {d.asignaciones?.length > 0 ? d.asignaciones.map(a => {
                      const mod = MODALIDAD_CONFIG[a.modalidad] || {};
                      return (<div key={a.id} className="flex items-center gap-2 text-sm mb-1">
                        <span className={mod.color}>{mod.icon}</span>
                        <span className="font-mono bg-slate-100 px-1 rounded text-xs">{a.catedra_codigo}</span>
                        <span className="text-slate-500 text-xs">{a.dia||''} {a.hora_inicio||''}</span>
                        {a.recibe_alumnos_presenciales && <span>👥</span>}
                      </div>);
                    }) : <span className="text-slate-400 text-sm">Sin asignaciones</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {modalSedes && <ModalEditarSedes docente={modalSedes} sedes={sedes} onSave={guardarSedes} onClose={() => setModalSedes(null)} />}
    </div>
  );
}

function ModalEditarSedes({ docente, sedes, onSave, onClose }) {
  const [sel, setSel] = useState(docente.sedes?.map(s => s.id) || []);
  const toggle = id => setSel(sel.includes(id) ? sel.filter(x => x !== id) : [...sel, id]);
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl p-6 max-w-md w-full mx-4">
        <h3 className="text-lg font-bold mb-4">Editar Sedes: {docente.nombre} {docente.apellido}</h3>
        <div className="space-y-2 mb-4">
          {sedes.filter(s => s.nombre !== 'Remoto').map(s => (
            <label key={s.id} className={`flex items-center gap-3 p-3 border rounded-lg cursor-pointer ${sel.includes(s.id) ? 'border-amber-500 bg-amber-50' : 'hover:bg-slate-50'}`}>
              <input type="checkbox" checked={sel.includes(s.id)} onChange={() => toggle(s.id)} />
              <span className={`w-3 h-3 rounded-full ${SEDE_COLORS[s.nombre]||'bg-gray-500'}`}></span>
              <span>{s.nombre}</span>
            </label>
          ))}
        </div>
        <div className="flex gap-2">
          <button onClick={() => onSave(docente.id, sel)} className="flex-1 py-2 bg-amber-500 rounded-lg font-medium">Guardar</button>
          <button onClick={onClose} className="flex-1 py-2 bg-slate-100 rounded-lg">Cancelar</button>
        </div>
      </div>
    </div>
  );
}

// ============ VISTA CALENDARIO ============
function CalendarioView({ catedras, docentes, sedes, cuatrimestre }) {
  const [filtroSede, setFiltroSede] = useState('');
  const [filtroDocente, setFiltroDocente] = useState('');
  const [filtroCatedra, setFiltroCatedra] = useState('');

  const allAsig = useMemo(() => catedras.flatMap(c => (c.asignaciones || []).map(a => ({ ...a, cat_codigo: c.codigo, cat_nombre: c.nombre }))), [catedras]);
  
  const asigConHorario = useMemo(() => {
    return allAsig.filter(a => a.dia && a.hora_inicio && a.docente).filter(a => {
      if (filtroSede === 'remoto') return !a.sede_id;
      if (filtroSede) return a.sede_id === parseInt(filtroSede);
      return true;
    }).filter(a => {
      if (filtroDocente) return a.docente?.id === parseInt(filtroDocente);
      return true;
    }).filter(a => {
      if (filtroCatedra) return a.cat_codigo === filtroCatedra;
      return true;
    });
  }, [allAsig, filtroSede, filtroDocente, filtroCatedra]);

  return (
    <div className="p-8">
      <div className="mb-6"><h2 className="text-2xl font-bold text-slate-800">Calendario</h2></div>
      {/* Filtros */}
      <div className="bg-white rounded-xl border p-4 mb-6 grid grid-cols-3 gap-4">
        <div><label className="text-sm text-slate-600 font-medium">Sede:</label>
          <select className="w-full border rounded-lg px-3 py-2 mt-1" value={filtroSede} onChange={e => setFiltroSede(e.target.value)}>
            <option value="">Todas</option>
            {sedes.map(s => <option key={s.id} value={s.id}>{s.nombre}</option>)}
            <option value="remoto">🏠 Solo Remotos</option>
          </select></div>
        <div><label className="text-sm text-slate-600 font-medium">Docente:</label>
          <select className="w-full border rounded-lg px-3 py-2 mt-1" value={filtroDocente} onChange={e => setFiltroDocente(e.target.value)}>
            <option value="">Todos</option>
            {docentes.map(d => <option key={d.id} value={d.id}>{d.nombre} {d.apellido}</option>)}
          </select></div>
        <div><label className="text-sm text-slate-600 font-medium">Cátedra:</label>
          <select className="w-full border rounded-lg px-3 py-2 mt-1" value={filtroCatedra} onChange={e => setFiltroCatedra(e.target.value)}>
            <option value="">Todas</option>
            {catedras.map(c => <option key={c.id} value={c.codigo}>{c.codigo} - {c.nombre}</option>)}
          </select></div>
      </div>
      {/* Grilla */}
      <div className="bg-white rounded-xl border shadow-sm overflow-auto mb-6">
        <table className="w-full text-sm">
          <thead><tr className="bg-slate-50 border-b">
            <th className="p-2 border-r w-20">Hora</th>
            {DIAS.map(d => <th key={d} className="p-2 border-r min-w-[130px]">{d}</th>)}
          </tr></thead>
          <tbody>
            {HORAS.map(hora => (
              <tr key={hora} className="border-b">
                <td className="p-2 border-r bg-slate-50 font-medium text-center">{hora}</td>
                {DIAS.map(dia => {
                  const celdas = asigConHorario.filter(a => a.dia === dia && a.hora_inicio === hora);
                  return (
                    <td key={dia} className="p-1 border-r align-top">
                      {celdas.map(a => {
                        const mod = MODALIDAD_CONFIG[a.modalidad] || {};
                        return (
                          <div key={a.id} className={`p-1 mb-1 rounded text-xs ${mod.bg} border ${mod.border}`}>
                            <p className={`font-bold ${mod.color}`}>{a.cat_codigo}</p>
                            <p className="truncate">{a.docente?.nombre}</p>
                            <p className="text-slate-500">{a.sede_nombre || '🏠'}</p>
                          </div>
                        );
                      })}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {/* Lista */}
      <div className="bg-white rounded-xl border shadow-sm p-4">
        <h3 className="font-semibold mb-3">📋 Lista ({asigConHorario.length} asignaciones)</h3>
        <div className="overflow-auto max-h-80">
          <table className="w-full text-sm">
            <thead className="bg-slate-50"><tr>
              <th className="p-2 text-left">Cátedra</th><th className="p-2 text-left">Docente</th>
              <th className="p-2">Modalidad</th><th className="p-2">Día</th><th className="p-2">Hora</th><th className="p-2">Sede</th>
            </tr></thead>
            <tbody>
              {asigConHorario.map(a => {
                const mod = MODALIDAD_CONFIG[a.modalidad] || {};
                return (
                  <tr key={a.id} className="border-b">
                    <td className="p-2"><span className="font-mono">{a.cat_codigo}</span> {a.cat_nombre}</td>
                    <td className="p-2">{a.docente?.nombre}</td>
                    <td className="p-2 text-center"><span className={mod.color}>{mod.icon}</span></td>
                    <td className="p-2 text-center">{a.dia}</td>
                    <td className="p-2 text-center">{a.hora_inicio}</td>
                    <td className="p-2 text-center">{a.sede_nombre ? <span className={`px-2 py-0.5 rounded text-white text-xs ${SEDE_COLORS[a.sede_nombre]||'bg-gray-500'}`}>{a.sede_nombre}</span> : '🏠 Remoto'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ============ VISTA SOLAPAMIENTOS ============
function SolapamientosView({ solapamientos }) {
  return (
    <div className="p-8">
      <div className="mb-6"><h2 className="text-2xl font-bold text-slate-800">Detector de Solapamientos</h2></div>
      {solapamientos.length === 0 ? (
        <div className="bg-green-50 border border-green-200 rounded-xl p-8 text-center">
          <p className="text-4xl mb-2">✅</p>
          <p className="text-green-700 font-medium text-lg">No hay solapamientos</p>
          <p className="text-green-600 text-sm">Todos los horarios están OK</p>
        </div>
      ) : (
        <div className="space-y-4">
          {solapamientos.map((s, i) => (
            <div key={i} className={`p-4 rounded-xl border ${s.tipo === 'CATEDRA' ? 'bg-red-50 border-red-300' : 'bg-orange-50 border-orange-300'}`}>
              <div className="flex items-center gap-2 mb-2">
                <span className={`px-3 py-1 rounded text-sm font-bold text-white ${s.tipo === 'CATEDRA' ? 'bg-red-500' : 'bg-orange-500'}`}>{s.severidad}</span>
                <span className="font-medium">{s.tipo === 'CATEDRA' ? '🎓 Cátedra' : '👨‍🏫 Docente'}</span>
              </div>
              <p className="text-slate-700">{s.mensaje}</p>
              {s.tipo === 'CATEDRA' && <p className="text-sm text-red-600 mt-1">⚠️ Comparten el link de Meet.</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ============ VISTA IMPORTAR ============
function ImportarView({ recargar }) {
  const [uploading, setUploading] = useState('');
  const [resultado, setResultado] = useState(null);

  const subirArchivo = async (endpoint, label) => {
    const input = document.createElement('input');
    input.type = 'file'; input.accept = '.xlsx,.xls';
    input.onchange = async (e) => {
      const file = e.target.files[0]; if (!file) return;
      setUploading(label); setResultado(null);
      const formData = new FormData();
      formData.append('file', file);
      try {
        const res = await fetch(`${API_URL}${endpoint}`, { method: 'POST', body: formData });
        const data = await res.json();
        if (res.ok) {
          setResultado({ ok: true, data, label });
          recargar();
        } else {
          setResultado({ ok: false, error: data.detail || 'Error desconocido', label });
        }
      } catch (err) { setResultado({ ok: false, error: err.message, label }); }
      setUploading('');
    };
    input.click();
  };

  const importadores = [
    {
      id: 'catedras', icon: '📚', titulo: 'Importar Cátedras',
      desc: 'Excel con columnas: Número + "c.XX Nombre"',
      ejemplo: 'Ej: | 1 | c.1 Administración |',
      endpoint: '/api/importar/catedras', color: 'bg-slate-800 text-white',
    },
    {
      id: 'cursos', icon: '🎓', titulo: 'Importar Cursos',
      desc: 'Excel con columnas: Sede + Nombre del curso',
      ejemplo: 'Ej: | Avellaneda | Marketing (Avellaneda) |',
      endpoint: '/api/importar/cursos', color: 'bg-blue-600 text-white',
    },
    {
      id: 'docentes', icon: '👨‍🏫', titulo: 'Importar Docentes',
      desc: 'Excel: DNI + "APELLIDO, NOMBRE" ó DNI/Nombre/Apellido/Email',
      ejemplo: 'Ej: | 20345678 | GARCÍA, MARÍA |',
      endpoint: '/api/importar/docentes', color: 'bg-amber-500 text-slate-900',
    },
  ];

  const importadoresFuturos = [
    {
      id: 'catedra-cursos', icon: '🔗', titulo: 'Vincular Cátedras ↔ Cursos',
      desc: 'Excel: Código | Materia (c.XX Nombre - Turno) | Curso | Sede',
      ejemplo: 'Ej: | 1 | c.1 Administración - Mañana | Marketing (Avellaneda) | Avellaneda |',
      endpoint: '/api/importar/catedra-cursos', color: 'bg-teal-600 text-white',
    },
    {
      id: 'links-meet', icon: '📹', titulo: 'Importar Links de Meet',
      desc: 'Excel: Código de cátedra + Link de Google Meet',
      ejemplo: 'Ej: | c.1 | https://meet.google.com/xxx |',
      endpoint: '/api/importar/links-meet', color: 'bg-green-600 text-white',
    },
  ];

  return (
    <div className="p-8">
      <div className="mb-6"><h2 className="text-2xl font-bold text-slate-800">Importar Datos</h2></div>
      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 mb-6">
        <p className="text-blue-700 text-sm">ℹ️ Los datos se guardan permanentemente. Si importás un archivo con datos que ya existen, se actualizan sin duplicar.</p>
      </div>
      <h3 className="font-semibold text-slate-600 mb-3">Datos base</h3>
      <div className="grid grid-cols-3 gap-6 mb-8">
        {importadores.map(imp => (
          <div key={imp.id} className="bg-white rounded-xl border p-6">
            <h3 className="font-semibold mb-2">{imp.icon} {imp.titulo}</h3>
            <p className="text-sm text-slate-500 mb-1">{imp.desc}</p>
            <p className="text-xs text-slate-400 mb-4 font-mono">{imp.ejemplo}</p>
            <button onClick={() => subirArchivo(imp.endpoint, imp.titulo)}
              disabled={uploading === imp.titulo}
              className={`w-full py-2.5 rounded-lg font-medium disabled:opacity-50 ${imp.color}`}>
              {uploading === imp.titulo ? '⏳ Importando...' : '📤 Subir Excel (.xlsx)'}
            </button>
          </div>
        ))}
      </div>
      <h3 className="font-semibold text-slate-600 mb-3">Vinculaciones</h3>
      <div className="grid grid-cols-2 gap-6 mb-6">
        {importadoresFuturos.map(imp => (
          <div key={imp.id} className="bg-white rounded-xl border p-6 border-dashed border-slate-300">
            <h3 className="font-semibold mb-2">{imp.icon} {imp.titulo}</h3>
            <p className="text-sm text-slate-500 mb-1">{imp.desc}</p>
            <p className="text-xs text-slate-400 mb-4 font-mono">{imp.ejemplo}</p>
            <button onClick={() => subirArchivo(imp.endpoint, imp.titulo)}
              disabled={uploading === imp.titulo}
              className={`w-full py-2.5 rounded-lg font-medium disabled:opacity-50 ${imp.color}`}>
              {uploading === imp.titulo ? '⏳ Importando...' : '📤 Subir Excel (.xlsx)'}
            </button>
          </div>
        ))}
      </div>
      {resultado && (
        <div className={`p-4 rounded-xl border ${resultado.ok ? 'bg-green-50 border-green-300' : 'bg-red-50 border-red-300'}`}>
          <p className="font-medium text-lg">{resultado.ok ? '✅' : '❌'} {resultado.label}</p>
          {resultado.ok && resultado.data && (
            <div className="mt-2 text-sm">
              {resultado.data.creadas !== undefined && <p>Creadas: <strong>{resultado.data.creadas}</strong></p>}
              {resultado.data.creados !== undefined && <p>Creados: <strong>{resultado.data.creados}</strong></p>}
              {resultado.data.actualizadas !== undefined && <p>Actualizadas: <strong>{resultado.data.actualizadas}</strong></p>}
              {resultado.data.actualizados !== undefined && <p>Actualizados: <strong>{resultado.data.actualizados}</strong></p>}
              {resultado.data.omitidos !== undefined && <p>Omitidos: <strong>{resultado.data.omitidos}</strong></p>}
              {resultado.data.errores?.length > 0 && (
                <div className="mt-2 text-xs text-orange-600">
                  <p>Advertencias:</p>
                  {resultado.data.errores.map((e, i) => <p key={i}>• {e}</p>)}
                </div>
              )}
            </div>
          )}
          {!resultado.ok && <p className="mt-2 text-sm text-red-600">{resultado.error}</p>}
        </div>
      )}
    </div>
  );
}

function ExportarView() {
  return (
    <div className="p-8">
      <h2 className="text-2xl font-bold text-slate-800 mb-6">Exportar</h2>
      <div className="bg-white rounded-xl border p-6 max-w-xl">
        <h3 className="font-semibold mb-3">📊 Exportar Horarios</h3>
        <button className="w-full py-2 bg-amber-500 text-slate-900 rounded-lg font-bold">📥 Descargar Excel</button>
      </div>
    </div>
  );
}

// ============ PANTALLA DE LOGIN ============
function LoginScreen({ onLogin }) {
  const [clave, setClave] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const intentarLogin = async () => {
    setError(''); setLoading(true);
    try {
      await apiFetch('/api/login', { method: 'POST', body: JSON.stringify({ clave }) });
      localStorage.setItem('iea_auth', 'true');
      onLogin();
    } catch (e) {
      setError('Contraseña incorrecta');
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center">
      <div className="bg-white rounded-2xl p-8 max-w-md w-full mx-4 shadow-2xl">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-slate-800">IEA Horarios</h1>
          <p className="text-slate-500 mt-1">Sistema de Gestión de Horarios v3.1</p>
        </div>
        <div className="space-y-4">
          <div>
            <label className="text-sm text-slate-600 font-medium">Contraseña de acceso:</label>
            <input type="password" className="w-full border-2 rounded-lg px-4 py-3 mt-1 text-lg focus:border-amber-500 focus:outline-none"
              value={clave} onChange={e => setClave(e.target.value)} placeholder="Ingresá la contraseña"
              onKeyDown={e => e.key === 'Enter' && intentarLogin()} autoFocus />
          </div>
          {error && <p className="text-red-500 text-sm text-center">{error}</p>}
          <button onClick={intentarLogin} disabled={loading || !clave}
            className="w-full py-3 bg-amber-500 text-slate-900 rounded-lg font-bold text-lg disabled:opacity-50 hover:bg-amber-400">
            {loading ? '⏳ Verificando...' : 'Ingresar'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ============ APP PRINCIPAL ============
export default function App() {
  const [autenticado, setAutenticado] = useState(() => localStorage.getItem('iea_auth') === 'true');
  const [activeView, setActiveView] = useState('catedras');
  const [cuatrimestre, setCuatrimestre] = useState('1');
  const [catedras, setCatedras] = useState([]);
  const [docentes, setDocentes] = useState([]);
  const [sedes, setSedes] = useState([]);
  const [solapamientos, setSolapamientos] = useState([]);
  const [loading, setLoading] = useState(true);

  const cargarDatos = useCallback(async () => {
    const cuatId = cuatrimestre !== 'todos' ? cuatrimestre : null;
    const qParam = cuatId ? `?cuatrimestre_id=${cuatId}` : '';
    
    // Cargar cada dato independientemente - si uno falla, los demás siguen
    try { const r = await apiFetch('/api/sedes'); setSedes(r); } catch (e) { console.error('Sedes:', e); }
    try { const r = await apiFetch(`/api/catedras${qParam}`); setCatedras(r); } catch (e) { console.error('Cátedras:', e); }
    try { const r = await apiFetch(`/api/docentes${qParam}`); setDocentes(r); } catch (e) { console.error('Docentes:', e); }
    try { const r = await apiFetch(`/api/horarios/solapamientos${qParam}`); setSolapamientos(r); } catch (e) { console.error('Solapamientos:', e); }
    
    setLoading(false);
  }, [cuatrimestre]);

  useEffect(() => { if (autenticado) cargarDatos(); }, [cargarDatos, autenticado]);

  if (!autenticado) return <LoginScreen onLogin={() => setAutenticado(true)} />;
  if (loading) return <div className="flex items-center justify-center min-h-screen"><p className="text-xl">⏳ Cargando sistema...</p></div>;

  return (
    <div className="flex min-h-screen bg-slate-100">
      <Sidebar activeView={activeView} setActiveView={setActiveView} cuatrimestre={cuatrimestre}
        setCuatrimestre={setCuatrimestre} sedes={sedes} solapamientosCount={solapamientos.length} />
      <main className="flex-1 overflow-auto">
        {activeView === 'catedras' && <CatedrasView catedras={catedras} docentes={docentes} sedes={sedes} cuatrimestre={cuatrimestre} recargar={cargarDatos} />}
        {activeView === 'docentes' && <DocentesView docentes={docentes} sedes={sedes} cuatrimestre={cuatrimestre} recargar={cargarDatos} />}
        {activeView === 'calendario' && <CalendarioView catedras={catedras} docentes={docentes} sedes={sedes} cuatrimestre={cuatrimestre} />}
        {activeView === 'solapamientos' && <SolapamientosView solapamientos={solapamientos} />}
        {activeView === 'importar' && <ImportarView recargar={cargarDatos} />}
        {activeView === 'exportar' && <ExportarView />}
      </main>
    </div>
  );
}
