import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';

const API_URL = '';

// ===== v4.0 MEJORA 10: Colores corregidos por sede =====
const SEDE_COLORS = {
  'Online - Interior': 'bg-purple-500', 'Online - Exterior': 'bg-violet-500',
  'Online - Cursos': 'bg-fuchsia-500', 'Online': 'bg-purple-400',
  'Avellaneda': 'bg-blue-500',
  'Caballito': 'bg-emerald-500',
  'Vicente Lopez': 'bg-amber-500', 'Vicente López': 'bg-amber-500',
  'Liniers': 'bg-pink-500', 'Monte Grande': 'bg-cyan-500',
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
const HORAS = ['07:00','08:00','09:00','10:00','11:00','12:00','13:00','14:00','17:00','18:00','19:00','20:00','21:00','22:00','23:00'];
const SEDES_OPERATIVAS = ['Avellaneda', 'Caballito', 'Vicente López', 'Online - Interior'];

function sortByCodigo(a, b) {
  const na = parseInt((a.codigo || '').replace(/[^0-9]/g, '')) || 9999;
  const nb = parseInt((b.codigo || '').replace(/[^0-9]/g, '')) || 9999;
  return na - nb;
}

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

// ==================== SIDEBAR ====================
function Sidebar({ activeView, setActiveView, cuatrimestre, setCuatrimestre, sedes, cuatrimestres, solapamientosCount, necesitanDocenteCount, solapCarrerasCount }) {
  const menuItems = [
    { id: 'dashboard', icon: '🏠', label: 'Dashboard' },
    { id: 'catedras', icon: '📚', label: 'Cátedras' },
    { id: 'cursos', icon: '🎓', label: 'Cursos' },
    { id: 'inscriptos_curso', icon: '📊', label: 'Inscriptos x Curso' },
    { id: 'docentes', icon: '👨‍🏫', label: 'Docentes' },
    { id: 'necesitan_docente', icon: '🔴', label: 'Necesitan Docente', badge: necesitanDocenteCount },
    { id: 'asincronicas', icon: '🎥', label: 'Asincrónicas' },
    { id: 'disponibilidad', icon: '🕐', label: 'Disponibilidad' },
    { id: 'docentes_dia', icon: '📋', label: 'Horarios x Día' },
    { id: 'calendario', icon: '📅', label: 'Calendario' },
    { id: 'plan_carrera', icon: '🗺️', label: 'Horarios x Carrera' },
    { id: 'sugerencias', icon: '🤖', label: 'Sug. Horarios x Carrera' },
    { id: 'solapamientos', icon: '⚠️', label: 'Solap. Horarios', badge: solapamientosCount },
    { id: 'solap_carreras', icon: '🎓', label: 'Solap. Carreras', badge: solapCarrerasCount },
    { id: 'bce_bea', icon: '🏫', label: 'BCE / BEA' },
    { id: 'control_insc', icon: '✅', label: 'Control Inscripciones' },
    { id: 'edi_alumnos', icon: '🔀', label: 'EDI por Cátedra' },
    { id: 'importar', icon: '📥', label: 'Importar', highlight: true },
    { id: 'exportar', icon: '📤', label: 'Exportar' },
    { id: 'decisiones', icon: '🎯', label: 'Toma de Decisiones' },
  ];
  return (
    <div className="w-64 bg-slate-900 min-h-screen p-4 flex flex-col">
      <div className="mb-6 px-2">
        <h1 className="text-xl font-bold text-white">IEA Horarios</h1>
        <p className="text-slate-500 text-sm">Sistema v16.0</p>
      </div>
      {/* v4.0 MEJORA 11: Selector año + cuatrimestre */}
      <div className="mb-6 px-2">
        <label className="text-xs text-slate-400 block mb-1">Ver cuatrimestre</label>
        <select className="w-full bg-slate-800 text-white rounded px-3 py-2 text-sm border border-slate-700"
          value={cuatrimestre} onChange={e => setCuatrimestre(e.target.value)}>
          <option value="todos">Todos los cuatrimestres</option>
          {(cuatrimestres || []).map(c => (
            <option key={c.id} value={c.id}>{c.nombre}</option>
          ))}
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
        <p className="text-xs text-slate-400 mb-2">Sedes operativas</p>
        {sedes.filter(s => SEDES_OPERATIVAS.includes(s.nombre)).map(s => (
          <div key={s.id} className="flex items-center gap-2 mb-1">
            <div className={`w-2 h-2 rounded-full ${SEDE_COLORS[s.nombre] || 'bg-gray-500'}`}></div>
            <span className="text-[10px] text-slate-300">{s.nombre}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

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
    } catch (e) { setError('Contraseña incorrecta'); }
    setLoading(false);
  };
  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center">
      <div className="bg-white rounded-2xl p-8 max-w-md w-full mx-4 shadow-2xl">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-slate-800">IEA Horarios</h1>
          <p className="text-slate-500 mt-1">Sistema de Gestión v6.0</p>
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

// ==================== MODAL EDITAR ASIGNACIÓN (v4.0 MEJORA 3) ====================
function ModalEditarAsignacion({ asignacion, docentes, sedes, onClose, recargar, catCodigo, catNombre }) {
  const [form, setForm] = useState({
    docente_id: asignacion.docente?.id?.toString() || '',
    modalidad: asignacion.modalidad || 'virtual_tm',
    sede_id: asignacion.sede_id?.toString() || '',
    dia: asignacion.dia || '',
    hora_inicio: asignacion.hora_inicio || '',
    recibe_alumnos_presenciales: asignacion.recibe_alumnos_presenciales || false,
  });
  const [error, setError] = useState('');

  const guardar = async () => {
    setError('');
    try {
      await apiFetch(`/api/asignaciones/${asignacion.id}`, {
        method: 'PUT',
        body: JSON.stringify({
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
        <h3 className="text-lg font-bold mb-2">✏️ Editar Asignación</h3>
        <p className="text-slate-600 mb-4">{catCodigo} - {catNombre}</p>
        <div className="space-y-3">
          <div><label className="text-sm text-slate-600 font-medium">Docente:</label>
            <select className="w-full border rounded-lg px-3 py-2 mt-1" value={form.docente_id} onChange={e => setForm({...form, docente_id: e.target.value})}>
              <option value="">Sin asignar</option>
              {docentes.map(d => <option key={d.id} value={d.id}>{d.nombre} {d.apellido}</option>)}
            </select></div>
          <div className="grid grid-cols-2 gap-3">
            <div><label className="text-sm text-slate-600">Modalidad:</label>
              <select className="w-full border rounded-lg px-3 py-2 mt-1" value={form.modalidad} onChange={e => setForm({...form, modalidad: e.target.value})}>
                {Object.entries(MODALIDAD_CONFIG).map(([k, v]) => <option key={k} value={k}>{v.icon} {v.label}</option>)}
              </select></div>
            <div><label className="text-sm text-slate-600">Sede:</label>
              <select className="w-full border rounded-lg px-3 py-2 mt-1" value={form.sede_id} onChange={e => setForm({...form, sede_id: e.target.value})}>
                <option value="">🏠 Remoto</option>
                {sedes.filter(s => SEDES_OPERATIVAS.includes(s.nombre)).map(s => <option key={s.id} value={s.id}>{s.nombre}</option>)}
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
          <button onClick={guardar} className="flex-1 py-2 bg-amber-500 text-slate-900 rounded-lg font-medium">Guardar</button>
          <button onClick={onClose} className="flex-1 py-2 bg-slate-100 rounded-lg">Cancelar</button>
        </div>
      </div>
    </div>
  );
}

// ==================== MODAL ASIGNAR CÁTEDRA ====================
function ModalAsignarCatedra({ catedra, docentes, sedes, cuatrimestre, cuatrimestres, onClose, recargar }) {
  const defaultCuat = cuatrimestre !== 'todos' ? cuatrimestre : ((cuatrimestres||[])[0]?.id?.toString() || '1');
  const [form, setForm] = useState({ cuatrimestre_id: defaultCuat, docente_id: '', modalidad: 'virtual_tm', sede_id: '', dia: '', hora_inicio: '', recibe_alumnos_presenciales: false });
  const [error, setError] = useState('');
  const crear = async () => {
    setError('');
    if (!form.cuatrimestre_id) { setError('Seleccioná un cuatrimestre'); return; }
    try {
      await apiFetch('/api/asignaciones', {
        method: 'POST',
        body: JSON.stringify({
          catedra_id: catedra.id,
          cuatrimestre_id: parseInt(form.cuatrimestre_id),
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
          <div><label className="text-sm text-slate-600 font-medium">Cuatrimestre:</label>
            <select className="w-full border-2 border-amber-300 rounded-lg px-3 py-2 mt-1 bg-amber-50" value={form.cuatrimestre_id} onChange={e => setForm({...form, cuatrimestre_id: e.target.value})}>
              {(cuatrimestres||[]).map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}
            </select></div>
          <div><label className="text-sm text-slate-600">Docente (opcional):</label>
            <select className="w-full border rounded-lg px-3 py-2 mt-1" value={form.docente_id} onChange={e => setForm({...form, docente_id: e.target.value})}>
              <option value="">Sin asignar (pendiente)</option>
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
                {sedes.filter(s => SEDES_OPERATIVAS.includes(s.nombre)).map(s => <option key={s.id} value={s.id}>{s.nombre}</option>)}
              </select></div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div><label className="text-sm text-slate-600">Día (opcional):</label>
              <select className="w-full border rounded-lg px-3 py-2 mt-1" value={form.dia} onChange={e => setForm({...form, dia: e.target.value})}>
                <option value="">Pendiente de confirmar</option>
                {DIAS.map(d => <option key={d} value={d}>{d}</option>)}
              </select></div>
            <div><label className="text-sm text-slate-600">Hora (opcional):</label>
              <select className="w-full border rounded-lg px-3 py-2 mt-1" value={form.hora_inicio} onChange={e => setForm({...form, hora_inicio: e.target.value})}>
                <option value="">Pendiente de confirmar</option>
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

// ==================== v11.0: DASHBOARD SEMÁFORO CON FLUJO GUIADO ====================
function DashboardView({ cuatrimestre, setActiveView }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    const cargar = async () => {
      setLoading(true);
      try {
        const cuatId = cuatrimestre !== 'todos' ? cuatrimestre : '';
        setData(await apiFetch(`/api/dashboard${cuatId ? `?cuatrimestre_id=${cuatId}` : ''}`));
      } catch (e) { console.error(e); }
      setLoading(false);
    };
    cargar();
  }, [cuatrimestre]);
  if (loading || !data) return <div className="p-8 text-center text-xl">⏳ Cargando dashboard...</div>;

  const cob = data.cobertura_pct;
  const sColor = cob >= 80 ? '#059669' : cob >= 50 ? '#D97706' : '#DC2626';
  const sBg = cob >= 80 ? 'bg-emerald-50 border-emerald-300' : cob >= 50 ? 'bg-amber-50 border-amber-300' : 'bg-red-50 border-red-300';
  const pasos = data.pasos || [];
  const pasoActual = pasos.find(p => !p.completo) || pasos[pasos.length - 1];

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <h2 className="text-2xl font-bold text-slate-800 mb-2">🏠 Dashboard — Estado del Cuatrimestre</h2>
      <p className="text-slate-500 mb-6">Seguí los pasos en orden para armar los horarios del cuatrimestre.</p>

      {/* Semáforo + resumen */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        <div className={`${sBg} border-2 rounded-2xl p-6 text-center`}>
          <p className="text-5xl font-extrabold" style={{color: sColor}}>{cob}%</p>
          <p className="text-sm font-bold mt-1" style={{color: sColor}}>Cobertura docentes</p>
        </div>
        <div className="bg-white border rounded-2xl p-6 text-center">
          <p className="text-3xl font-extrabold text-cyan-600">{data.total_inscripciones}</p>
          <p className="text-sm text-slate-500">Inscripciones</p>
          <div className="mt-2 text-xs text-slate-500">
            <span className="font-bold text-slate-700">{data.total_docentes}</span> docentes ·
            <span className="font-bold text-blue-600 ml-1">{data.docentes_con_asignacion}</span> con cátedra ·
            <span className="font-bold text-purple-600 ml-1">{data.total_asignaciones || 0}</span> asignaciones
          </div>
        </div>
        <div className="bg-white border rounded-2xl p-6 text-center">
          <div className="flex justify-center gap-4">
            {data.sin_docente > 0 && <div><p className="text-2xl font-bold text-red-500">{data.sin_docente}</p><p className="text-[10px] text-red-400">sin docente</p></div>}
            {data.solapamientos > 0 && <div><p className="text-2xl font-bold text-orange-500">{data.solapamientos}</p><p className="text-[10px] text-orange-400">solapamientos</p></div>}
            {data.sin_docente === 0 && data.solapamientos === 0 && <div><p className="text-3xl">✅</p><p className="text-sm text-emerald-600">Todo OK</p></div>}
          </div>
        </div>
      </div>

      {/* Flujo paso a paso */}
      <div className="space-y-3">
        {pasos.map(paso => {
          const esActual = paso.num === pasoActual?.num;
          const estado = paso.completo ? 'completo' : paso.parcial ? 'parcial' : (esActual ? 'actual' : 'pendiente');
          return (
            <div key={paso.num}
              onClick={() => setActiveView(paso.seccion)}
              className={`rounded-xl border-2 p-5 cursor-pointer transition-all hover:shadow-lg ${
                estado === 'completo' ? 'bg-emerald-50 border-emerald-300' :
                estado === 'parcial' ? 'bg-amber-50 border-amber-300' :
                esActual ? 'bg-blue-50 border-blue-400 shadow-md ring-2 ring-blue-200' :
                'bg-white border-slate-200 opacity-60'
              }`}>
              <div className="flex items-center gap-4">
                {/* Número/estado */}
                <div className={`w-12 h-12 rounded-full flex items-center justify-center text-lg font-extrabold flex-shrink-0 ${
                  estado === 'completo' ? 'bg-emerald-500 text-white' :
                  estado === 'parcial' ? 'bg-amber-500 text-white' :
                  esActual ? 'bg-blue-500 text-white animate-pulse' :
                  'bg-slate-200 text-slate-400'
                }`}>
                  {estado === 'completo' ? '✓' : paso.num}
                </div>
                {/* Contenido */}
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <h3 className={`font-bold text-lg ${estado === 'completo' ? 'text-emerald-700' : esActual ? 'text-blue-700' : 'text-slate-700'}`}>
                      {paso.titulo}
                    </h3>
                    {estado === 'parcial' && <span className="px-2 py-0.5 bg-amber-200 text-amber-800 rounded text-xs font-bold">EN PROGRESO</span>}
                    {esActual && estado !== 'parcial' && <span className="px-2 py-0.5 bg-blue-200 text-blue-800 rounded text-xs font-bold">← SIGUIENTE PASO</span>}
                  </div>
                  <p className="text-sm text-slate-500">{paso.desc}</p>
                  <p className={`text-sm font-medium mt-1 ${estado === 'completo' ? 'text-emerald-600' : estado === 'parcial' ? 'text-amber-700' : 'text-slate-400'}`}>
                    {paso.detalle}
                  </p>
                </div>
                {/* Flecha */}
                <div className="text-slate-300 text-2xl flex-shrink-0">→</div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Resumen rápido abajo */}
      <div className="grid grid-cols-4 gap-3 mt-8">
        {[
          {val: data.abrir, label: 'A abrir', color: 'text-emerald-600', bg: 'bg-emerald-50'},
          {val: data.asincronicas, label: 'Asincrónicas', color: 'text-purple-600', bg: 'bg-purple-50'},
          {val: data.sin_alumnos, label: 'Sin alumnos', color: 'text-slate-400', bg: 'bg-slate-50'},
          {val: data.docs_sugeridos, label: 'Docentes sugeridos', color: 'text-blue-600', bg: 'bg-blue-50'},
        ].map((s, i) => (
          <div key={i} className={`${s.bg} rounded-xl p-3 text-center`}>
            <p className={`text-2xl font-extrabold ${s.color}`}>{s.val}</p>
            <p className="text-xs text-slate-500">{s.label}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

// ==================== CÁTEDRAS VIEW (con mejoras 5, 7, 9) ====================
function CatedrasView({ catedras, docentes, sedes, cuatrimestre, cuatrimestres, recargar }) {
  const [filtros, setFiltros] = useState({ buscar: '', soloSinAsignar: false });
  const [modalCatedra, setModalCatedra] = useState(null);
  const [modalEditar, setModalEditar] = useState(null);
  const [editCatInfo, setEditCatInfo] = useState(null);
  const [paginaActual, setPaginaActual] = useState(1);
  const porPagina = 20;

  const catedrasFiltradas = useMemo(() => {
    return catedras.filter(c => {
      if (filtros.buscar && !c.nombre.toLowerCase().includes(filtros.buscar.toLowerCase()) &&
          !c.codigo.toLowerCase().includes(filtros.buscar.toLowerCase())) return false;
      if (filtros.soloSinAsignar && c.asignaciones?.length > 0) return false;
      return true;
    }); // Ya vienen ordenadas del backend por código numérico
  }, [catedras, filtros]);

  const totalPaginas = Math.ceil(catedrasFiltradas.length / porPagina);
  const catedrasPag = catedrasFiltradas.slice((paginaActual - 1) * porPagina, paginaActual * porPagina);

  const stats = useMemo(() => {
    const totalTM = catedras.reduce((s, c) => s + (c.tm_total || 0), 0);
    const totalTN = catedras.reduce((s, c) => s + (c.tn_total || 0), 0);
    const totalVirt = catedras.reduce((s, c) => s + (c.virt_cied || 0), 0);
    const totalSinClasif = catedras.reduce((s, c) => s + (c.sin_clasificar || 0), 0);
    const totalInsc = catedras.reduce((s, c) => s + (c.inscriptos || 0), 0);
    // v7.0: contar asignaciones por modalidad
    const allAsig = catedras.flatMap(c => c.asignaciones || []);
    const tmVirtual = allAsig.filter(a => a.modalidad === 'virtual_tm').length;
    const tnVirtual = allAsig.filter(a => a.modalidad === 'virtual_tn').length;
    const presencial = allAsig.filter(a => a.modalidad === 'presencial').length;
    const asinc = allAsig.filter(a => a.modalidad === 'asincronica').length;
    return {
      total: catedras.length,
      abiertas: catedras.filter(c => (c.asignaciones || []).length > 0).length,
      totalTM, totalTN, totalVirt, totalSinClasif, totalInsc,
      tmVirtual, tnVirtual, presencial, asinc,
    };
  }, [catedras]);

  const eliminarAsig = async (id) => {
    if (!window.confirm('¿Eliminar esta asignación?')) return;
    try { await apiFetch(`/api/asignaciones/${id}`, { method: 'DELETE' }); recargar(); } catch (e) { alert(e.message); }
  };

  const abrirEditar = (asig, cat) => {
    setModalEditar(asig);
    setEditCatInfo({ codigo: cat.codigo, nombre: cat.nombre });
  };

  return (
    <div className="p-8">
      <div className="mb-6"><h2 className="text-2xl font-bold text-slate-800">Cátedras</h2></div>
      {/* v4.0 MEJORA 9: Stats separadas */}
      <div className="grid grid-cols-7 gap-3 mb-4">
        {[
          { label: 'Total Cátedras', val: stats.total, color: '' },
          { label: '📋 Abiertas', val: stats.abiertas, color: 'text-blue-600' },
          { label: '☀️ Insc. TM', val: stats.totalTM, color: 'text-yellow-600' },
          { label: '🌙 Insc. TN', val: stats.totalTN, color: 'text-indigo-600' },
          { label: '🖥️ CIED Virt', val: stats.totalVirt, color: 'text-purple-600' },
          { label: '⚠️ Sin clasif.', val: stats.totalSinClasif, color: 'text-red-500' },
          { label: '👥 Total Inscr.', val: stats.totalInsc, color: 'text-cyan-600' },
        ].map((s, i) => (
          <div key={i} className="bg-white rounded-xl border p-3 text-center">
            <p className="text-slate-500 text-xs">{s.label}</p>
            <p className={`text-2xl font-bold ${s.color}`}>{s.val}</p>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-4 gap-3 mb-4">
        {[
          { label: '🖥️☀️ TM Virtual', val: stats.tmVirtual, color: 'text-blue-600' },
          { label: '🖥️🌙 TN Virtual', val: stats.tnVirtual, color: 'text-indigo-600' },
          { label: '🏫 Presencial', val: stats.presencial, color: 'text-emerald-600' },
          { label: '🎥 Asincrónicas', val: stats.asinc, color: 'text-purple-600' },
        ].map((s, i) => (
          <div key={i} className="bg-white rounded-xl border p-2 text-center">
            <p className="text-slate-500 text-[10px]">{s.label}</p>
            <p className={`text-xl font-bold ${s.color}`}>{s.val}</p>
          </div>
        ))}
      </div>
      {stats.totalSinClasif > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-3 mb-4">
          <p className="text-red-700 text-sm">⚠️ Hay <strong>{stats.totalSinClasif}</strong> inscripciones sin clasificar (importadas con la versión anterior). Reimportá los archivos de alumnos para que se clasifiquen correctamente por sede y turno.</p>
        </div>
      )}
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
      <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="bg-slate-800 text-white text-[10px]">
              <th className="p-2 text-left font-semibold" rowSpan="2" style={{width:'180px'}}>Cátedra</th>
              <th className="p-1 text-center bg-yellow-700" colSpan="5">TURNO MAÑANA</th>
              <th className="p-1 text-center bg-indigo-700" colSpan="5">TURNO NOCHE</th>
              <th className="p-1 text-center bg-purple-700" rowSpan="2">Virt</th>
              <th className="p-1 text-center bg-slate-600" colSpan="4">TOTAL SEDE</th>
              <th className="p-1 text-center bg-cyan-700" rowSpan="2">Total</th>
              <th className="p-1 text-center bg-red-700" rowSpan="2">?</th>
              <th className="p-1 text-center bg-slate-600" rowSpan="2">Doc</th>
              <th className="p-1 text-center bg-emerald-700" rowSpan="2" style={{width:'90px'}}>Decisión</th>
              <th className="p-1 text-center font-semibold" rowSpan="2" style={{width:'120px'}}>Asignaciones</th>
              <th className="p-1 text-center" rowSpan="2">Acc.</th>
            </tr>
            <tr className="bg-slate-700 text-white text-[9px]">
              <th className="p-0.5 bg-yellow-800">Av</th>
              <th className="p-0.5 bg-yellow-800">Cab</th>
              <th className="p-0.5 bg-yellow-800">VL</th>
              <th className="p-0.5 bg-yellow-800">CIED</th>
              <th className="p-0.5 bg-yellow-800 font-bold">TM</th>
              <th className="p-0.5 bg-indigo-800">Av</th>
              <th className="p-0.5 bg-indigo-800">Cab</th>
              <th className="p-0.5 bg-indigo-800">VL</th>
              <th className="p-0.5 bg-indigo-800">CIED</th>
              <th className="p-0.5 bg-indigo-800 font-bold">TN</th>
              <th className="p-0.5 bg-slate-600">Av</th>
              <th className="p-0.5 bg-slate-600">Cab</th>
              <th className="p-0.5 bg-slate-600">VL</th>
              <th className="p-0.5 bg-slate-600">CIED</th>
            </tr>
          </thead>
          <tbody>
            {catedrasPag.map(cat => {
              const necesitaApertura = (cat.inscriptos || 0) > 9 && (!cat.asignaciones || cat.asignaciones.length === 0);
              return (
              <tr key={cat.id} className={`border-b hover:bg-slate-50 text-xs ${necesitaApertura ? 'bg-yellow-50' : ''}`}>
                <td className="p-1.5" style={{minWidth:'160px'}}>
                  <span className="px-1.5 py-0.5 bg-slate-800 text-white rounded text-[10px] font-mono mr-1">{cat.codigo}</span>
                  <span className="text-xs font-medium">{cat.nombre}</span>
                  {necesitaApertura && <span className="ml-1 px-1 py-0.5 bg-yellow-300 text-yellow-900 rounded text-[9px] font-bold">ABRIR</span>}
                </td>
                <td className="p-0.5 text-center bg-yellow-50/40"><span className="font-bold text-blue-700">{cat.tm_av || ''}</span></td>
                <td className="p-0.5 text-center bg-yellow-50/40"><span className="font-bold text-emerald-700">{cat.tm_cab || ''}</span></td>
                <td className="p-0.5 text-center bg-yellow-50/40"><span className="font-bold text-amber-700">{cat.tm_vl || ''}</span></td>
                <td className="p-0.5 text-center bg-yellow-50/40"><span className="font-bold text-purple-600">{cat.tm_cied || ''}</span></td>
                <td className="p-0.5 text-center bg-yellow-100/60"><span className="font-extrabold text-sm">{cat.tm_total || ''}</span></td>
                <td className="p-0.5 text-center bg-indigo-50/40"><span className="font-bold text-blue-700">{cat.tn_av || ''}</span></td>
                <td className="p-0.5 text-center bg-indigo-50/40"><span className="font-bold text-emerald-700">{cat.tn_cab || ''}</span></td>
                <td className="p-0.5 text-center bg-indigo-50/40"><span className="font-bold text-amber-700">{cat.tn_vl || ''}</span></td>
                <td className="p-0.5 text-center bg-indigo-50/40"><span className="font-bold text-purple-600">{cat.tn_cied || ''}</span></td>
                <td className="p-0.5 text-center bg-indigo-100/60"><span className="font-extrabold text-sm">{cat.tn_total || ''}</span></td>
                <td className="p-0.5 text-center bg-purple-50/40"><span className="font-bold text-purple-600">{cat.virt_cied || ''}</span></td>
                <td className="p-0.5 text-center"><span className="font-bold text-blue-700">{cat.sede_av || ''}</span></td>
                <td className="p-0.5 text-center"><span className="font-bold text-emerald-700">{cat.sede_cab || ''}</span></td>
                <td className="p-0.5 text-center"><span className="font-bold text-amber-700">{cat.sede_vl || ''}</span></td>
                <td className="p-0.5 text-center"><span className="font-bold text-purple-600">{cat.sede_cied || ''}</span></td>
                <td className="p-0.5 text-center"><span className="text-sm font-extrabold text-cyan-600">{cat.inscriptos || ''}</span></td>
                <td className="p-0.5 text-center text-[10px] text-red-400">{cat.sin_clasificar || ''}</td>
                <td className="p-0.5 text-center">
                  {cat.docentes_sugeridos > 0 ? (
                    <span className={`text-xs font-bold ${(cat.asignaciones?.filter(a => a.docente)?.length || 0) < cat.docentes_sugeridos ? 'text-red-500' : 'text-emerald-500'}`}>
                      {cat.asignaciones?.filter(a => a.docente)?.length || 0}/{cat.docentes_sugeridos}
                    </span>
                  ) : <span className="text-slate-300 text-[10px]">-</span>}
                </td>
                <td className="p-0.5" style={{minWidth:'85px'}}>
                  <DecisionInput catedra={cat} />
                </td>
                <td className="p-1" style={{maxWidth:'120px'}}>
                  {cat.asignaciones?.length > 0 ? (
                    <div className="flex flex-wrap gap-0.5">
                      {cat.asignaciones.map(a => {
                        const mod = MODALIDAD_CONFIG[a.modalidad] || {};
                        return (
                          <div key={a.id} className="px-1 py-0.5 rounded text-[9px] border bg-white" title={`${mod.label || ''} ${a.docente ? a.docente.nombre : 'Sin doc.'} ${a.dia||''} ${a.hora_inicio||''} ${a.sede_nombre||''}`}>
                            <span>{mod.icon || '⏳'}</span>
                            <span className="ml-0.5">{a.docente ? a.docente.nombre.split(' ')[0] : '⚠️'}</span>
                            <button onClick={() => abrirEditar(a, cat)} className="text-blue-500 ml-0.5">✏️</button>
                            <button onClick={() => eliminarAsig(a.id)} className="text-red-400 ml-0.5">×</button>
                          </div>
                        );
                      })}
                    </div>
                  ) : <span className="text-slate-300 text-[10px]">—</span>}
                </td>
                <td className="p-1 text-center">
                  <button onClick={() => setModalCatedra(cat)} className="px-2 py-1 bg-amber-500 text-slate-900 rounded text-[10px] font-medium">+</button>
                </td>
              </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="flex justify-center gap-2 mt-4">
        <button onClick={() => setPaginaActual(Math.max(1, paginaActual - 1))} disabled={paginaActual === 1} className="px-3 py-1 bg-slate-200 rounded disabled:opacity-50">← Anterior</button>
        <span className="px-3 py-1 text-sm text-slate-600">Página {paginaActual} de {totalPaginas || 1}</span>
        <button onClick={() => setPaginaActual(Math.min(totalPaginas, paginaActual + 1))} disabled={paginaActual >= totalPaginas} className="px-3 py-1 bg-slate-200 rounded disabled:opacity-50">Siguiente →</button>
      </div>
      {modalCatedra && <ModalAsignarCatedra catedra={modalCatedra} docentes={docentes} sedes={sedes} cuatrimestre={cuatrimestre} cuatrimestres={cuatrimestres} onClose={() => setModalCatedra(null)} recargar={recargar} />}
      {modalEditar && editCatInfo && <ModalEditarAsignacion asignacion={modalEditar} docentes={docentes} sedes={sedes} onClose={() => { setModalEditar(null); setEditCatInfo(null); }} recargar={recargar} catCodigo={editCatInfo.codigo} catNombre={editCatInfo.nombre} />}
    </div>
  );
}

// ==================== v12.0: DECISIONES - Módulo central ====================
function DecisionesView({ catedras, cuatrimestre, recargar }) {
  const [criterio, setCriterio] = useState(null);
  const [sugerencias, setSugerencias] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filtro, setFiltro] = useState('todas');
  const [marcando, setMarcando] = useState(false);
  useEffect(() => {
    const cargar = async () => {
      setLoading(true);
      try {
        const cuatId = cuatrimestre !== 'todos' ? cuatrimestre : '';
        const qp = cuatId ? `?cuatrimestre_id=${cuatId}` : '';
        setCriterio(await apiFetch(`/api/catedras/criterio-apertura${qp}`));
        try {
          const sug = await apiFetch(`/api/sugerencias-armado${qp}`);
          // Flatten all suggestions into a code→suggestion map
          const sugMap = {};
          for (const sede of Object.values(sug.sedes || {})) {
            for (const carrera of Object.values(sede)) {
              for (const cats of Object.values(carrera)) {
                for (const cat of cats) {
                  if (!sugMap[cat.codigo] || cat.sugerencia_docente) sugMap[cat.codigo] = cat;
                }
              }
            }
          }
          setSugerencias(sugMap);
        } catch (e) { console.error(e); }
      } catch (e) { console.error(e); }
      setLoading(false);
    };
    cargar();
  }, [cuatrimestre]);
  const autoMarcarAsinc = async () => {
    setMarcando(true);
    try {
      const cuatId = cuatrimestre !== 'todos' ? cuatrimestre : '';
      const r = await apiFetch(`/api/catedras/auto-decision-asincronicas${cuatId ? `?cuatrimestre_id=${cuatId}` : ''}`, { method: 'POST' });
      alert(`✅ ${r.marcadas} cátedras marcadas (${r.asincronicas} asincrónicas + ${r.sin_alumnos} sin alumnos)`);
      recargar();
    } catch (e) { alert(e.message); }
    setMarcando(false);
  };
  if (loading) return <div className="p-8 text-center">⏳ Cargando...</div>;
  const catsConInfo = catedras.map(c => {
    const enAbrir = criterio?.abrir?.find(a => a.codigo === c.codigo);
    const enAsinc = criterio?.asincronica?.find(a => a.codigo === c.codigo);
    let sug = 'SIN ALUMNOS'; let docs = 0;
    if (enAbrir) { sug = 'ABRIR'; docs = enAbrir.docentes_sugeridos; }
    else if (enAsinc) sug = 'ASINCRÓNICA';
    // Get docente info from sugerencias
    const sugInfo = sugerencias?.[c.codigo];
    const tieneDocente = !!sugInfo?.docente_actual;
    const tieneSugerencia = !!sugInfo?.sugerencia_docente;
    return { ...c, sugerencia: sug, docs_sug_calc: docs, tieneDocente, tieneSugerencia, sugInfo };
  }).filter(c => {
    if (filtro === 'abrir') return c.sugerencia === 'ABRIR';
    if (filtro === 'asinc') return c.sugerencia === 'ASINCRÓNICA';
    if (filtro === 'sin') return c.sugerencia === 'SIN ALUMNOS';
    if (filtro === 'pendientes') return c.sugerencia === 'ABRIR' && !c.tieneDocente;
    if (filtro === 'decididas') return c.tieneDocente;
    return true;
  });
  const totalDecididas = catedras.filter(c => {
    const si = sugerencias?.[c.codigo];
    return !!si?.docente_actual;
  }).length;
  const totalPendAbrir = catedras.filter(c => {
    const enAbrir = criterio?.abrir?.find(a => a.codigo === c.codigo);
    const si = sugerencias?.[c.codigo];
    return enAbrir && !si?.docente_actual;
  }).length;
  return (
    <div className="p-8">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-slate-800">🎯 Toma de Decisiones</h2>
        <p className="text-slate-500 text-sm mt-1">Decidí qué cátedras abrir, cuáles van asincrónicas, y asigná docentes.</p>
        <div className="mt-3 bg-blue-50 border border-blue-200 rounded-xl p-4">
          <p className="text-blue-800 font-semibold mb-2">Criterio de apertura</p>
          <div className="text-sm text-blue-700 space-y-1">
            <p>• <strong>≥10 inscriptos total</strong> → <strong>ABRIR</strong> (contratar docente)</p>
            <p>• <strong>1 a 9 inscriptos</strong> → <strong>ASINCRÓNICA</strong> (material pregrabado, sin docente)</p>
            <p>• <strong>0 inscriptos</strong> → <strong>NO SE ABRE</strong></p>
          </div>
        </div>
      </div>
      <div className="grid grid-cols-5 gap-3 mb-4">
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-3 text-center"><p className="text-2xl font-bold text-emerald-600">{totalDecididas}</p><p className="text-xs">✅ Con docente</p></div>
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-center"><p className="text-2xl font-bold text-amber-600">{totalPendAbrir}</p><p className="text-xs">⚠️ Pendientes</p></div>
        <div className="bg-slate-50 border rounded-xl p-3 text-center"><p className="text-2xl font-bold">{criterio?.stats?.total_abrir||0}</p><p className="text-xs">A abrir (≥10)</p></div>
        <div className="bg-purple-50 border border-purple-200 rounded-xl p-3 text-center"><p className="text-2xl font-bold text-purple-600">{criterio?.stats?.total_asincronica||0}</p><p className="text-xs">Asincrónicas</p></div>
        <div className="bg-slate-50 border rounded-xl p-3 text-center"><p className="text-2xl font-bold text-slate-400">{criterio?.stats?.total_sin_alumnos||0}</p><p className="text-xs">Sin alumnos</p></div>
      </div>
      <div className="flex gap-2 mb-4 flex-wrap items-center">
        {[['todas','Todas'],['abrir','A abrir'],['decididas','✅ Con docente asignado'],['pendientes','⚠️ Pendientes y sugerencias'],['asinc','🎥 Asincrónicas'],['sin','Sin alumnos']].map(([k,l]) => (
          <button key={k} onClick={() => setFiltro(k)} className={`px-3 py-1.5 rounded-lg text-sm ${filtro === k ? 'bg-blue-600 text-white' : 'bg-slate-100'}`}>{l}</button>
        ))}
        <div className="flex-1" />
        <button onClick={autoMarcarAsinc} disabled={marcando} className="px-4 py-2 bg-purple-600 text-white rounded-lg text-sm font-medium disabled:opacity-50">
          {marcando ? '⏳...' : '🎥 Auto-marcar asincrónicas'}
        </button>
      </div>
      {filtro === 'pendientes' && totalPendAbrir > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 mb-4">
          <p className="text-amber-800 text-sm font-medium">⚠️ {totalPendAbrir} cátedras abiertas sin docente asignado. Las que tienen sugerencia aparecen en <span className="text-blue-600 font-bold">azul</span>, las que no en <span className="text-red-500 font-bold">rojo</span>.</p>
        </div>
      )}
      <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead><tr className="bg-slate-800 text-white text-xs">
            <th className="p-2 text-left">Cátedra</th>
            <th className="p-2 text-center w-20">Inscr.</th>
            <th className="p-2 text-center w-24">Criterio</th>
            <th className="p-2 text-center w-14">Doc.</th>
            <th className="p-2 text-left" style={{width:'180px'}}>Docente / Sugerencia</th>
            <th className="p-2 text-center" style={{width:'160px'}}>Decisión (multi-sede)</th>
            <th className="p-2 text-left" style={{width:'120px'}}>Notas</th>
          </tr></thead>
          <tbody>
            {catsConInfo.map(cat => {
              const rowBg = cat.tieneDocente ? 'bg-emerald-50' : cat.tieneSugerencia ? 'bg-blue-50' : (cat.sugerencia === 'ABRIR' ? 'bg-red-50' : '');
              return (
              <tr key={cat.id} className={`border-b hover:bg-slate-100 ${rowBg}`}>
                <td className="p-2"><span className="font-mono text-[10px] bg-slate-800 text-white px-1 rounded mr-1">{cat.codigo}</span><span className="text-xs">{cat.nombre}</span></td>
                <td className="p-2 text-center"><span className="text-lg font-bold text-cyan-600">{cat.inscriptos || 0}</span></td>
                <td className="p-2 text-center"><span className={`px-2 py-0.5 rounded text-[10px] font-bold ${cat.sugerencia==='ABRIR'?'bg-emerald-100 text-emerald-700':cat.sugerencia==='ASINCRÓNICA'?'bg-purple-100 text-purple-700':'bg-slate-100 text-slate-400'}`}>{cat.sugerencia}</span></td>
                <td className="p-2 text-center font-bold">{cat.docs_sug_calc || ''}</td>
                <td className="p-2 text-xs">
                  {cat.tieneDocente ? (
                    <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-500 inline-block"></span><span className="text-emerald-700 font-bold">{cat.sugInfo?.docente_actual}</span></span>
                  ) : cat.tieneSugerencia ? (
                    <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-blue-500 inline-block"></span><span className="text-blue-600 italic font-medium">{cat.sugInfo?.sugerencia_docente}</span><span className="text-[9px] text-blue-400">(sugerido)</span></span>
                  ) : cat.sugerencia === 'ABRIR' ? (
                    <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-400 inline-block"></span><span className="text-red-400">Sin docente disponible</span></span>
                  ) : ''}
                </td>
                <td className="p-2"><DecisionInput catedra={cat} /></td>
                <td className="p-2"><NotasInput item={cat} endpoint="catedras" /></td>
              </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="text-sm text-slate-500 mt-3 text-center">{catsConInfo.length} cátedras — {totalDecididas} con docente asignado — {totalPendAbrir} pendientes</p>
    </div>
  );
}

// ==================== v4.0 MEJORA 8: NECESITAN DOCENTE ====================
function NecesitanDocenteView({ cuatrimestre, cuatrimestres }) {
  const [datos, setDatos] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const cargar = async () => {
      setLoading(true);
      try {
        const cuatId = cuatrimestre !== 'todos' ? cuatrimestre : '';
        const qParam = cuatId ? `?cuatrimestre_id=${cuatId}` : '';
        const r = await apiFetch(`/api/catedras/necesitan-docente${qParam}`);
        setDatos(r);
      } catch (e) { console.error(e); }
      setLoading(false);
    };
    cargar();
  }, [cuatrimestre]);

  if (loading) return <div className="p-8 text-center">⏳ Cargando...</div>;

  return (
    <div className="p-8">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-slate-800">🔴 Materias que necesitan docente</h2>
        <p className="text-slate-500 text-sm">Cátedras con 10 o más inscriptos en una misma sede y turno, sin docente asignado.</p>
      </div>
      {datos.length === 0 ? (
        <div className="bg-green-50 border border-green-200 rounded-xl p-8 text-center">
          <p className="text-4xl mb-2">✅</p>
          <p className="text-green-700 font-medium">Todas las combinaciones sede/turno con +5 inscriptos tienen docente</p>
        </div>
      ) : (
        <>
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-6">
            <p className="text-red-700 font-medium">{datos.length} cátedras necesitan más docentes</p>
            <p className="text-red-600 text-sm">Total docentes faltantes: {datos.reduce((s, d) => s + (d.faltan || 0), 0)}</p>
          </div>
          <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
            <table className="w-full">
              <thead><tr className="bg-slate-50 border-b">
                <th className="text-left p-3 text-sm font-semibold">Cátedra</th>
                <th className="text-center p-3 text-sm font-semibold w-16">Inscr.</th>
                <th className="text-center p-3 text-sm font-semibold w-16">Neces.</th>
                <th className="text-center p-3 text-sm font-semibold w-16">Actual</th>
                <th className="text-center p-3 text-sm font-semibold w-16">Faltan</th>
                <th className="text-left p-3 text-sm font-semibold">✅ Sedes ya asignadas</th>
                <th className="text-left p-3 text-sm font-semibold">⚠️ Desglose inscriptos</th>
              </tr></thead>
              <tbody>
                {datos.map(d => (
                  <tr key={d.catedra_id} className="border-b hover:bg-slate-50">
                    <td className="p-3">
                      <span className="px-2 py-1 bg-slate-800 text-white rounded text-xs font-mono mr-2">{d.codigo}</span>
                      <span className="font-medium">{d.nombre}</span>
                    </td>
                    <td className="p-3 text-center"><span className="text-lg font-bold text-cyan-600">{d.inscriptos_total}</span></td>
                    <td className="p-3 text-center"><span className="text-lg font-bold">{d.docs_necesarios}</span></td>
                    <td className="p-3 text-center"><span className={`text-lg font-bold ${d.docentes_asignados > 0 ? 'text-emerald-600' : 'text-red-500'}`}>{d.docentes_asignados}</span></td>
                    <td className="p-3 text-center"><span className="px-3 py-1 bg-red-100 text-red-700 rounded-full font-bold">{d.faltan}</span></td>
                    <td className="p-3">
                      {(d.sedes_asignadas || []).length > 0 ? (
                        <div className="flex flex-wrap gap-1">
                          {d.sedes_asignadas.map((sa, i) => (
                            <div key={i} className="px-2 py-1 bg-emerald-50 border border-emerald-300 rounded text-xs">
                              <span className="font-bold text-emerald-700">✅ {sa.turno}</span>
                              <span className={`ml-1 px-1 rounded text-white text-[10px] ${
                                sa.sede.includes('Avellaneda') ? 'bg-blue-500' : sa.sede.includes('Caballito') ? 'bg-emerald-500' :
                                sa.sede.includes('Vicente') ? 'bg-amber-500' : 'bg-purple-500'
                              }`}>{sa.sede}</span>
                              <span className="ml-1 text-emerald-600 text-[10px]">{sa.docente}</span>
                            </div>
                          ))}
                        </div>
                      ) : <span className="text-red-400 text-sm italic">Sin docente</span>}
                    </td>
                    <td className="p-3">
                      <div className="flex flex-wrap gap-1">
                        {(d.aperturas_info || []).map((ap, i) => (
                          <div key={i} className="px-2 py-1 bg-slate-50 border rounded text-xs">
                            <span className="font-medium">{ap.turno}</span>
                            <span className={`ml-1 px-1 rounded text-white text-[10px] ${
                              ap.sede === 'Avellaneda' ? 'bg-blue-500' : ap.sede === 'Caballito' ? 'bg-emerald-500' :
                              ap.sede === 'Vicente López' ? 'bg-amber-500' : 'bg-purple-500'
                            }`}>{ap.sede}</span>
                            <span className="ml-1 text-slate-500">({ap.inscriptos})</span>
                          </div>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

// ==================== v8.0: MATERIAS ASINCRÓNICAS (1-9 alumnos) ====================
function AsincronicasView({ cuatrimestre }) {
  const [datos, setDatos] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    const cargar = async () => {
      setLoading(true);
      try {
        const cuatId = cuatrimestre !== 'todos' ? cuatrimestre : '';
        const qParam = cuatId ? `?cuatrimestre_id=${cuatId}` : '';
        const r = await apiFetch(`/api/catedras/criterio-apertura${qParam}`);
        setDatos(r);
      } catch (e) { console.error(e); }
      setLoading(false);
    };
    cargar();
  }, [cuatrimestre]);
  if (loading) return <div className="p-8 text-center">⏳ Cargando...</div>;
  if (!datos) return null;
  return (
    <div className="p-8">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-slate-800">🎥 Materias Asincrónicas</h2>
        <p className="text-slate-500 text-sm">Cátedras con 1 a 9 inscriptos totales. Se dictan con material pregrabado (sin docente en vivo).</p>
      </div>
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 text-center">
          <p className="text-xs text-emerald-600">Abrir con docente</p><p className="text-3xl font-bold text-emerald-700">{datos.stats.total_abrir}</p><p className="text-xs text-emerald-500">≥10 inscriptos</p>
        </div>
        <div className="bg-purple-50 border border-purple-200 rounded-xl p-4 text-center">
          <p className="text-xs text-purple-600">Asincrónicas</p><p className="text-3xl font-bold text-purple-700">{datos.stats.total_asincronica}</p><p className="text-xs text-purple-500">1-9 inscriptos</p>
        </div>
        <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 text-center">
          <p className="text-xs text-slate-600">Sin alumnos</p><p className="text-3xl font-bold text-slate-400">{datos.stats.total_sin_alumnos}</p><p className="text-xs text-slate-400">0 inscriptos</p>
        </div>
      </div>
      <div className="bg-white rounded-xl border shadow-sm overflow-hidden mb-6">
        <div className="p-3 bg-purple-50 border-b"><h3 className="font-semibold text-purple-800">🎥 Asincrónicas ({datos.asincronica.length})</h3></div>
        <table className="w-full">
          <thead><tr className="bg-slate-50 border-b text-sm">
            <th className="p-3 text-left">Cátedra</th><th className="p-3 text-center w-24">Inscriptos</th><th className="p-3 text-left">Estado</th>
          </tr></thead>
          <tbody>
            {datos.asincronica.map((d, i) => (
              <tr key={i} className="border-b hover:bg-purple-50/30">
                <td className="p-3"><span className="font-mono text-xs bg-purple-800 text-white px-1 rounded mr-2">{d.codigo}</span>{d.nombre}</td>
                <td className="p-3 text-center"><span className="text-lg font-bold text-purple-600">{d.total}</span></td>
                <td className="p-3"><span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs">🎥 Asincrónica — Material pregrabado</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {datos.sin_alumnos.length > 0 && (
        <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
          <div className="p-3 bg-slate-50 border-b"><h3 className="font-semibold text-slate-600">Sin alumnos ({datos.sin_alumnos.length})</h3></div>
          <div className="p-4 flex flex-wrap gap-2">
            {datos.sin_alumnos.map((d, i) => (
              <span key={i} className="px-2 py-1 bg-slate-100 rounded text-xs text-slate-500">
                <span className="font-mono">{d.codigo}</span> {d.nombre}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ==================== DOCENTES VIEW ====================
function DocentesView({ docentes, sedes, cuatrimestre, recargar }) {
  const [modalSedes, setModalSedes] = useState(null);
  const [modalEditar, setModalEditar] = useState(null);
  const [modalNuevo, setModalNuevo] = useState(false);
  const [buscar, setBuscar] = useState('');

  // v15: editStore persiste datos editables en un ref que NUNCA se pierde
  const editStore = useRef({});
  const editInitialized = useRef(false);
  if (!editInitialized.current && docentes.length > 0) {
    docentes.forEach(d => {
      if (!editStore.current[d.id]) {
        editStore.current[d.id] = {
          horas_asignadas: d.horas_asignadas || 0,
          materias_av: d.materias_av || 0,
          materias_cab: d.materias_cab || 0,
          materias_vl: d.materias_vl || 0,
          sociedad_cfpea: d.sociedad_cfpea || false,
          sociedad_isftea: d.sociedad_isftea || false,
          notas: d.notas || '',
          especialidad: d.especialidad || '',
          catedras_referencia: d.catedras_referencia || '',
        };
      }
    });
    editInitialized.current = true;
  }
  // Also add new docentes that weren't there at init
  docentes.forEach(d => {
    if (!editStore.current[d.id]) {
      editStore.current[d.id] = {
        horas_asignadas: d.horas_asignadas || 0,
        materias_av: d.materias_av || 0,
        materias_cab: d.materias_cab || 0,
        materias_vl: d.materias_vl || 0,
        sociedad_cfpea: d.sociedad_cfpea || false,
        sociedad_isftea: d.sociedad_isftea || false,
        notas: d.notas || '',
        especialidad: d.especialidad || '',
        catedras_referencia: d.catedras_referencia || '',
      };
    }
  });

  const stats = useMemo(() => {
    const s = { PRESENCIAL_VIRTUAL: 0, SEDE_VIRTUAL: 0, REMOTO: 0, SIN_ASIGNACIONES: 0 };
    let horas_cfpea = 0, horas_isftea = 0, horas_total = 0;
    let mat_av_total = 0, mat_cab_total = 0, mat_vl_total = 0;
    const por_sede = {};
    docentes.forEach(d => {
      if (s[d.tipo_modalidad] !== undefined) s[d.tipo_modalidad]++;
      const h = d.horas_asignadas || 0;
      horas_total += h;
      if (d.sociedad_cfpea) horas_cfpea += h;
      if (d.sociedad_isftea) horas_isftea += h;
      mat_av_total += d.materias_av || 0;
      mat_cab_total += d.materias_cab || 0;
      mat_vl_total += d.materias_vl || 0;
      (d.sedes || []).forEach(sd => {
        por_sede[sd.nombre] = (por_sede[sd.nombre] || 0) + 1;
      });
    });
    return { ...s, horas_cfpea, horas_isftea, horas_total, mat_av_total, mat_cab_total, mat_vl_total, por_sede };
  }, [docentes]);

  const docentesFiltrados = useMemo(() => {
    if (!buscar) return docentes;
    const b = buscar.toLowerCase();
    return docentes.filter(d => d.nombre.toLowerCase().includes(b) || d.apellido.toLowerCase().includes(b) || d.dni.includes(b));
  }, [docentes, buscar]);

  const guardarSedes = async (docenteId, sedeIds) => {
    try { await apiFetch(`/api/docentes/${docenteId}/sedes`, { method: 'PUT', body: JSON.stringify({ sede_ids: sedeIds }) }); recargar(); setModalSedes(null); } catch (e) { alert(e.message); }
  };
  const guardarDocente = async (docenteId, data) => {
    try { await apiFetch(`/api/docentes/${docenteId}`, { method: 'PUT', body: JSON.stringify(data) }); recargar(); setModalEditar(null); } catch (e) { alert(e.message); }
  };
  const crearDocente = async (data) => {
    try { await apiFetch('/api/docentes', { method: 'POST', body: JSON.stringify(data) }); recargar(); setModalNuevo(false); } catch (e) { alert(e.message); }
  };
  const eliminarDocente = async (d) => {
    if (!window.confirm(`¿Eliminar a ${d.nombre} ${d.apellido}?`)) return;
    try { await apiFetch(`/api/docentes/${d.id}`, { method: 'DELETE' }); recargar(); } catch (e) { alert(e.message); }
  };

  return (
    <div className="p-8">
      <div className="flex justify-between items-center mb-6">
        <div><h2 className="text-2xl font-bold text-slate-800">Docentes</h2></div>
        <button onClick={() => setModalNuevo(true)} className="px-4 py-2 bg-amber-500 text-slate-900 rounded-lg font-medium hover:bg-amber-400">+ Agregar Docente</button>
      </div>
      <div className="grid grid-cols-4 gap-4 mb-6">
        {Object.entries(TIPO_DOCENTE_CONFIG).map(([key, cfg]) => (
          <div key={key} className={`p-4 rounded-xl border ${cfg.bg}`}>
            <p className={`font-medium ${cfg.color}`}>{cfg.icon} {cfg.label}</p>
            <p className={`text-3xl font-bold ${cfg.color}`}>{stats[key] || 0}</p>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-4 gap-3 mb-4">
        <div className="bg-slate-800 rounded-xl p-3 text-white"><p className="text-xs opacity-70">Total docentes</p><p className="text-2xl font-bold">{docentes.length}</p></div>
        <div className="bg-white rounded-xl border p-3"><p className="text-xs text-slate-500">Total horas</p><p className="text-2xl font-bold">{stats.horas_total}h</p></div>
        <div className="bg-white rounded-xl border p-3"><p className="text-xs text-slate-500">Horas CFPEA SRL</p><p className="text-2xl font-bold text-blue-600">{stats.horas_cfpea}h</p></div>
        <div className="bg-white rounded-xl border p-3"><p className="text-xs text-slate-500">Horas ISFTEA SRL</p><p className="text-2xl font-bold text-emerald-600">{stats.horas_isftea}h</p></div>
      </div>
      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="bg-blue-50 rounded-xl border border-blue-200 p-3"><p className="text-xs text-blue-600">Materias Avellaneda</p><p className="text-2xl font-bold text-blue-700">{stats.mat_av_total}</p></div>
        <div className="bg-emerald-50 rounded-xl border border-emerald-200 p-3"><p className="text-xs text-emerald-600">Materias Caballito</p><p className="text-2xl font-bold text-emerald-700">{stats.mat_cab_total}</p></div>
        <div className="bg-amber-50 rounded-xl border border-amber-200 p-3"><p className="text-xs text-amber-600">Materias V. López</p><p className="text-2xl font-bold text-amber-700">{stats.mat_vl_total}</p></div>
      </div>
      {Object.keys(stats.por_sede).length > 0 && (
        <div className="flex gap-2 mb-4 flex-wrap">
          <span className="text-xs text-slate-500 py-1">Docentes por sede:</span>
          {Object.entries(stats.por_sede).map(([sede, cnt]) => (
            <span key={sede} className={`px-2 py-1 rounded text-white text-xs ${SEDE_COLORS[sede] || 'bg-gray-500'}`}>{sede}: {cnt}</span>
          ))}
        </div>
      )}
      <div className="bg-white rounded-xl border p-3 mb-4">
        <input type="text" placeholder="Buscar por nombre, apellido o DNI..." className="w-full px-3 py-2 border rounded-lg text-sm"
          value={buscar} onChange={e => setBuscar(e.target.value)} />
      </div>
      <div className="bg-white rounded-xl border shadow-sm">
        <table className="w-full">
          <thead><tr className="bg-slate-50 border-b">
            <th className="text-left p-4 text-sm font-semibold">Docente</th>
            <th className="text-center p-4 text-sm font-semibold">Tipo</th>
            <th className="text-center p-4 text-sm font-semibold">Sedes</th>
            <th className="text-center p-2 text-xs font-semibold" colSpan="7">Horas · Materias por sede · CFPEA · ISFTEA · Notas · Especialidad · Cát. ref.</th>
            <th className="text-center p-2 text-xs font-semibold">Disponib.</th>
            <th className="text-left p-4 text-sm font-semibold">Asignaciones</th>
            <th className="text-center p-4 text-sm font-semibold w-36">Acciones</th>
          </tr></thead>
          <tbody>
            {docentesFiltrados.map(d => {
              const tipoCfg = TIPO_DOCENTE_CONFIG[d.tipo_modalidad] || TIPO_DOCENTE_CONFIG.SIN_ASIGNACIONES;
              return (
                <tr key={d.id} className={`border-b hover:bg-slate-50 ${(d.horas_asignadas > 0 || d.asignaciones?.length > 0) ? 'bg-emerald-50/50' : ''}`}>
                  <td className="p-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-slate-800 text-white flex items-center justify-center font-bold text-sm">{(d.nombre||'?')[0]}{(d.apellido||'?')[0]}</div>
                      <div><p className="font-medium">{d.nombre} {d.apellido}</p><p className="text-xs text-slate-500">DNI: {d.dni}</p>
                        {d.email && <p className="text-xs text-slate-400">{d.email}</p>}</div>
                    </div>
                  </td>
                  <td className="p-4 text-center"><span className={`px-3 py-1 rounded-full text-xs font-medium ${tipoCfg.bg} ${tipoCfg.color}`}>{tipoCfg.icon} {tipoCfg.label}</span></td>
                  <td className="p-4 text-center">
                    <div className="flex flex-wrap justify-center gap-1">
                      {d.sedes?.length > 0 ? d.sedes.map(s => <span key={s.id} className={`px-2 py-0.5 rounded text-white text-xs ${SEDE_COLORS[s.nombre]||'bg-gray-500'}`}>{s.nombre}</span>)
                        : <span className="text-slate-400 text-xs">Sin sedes</span>}
                    </div>
                    <button onClick={() => setModalSedes(d)} className="text-xs text-blue-600 hover:underline mt-1">Editar sedes</button>
                  </td>
                  <td className="p-1" colSpan="7">
                    <DocenteEditRow docId={d.id} editStore={editStore} />
                  </td>
                  <td className="p-2 text-center text-xs">
                    <span className={`px-2 py-1 rounded ${d.disponibilidad_resumen === 'Sin asignar' ? 'bg-slate-100 text-slate-400' : 'bg-emerald-100 text-emerald-700'}`}>
                      {d.disponibilidad_resumen || 'Sin asignar'}
                    </span>
                    {d.disponibilidad_franjas?.length > 0 && (
                      <div className="mt-1 text-[9px] text-slate-400">{d.disponibilidad_franjas.slice(0,3).join(', ')}{d.disponibilidad_franjas.length > 3 ? '...' : ''}</div>
                    )}
                  </td>
                  <td className="p-4">
                    {d.asignaciones?.length > 0 ? d.asignaciones.map(a => {
                      const mod = MODALIDAD_CONFIG[a.modalidad] || {};
                      return (<div key={a.id} className="flex items-center gap-2 text-sm mb-1">
                        <span className={mod.color}>{mod.icon}</span>
                        <span className="font-mono bg-slate-100 px-1 rounded text-xs">{a.catedra_codigo}</span>
                        <span className="text-slate-500 text-xs">{a.dia||'Pend.'} {a.hora_inicio||''}</span>
                      </div>);
                    }) : <span className="text-slate-400 text-sm">Sin asignaciones</span>}
                  </td>
                  <td className="p-4 text-center">
                    <div className="flex gap-1 justify-center">
                      <button onClick={() => setModalEditar(d)} className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs hover:bg-blue-200">✏️</button>
                      <button onClick={() => eliminarDocente(d)} className="px-2 py-1 bg-red-100 text-red-700 rounded text-xs hover:bg-red-200">🗑️</button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="text-sm text-slate-500 mt-3 text-center">{docentesFiltrados.length} docentes</p>
      {modalSedes && <ModalEditarSedes docente={modalSedes} sedes={sedes} onSave={guardarSedes} onClose={() => setModalSedes(null)} />}
      {modalEditar && <ModalEditarDocente docente={modalEditar} onSave={guardarDocente} onClose={() => setModalEditar(null)} />}
      {modalNuevo && <ModalNuevoDocente onSave={crearDocente} onClose={() => setModalNuevo(false)} />}
    </div>
  );
}

function ModalEditarDocente({ docente, onSave, onClose }) {
  const [form, setForm] = useState({ nombre: docente.nombre, apellido: docente.apellido, dni: docente.dni, email: docente.email || '' });
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"><div className="bg-white rounded-xl p-6 max-w-md w-full mx-4">
      <h3 className="text-lg font-bold mb-4">Editar Docente</h3>
      <div className="space-y-3">
        {['dni','nombre','apellido','email'].map(f => (
          <div key={f}><label className="text-sm text-slate-600 capitalize">{f}</label>
            <input className="w-full border rounded-lg px-3 py-2 mt-1" value={form[f]} onChange={e => setForm({...form, [f]: e.target.value})} /></div>
        ))}
      </div>
      <div className="flex gap-2 mt-4">
        <button onClick={() => onSave(docente.id, form)} className="flex-1 py-2 bg-amber-500 rounded-lg font-medium">Guardar</button>
        <button onClick={onClose} className="flex-1 py-2 bg-slate-100 rounded-lg">Cancelar</button>
      </div>
    </div></div>
  );
}

function ModalNuevoDocente({ onSave, onClose }) {
  const [form, setForm] = useState({ dni: '', nombre: '', apellido: '', email: '' });
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"><div className="bg-white rounded-xl p-6 max-w-md w-full mx-4">
      <h3 className="text-lg font-bold mb-4">Agregar Docente</h3>
      <div className="space-y-3">
        {[{f:'dni',p:'Ej: 20345678'},{f:'nombre',p:''},{f:'apellido',p:''},{f:'email',p:''}].map(({f,p}) => (
          <div key={f}><label className="text-sm text-slate-600 capitalize">{f} {['dni','nombre','apellido'].includes(f) ? '*' : ''}</label>
            <input className="w-full border rounded-lg px-3 py-2 mt-1" value={form[f]} onChange={e => setForm({...form, [f]: e.target.value})} placeholder={p} /></div>
        ))}
      </div>
      <div className="flex gap-2 mt-4">
        <button onClick={() => { if (!form.dni || !form.nombre || !form.apellido) { alert('DNI, Nombre y Apellido son obligatorios'); return; } onSave(form); }}
          className="flex-1 py-2 bg-amber-500 rounded-lg font-medium">Crear</button>
        <button onClick={onClose} className="flex-1 py-2 bg-slate-100 rounded-lg">Cancelar</button>
      </div>
    </div></div>
  );
}

function ModalEditarSedes({ docente, sedes, onSave, onClose }) {
  const [sel, setSel] = useState(docente.sedes?.map(s => s.id) || []);
  const toggle = id => setSel(sel.includes(id) ? sel.filter(x => x !== id) : [...sel, id]);
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"><div className="bg-white rounded-xl p-6 max-w-md w-full mx-4">
      <h3 className="text-lg font-bold mb-4">Sedes: {docente.nombre} {docente.apellido}</h3>
      <div className="space-y-2 mb-4">
        {sedes.filter(s => SEDES_OPERATIVAS.includes(s.nombre)).map(s => (
          <label key={s.id} className={`flex items-center gap-3 p-3 border rounded-lg cursor-pointer ${sel.includes(s.id) ? 'border-amber-500 bg-amber-50' : 'hover:bg-slate-50'}`}>
            <input type="checkbox" checked={sel.includes(s.id)} onChange={() => toggle(s.id)} />
            <span className={`w-3 h-3 rounded-full ${SEDE_COLORS[s.nombre]||'bg-gray-500'}`}></span><span>{s.nombre}</span>
          </label>
        ))}
      </div>
      <div className="flex gap-2">
        <button onClick={() => onSave(docente.id, sel)} className="flex-1 py-2 bg-amber-500 rounded-lg font-medium">Guardar</button>
        <button onClick={onClose} className="flex-1 py-2 bg-slate-100 rounded-lg">Cancelar</button>
      </div>
    </div></div>
  );
}

// ==================== CALENDARIO VIEW ====================
// ==================== v16.0: EDI POR CÁTEDRA ====================
function EdiAlumnosView({ cuatrimestre }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [abiertos, setAbiertos] = useState({});

  useEffect(() => {
    const cargar = async () => {
      setLoading(true);
      try {
        const cuatId = cuatrimestre !== 'todos' ? cuatrimestre : '';
        const qp = cuatId ? `?cuatrimestre_id=${cuatId}` : '';
        setData(await apiFetch(`/api/edi-inscripciones${qp}`));
      } catch (e) { console.error(e); }
      setLoading(false);
    };
    cargar();
  }, [cuatrimestre]);

  if (loading) return <div className="p-8 text-center">⏳ Cargando EDIs...</div>;

  const cats = data?.por_catedra ? Object.entries(data.por_catedra) : [];

  return (
    <div className="p-8">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-slate-800">🔀 Alumnos inscriptos a EDI por Cátedra</h2>
        <p className="text-slate-500 text-sm mt-1">Alumnos cuya inscripción dice "EDI" y fueron contabilizados dentro de la cátedra principal del archivo de inscripción.</p>
      </div>

      <div className="bg-violet-50 border border-violet-200 rounded-xl p-4 mb-6">
        <p className="text-violet-800 font-bold text-lg">{data?.total || 0} inscripciones EDI en {cats.length} cátedras</p>
        <p className="text-violet-600 text-sm mt-1">Estos alumnos eligieron un Espacio de Definición Institucional y se contabilizaron como inscriptos de la cátedra correspondiente.</p>
      </div>

      {cats.length === 0 ? (
        <div className="bg-slate-50 border rounded-xl p-8 text-center">
          <p className="text-4xl mb-2">📭</p>
          <p className="text-slate-500">No se encontraron inscripciones EDI. Se detectan al importar alumnos (archivos que contengan registros con "EDI" en la materia).</p>
        </div>
      ) : (
        <div className="space-y-3">
          {cats.map(([key, cat]) => {
            const isOpen = abiertos[key] !== false;
            return (
              <div key={key} className="bg-white rounded-xl border shadow-sm overflow-hidden">
                <div onClick={() => setAbiertos(p => ({...p, [key]: !isOpen}))}
                  className="flex items-center gap-3 p-4 cursor-pointer hover:bg-slate-50">
                  <span className="text-lg">{isOpen ? '▼' : '▶'}</span>
                  <span className="font-mono bg-violet-600 text-white px-2 py-0.5 rounded text-sm">{cat.codigo}</span>
                  <span className="font-bold flex-1">{cat.nombre}</span>
                  <span className="bg-violet-100 text-violet-700 px-3 py-1 rounded-full text-sm font-bold">{cat.total} EDI</span>
                </div>
                {isOpen && (
                  <table className="w-full text-sm border-t">
                    <thead><tr className="bg-violet-50 text-violet-800 text-xs">
                      <th className="p-2 text-left">Alumno</th>
                      <th className="p-2 text-left">DNI</th>
                      <th className="p-2 text-left">Materia EDI original</th>
                      <th className="p-2 text-left">Curso</th>
                      <th className="p-2 text-center">Sede</th>
                      <th className="p-2 text-center">Turno</th>
                    </tr></thead>
                    <tbody>
                      {cat.alumnos.map((a, i) => (
                        <tr key={i} className="border-b hover:bg-violet-50">
                          <td className="p-2 font-medium">{a.nombre}</td>
                          <td className="p-2 font-mono text-xs">{a.dni}</td>
                          <td className="p-2 text-violet-600 italic text-xs">{a.edi_materia || '—'}</td>
                          <td className="p-2 text-xs text-slate-500">{a.curso}</td>
                          <td className="p-2 text-center text-xs">{a.sede || '—'}</td>
                          <td className="p-2 text-center text-xs">{a.turno || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ==================== v16.0: CONTROL DE INSCRIPCIONES ====================
function ControlInscripcionesView({ cuatrimestre }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [filtro, setFiltro] = useState('todos');
  const [buscar, setBuscar] = useState('');

  const analizar = async () => {
    const input = document.createElement('input'); input.type = 'file'; input.accept = '.xlsx';
    input.onchange = async (ev) => {
      const file = ev.target.files?.[0]; if (!file) return;
      setLoading(true);
      try {
        const form = new FormData(); form.append('file', file);
        const cuatId = cuatrimestre !== 'todos' ? cuatrimestre : '0';
        const res = await fetch(`${API_URL}/api/control-inscripciones?cuatrimestre_id=${cuatId}`, { method: 'POST', body: form });
        const result = await res.json();
        if (result._debug) console.log('Control debug:', result._debug);
        setData(result);
      } catch (e) { alert('Error: ' + e.message); }
      setLoading(false);
    }; input.click();
  };

  const ESTADO_CFG = {
    'CORRECTO': { bg: 'bg-emerald-50', badge: 'bg-emerald-500', label: '✅ Correcto', icon: '✅' },
    'MATERIAS_EXTRA': { bg: 'bg-blue-50', badge: 'bg-blue-500', label: '➕ Materias extra', icon: '➕' },
    'FALTAN_MATERIAS': { bg: 'bg-amber-50', badge: 'bg-amber-500', label: '⚠️ Faltan materias', icon: '⚠️' },
    'FALTAN_Y_SOBRAN': { bg: 'bg-red-50', badge: 'bg-red-500', label: '❌ Faltan y sobran', icon: '❌' },
    'SIN_INSCRIPCIONES': { bg: 'bg-red-50', badge: 'bg-red-700', label: '🚫 Sin inscripciones', icon: '🚫' },
    'SIN_PLAN': { bg: 'bg-slate-50', badge: 'bg-slate-400', label: '— Sin plan', icon: '—' },
  };

  const filtered = (data?.results || []).filter(r => {
    if (filtro === 'ok') return r.estado === 'CORRECTO';
    if (filtro === 'faltan') return r.estado === 'FALTAN_MATERIAS' || r.estado === 'FALTAN_Y_SOBRAN';
    if (filtro === 'sobran') return r.estado === 'MATERIAS_EXTRA' || r.estado === 'FALTAN_Y_SOBRAN';
    if (filtro === 'sin_insc') return r.estado === 'SIN_INSCRIPCIONES';
    if (filtro === 'sin_plan') return r.estado === 'SIN_PLAN';
    if (filtro === 'problemas') return r.estado !== 'CORRECTO' && r.estado !== 'SIN_PLAN';
    return true;
  }).filter(r => !buscar || r.nombre.toLowerCase().includes(buscar.toLowerCase()) || r.dni.includes(buscar));

  const st = data?.stats || {};

  return (
    <div className="p-8">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-slate-800">✅ Control de Inscripciones a Materias</h2>
        <p className="text-slate-500 text-sm mt-1">Subí el Excel de control de alumnos. El sistema cruza: carrera + fecha de inicio → año de cursada → plan de carrera → cátedras que debe cursar → vs. cátedras realmente inscriptas.</p>
      </div>

      {!data ? (
        <div className="text-center py-16">
          <p className="text-6xl mb-4">📋</p>
          <p className="text-slate-600 text-lg mb-4">Subí el archivo "Control de alumnos inscriptos a materias" para analizar</p>
          <button onClick={analizar} disabled={loading} className="px-8 py-3 bg-blue-600 text-white rounded-xl font-bold text-lg hover:bg-blue-700 disabled:opacity-50">
            {loading ? '⏳ Analizando...' : '📤 Subir Excel de control'}
          </button>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-6 gap-3 mb-6">
            <div className="bg-slate-800 text-white rounded-xl p-3 text-center"><p className="text-2xl font-bold">{st.total||0}</p><p className="text-[10px] opacity-70">Total</p></div>
            <div className="bg-emerald-500 text-white rounded-xl p-3 text-center"><p className="text-2xl font-bold">{st.ok||0}</p><p className="text-[10px] opacity-80">✅ Correctos</p></div>
            <div className="bg-amber-500 text-white rounded-xl p-3 text-center"><p className="text-2xl font-bold">{st.faltan||0}</p><p className="text-[10px] opacity-80">⚠️ Faltan</p></div>
            <div className="bg-blue-500 text-white rounded-xl p-3 text-center"><p className="text-2xl font-bold">{st.sobran||0}</p><p className="text-[10px] opacity-80">➕ Extra</p></div>
            <div className="bg-red-600 text-white rounded-xl p-3 text-center"><p className="text-2xl font-bold">{st.sin_insc||0}</p><p className="text-[10px] opacity-80">🚫 Sin inscr.</p></div>
            <div className="bg-slate-400 text-white rounded-xl p-3 text-center"><p className="text-2xl font-bold">{st.sin_plan||0}</p><p className="text-[10px] opacity-80">— Sin plan</p></div>
          </div>

          <div className="flex gap-2 mb-4 flex-wrap items-center">
            {[['todos','Todos'],['problemas','⚠️ Con problemas'],['ok','✅ Correctos'],['faltan','Faltan materias'],['sobran','Materias extra'],['sin_insc','🚫 Sin inscripciones'],['sin_plan','Sin plan']].map(([k,l]) => (
              <button key={k} onClick={() => setFiltro(k)} className={`px-3 py-1.5 rounded-lg text-xs ${filtro === k ? 'bg-blue-600 text-white' : 'bg-slate-100'}`}>{l}</button>
            ))}
            <div className="flex-1" />
            <input type="text" placeholder="🔍 Buscar por nombre o DNI..." value={buscar} onChange={e => setBuscar(e.target.value)}
              className="px-3 py-1.5 border rounded-lg text-sm w-48" />
            <button onClick={analizar} className="px-3 py-1.5 bg-slate-200 rounded-lg text-xs hover:bg-slate-300">📤 Nuevo análisis</button>
            <button onClick={() => {
              if (!data?.results?.length) return alert('No hay datos para exportar');
              const rows = [['Alumno','DNI','Sede','Carrera','Año','Estado','Debe cursar','Inscripto a','Faltantes','Sobrantes']];
              for (const r of (data.results || [])) {
                rows.push([r.nombre, r.dni, r.sede||'', r.curso||'', r.anno, r.estado,
                  (r.debe_cursar||[]).join('; '), (r.inscripto_a||[]).join('; '),
                  (r.faltantes||[]).join('; '), (r.sobrantes||[]).join('; ')]);
              }
              const csv = rows.map(r => r.map(c => '"' + String(c||'').replace(/"/g,'""') + '"').join(',')).join('\n');
              const blob = new Blob(['\uFEFF' + csv], {type:'text/csv;charset=utf-8'});
              const url = URL.createObjectURL(blob); const a = document.createElement('a');
              a.href = url; a.download = 'control_inscripciones.csv'; a.click(); URL.revokeObjectURL(url);
            }} className="px-3 py-1.5 bg-emerald-600 text-white rounded-lg text-xs hover:bg-emerald-700">📥 Exportar CSV</button>
          </div>

          <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
            <table className="w-full text-[11px]">
              <thead><tr className="bg-slate-800 text-white">
                <th className="p-2 text-left">Alumno</th>
                <th className="p-2 text-left">DNI</th>
                <th className="p-2 text-left">Carrera</th>
                <th className="p-2 text-center">Año</th>
                <th className="p-2 text-center">Estado</th>
                <th className="p-2 text-left">Debe cursar</th>
                <th className="p-2 text-left">Inscripto a</th>
                <th className="p-2 text-left">Faltantes</th>
                <th className="p-2 text-left">Sobrantes</th>
              </tr></thead>
              <tbody>
                {filtered.map((r, i) => {
                  const cfg = ESTADO_CFG[r.estado] || ESTADO_CFG['SIN_PLAN'];
                  return (
                    <tr key={i} className={`border-b ${cfg.bg} hover:bg-slate-100`}>
                      <td className="p-2 font-medium">{r.nombre}</td>
                      <td className="p-2 font-mono text-[10px]">{r.dni}</td>
                      <td className="p-2 text-[10px]">{r.curso}{r.is_doble && <span className="ml-1 bg-violet-100 text-violet-700 px-1 rounded text-[8px]">DOBLE</span>}</td>
                      <td className="p-2 text-center font-bold">{r.anno}</td>
                      <td className="p-2 text-center"><span className={`px-1.5 py-0.5 rounded text-white text-[9px] font-bold ${cfg.badge}`}>{cfg.label}</span></td>
                      <td className="p-2 text-[9px]">
                        {r.debe_cursar?.map((c,j) => <div key={j} className="text-slate-600">{c}</div>)}
                      </td>
                      <td className="p-2 text-[9px]">
                        {r.inscripto_a?.map((c,j) => <div key={j} className="text-slate-600">{c}</div>)}
                      </td>
                      <td className="p-2 text-[9px]">
                        {r.faltantes?.map((c,j) => <div key={j} className="text-red-600 font-medium">{c}</div>)}
                      </td>
                      <td className="p-2 text-[9px]">
                        {r.sobrantes?.map((c,j) => <div key={j} className="text-blue-600">{c}</div>)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="text-sm text-slate-500 mt-3 text-center">{filtered.length} alumnos{data.total_results !== filtered.length ? ` (de ${data.total_results} totales)` : ''}</p>
          {data._debug && st.total === 0 && (
            <div className="mt-4 bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm">
              <p className="font-bold text-amber-800">⚠️ No se procesaron alumnos. Verificá:</p>
              <p className="text-amber-700 mt-1">Plan de carreras cargado: {data._debug.plan_carreras} carreras</p>
              <p className="text-amber-700">Inscripciones en el sistema: {data._debug.inscripciones_db} (DNIs únicos: {data._debug.dnis_con_inscripciones})</p>
              <p className="text-amber-700">Cuatrimestre ID: {data._debug.cuatrimestre_id || 'Todos'}</p>
              {data._debug.inscripciones_db === 0 && <p className="text-red-600 mt-2 font-bold">→ No hay inscripciones cargadas. Importá primero los archivos de alumnos inscriptos.</p>}
              {data._debug.plan_carreras === 0 && <p className="text-red-600 mt-2 font-bold">→ No hay plan de carreras. Importá primero el molde Horarios.xlsx.</p>}
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ==================== v16.0: SUGERENCIAS DE ARMADO DE HORARIOS ====================
function SugerenciasArmadoView({ cuatrimestre }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sedeActiva, setSedeActiva] = useState('');
  const [carreraAbierta, setCarreraAbierta] = useState({});

  useEffect(() => {
    const cargar = async () => {
      setLoading(true);
      try {
        const cuatId = cuatrimestre !== 'todos' ? cuatrimestre : '';
        const qp = cuatId ? `?cuatrimestre_id=${cuatId}` : '';
        setData(await apiFetch(`/api/sugerencias-armado${qp}`));
      } catch (e) { console.error(e); }
      setLoading(false);
    };
    cargar();
  }, [cuatrimestre]);

  useEffect(() => {
    if (data?.sedes) {
      const keys = Object.keys(data.sedes);
      if (keys.length > 0 && !sedeActiva) setSedeActiva(keys[0]);
    }
  }, [data]);

  if (loading) return <div className="p-8 text-center">⏳ Analizando cátedras, docentes y disponibilidad...</div>;

  const sedes = data?.sedes || {};
  const sedeKeys = Object.keys(sedes);
  const st = data?.stats || {};

  const ESTADO_CONFIG = {
    asignado: { bg: 'bg-emerald-50', border: 'border-emerald-200', badge: 'bg-emerald-500', label: '✅ Con docente' },
    sugerido: { bg: 'bg-blue-50', border: 'border-blue-200', badge: 'bg-blue-500', label: '🤖 Sugerido' },
    sin_sugerencia: { bg: 'bg-red-50', border: 'border-red-200', badge: 'bg-red-500', label: '❌ Sin sugerencia' },
    asincronica: { bg: 'bg-purple-50', border: 'border-purple-200', badge: 'bg-purple-500', label: '🎥 Asincrónica' },
    sin_alumnos: { bg: 'bg-slate-50', border: '', badge: 'bg-slate-300', label: '—' },
  };

  return (
    <div className="p-8">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-slate-800">🤖 Sugerencia de Horarios por Carrera</h2>
        <p className="text-slate-500 text-sm">Pre-armado automático cruzando cátedras abiertas, disponibilidad docente y cátedras de referencia.</p>
      </div>

      <div className="grid grid-cols-5 gap-3 mb-6">
        <div className="bg-slate-800 text-white rounded-xl p-4 text-center"><p className="text-3xl font-bold">{st.total||0}</p><p className="text-xs opacity-70">Total cátedras</p></div>
        <div className="bg-emerald-500 text-white rounded-xl p-4 text-center"><p className="text-3xl font-bold">{st.con_docente||0}</p><p className="text-xs opacity-80">✅ Con docente</p></div>
        <div className="bg-blue-500 text-white rounded-xl p-4 text-center"><p className="text-3xl font-bold">{st.sugerido||0}</p><p className="text-xs opacity-80">🤖 Sugerido</p></div>
        <div className="bg-red-500 text-white rounded-xl p-4 text-center"><p className="text-3xl font-bold">{st.sin_sugerencia||0}</p><p className="text-xs opacity-80">❌ Sin sugerencia</p></div>
        <div className="bg-purple-500 text-white rounded-xl p-4 text-center"><p className="text-3xl font-bold">{st.asincronica||0}</p><p className="text-xs opacity-80">🎥 Asincrónicas</p></div>
      </div>

      <div className="flex gap-2 mb-6 flex-wrap">
        {sedeKeys.map(s => (
          <button key={s} onClick={() => setSedeActiva(s)} className={`px-4 py-2 rounded-lg text-sm font-medium ${sedeActiva === s ? 'bg-slate-800 text-white' : 'bg-slate-100'}`}>{s}</button>
        ))}
      </div>

      {sedeActiva && sedes[sedeActiva] ? Object.entries(sedes[sedeActiva]).map(([carrera, annos]) => {
        const key = `${sedeActiva}-${carrera}`;
        const abierta = carreraAbierta[key] !== false;
        const allCats = Object.values(annos).flat();
        const conDoc = allCats.filter(c => c.estado === 'asignado').length;
        const sugeridos = allCats.filter(c => c.estado === 'sugerido').length;
        const sinSug = allCats.filter(c => c.estado === 'sin_sugerencia').length;
        return (
          <div key={key} className="mb-3">
            <div onClick={() => setCarreraAbierta(prev => ({...prev, [key]: !prev[key]}))} className="flex items-center gap-3 p-3 bg-slate-800 text-white rounded-t-xl cursor-pointer hover:bg-slate-700">
              <span className="text-lg">{abierta ? '▼' : '▶'}</span>
              <span className="font-bold flex-1">{carrera}</span>
              <span className="text-xs bg-slate-600 px-2 py-1 rounded">{allCats.length} cát.</span>
              {conDoc > 0 && <span className="text-xs bg-emerald-500 px-2 py-1 rounded">{conDoc} ✅</span>}
              {sugeridos > 0 && <span className="text-xs bg-blue-500 px-2 py-1 rounded">{sugeridos} 🤖</span>}
              {sinSug > 0 && <span className="text-xs bg-red-500 px-2 py-1 rounded">{sinSug} ❌</span>}
            </div>
            {abierta && (
              <div className="bg-white border border-t-0 rounded-b-xl overflow-hidden">
                <table className="w-full text-xs">
                  <thead><tr className="bg-slate-100 text-slate-600">
                    <th className="p-2 text-left">Año</th>
                    <th className="p-2 text-left">Cátedra</th>
                    <th className="p-2 text-center w-14">Inscr.</th>
                    <th className="p-2 text-center w-20">Criterio</th>
                    <th className="p-2 text-center">Estado</th>
                    <th className="p-2 text-left">Docente actual</th>
                    <th className="p-2 text-left">Sugerencia docente</th>
                    <th className="p-2 text-left">Horarios</th>
                  </tr></thead>
                  <tbody>
                    {Object.entries(annos).map(([anno, cats]) => cats.map((cat, idx) => {
                      const cfg = ESTADO_CONFIG[cat.estado] || ESTADO_CONFIG.sin_alumnos;
                      return (
                        <tr key={`${anno}-${cat.codigo}-${idx}`} className={`border-b ${cfg.bg}`}>
                          <td className="p-2 text-slate-500">{idx === 0 ? anno : ''}</td>
                          <td className="p-2">
                            <span className="font-mono bg-slate-800 text-white px-1 rounded text-[9px] mr-1">{cat.codigo}</span>
                            {cat.nombre?.substring(0, 30)}
                          </td>
                          <td className="p-2 text-center font-bold text-cyan-600">{cat.inscriptos || ''}</td>
                          <td className="p-2 text-center">
                            <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${cat.criterio === 'ABRIR' ? 'bg-emerald-100 text-emerald-700' : cat.criterio === 'ASINCRÓNICA' ? 'bg-purple-100 text-purple-700' : 'bg-slate-100 text-slate-400'}`}>{cat.criterio}</span>
                          </td>
                          <td className="p-2 text-center">
                            <span className={`px-1.5 py-0.5 rounded text-white text-[9px] font-bold ${cfg.badge}`}>{cfg.label}</span>
                          </td>
                          <td className="p-2">
                            {cat.docente_actual ? <span className="text-emerald-700 font-medium">{cat.docente_actual}</span> : ''}
                          </td>
                          <td className="p-2">
                            {cat.sugerencia_docente ? <span className="text-blue-600 font-medium italic">{cat.sugerencia_docente}</span> : cat.estado === 'sin_sugerencia' ? <span className="text-red-400">Sin docente disponible</span> : ''}
                          </td>
                          <td className="p-2 text-[10px] text-slate-500">
                            {cat.horarios?.map((h, i) => <span key={i} className="bg-slate-100 px-1 rounded mr-1">{h}</span>)}
                          </td>
                        </tr>
                      );
                    }))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        );
      }) : <p className="text-slate-400 text-center p-8">Seleccioná una sede</p>}
    </div>
  );
}

// ==================== v15.0: DOCENTES POR DÍA Y TURNO ====================
function DocentesDiaView({ catedras }) {
  const allAsig = useMemo(() => catedras.flatMap(c => (c.asignaciones || []).filter(a => a.dia && a.dia !== 'Pend.' && a.hora_inicio && a.hora_inicio !== 'Pend.').map(a => ({
    ...a, cat_codigo: c.codigo, cat_nombre: c.nombre
  }))), [catedras]);

  const DIAS_ORD = ['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado'];
  
  const agrupado = useMemo(() => {
    const result = {};
    for (const dia of DIAS_ORD) {
      const del_dia = allAsig.filter(a => a.dia === dia);
      const tm = del_dia.filter(a => a.hora_inicio < '15:00').sort((a,b) => a.hora_inicio.localeCompare(b.hora_inicio));
      const tn = del_dia.filter(a => a.hora_inicio >= '15:00').sort((a,b) => a.hora_inicio.localeCompare(b.hora_inicio));
      result[dia] = { tm, tn };
    }
    return result;
  }, [allAsig]);

  const renderTabla = (asigs, turnoLabel) => {
    if (asigs.length === 0) return <p className="text-slate-300 text-sm p-3 text-center">Sin asignaciones</p>;
    return (
      <table className="w-full text-xs">
        <thead><tr className="bg-slate-100">
          <th className="p-2 text-left w-16">Hora</th>
          <th className="p-2 text-left">Cátedra</th>
          <th className="p-2 text-left">Docente</th>
          <th className="p-2 text-left">Sede</th>
        </tr></thead>
        <tbody>
          {asigs.map((a, i) => (
            <tr key={i} className={`border-b ${!a.docente ? 'bg-yellow-50' : ''}`}>
              <td className="p-2 font-bold">{a.hora_inicio}</td>
              <td className="p-2"><span className="font-mono bg-slate-800 text-white px-1 rounded text-[9px] mr-1">{a.cat_codigo}</span>{a.cat_nombre}</td>
              <td className="p-2">{a.docente ? <span className="text-emerald-600 font-medium">{a.docente.nombre} {a.docente.apellido}</span> : <span className="text-red-400 italic">Pendiente</span>}</td>
              <td className="p-2">{a.sede_nombre || 'Remoto'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  };

  return (
    <div className="p-8">
      <h2 className="text-2xl font-bold text-slate-800 mb-2">📋 Docentes por Día y Turno</h2>
      <p className="text-slate-500 text-sm mb-6">Listado de todas las cátedras y docentes ordenados por día, empezando por TM y luego TN.</p>
      <div className="space-y-6">
        {DIAS_ORD.map(dia => {
          const { tm, tn } = agrupado[dia] || { tm: [], tn: [] };
          if (tm.length === 0 && tn.length === 0) return null;
          return (
            <div key={dia}>
              <h3 className="text-lg font-bold text-slate-700 mb-2">{dia.toUpperCase()}</h3>
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-white rounded-xl border overflow-hidden">
                  <div className="bg-yellow-500 text-white text-center py-2 font-bold text-sm">☀️ TURNO MAÑANA ({tm.length})</div>
                  {renderTabla(tm, 'TM')}
                </div>
                <div className="bg-white rounded-xl border overflow-hidden">
                  <div className="bg-indigo-600 text-white text-center py-2 font-bold text-sm">🌙 TURNO NOCHE ({tn.length})</div>
                  {renderTabla(tn, 'TN')}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ==================== CALENDARIO ====================
function CalendarioView({ catedras, docentes, sedes, cuatrimestre }) {
  const [filtroSede, setFiltroSede] = useState('');
  const [filtroDocente, setFiltroDocente] = useState('');
  const [filtroCatedra, setFiltroCatedra] = useState('');
  const [filtroDia, setFiltroDia] = useState('');
  const [buscarDocente, setBuscarDocente] = useState('');
  const [buscarCatedra, setBuscarCatedra] = useState('');
  const [mostrarSugDoc, setMostrarSugDoc] = useState(false);
  const [mostrarSugCat, setMostrarSugCat] = useState(false);

  const allAsig = useMemo(() => catedras.flatMap(c => (c.asignaciones || []).map(a => ({ ...a, cat_codigo: c.codigo, cat_nombre: c.nombre, cat_inscriptos: c.inscriptos || 0 }))), [catedras]);

  // v4.0 MEJORA 5: Ordenar por código
  const asigOrdenadas = useMemo(() => {
    return [...allAsig].sort((a, b) => {
      const na = parseInt((a.cat_codigo || '').replace(/[^0-9]/g, '')) || 9999;
      const nb = parseInt((b.cat_codigo || '').replace(/[^0-9]/g, '')) || 9999;
      return na - nb;
    });
  }, [allAsig]);

  const asigFiltradas = useMemo(() => {
    return asigOrdenadas.filter(a => a.dia && a.hora_inicio).filter(a => {
      if (filtroDia && a.dia !== filtroDia) return false;
      if (filtroSede === 'remoto') return !a.sede_id;
      if (filtroSede) return a.sede_id === parseInt(filtroSede);
      return true;
    }).filter(a => {
      if (filtroDocente) return a.docente?.id === parseInt(filtroDocente);
      if (buscarDocente && !filtroDocente) {
        const b = buscarDocente.toLowerCase();
        if (!a.docente) return false;
        return (a.docente.nombre || '').toLowerCase().includes(b);
      }
      return true;
    }).filter(a => {
      if (filtroCatedra) return a.cat_codigo === filtroCatedra;
      if (buscarCatedra && !filtroCatedra) {
        const b = buscarCatedra.toLowerCase();
        return a.cat_codigo.toLowerCase().includes(b) || a.cat_nombre.toLowerCase().includes(b);
      }
      return true;
    });
  }, [asigOrdenadas, filtroSede, filtroDocente, filtroCatedra, buscarDocente, buscarCatedra]);

  const docentesSugeridos = useMemo(() => {
    if (!buscarDocente || filtroDocente) return [];
    const b = buscarDocente.toLowerCase();
    return docentes.filter(d => d.nombre.toLowerCase().includes(b) || d.apellido.toLowerCase().includes(b)).slice(0, 8);
  }, [docentes, buscarDocente, filtroDocente]);

  const catedrasSugeridas = useMemo(() => {
    if (!buscarCatedra || filtroCatedra) return [];
    const b = buscarCatedra.toLowerCase();
    return catedras.filter(c => c.codigo.toLowerCase().includes(b) || c.nombre.toLowerCase().includes(b)).slice(0, 8);
  }, [catedras, buscarCatedra, filtroCatedra]);

  return (
    <div className="p-8">
      <div className="mb-6"><h2 className="text-2xl font-bold text-slate-800">Calendario</h2></div>
      <div className="bg-white rounded-xl border p-4 mb-6 grid grid-cols-4 gap-4">
        <div>
          <label className="text-sm text-slate-600 font-medium">Día:</label>
          <select className="w-full border rounded-lg px-3 py-2 mt-1" value={filtroDia} onChange={e => setFiltroDia(e.target.value)}>
            <option value="">Todos los días</option>
            {DIAS.map(d => <option key={d} value={d}>{d}</option>)}
          </select>
        </div>
        <div>
          <label className="text-sm text-slate-600 font-medium">Sede:</label>
          <select className="w-full border rounded-lg px-3 py-2 mt-1" value={filtroSede} onChange={e => setFiltroSede(e.target.value)}>
            <option value="">Todas</option>
            {sedes.filter(s => SEDES_OPERATIVAS.includes(s.nombre)).map(s => <option key={s.id} value={s.id}>{s.nombre}</option>)}
            <option value="remoto">🏠 Solo Remotos</option>
          </select>
        </div>
        <div className="relative">
          <label className="text-sm text-slate-600 font-medium">Docente:</label>
          <input type="text" placeholder="Buscar por nombre..." className="w-full border rounded-lg px-3 py-2 mt-1 text-sm"
            value={buscarDocente} onChange={e => { setBuscarDocente(e.target.value); setFiltroDocente(''); setMostrarSugDoc(true); }}
            onFocus={() => setMostrarSugDoc(true)} onBlur={() => setTimeout(() => setMostrarSugDoc(false), 150)} />
          {filtroDocente && <button onClick={() => { setBuscarDocente(''); setFiltroDocente(''); }} className="absolute right-2 top-9 text-slate-400 hover:text-red-500 text-lg">×</button>}
          {mostrarSugDoc && docentesSugeridos.length > 0 && (
            <div className="absolute z-20 w-full border rounded-lg bg-white shadow-lg mt-1 max-h-48 overflow-y-auto">
              <div className="p-2 text-xs text-slate-400 border-b cursor-pointer hover:bg-slate-50"
                onMouseDown={() => { setBuscarDocente(''); setFiltroDocente(''); setMostrarSugDoc(false); }}>Ver todos</div>
              {docentesSugeridos.map(d => (
                <div key={d.id} className="p-2 text-sm cursor-pointer hover:bg-amber-50"
                  onMouseDown={() => { setFiltroDocente(d.id.toString()); setBuscarDocente(`${d.nombre} ${d.apellido}`); setMostrarSugDoc(false); }}>
                  {d.nombre} {d.apellido}
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="relative">
          <label className="text-sm text-slate-600 font-medium">Cátedra:</label>
          <input type="text" placeholder="Buscar por código o nombre..." className="w-full border rounded-lg px-3 py-2 mt-1 text-sm"
            value={buscarCatedra} onChange={e => { setBuscarCatedra(e.target.value); setFiltroCatedra(''); setMostrarSugCat(true); }}
            onFocus={() => setMostrarSugCat(true)} onBlur={() => setTimeout(() => setMostrarSugCat(false), 150)} />
          {filtroCatedra && <button onClick={() => { setBuscarCatedra(''); setFiltroCatedra(''); }} className="absolute right-2 top-9 text-slate-400 hover:text-red-500 text-lg">×</button>}
          {mostrarSugCat && catedrasSugeridas.length > 0 && (
            <div className="absolute z-20 w-full border rounded-lg bg-white shadow-lg mt-1 max-h-48 overflow-y-auto">
              <div className="p-2 text-xs text-slate-400 border-b cursor-pointer hover:bg-slate-50"
                onMouseDown={() => { setBuscarCatedra(''); setFiltroCatedra(''); setMostrarSugCat(false); }}>Ver todas</div>
              {catedrasSugeridas.map(c => (
                <div key={c.id} className="p-2 text-sm cursor-pointer hover:bg-amber-50"
                  onMouseDown={() => { setFiltroCatedra(c.codigo); setBuscarCatedra(`${c.codigo} - ${c.nombre}`); setMostrarSugCat(false); }}>
                  <span className="font-mono text-xs bg-slate-800 text-white px-1 rounded mr-1">{c.codigo}</span>{c.nombre}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
      {/* Grilla */}
      {(() => { const diasMostrar = filtroDia ? [filtroDia] : DIAS; return (
      <div className="bg-white rounded-xl border shadow-sm overflow-auto mb-6">
        <table className="w-full text-sm">
          <thead><tr className="bg-slate-50 border-b">
            <th className="p-2 border-r w-20">Hora</th>
            {diasMostrar.map(d => <th key={d} className="p-2 border-r min-w-[130px]">{d}</th>)}
          </tr></thead>
          <tbody>
            {HORAS.map(hora => (
              <tr key={hora} className="border-b">
                <td className="p-2 border-r bg-slate-50 font-medium text-center">{hora}</td>
                {diasMostrar.map(dia => {
                  const celdas = asigFiltradas.filter(a => a.dia === dia && a.hora_inicio === hora);
                  return (
                    <td key={dia} className="p-1 border-r align-top">
                      {celdas.map(a => {
                        const sinDocente = !a.docente;
                        // v4.0 MEJORA 10: Color por sede
                        const sedeNombre = a.sede_nombre || '';
                        let bgClass = 'bg-gray-50 border-gray-200';
                        if (sinDocente) { bgClass = 'bg-orange-50 border-orange-300'; }
                        else if (sedeNombre.includes('Caballito')) { bgClass = 'bg-emerald-50 border-emerald-300'; }
                        else if (sedeNombre.includes('Vicente')) { bgClass = 'bg-amber-50 border-amber-300'; }
                        else if (sedeNombre.includes('Avellaneda')) { bgClass = 'bg-blue-50 border-blue-300'; }
                        else if (sedeNombre.includes('Online')) { bgClass = 'bg-purple-50 border-purple-300'; }
                        return (
                          <div key={a.id} className={`p-1 mb-1 rounded text-xs border ${bgClass}`}>
                            <p className="font-bold text-slate-800">{a.cat_codigo}</p>
                            <p className={sinDocente ? 'text-orange-500 italic' : 'text-slate-600'}>{sinDocente ? '⚠️ Sin docente' : a.docente?.nombre}</p>
                            <p className="text-slate-400">{sedeNombre || '🏠'}</p>
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
      ); })()}
      {/* Lista ordenada por código */}
      <div className="bg-white rounded-xl border shadow-sm p-4">
        <h3 className="font-semibold mb-3">📋 Lista ({asigFiltradas.length} asignaciones) — ordenadas por código</h3>
        <div className="overflow-auto max-h-80">
          <table className="w-full text-sm">
            <thead className="bg-slate-50"><tr>
              <th className="p-2 text-left">Cátedra</th><th className="p-2 text-left">Docente</th>
              <th className="p-2">Modalidad</th><th className="p-2">Día</th><th className="p-2">Hora</th><th className="p-2">Sede</th><th className="p-2">Inscriptos</th>
            </tr></thead>
            <tbody>
              {asigFiltradas.map(a => {
                const mod = MODALIDAD_CONFIG[a.modalidad] || {};
                return (
                  <tr key={a.id} className="border-b">
                    <td className="p-2"><span className="font-mono">{a.cat_codigo}</span> {a.cat_nombre}</td>
                    <td className="p-2">{a.docente ? a.docente.nombre : <span className="text-orange-500 italic">⚠️ Sin docente</span>}</td>
                    <td className="p-2 text-center"><span className={mod.color}>{mod.icon}</span></td>
                    <td className="p-2 text-center">{a.dia}</td>
                    <td className="p-2 text-center">{a.hora_inicio}</td>
                    <td className="p-2 text-center">{a.sede_nombre ? <span className={`px-2 py-0.5 rounded text-white text-xs ${SEDE_COLORS[a.sede_nombre]||'bg-gray-500'}`}>{a.sede_nombre}</span> : '🏠'}</td>
                    <td className="p-2 text-center font-bold text-cyan-600">{a.cat_inscriptos || 0}</td>
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

// ==================== v13.0: HORARIOS POR CARRERA Y SEDE ====================
function PlanCarreraView({ cuatrimestre }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sedeActiva, setSedeActiva] = useState('');
  const [carreraAbierta, setCarreraAbierta] = useState({});
  const [importando, setImportando] = useState(false);

  const cargar = async (sedeOverride) => {
    setLoading(true);
    try {
      const cuatId = cuatrimestre !== 'todos' ? cuatrimestre : '';
      const qp = cuatId ? `?cuatrimestre_id=${cuatId}` : '';
      const sede = sedeOverride || sedeActiva;
      const sedeP = sede ? `${qp ? '&' : '?'}sede=${encodeURIComponent(sede)}` : '';
      setData(await apiFetch(`/api/plan-carrera/sugerencias${qp}${sedeP}`));
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  // ALL hooks BEFORE any conditional return
  useEffect(() => { cargar(); }, [cuatrimestre]);
  
  // Set default sede when data arrives
  useEffect(() => {
    if (data?.sedes) {
      const keys = Object.keys(data.sedes);
      if (keys.length > 0 && !sedeActiva) {
        setSedeActiva(keys[0]);
      }
    }
  }, [data]);

  const importarPlan = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImportando(true);
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await fetch(`${API_URL}/api/importar/plan-carrera`, { method: 'POST', body: form });
      const r = await res.json();
      alert(`✅ ${r.importados} registros importados`);
      cargar();
    } catch (e) { alert('Error: ' + e.message); }
    setImportando(false);
    e.target.value = '';
  };

  const toggleCarrera = (key) => {
    setCarreraAbierta(prev => ({...prev, [key]: !prev[key]}));
  };

  const cambiarSede = (s) => {
    setSedeActiva(s);
    cargar(s);
  };

  // Conditional return AFTER all hooks
  if (loading) return <div className="p-8 text-center">⏳ Cargando...</div>;

  const sedes = data?.sedes || {};
  const sedeKeys = Object.keys(sedes);

  return (
    <div className="p-8">
      <div className="flex justify-between items-start mb-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-800">🗺️ Horarios por Carrera y Sede</h2>
          <p className="text-slate-500 text-sm">Sugerencia automática basada en el molde de horarios importado, cruzado con inscriptos actuales.</p>
        </div>
        <label className={`px-4 py-2 rounded-lg text-sm font-medium cursor-pointer ${importando ? 'bg-slate-300' : 'bg-blue-600 text-white hover:bg-blue-700'}`}>
          {importando ? '⏳ Importando...' : '📥 Importar molde (Horarios.xlsx)'}
          <input type="file" accept=".xlsx" className="hidden" onChange={importarPlan} disabled={importando} />
        </label>
      </div>

      {!data?.plan_importado ? (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-8 text-center">
          <p className="text-4xl mb-3">📥</p>
          <p className="text-amber-800 font-medium">No hay molde de horarios importado</p>
          <p className="text-amber-600 text-sm mt-2">Subí el archivo Horarios.xlsx con la estructura de carreras, años y cátedras por sede. El sistema lo cruza con los inscriptos para generar sugerencias.</p>
        </div>
      ) : (
        <>
          <div className="flex gap-2 mb-6 flex-wrap">
            {sedeKeys.map(s => (
              <button key={s} onClick={() => cambiarSede(s)} className={`px-4 py-2 rounded-lg text-sm font-medium ${sedeActiva === s ? 'bg-slate-800 text-white' : 'bg-slate-100'}`}>{s}</button>
            ))}
          </div>

          {sedeActiva && sedes[sedeActiva] ? Object.entries(sedes[sedeActiva]).map(([carrera, annos]) => {
                const key = `${sedeActiva}-${carrera}`;
                const abierta = carreraAbierta[key] !== false;
                const totalCats = Object.values(annos).flat().length;
                const abrir = Object.values(annos).flat().filter(c => c.criterio === 'ABRIR').length;
                const asinc = Object.values(annos).flat().filter(c => c.criterio === 'ASINCRÓNICA').length;
                const conDoc = Object.values(annos).flat().filter(c => c.tiene_docente).length;
                return (
                  <div key={key} className="mb-3">
                    <div onClick={() => toggleCarrera(key)} className="flex items-center gap-3 p-3 bg-blue-900 text-white rounded-t-xl cursor-pointer hover:bg-blue-800">
                      <span className="text-lg">{abierta ? '▼' : '▶'}</span>
                      <span className="font-bold flex-1">{carrera}</span>
                      <span className="text-xs bg-blue-700 px-2 py-1 rounded">{totalCats} cát.</span>
                      <span className="text-xs bg-emerald-600 px-2 py-1 rounded">{conDoc} con doc.</span>
                      {abrir - conDoc > 0 && <span className="text-xs bg-red-500 px-2 py-1 rounded">{abrir - conDoc} faltan</span>}
                      {asinc > 0 && <span className="text-xs bg-purple-500 px-2 py-1 rounded">{asinc} asinc.</span>}
                    </div>
                    {abierta && (
                      <div className="bg-white border border-t-0 rounded-b-xl overflow-hidden">
                        <table className="w-full text-xs">
                          <thead><tr className="bg-slate-100 text-slate-600">
                            <th className="p-2 text-left">Año</th>
                            <th className="p-2 text-left">Cátedra</th>
                            <th className="p-2 text-center w-14">Inscr.</th>
                            <th className="p-2 text-center w-20">Criterio</th>
                            <th className="p-2 text-center">Sugerencia TM</th>
                            <th className="p-2 text-center">Sugerencia TN</th>
                            <th className="p-2 text-center">Actual TM</th>
                            <th className="p-2 text-center">Actual TN</th>
                            <th className="p-2 text-left">Docente</th>
                          </tr></thead>
                          <tbody>
                            {Object.entries(annos).map(([anno, cats]) => cats.map((cat, idx) => (
                              <tr key={`${anno}-${cat.codigo}-${idx}`} className={`border-b ${cat.criterio === 'ASINCRÓNICA' ? 'bg-purple-50' : cat.criterio === 'SIN ALUMNOS' ? 'bg-slate-50 text-slate-400' : !cat.tiene_docente && cat.criterio === 'ABRIR' ? 'bg-yellow-50' : ''}`}>
                                <td className="p-2 text-slate-500">{idx === 0 ? anno : ''}</td>
                                <td className="p-2">
                                  <span className="font-mono bg-slate-800 text-white px-1 rounded text-[9px] mr-1">{cat.codigo}</span>
                                  {cat.nombre}
                                </td>
                                <td className="p-2 text-center font-bold text-cyan-600">{cat.inscriptos || ''}</td>
                                <td className="p-2 text-center">
                                  <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${cat.criterio === 'ABRIR' ? 'bg-emerald-100 text-emerald-700' : cat.criterio === 'ASINCRÓNICA' ? 'bg-purple-100 text-purple-700' : 'bg-slate-100 text-slate-400'}`}>{cat.criterio}</span>
                                </td>
                                <td className="p-2 text-center text-blue-600">{cat.sugerencia_tm || ''}</td>
                                <td className="p-2 text-center text-indigo-600">{cat.sugerencia_tn || ''}</td>
                                <td className="p-2 text-center">{cat.actual_tm ? <span className="bg-emerald-100 text-emerald-700 px-1 rounded text-[9px]">{cat.actual_tm}</span> : ''}</td>
                                <td className="p-2 text-center">{cat.actual_tn ? <span className="bg-indigo-100 text-indigo-700 px-1 rounded text-[9px]">{cat.actual_tn}</span> : ''}</td>
                                <td className="p-2">{cat.docente ? <span className="text-emerald-600 font-medium">{cat.docente}</span> : cat.criterio === 'ABRIR' ? <span className="text-red-400 italic">Pendiente</span> : <span className="text-purple-400">🎥</span>}</td>
                              </tr>
                            )))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                );
              }) : <p className="text-slate-400 text-center p-8">Seleccioná una sede</p>}
        </>
      )}
    </div>
  );
}

// ==================== SOLAPAMIENTOS ====================
function SolapamientosView({ solapamientos, cuatrimestre, tab: initialTab = 'horarios' }) {
  const [tab, setTab] = useState(initialTab);
  const [carreraConf, setCarreraConf] = useState(null);
  const [loadingCarr, setLoadingCarr] = useState(false);

  useEffect(() => {
    const cargar = async () => {
      setLoadingCarr(true);
      try {
        const cuatId = cuatrimestre !== 'todos' ? cuatrimestre : '';
        const qp = cuatId ? `?cuatrimestre_id=${cuatId}` : '';
        setCarreraConf(await apiFetch(`/api/solapamientos-carreras${qp}`));
      } catch (e) { console.error(e); }
      setLoadingCarr(false);
    };
    cargar();
  }, [cuatrimestre]);

  const totalCarr = carreraConf?.total || 0;

  const renderConflictTable = (items, color, showSede = true) => {
    if (!items?.length) return <div className="bg-green-50 border border-green-200 rounded-xl p-6 text-center"><p className="text-2xl mb-1">✅</p><p className="text-green-700 font-medium">Sin conflictos</p></div>;
    return (
      <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead><tr className={`${color} text-white text-xs`}>
            <th className="p-3 text-left">Carrera</th><th className="p-3 text-left">Año</th>
            {showSede && <th className="p-3 text-left">Sede</th>}
            <th className="p-3 text-center">Día</th><th className="p-3 text-center">Hora</th>
            <th className="p-3 text-left">Cátedras en conflicto</th>
          </tr></thead>
          <tbody>{items.map((conf, i) => (
            <tr key={i} className="border-b bg-yellow-50 hover:bg-yellow-100">
              <td className="p-3 font-medium text-xs">{conf.carrera}</td>
              <td className="p-3 text-xs">{conf.anno}</td>
              {showSede && <td className="p-3 text-xs">{conf.sede_plan}</td>}
              <td className="p-3 text-center font-bold">{conf.dia}</td>
              <td className="p-3 text-center font-bold">{conf.hora}</td>
              <td className="p-3"><div className="flex flex-wrap gap-1">
                {conf.catedras_en_conflicto.map((c, j) => (
                  <span key={j} className="px-2 py-1 bg-red-100 border border-red-300 rounded text-xs">
                    <span className="font-mono font-bold">{c.codigo}</span> {c.nombre?.substring(0, 25)}
                    {c.docente && <span className="text-emerald-600 ml-1 font-medium">({c.docente})</span>}
                    {!c.docente && <span className="text-slate-400 ml-1">(sin doc.)</span>}
                  </span>
                ))}
              </div></td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    );
  };

  return (
    <div className="p-8">
      <div className="mb-6"><h2 className="text-2xl font-bold text-slate-800">⚠️ Detector de Solapamientos</h2></div>
      <div className="flex gap-2 mb-6">
        <button onClick={() => setTab('horarios')} className={`px-4 py-2 rounded-lg text-sm font-medium ${tab === 'horarios' ? 'bg-orange-500 text-white' : 'bg-slate-100'}`}>
          🕐 Horarios/Docentes ({solapamientos.length})
        </button>
        <button onClick={() => setTab('carreras')} className={`px-4 py-2 rounded-lg text-sm font-medium ${tab === 'carreras' ? 'bg-red-600 text-white' : 'bg-slate-100'}`}>
          🎓 Entre Carreras ({totalCarr})
        </button>
      </div>

      {tab === 'horarios' && (
        solapamientos.length === 0 ? (
          <div className="bg-green-50 border border-green-200 rounded-xl p-8 text-center">
            <p className="text-4xl mb-2">✅</p><p className="text-green-700 font-medium text-lg">No hay solapamientos de horarios</p>
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
              </div>
            ))}
          </div>
        )
      )}

      {tab === 'carreras' && (
        loadingCarr ? <div className="text-center p-8">⏳ Analizando...</div> :
        carreraConf?.sin_plan ? (
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-8 text-center">
            <p className="text-4xl mb-2">📥</p>
            <p className="text-amber-700 font-medium">Importá primero el molde de horarios para detectar solapamientos entre carreras</p>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-4 gap-4 mb-6">
              <div className="bg-white rounded-xl border p-4 text-center">
                <p className={`text-3xl font-bold ${totalCarr > 0 ? 'text-red-600' : 'text-green-600'}`}>{totalCarr}</p>
                <p className="text-xs text-slate-500">Total conflictos</p>
              </div>
              <div className="bg-white rounded-xl border p-4 text-center">
                <p className={`text-3xl font-bold ${(carreraConf?.total_presencial||0) > 0 ? 'text-blue-600' : 'text-green-600'}`}>{carreraConf?.total_presencial || 0}</p>
                <p className="text-xs text-slate-500">🏫 Presenciales</p>
              </div>
              <div className="bg-white rounded-xl border p-4 text-center">
                <p className={`text-3xl font-bold ${(carreraConf?.total_cied||0) > 0 ? 'text-purple-600' : 'text-green-600'}`}>{carreraConf?.total_cied || 0}</p>
                <p className="text-xs text-slate-500">🖥️ CIED</p>
              </div>
              <div className="bg-white rounded-xl border p-4 text-center">
                <p className={`text-3xl font-bold ${(carreraConf?.total_docentes||0) > 0 ? 'text-orange-600' : 'text-green-600'}`}>{carreraConf?.total_docentes || 0}</p>
                <p className="text-xs text-slate-500">👨‍🏫 Docentes</p>
              </div>
            </div>

            <div className="mb-6">
              <h3 className="text-lg font-bold text-blue-800 mb-3 flex items-center gap-2">🏫 Presenciales <span className="text-sm font-normal text-slate-500">— Alumnos que no pueden cursar dos materias de su carrera porque coinciden en día/hora en su sede</span></h3>
              {renderConflictTable(carreraConf?.presencial, 'bg-blue-800')}
            </div>

            <div className="mb-6">
              <h3 className="text-lg font-bold text-purple-800 mb-3 flex items-center gap-2">🖥️ CIED <span className="text-sm font-normal text-slate-500">— Solo si NO hay ninguna combinación de horarios que evite el conflicto</span></h3>
              {renderConflictTable(carreraConf?.cied, 'bg-purple-800', false)}
            </div>

            <div className="mb-6">
              <h3 className="text-lg font-bold text-orange-800 mb-3 flex items-center gap-2">👨‍🏫 Docentes <span className="text-sm font-normal text-slate-500">— Un mismo docente asignado a dos cátedras distintas al mismo tiempo</span></h3>
              {carreraConf?.docentes?.length > 0 ? (
                <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
                  <table className="w-full text-sm">
                    <thead><tr className="bg-orange-800 text-white text-xs">
                      <th className="p-3 text-left">Docente</th><th className="p-3 text-center">Día</th><th className="p-3 text-center">Hora</th>
                      <th className="p-3 text-left">Cátedras en conflicto</th>
                    </tr></thead>
                    <tbody>{carreraConf.docentes.map((conf, i) => (
                      <tr key={i} className="border-b bg-yellow-50 hover:bg-yellow-100">
                        <td className="p-3 font-bold text-orange-700">{conf.docente}</td>
                        <td className="p-3 text-center font-bold">{conf.dia}</td>
                        <td className="p-3 text-center font-bold">{conf.hora}</td>
                        <td className="p-3"><div className="flex flex-wrap gap-1">
                          {conf.asignaciones.map((a, j) => (
                            <span key={j} className="px-2 py-1 bg-orange-100 border border-orange-300 rounded text-xs">
                              <span className="font-mono font-bold">{a.codigo}</span> {a.nombre?.substring(0, 25)} <span className="text-slate-500">({a.sede})</span>
                            </span>
                          ))}
                        </div></td>
                      </tr>
                    ))}</tbody>
                  </table>
                </div>
              ) : <div className="bg-green-50 border border-green-200 rounded-xl p-6 text-center"><p className="text-2xl mb-1">✅</p><p className="text-green-700 font-medium">Ningún docente está asignado a dos cátedras distintas al mismo tiempo</p></div>}
            </div>
          </>
        )
      )}
    </div>
  );
}

// ==================== v6.0: INSCRIPTOS POR CURSO ====================
function InscriptosPorCursoView({ cuatrimestre }) {
  const [datos, setDatos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [buscar, setBuscar] = useState('');
  const [filtroMod, setFiltroMod] = useState('');
  const [filtroTipo, setFiltroTipo] = useState('');

  useEffect(() => {
    const cargar = async () => {
      setLoading(true);
      try {
        const cuatId = cuatrimestre !== 'todos' ? cuatrimestre : '';
        const qParam = cuatId ? `?cuatrimestre_id=${cuatId}` : '';
        const r = await apiFetch(`/api/inscriptos/por-curso${qParam}`);
        setDatos(r);
      } catch (e) { console.error(e); }
      setLoading(false);
    };
    cargar();
  }, [cuatrimestre]);

  const filtrados = useMemo(() => {
    return datos.filter(d => {
      if (buscar && !d.curso_completo.toLowerCase().includes(buscar.toLowerCase()) &&
          !d.curso_nombre.toLowerCase().includes(buscar.toLowerCase())) return false;
      if (filtroMod && d.modalidad !== filtroMod) return false;
      if (filtroTipo && d.tipo_curso !== filtroTipo) return false;
      return true;
    });
  }, [datos, buscar, filtroMod, filtroTipo]);

  const totalAlumnos = filtrados.reduce((s, d) => s + (d.alumnos_unicos || 0), 0);
  const totalInsc = filtrados.reduce((s, d) => s + (d.inscripciones || 0), 0);

  if (loading) return <div className="p-8 text-center">⏳ Cargando...</div>;

  return (
    <div className="p-8">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-slate-800">📊 Inscriptos por Curso</h2>
        <p className="text-slate-500 text-sm">Cantidad de alumnos inscriptos en cada curso/carrera. Datos importados del Excel de alumnos.</p>
      </div>
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="bg-white rounded-xl border p-4 text-center"><p className="text-xs text-slate-500">Total Cursos</p><p className="text-2xl font-bold">{filtrados.length}</p></div>
        <div className="bg-white rounded-xl border p-4 text-center"><p className="text-xs text-slate-500">👤 Alumnos (DNI único)</p><p className="text-2xl font-bold text-blue-600">{totalAlumnos}</p></div>
        <div className="bg-white rounded-xl border p-4 text-center"><p className="text-xs text-slate-500">📚 Inscripciones a materias</p><p className="text-2xl font-bold text-cyan-600">{totalInsc}</p></div>
      </div>
      <div className="bg-white rounded-xl border p-3 mb-4 flex gap-3">
        <input type="text" placeholder="Buscar curso..." className="flex-1 px-3 py-2 border rounded-lg text-sm"
          value={buscar} onChange={e => setBuscar(e.target.value)} />
        <select className="border rounded-lg px-3 py-2 text-sm" value={filtroMod} onChange={e => setFiltroMod(e.target.value)}>
          <option value="">Todas las modalidades</option>
          <option value="CIED">🖥️ CIED</option>
          <option value="Presencial">🏫 Presencial</option>
        </select>
        <select className="border rounded-lg px-3 py-2 text-sm" value={filtroTipo} onChange={e => setFiltroTipo(e.target.value)}>
          <option value="">Todos los tipos</option>
          <option value="Superior">Superior</option>
          <option value="BCE">BCE Secundario</option>
          <option value="BEA">BEA</option>
        </select>
      </div>
      <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
        <table className="w-full">
          <thead><tr className="bg-slate-50 border-b">
            <th className="text-left p-3 text-sm font-semibold">#</th>
            <th className="text-left p-3 text-sm font-semibold">Curso</th>
            <th className="text-center p-3 text-sm font-semibold">Sede</th>
            <th className="text-center p-3 text-sm font-semibold">Modalidad</th>
            <th className="text-center p-3 text-sm font-semibold">Tipo</th>
            <th className="text-center p-3 text-sm font-semibold">Alumnos</th>
            <th className="text-center p-3 text-sm font-semibold">Inscripciones</th>
          </tr></thead>
          <tbody>
            {filtrados.map((d, i) => (
              <tr key={i} className="border-b hover:bg-slate-50">
                <td className="p-3 text-sm text-slate-400">{i + 1}</td>
                <td className="p-3 text-sm">{d.curso_completo}</td>
                <td className="p-3 text-center">
                  <span className={`px-2 py-0.5 rounded text-white text-xs ${SEDE_COLORS[d.sede] || 'bg-gray-500'}`}>{d.sede}</span>
                </td>
                <td className="p-3 text-center">
                  <span className={`px-2 py-1 rounded text-xs font-medium ${d.modalidad === 'CIED' ? 'bg-purple-100 text-purple-700' : 'bg-emerald-100 text-emerald-700'}`}>
                    {d.modalidad === 'CIED' ? '🖥️ CIED' : '🏫 Presencial'}
                  </span>
                </td>
                <td className="p-3 text-center">
                  {d.tipo_curso !== 'Superior' ? <span className={`px-2 py-0.5 rounded text-xs font-bold ${d.tipo_curso === 'BCE' ? 'bg-orange-100 text-orange-700' : 'bg-teal-100 text-teal-700'}`}>{d.tipo_curso}</span> : ''}
                </td>
                <td className="p-3 text-center"><span className="text-lg font-bold text-blue-600">{d.alumnos_unicos || 0}</span></td>
                <td className="p-3 text-center"><span className="text-lg font-bold text-cyan-600">{d.inscripciones || 0}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-sm text-slate-500 mt-3 text-center">{filtrados.length} cursos — {totalAlumnos} alumnos — {totalInsc} inscripciones a materias</p>
    </div>
  );
}

// ==================== CURSOS ====================
function CursosView({ cursos, sedes, recargar }) {
  const [buscar, setBuscar] = useState('');
  const [filtroSede, setFiltroSede] = useState('');
  const [expandido, setExpandido] = useState(null);
  const cursosFiltrados = useMemo(() => {
    return cursos.filter(c => {
      if (buscar && !c.nombre.toLowerCase().includes(buscar.toLowerCase())) return false;
      if (filtroSede && c.sede_id !== parseInt(filtroSede)) return false;
      return true;
    });
  }, [cursos, buscar, filtroSede]);
  return (
    <div className="p-8">
      <div className="mb-6"><h2 className="text-2xl font-bold text-slate-800">Cursos / Carreras</h2></div>
      <div className="bg-white rounded-xl border p-3 mb-4 flex gap-3">
        <input type="text" placeholder="Buscar curso..." className="flex-1 px-3 py-2 border rounded-lg text-sm" value={buscar} onChange={e => setBuscar(e.target.value)} />
        <select className="border rounded-lg px-3 py-2 text-sm" value={filtroSede} onChange={e => setFiltroSede(e.target.value)}>
          <option value="">Todas las sedes</option>
          {sedes.filter(s => SEDES_OPERATIVAS.includes(s.nombre)).map(s => <option key={s.id} value={s.id}>{s.nombre}</option>)}
        </select>
      </div>
      <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
        <table className="w-full">
          <thead><tr className="bg-slate-50 border-b">
            <th className="text-left p-4 text-sm font-semibold">Curso</th>
            <th className="text-center p-4 text-sm font-semibold">Sede</th>
            <th className="text-center p-4 text-sm font-semibold">Cátedras</th>
            <th className="text-center p-4 text-sm font-semibold w-24">Ver</th>
          </tr></thead>
          <tbody>
            {cursosFiltrados.map(c => (
              <React.Fragment key={c.id}>
                <tr className="border-b hover:bg-slate-50">
                  <td className="p-4 font-medium">{c.nombre}</td>
                  <td className="p-4 text-center">{c.sede_nombre ? <span className={`px-2 py-0.5 rounded text-white text-xs ${SEDE_COLORS[c.sede_nombre]||'bg-gray-500'}`}>{c.sede_nombre}</span> : '-'}</td>
                  <td className="p-4 text-center"><span className={`text-lg font-bold ${c.cant_catedras > 0 ? 'text-emerald-600' : 'text-slate-300'}`}>{c.cant_catedras}</span></td>
                  <td className="p-4 text-center">{c.cant_catedras > 0 && <button onClick={() => setExpandido(expandido === c.id ? null : c.id)} className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs">{expandido === c.id ? '▲' : '▼'}</button>}</td>
                </tr>
                {expandido === c.id && c.catedras?.length > 0 && (
                  <tr><td colSpan="4" className="bg-slate-50 px-8 py-3">
                    <div className="flex flex-wrap gap-2">
                      {c.catedras.map(cat => (
                        <span key={cat.id} className="px-3 py-1 bg-white border rounded-lg text-sm">
                          <span className="font-mono bg-slate-800 text-white px-1 rounded text-xs mr-1">{cat.catedra_codigo}</span>{cat.catedra_nombre}
                        </span>
                      ))}
                    </div>
                  </td></tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-sm text-slate-500 mt-3 text-center">{cursosFiltrados.length} cursos</p>
    </div>
  );
}

// ==================== v6.0: BCE / BEA SECUNDARIO ====================
function BceBeaView({ catedras, docentes, sedes, cuatrimestre, cuatrimestres, recargar }) {
  const [modalCatedra, setModalCatedra] = useState(null);
  const [modalEditar, setModalEditar] = useState(null);
  const [editCatInfo, setEditCatInfo] = useState(null);
  const [buscar, setBuscar] = useState('');

  const catedrasBCE = useMemo(() => {
    return catedras.filter(c => {
      const n = (c.nombre || '').toUpperCase();
      const vinc = c.cursos_vinculados || [];
      return vinc.some(v => {
        const cn = (v.curso_nombre || '').toUpperCase();
        return cn.includes('BCE') || cn.includes('BEA') || cn.includes('SECUNDARIO') || cn.includes('BACHILLERATO');
      }) || n.includes('BCE') || n.includes('BEA') || n.includes('SECUNDARIO');
    });
  }, [catedras]);

  const lista = useMemo(() => {
    const base = catedrasBCE.length > 0 ? catedrasBCE : catedras;
    if (!buscar) return base;
    const b = buscar.toLowerCase();
    return base.filter(c => c.nombre.toLowerCase().includes(b) || c.codigo.toLowerCase().includes(b));
  }, [catedras, catedrasBCE, buscar]);

  const eliminarAsig = async (id) => {
    if (!window.confirm('¿Eliminar?')) return;
    try { await apiFetch(`/api/asignaciones/${id}`, { method: 'DELETE' }); recargar(); } catch (e) { alert(e.message); }
  };

  return (
    <div className="p-8">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-slate-800">🏫 BCE Secundario / BEA</h2>
        <p className="text-slate-500 text-sm">Cátedras del secundario acelerado. Asignaciones y horarios se tratan aparte.</p>
      </div>
      <div className="bg-white rounded-xl border p-3 mb-4">
        <input type="text" placeholder="Buscar cátedra por código o nombre..." className="w-full px-3 py-2 border rounded-lg text-sm"
          value={buscar} onChange={e => setBuscar(e.target.value)} />
      </div>
      {catedrasBCE.length === 0 && !buscar && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-4">
          <p className="text-amber-700 text-sm">No se detectaron cátedras vinculadas a cursos BCE/BEA automáticamente. Usá el buscador para encontrar las cátedras que necesitás, o vinculá los cursos BCE/BEA desde Importar.</p>
        </div>
      )}
      <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
        <table className="w-full">
          <thead><tr className="bg-orange-50 border-b">
            <th className="text-left p-3 text-sm font-semibold">Cátedra</th>
            <th className="text-left p-3 text-sm font-semibold">Asignaciones</th>
            <th className="text-center p-3 text-sm font-semibold w-20">Inscriptos</th>
            <th className="text-center p-3 text-sm font-semibold w-24">Acciones</th>
          </tr></thead>
          <tbody>
            {lista.slice(0, 50).map(cat => (
              <tr key={cat.id} className="border-b hover:bg-slate-50">
                <td className="p-3">
                  <span className="px-2 py-1 bg-orange-700 text-white rounded text-xs font-mono mr-2">{cat.codigo}</span>
                  <span className="font-medium">{cat.nombre}</span>
                </td>
                <td className="p-3">
                  {cat.asignaciones?.length > 0 ? cat.asignaciones.map(a => {
                    const mod = MODALIDAD_CONFIG[a.modalidad] || {};
                    return (
                      <div key={a.id} className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs border mr-1 mb-1" style={{background: mod.bg ? undefined : '#f8f8f8'}}>
                        <span>{a.docente ? a.docente.nombre : '⚠️ Sin doc.'}</span>
                        {a.dia && <span className="text-slate-400">{a.dia} {a.hora_inicio}</span>}
                        <button onClick={() => { setModalEditar(a); setEditCatInfo({codigo: cat.codigo, nombre: cat.nombre}); }} className="text-blue-500">✏️</button>
                        <button onClick={() => eliminarAsig(a.id)} className="text-red-400">×</button>
                      </div>
                    );
                  }) : <span className="text-slate-400 text-sm">Sin asignaciones</span>}
                </td>
                <td className="p-3 text-center"><span className="text-lg font-bold text-cyan-600">{cat.inscriptos || 0}</span></td>
                <td className="p-3 text-center">
                  <button onClick={() => setModalCatedra(cat)} className="px-3 py-1 bg-amber-500 text-slate-900 rounded text-sm font-medium">+ Asignar</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-sm text-slate-500 mt-3 text-center">{lista.length} cátedras</p>
      {modalCatedra && <ModalAsignarCatedra catedra={modalCatedra} docentes={docentes} sedes={sedes} cuatrimestre={cuatrimestre} cuatrimestres={cuatrimestres} onClose={() => setModalCatedra(null)} recargar={recargar} />}
      {modalEditar && editCatInfo && <ModalEditarAsignacion asignacion={modalEditar} docentes={docentes} sedes={sedes} onClose={() => { setModalEditar(null); setEditCatInfo(null); }} recargar={recargar} catCodigo={editCatInfo.codigo} catNombre={editCatInfo.nombre} />}
    </div>
  );
}

// ==================== IMPORTAR VIEW (v4.0 con apertura y alumnos consolidados) ====================
function ImportarView({ recargar, cuatrimestres, cuatrimestre }) {
  const [uploading, setUploading] = useState('');
  const [resultado, setResultado] = useState(null);
  const [horariosPreview, setHorariosPreview] = useState(null);
  const [cuatriSeleccionado, setCuatriSeleccionado] = useState(
    cuatrimestre !== 'todos' ? cuatrimestre : ((cuatrimestres||[])[0]?.id?.toString() || '1')
  );

  const subirArchivo = async (endpoint, label, extraParams = '') => {
    const input = document.createElement('input');
    input.type = 'file'; input.accept = '.xlsx,.xls';
    input.onchange = async (e) => {
      const file = e.target.files[0]; if (!file) return;
      setUploading(label); setResultado(null);
      const formData = new FormData();
      formData.append('file', file);
      try {
        const res = await fetch(`${API_URL}${endpoint}${extraParams}`, { method: 'POST', body: formData });
        const data = await res.json();
        if (res.ok) { setResultado({ ok: true, data, label }); recargar(); }
        else { setResultado({ ok: false, error: data.detail || 'Error', label }); }
      } catch (err) { setResultado({ ok: false, error: err.message, label }); }
      setUploading('');
    };
    input.click();
  };

  // v4.0 MEJORA 12: Replicar cuatrimestre
  const [replicarOrigen, setReplicarOrigen] = useState('');
  const [replicarDestino, setReplicarDestino] = useState('');
  const [replicando, setReplicando] = useState(false);

  const replicar = async () => {
    if (!replicarOrigen || !replicarDestino) { alert('Seleccioná origen y destino'); return; }
    if (replicarOrigen === replicarDestino) { alert('Origen y destino no pueden ser iguales'); return; }
    if (!window.confirm('¿Replicar todas las aperturas del cuatrimestre seleccionado? Los docentes NO se copian, solo la estructura.')) return;
    setReplicando(true);
    try {
      const r = await apiFetch('/api/cuatrimestres/replicar', {
        method: 'POST',
        body: JSON.stringify({ origen_id: parseInt(replicarOrigen), destino_id: parseInt(replicarDestino) }),
      });
      setResultado({ ok: true, data: r, label: 'Replicar cuatrimestre' });
      recargar();
    } catch (e) { setResultado({ ok: false, error: e.message, label: 'Replicar' }); }
    setReplicando(false);
  };

  return (
    <div className="p-8">
      <div className="mb-6"><h2 className="text-2xl font-bold text-slate-800">Importar Datos</h2></div>
      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 mb-6">
        <p className="text-blue-700 text-sm">ℹ️ Los datos se guardan permanentemente. Si importás un archivo con datos que ya existen, se actualizan sin duplicar.</p>
      </div>

      {/* v4.0 MEJORA 1: Apertura masiva de cátedras */}
      <h3 className="font-semibold text-slate-600 mb-3">📋 Apertura de cátedras por cuatrimestre</h3>
      <div className="bg-white rounded-xl border p-6 mb-8 border-amber-200">
        <h3 className="font-semibold mb-2">📚 Abrir cátedras para un cuatrimestre</h3>
        <p className="text-sm text-slate-500 mb-1">Subí un Excel con las cátedras que se abrirán. Cada una se crea como "pendiente" (sin turno ni docente asignado).</p>
        <p className="text-xs text-slate-400 mb-3 font-mono">Formato: | Número | c.XX Nombre de la cátedra |</p>
        <div className="mb-4">
          <label className="text-sm text-slate-600 font-medium">Cuatrimestre destino:</label>
          <select className="w-full border-2 border-amber-300 rounded-lg px-3 py-2 mt-1 bg-amber-50"
            value={cuatriSeleccionado} onChange={e => setCuatriSeleccionado(e.target.value)}>
            {(cuatrimestres||[]).map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}
          </select>
        </div>
        <button onClick={() => subirArchivo('/api/importar/apertura-catedras', 'Apertura Cátedras', `?cuatrimestre_id=${cuatriSeleccionado}`)}
          disabled={uploading === 'Apertura Cátedras'}
          className="w-full py-2.5 rounded-lg font-medium disabled:opacity-50 bg-amber-500 text-slate-900 hover:bg-amber-400">
          {uploading === 'Apertura Cátedras' ? '⏳ Importando...' : '📤 Subir Excel de aperturas'}
        </button>
      </div>

      <h3 className="font-semibold text-slate-600 mb-3">Datos base</h3>
      <div className="grid grid-cols-3 gap-6 mb-8">
        {[
          { id: 'catedras', icon: '📚', titulo: 'Importar Cátedras', desc: 'Excel con: Número + "c.XX Nombre"', endpoint: '/api/importar/catedras', color: 'bg-slate-800 text-white' },
          { id: 'cursos', icon: '🎓', titulo: 'Importar Cursos', desc: 'Excel con: Sede + Nombre del curso', endpoint: '/api/importar/cursos', color: 'bg-blue-600 text-white' },
          { id: 'docentes', icon: '👨‍🏫', titulo: 'Importar Docentes', desc: 'Excel: DNI + Apellido, Nombre', endpoint: '/api/importar/docentes', color: 'bg-amber-500 text-slate-900' },
        ].map(imp => (
          <div key={imp.id} className="bg-white rounded-xl border p-6">
            <h3 className="font-semibold mb-2">{imp.icon} {imp.titulo}</h3>
            <p className="text-sm text-slate-500 mb-4">{imp.desc}</p>
            <button onClick={() => subirArchivo(imp.endpoint, imp.titulo)} disabled={uploading === imp.titulo}
              className={`w-full py-2.5 rounded-lg font-medium disabled:opacity-50 ${imp.color}`}>
              {uploading === imp.titulo ? '⏳...' : '📤 Subir Excel'}
            </button>
          </div>
        ))}
      </div>

      <h3 className="font-semibold text-slate-600 mb-3">Vinculaciones</h3>
      <div className="grid grid-cols-2 gap-6 mb-8">
        {[
          { id: 'cc', icon: '🔗', titulo: 'Vincular Cátedras ↔ Cursos', endpoint: '/api/importar/catedra-cursos', color: 'bg-teal-600 text-white' },
          { id: 'meet', icon: '📹', titulo: 'Links de Meet', endpoint: '/api/importar/links-meet', color: 'bg-green-600 text-white' },
        ].map(imp => (
          <div key={imp.id} className="bg-white rounded-xl border p-6 border-dashed border-slate-300">
            <h3 className="font-semibold mb-2">{imp.icon} {imp.titulo}</h3>
            <button onClick={() => subirArchivo(imp.endpoint, imp.titulo)} disabled={uploading === imp.titulo}
              className={`w-full py-2.5 rounded-lg font-medium disabled:opacity-50 ${imp.color}`}>
              {uploading === imp.titulo ? '⏳...' : '📤 Subir Excel'}
            </button>
          </div>
        ))}
      </div>

      <h3 className="font-semibold text-slate-600 mb-3">🗺️ Molde de horarios por carrera</h3>
      <div className="bg-white rounded-xl border p-6 mb-6 border-blue-200">
        <p className="text-sm text-slate-500 mb-3">Subí el archivo <strong>Horarios.xlsx</strong> con la estructura de carreras, años y cátedras por sede. Se importa una sola vez y sirve como "molde" para generar sugerencias.</p>
        <button onClick={() => subirArchivo('/api/importar/plan-carrera', 'Plan Carrera')}
          disabled={uploading === 'Plan Carrera'}
          className="w-full py-2.5 rounded-lg font-medium disabled:opacity-50 bg-blue-600 text-white hover:bg-blue-700">
          {uploading === 'Plan Carrera' ? '⏳ Importando...' : '📤 Importar molde de horarios'}
        </button>
      </div>

      {/* v4.0 MEJORA 4: Alumnos consolidados */}
      <h3 className="font-semibold text-slate-600 mb-3">Alumnos inscriptos</h3>
      <div className="bg-white rounded-xl border p-6 mb-6 border-cyan-200">
        <h3 className="font-semibold mb-2">👥 Importar Alumnos Inscriptos (v6.0)</h3>
        <p className="text-sm text-slate-500 mb-1">El sistema ahora clasifica automáticamente cada alumno según su CURSO:</p>
        <p className="text-xs text-slate-500 mb-1">🖥️ <strong>Virtual</strong>: Si el curso dice "CIED" o es "Online-Interior"</p>
        <p className="text-xs text-slate-500 mb-1">🏫 <strong>Presencial</strong>: Si el curso NO dice "CIED" (requiere profesor en aula)</p>
        <p className="text-xs text-slate-500 mb-1">📋 <strong>Turno</strong>: Se lee de la MATERIA (Mañana / Noche / Virtual)</p>
        <p className="text-xs text-slate-400 mb-3">Si el Excel tiene varias hojas, se procesan todas.</p>
        <div className="mb-4">
          <label className="text-sm text-slate-600 font-medium">Cuatrimestre:</label>
          <select className="w-full border-2 border-cyan-300 rounded-lg px-3 py-2 mt-1 bg-cyan-50"
            value={cuatriSeleccionado} onChange={e => setCuatriSeleccionado(e.target.value)}>
            {(cuatrimestres||[]).map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}
          </select>
        </div>
        <button onClick={() => subirArchivo('/api/importar/alumnos', 'Alumnos', `?cuatrimestre_id=${cuatriSeleccionado}`)}
          disabled={uploading === 'Alumnos'}
          className="w-full py-2.5 rounded-lg font-medium disabled:opacity-50 bg-cyan-600 text-white hover:bg-cyan-700">
          {uploading === 'Alumnos' ? '⏳...' : '📤 Subir Excel de inscriptos'}
        </button>
      </div>

      <div className="bg-white rounded-xl border p-6 mb-6 border-emerald-200">
        <h3 className="font-semibold mb-2">📅 Importar Horarios y Designaciones</h3>
        <p className="text-sm text-slate-500 mb-1">Importa asignaciones con día, hora, sede y docente. <strong>Borra las asignaciones anteriores</strong> y carga las nuevas.</p>
        <p className="text-xs text-slate-400 mb-3">Paso 1: Vista previa de cambios → Paso 2: Confirmar y aplicar. Docentes no existentes se crean automáticamente.</p>
        {!horariosPreview ? (
          <button onClick={async () => {
            const input = document.createElement('input'); input.type = 'file'; input.accept = '.xlsx';
            input.onchange = async (ev) => {
              const file = ev.target.files?.[0]; if (!file) return;
              setUploading('Preview Horarios');
              try {
                const form = new FormData(); form.append('file', file);
                const res = await fetch(`${API_URL}/api/importar/horarios-preview?cuatrimestre_id=${cuatriSeleccionado}`, { method: 'POST', body: form });
                const data = await res.json();
                console.log('Preview response:', data);
                if (data.detail || data.error) { alert('Error: ' + (data.detail || data.error)); setUploading(null); return; }
                setHorariosPreview({ data, file });
              } catch (e) { alert('Error: ' + e.message); }
              setUploading(null);
            }; input.click();
          }} disabled={uploading === 'Preview Horarios'}
            className="w-full py-2.5 rounded-lg font-medium disabled:opacity-50 bg-emerald-600 text-white hover:bg-emerald-700">
            {uploading === 'Preview Horarios' ? '⏳ Analizando...' : '🔍 Paso 1: Analizar Excel de horarios'}
          </button>
        ) : (
          <div>
            <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4 mb-3">
              <p className="font-bold text-emerald-800 text-lg mb-2">Vista previa de cambios</p>
              {horariosPreview.data.error && (
                <div className="bg-red-50 border border-red-200 rounded p-3 mb-3">
                  <p className="font-bold text-red-800">⚠️ Error: {horariosPreview.data.error}</p>
                  {horariosPreview.data.traceback && <pre className="text-[9px] text-red-600 mt-1 overflow-auto max-h-24">{horariosPreview.data.traceback}</pre>}
                </div>
              )}
              {horariosPreview.data._debug && (
                <p className="text-[10px] text-slate-400 mb-2">DB: {horariosPreview.data._debug.total_catedras_db} cátedras, {horariosPreview.data._debug.total_docentes_db} docentes | No encontradas: {horariosPreview.data._debug.no_cat_count}</p>
              )}
              <div className="grid grid-cols-3 gap-3 text-sm mb-3">
                <div className="bg-white rounded p-2 text-center"><p className="text-2xl font-bold text-red-600">{horariosPreview.data.asignaciones_actuales_a_borrar ?? 0}</p><p className="text-xs text-slate-500">Se borran</p></div>
                <div className="bg-white rounded p-2 text-center"><p className="text-2xl font-bold text-emerald-600">{horariosPreview.data.asignaciones_nuevas ?? 0}</p><p className="text-xs text-slate-500">Se crean</p></div>
                <div className="bg-white rounded p-2 text-center"><p className="text-2xl font-bold text-blue-600">{horariosPreview.data.con_docente_existente ?? 0}</p><p className="text-xs text-slate-500">Con docente</p></div>
              </div>
              {horariosPreview.data.docentes_a_crear?.length > 0 && (
                <div className="bg-amber-50 border border-amber-200 rounded p-3 mb-3">
                  <p className="font-medium text-amber-800 text-sm">🆕 Se crearán {horariosPreview.data.docentes_a_crear.length} docentes nuevos:</p>
                  <p className="text-xs text-amber-600 mt-1">{horariosPreview.data.docentes_a_crear.join(', ')}</p>
                </div>
              )}
              {horariosPreview.data.catedras_no_encontradas?.length > 0 && (
                <div className="bg-red-50 border border-red-200 rounded p-3 mb-3">
                  <p className="font-medium text-red-800 text-sm">⚠️ Cátedras no encontradas:</p>
                  <p className="text-xs text-red-600 mt-1">{horariosPreview.data.catedras_no_encontradas.join(', ')}</p>
                </div>
              )}
              {horariosPreview.data.preview?.length > 0 && (
                <details className="mt-2"><summary className="text-xs text-slate-500 cursor-pointer">Ver primeras {horariosPreview.data.preview.length} asignaciones</summary>
                  <div className="mt-2 max-h-48 overflow-y-auto text-[10px]">
                    <table className="w-full"><thead><tr className="bg-slate-100"><th className="p-1">Cát.</th><th className="p-1">Nombre</th><th className="p-1">Día</th><th className="p-1">Hora</th><th className="p-1">Sede</th><th className="p-1">Docente</th><th className="p-1">Est.</th></tr></thead>
                    <tbody>{horariosPreview.data.preview.map((r,i) => <tr key={i} className="border-b"><td className="p-1 font-mono">{r.cat}</td><td className="p-1">{r.nombre}</td><td className="p-1">{r.dia}</td><td className="p-1">{r.hora}</td><td className="p-1">{r.sede}</td><td className="p-1">{r.docente}</td><td className="p-1">{r.estado}</td></tr>)}</tbody></table>
                  </div>
                </details>
              )}
            </div>
            <div className="flex gap-3">
              <button onClick={async () => {
                setUploading('Aplicar Horarios');
                try {
                  const form = new FormData(); form.append('file', horariosPreview.file);
                  const res = await fetch(`${API_URL}/api/importar/horarios-aplicar?cuatrimestre_id=${cuatriSeleccionado}`, { method: 'POST', body: form });
                  if (!res.ok) { const txt = await res.text(); throw new Error(txt); }
                  const data = await res.json();
                  if (data.error) { alert('⚠️ ' + data.error); setUploading(null); return; }
                  setResultado({ ok: true, data, label: 'Importar Horarios' });
                  setHorariosPreview(null); recargar();
                } catch (e) { alert('Error: ' + e.message); }
                setUploading(null);
              }} disabled={uploading === 'Aplicar Horarios'}
                className="flex-1 py-2.5 rounded-lg font-bold bg-emerald-600 text-white hover:bg-emerald-700">
                {uploading === 'Aplicar Horarios' ? '⏳ Aplicando...' : '✅ Confirmar y aplicar cambios'}
              </button>
              <button onClick={() => setHorariosPreview(null)} className="px-6 py-2.5 rounded-lg font-medium bg-slate-200 hover:bg-slate-300">
                ❌ Cancelar
              </button>
            </div>
          </div>
        )}
      </div>

      <h3 className="font-semibold text-slate-600 mb-3">👨‍🏫 Docentes</h3>
      <div className="bg-white rounded-xl border p-6 mb-6 border-indigo-200">
        <h3 className="font-semibold mb-2">📋 Importar Docentes desde CUIT</h3>
        <p className="text-sm text-slate-500 mb-3">Excel con columnas: CUIT | APELLIDO, NOMBRE. Extrae el DNI automáticamente. Si ya existe, actualiza el nombre.</p>
        <button onClick={() => subirArchivo('/api/importar/docentes-cuit', 'Docentes CUIT')}
          disabled={uploading === 'Docentes CUIT'}
          className="w-full py-2.5 rounded-lg font-medium disabled:opacity-50 bg-indigo-600 text-white hover:bg-indigo-700">
          {uploading === 'Docentes CUIT' ? '⏳...' : '📤 Importar docentes con CUIT'}
        </button>
      </div>

      <div className="bg-white rounded-xl border p-6 mb-6 border-violet-200">
        <h3 className="font-semibold mb-2">🎯 Cátedras de Referencia por Docente</h3>
        <p className="text-sm text-slate-500 mb-3">Define qué cátedras puede dictar cada docente. Se usa para las sugerencias automáticas de armado de horarios.</p>
        <div className="flex gap-3">
          <button onClick={() => subirArchivo('/api/importar/catedras-referencia', 'Cát. Referencia')}
            disabled={uploading === 'Cát. Referencia'}
            className="flex-1 py-2.5 rounded-lg font-medium disabled:opacity-50 bg-violet-600 text-white hover:bg-violet-700">
            {uploading === 'Cát. Referencia' ? '⏳...' : '📤 Importar desde Excel de designaciones'}
          </button>
          <button onClick={async () => {
            setUploading('Auto-ref');
            try {
              const r = await fetch(`${API_URL}/api/docentes/auto-referencia?cuatrimestre_id=${cuatriSeleccionado}`, { method: 'POST' });
              const data = await r.json();
              setResultado({ ok: true, data, label: 'Auto-asignar referencias' }); recargar();
            } catch (e) { alert(e.message); }
            setUploading(null);
          }} disabled={uploading === 'Auto-ref'}
            className="flex-1 py-2.5 rounded-lg font-medium disabled:opacity-50 bg-violet-100 text-violet-700 border border-violet-300 hover:bg-violet-200">
            {uploading === 'Auto-ref' ? '⏳...' : '🔄 Auto-asignar desde asignaciones actuales'}
          </button>
        </div>
      </div>

      <div className="bg-white rounded-xl border p-6 mb-6 border-orange-200">
        <h3 className="font-semibold mb-2">🏫 Importar Alumnos BCE / BEA</h3>
        <p className="text-sm text-slate-500 mb-1">BCE: alumnos del secundario acelerado. Se asignan como <strong>Virtual</strong> a la sede del curso.</p>
        <p className="text-sm text-slate-500 mb-3">BEA: alumnos del bachillerato. Todos se asignan a <strong>Caballito Virtual</strong>.</p>
        <button onClick={() => subirArchivo('/api/importar/alumnos-bce-bea', 'BCE/BEA', `?cuatrimestre_id=${cuatriSeleccionado}`)}
          disabled={uploading === 'BCE/BEA'}
          className="w-full py-2.5 rounded-lg font-medium disabled:opacity-50 bg-orange-500 text-white hover:bg-orange-600">
          {uploading === 'BCE/BEA' ? '⏳...' : '📤 Subir Excel BCE/BEA'}
        </button>
      </div>

      {/* v4.0 MEJORA 12: Replicar cuatrimestre */}
      <h3 className="font-semibold text-slate-600 mb-3">🔄 Replicar cuatrimestre anterior</h3>
      <div className="bg-white rounded-xl border p-6 mb-6 border-violet-200">
        <p className="text-sm text-slate-500 mb-3">Copiá la apertura de cátedras de un cuatrimestre anterior a uno nuevo. Se copian las materias abiertas con su horario y sede, pero sin docente (hay que reasignarlos).</p>
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label className="text-sm text-slate-600 font-medium">Copiar de:</label>
            <select className="w-full border rounded-lg px-3 py-2 mt-1" value={replicarOrigen} onChange={e => setReplicarOrigen(e.target.value)}>
              <option value="">Seleccionar origen</option>
              {(cuatrimestres||[]).map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}
            </select>
          </div>
          <div>
            <label className="text-sm text-slate-600 font-medium">Hacia:</label>
            <select className="w-full border rounded-lg px-3 py-2 mt-1" value={replicarDestino} onChange={e => setReplicarDestino(e.target.value)}>
              <option value="">Seleccionar destino</option>
              {(cuatrimestres||[]).map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}
            </select>
          </div>
        </div>
        <button onClick={replicar} disabled={replicando}
          className="w-full py-2.5 rounded-lg font-medium disabled:opacity-50 bg-violet-600 text-white hover:bg-violet-700">
          {replicando ? '⏳ Replicando...' : '🔄 Replicar apertura'}
        </button>
      </div>

      {resultado && (
        <div className={`p-4 rounded-xl border ${resultado.ok ? 'bg-green-50 border-green-300' : 'bg-red-50 border-red-300'}`}>
          <p className="font-medium text-lg">{resultado.ok ? '✅' : '❌'} {resultado.label}</p>
          {resultado.ok && resultado.data && (
            <div className="mt-2 text-sm">
              {Object.entries(resultado.data).filter(([k]) => k !== 'errores').map(([k, v]) => {
                if (Array.isArray(v) && v.length > 0) {
                  return <div key={k} className="mt-2"><p className="font-medium text-orange-700">{k} ({v.length}):</p>{v.map((item, i) => <p key={i} className="text-xs ml-2">• {typeof item === 'string' ? item : JSON.stringify(item)}</p>)}</div>;
                }
                if (Array.isArray(v) && v.length === 0) return null;
                if (typeof v === 'object' && v !== null) {
                  return <p key={k}>{k}: <strong>{Object.entries(v).map(([sk,sv]) => `${sk}: ${sv}`).join(', ')}</strong></p>;
                }
                return <p key={k}>{k}: <strong>{v}</strong></p>;
              })}
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

// ==================== v15.0: DOCENTE ROW EDITOR — ESTADO EN EL PADRE ====================
// DocenteEditRow reads/writes from a shared editStore ref, never loses data
function DocenteEditRow({ docId, editStore, onSave }) {
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const vals = editStore.current[docId] || {};
  const set = (campo, valor) => {
    editStore.current[docId] = {...editStore.current[docId], [campo]: valor};
    setDirty(true); setSaved(false);
  };

  const guardar = async () => {
    setSaving(true);
    const data = editStore.current[docId];
    try {
      const payload = {
        horas_asignadas: parseInt(data.horas_asignadas) || 0,
        materias_av: parseInt(data.materias_av) || 0,
        materias_cab: parseInt(data.materias_cab) || 0,
        materias_vl: parseInt(data.materias_vl) || 0,
        sociedad_cfpea: !!data.sociedad_cfpea,
        sociedad_isftea: !!data.sociedad_isftea,
        notas: data.notas || '',
        especialidad: data.especialidad || '',
        catedras_referencia: data.catedras_referencia || '',
      };
      const res = await fetch(`${API_URL}/api/docentes/${docId}`, {
        method: 'PUT', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error('Error del servidor');
      setDirty(false); setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (e) { alert('Error al guardar: ' + e.message); }
    setSaving(false);
  };

  // Force re-render when editStore changes (using a trick)
  const [, forceUpdate] = useState(0);
  const setAndUpdate = (campo, valor) => { set(campo, valor); forceUpdate(n => n + 1); };

  return (
    <div className="flex items-center gap-2 flex-wrap">
      {[['horas_asignadas','Hs'],['materias_av','Av'],['materias_cab','Cab'],['materias_vl','VL']].map(([campo,label]) => (
        <div key={campo} className="text-center">
          <label className="text-[8px] text-slate-400 block">{label}</label>
          <input type="number" min="0" max="99" className={`w-10 text-center border rounded px-0.5 py-0.5 text-[10px] ${dirty ? 'border-amber-400' : ''}`}
            value={vals[campo] ?? 0} onChange={e => setAndUpdate(campo, e.target.value)} onKeyDown={e => e.key === 'Enter' && guardar()} />
        </div>
      ))}
      {[['sociedad_cfpea','CFPEA'],['sociedad_isftea','ISFTEA']].map(([campo,label]) => (
        <div key={campo} className="text-center">
          <label className="text-[8px] text-slate-400 block">{label}</label>
          <input type="checkbox" checked={!!vals[campo]} onChange={e => setAndUpdate(campo, e.target.checked)} className="w-4 h-4" />
        </div>
      ))}
      <div className="flex-1 min-w-[80px]">
        <input type="text" placeholder="Notas..." className={`w-full border rounded px-1 py-0.5 text-[10px] ${dirty ? 'border-amber-400' : ''}`}
          value={vals.notas ?? ''} onChange={e => setAndUpdate('notas', e.target.value)} onKeyDown={e => e.key === 'Enter' && guardar()} />
      </div>
      <div className="min-w-[70px]">
        <label className="text-[8px] text-slate-400 block">Especialidad</label>
        <input type="text" placeholder="Área..." className={`w-full border rounded px-1 py-0.5 text-[10px] ${dirty ? 'border-amber-400' : ''}`}
          value={vals.especialidad ?? ''} onChange={e => setAndUpdate('especialidad', e.target.value)} onKeyDown={e => e.key === 'Enter' && guardar()} />
      </div>
      <div className="min-w-[80px]">
        <label className="text-[8px] text-slate-400 block">Cát. ref.</label>
        <input type="text" placeholder="c.1, c.3..." className={`w-full border rounded px-1 py-0.5 text-[10px] ${dirty ? 'border-amber-400' : ''}`}
          value={vals.catedras_referencia ?? ''} onChange={e => setAndUpdate('catedras_referencia', e.target.value)} onKeyDown={e => e.key === 'Enter' && guardar()} />
      </div>
      <button onClick={guardar} disabled={saving}
        className={`px-3 py-1.5 rounded text-xs font-bold whitespace-nowrap ${saved ? 'bg-emerald-500 text-white' : dirty ? 'bg-amber-500 text-white animate-pulse' : 'bg-slate-200 text-slate-400'}`}>
        {saving ? '⏳' : saved ? '✅' : dirty ? '💾 GUARDAR' : '—'}
      </button>
    </div>
  );
}

// SociedadCheck is now handled by DocenteEditRow

// ==================== v10.0: NOTAS INPUT ====================
function NotasInput({ item, endpoint }) {
  const [val, setVal] = useState(item.notas || '');
  const [saved, setSaved] = useState(true);
  const [saving, setSaving] = useState(false);
  const guardar = async () => {
    setSaving(true);
    try {
      await apiFetch(`/api/${endpoint}/${item.id}`, { method: 'PUT', body: JSON.stringify({ notas: val }) });
      setSaved(true);
    } catch (e) { alert(e.message); }
    setSaving(false);
  };
  return (
    <div className="flex items-center gap-0.5">
      <input type="text" className={`w-full border rounded px-1 py-0.5 text-[10px] ${!saved ? 'border-amber-500 bg-amber-50' : 'border-slate-200'}`}
        placeholder="Notas..." value={val} onChange={e => { setVal(e.target.value); setSaved(false); }}
        onBlur={() => { if (!saved) guardar(); }} onKeyDown={e => e.key === 'Enter' && guardar()} />
      {!saved && !saving && <button onClick={guardar} className="text-[9px] bg-amber-500 text-white px-0.5 rounded">💾</button>}
    </div>
  );
}

// ==================== v12.0: DECISION INPUT MULTI-SELECT ====================
function DecisionInput({ catedra }) {
  const opciones = ['TM Avellaneda','TN Avellaneda','TM Caballito','TN Caballito','TM Vicente López','TN Vicente López','CIED Virtual','Asincrónica','No abrir'];
  const initRef = useRef(false);
  const [selected, setSelected] = useState(() => {
    const d = catedra.decision_apertura || '';
    return d ? d.split(',').map(s => s.trim()).filter(Boolean) : [];
  });
  const [open, setOpen] = useState(false);
  // Do NOT re-sync from parent — only initialize once
  
  const toggle = async (op) => {
    let newSel;
    if (op === 'No abrir' || op === 'Asincrónica') {
      newSel = selected.includes(op) ? [] : [op];
    } else {
      newSel = selected.filter(s => s !== 'No abrir' && s !== 'Asincrónica');
      newSel = newSel.includes(op) ? newSel.filter(s => s !== op) : [...newSel, op];
    }
    setSelected(newSel);
    try {
      await fetch(`${API_URL}/api/catedras/${catedra.id}`, {
        method: 'PUT', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ decision_apertura: newSel.join(', ') })
      });
    } catch (e) {}
  };
  
  const color = selected.length === 0 ? 'border-slate-200' : 
    selected.includes('No abrir') ? 'border-red-300 bg-red-50' : 
    selected.includes('Asincrónica') ? 'border-purple-300 bg-purple-50' : 'border-emerald-300 bg-emerald-50';
  
  return (
    <div className="relative">
      <button onClick={() => setOpen(!open)} className={`w-full border rounded px-1 py-0.5 text-[8px] text-left ${color}`}>
        {selected.length > 0 ? selected.join(', ') : '— Decidir —'}
      </button>
      {open && (
        <div className="absolute z-50 bg-white border shadow-xl rounded-lg p-2 w-48 left-0 top-full mt-1" onMouseLeave={() => setOpen(false)}>
          {opciones.map(op => (
            <label key={op} className="flex items-center gap-1.5 py-0.5 px-1 hover:bg-slate-50 rounded cursor-pointer text-[10px]">
              <input type="checkbox" checked={selected.includes(op)} onChange={() => toggle(op)} className="w-3 h-3" />
              {op}
            </label>
          ))}
        </div>
      )}
    </div>
  );
}

// ==================== v6.0: DISPONIBILIDAD DOCENTE ====================
function DisponibilidadView({ docentes, catedras, sedes, cuatrimestre, cuatrimestres, recargar }) {
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [buscar, setBuscar] = useState('');
  const [disponibilidad, setDisponibilidad] = useState([]);
  const [loading, setLoading] = useState(false);
  const [guardando, setGuardando] = useState(false);

  const docsFiltrados = useMemo(() => {
    if (!buscar) return docentes;
    const b = buscar.toLowerCase();
    return docentes.filter(d => d.nombre.toLowerCase().includes(b) || d.apellido.toLowerCase().includes(b));
  }, [docentes, buscar]);

  const cargarDisp = async (docId) => {
    setLoading(true);
    try { setDisponibilidad(await apiFetch(`/api/docentes/${docId}/disponibilidad`)); }
    catch (e) { setDisponibilidad([]); }
    setLoading(false);
  };
  const seleccionar = (d) => { setSelectedDoc(d); cargarDisp(d.id); };
  const isDisponible = (dia, hora) => disponibilidad.find(d => d.dia === dia && d.hora === hora)?.disponible || false;
  const toggleCelda = (dia, hora) => {
    const existe = disponibilidad.find(d => d.dia === dia && d.hora === hora);
    if (existe) setDisponibilidad(disponibilidad.map(d => d.dia === dia && d.hora === hora ? {...d, disponible: !d.disponible} : d));
    else setDisponibilidad([...disponibilidad, {dia, hora, disponible: true}]);
  };
  const guardar = async () => {
    if (!selectedDoc) return;
    setGuardando(true);
    try {
      await apiFetch(`/api/docentes/${selectedDoc.id}/disponibilidad`, { method: 'PUT', body: JSON.stringify({ disponibilidad: disponibilidad.filter(d => d.disponible) }) });
      alert('Disponibilidad guardada');
    } catch (e) { alert('Error: ' + e.message); }
    setGuardando(false);
  };

  // Cátedras asignadas a este docente
  const asigDocente = useMemo(() => {
    if (!selectedDoc) return [];
    return catedras.flatMap(c => (c.asignaciones || []).filter(a => a.docente?.id === selectedDoc.id).map(a => ({...a, cat_codigo: c.codigo, cat_nombre: c.nombre})));
  }, [selectedDoc, catedras]);

  // Find assigned class at a specific dia+hora
  const asigEnCelda = (dia, hora) => asigDocente.find(a => a.dia === dia && a.hora_inicio === hora);

  return (
    <div className="p-8">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-slate-800">🕐 Disponibilidad y Asignaciones</h2>
        <p className="text-slate-500 text-sm">Marcá disponibilidad (verde) y visualizá las cátedras asignadas (azul) en formato calendario.</p>
      </div>
      <div className="grid grid-cols-4 gap-6">
        <div className="col-span-1">
          <input type="text" placeholder="Buscar docente..." className="w-full border rounded-lg px-3 py-2 text-sm mb-3"
            value={buscar} onChange={e => setBuscar(e.target.value)} />
          <div className="bg-white rounded-xl border max-h-96 overflow-y-auto">
            {docsFiltrados.map(d => (
              <div key={d.id} onClick={() => seleccionar(d)}
                className={`p-3 border-b cursor-pointer hover:bg-amber-50 ${selectedDoc?.id === d.id ? 'bg-amber-100 font-medium' : ''}`}>
                <p className="text-sm">{d.nombre} {d.apellido}</p>
                <p className="text-xs text-slate-400">{d.horas_asignadas || 0}h — {d.asignaciones?.length || 0} cátedras</p>
              </div>
            ))}
          </div>
        </div>
        <div className="col-span-3">
          {!selectedDoc ? (
            <div className="bg-slate-50 rounded-xl p-12 text-center text-slate-400">← Seleccioná un docente</div>
          ) : loading ? (
            <div className="text-center p-8">⏳ Cargando...</div>
          ) : (
            <div>
              <div className="flex justify-between items-center mb-4">
                <div>
                  <h3 className="font-bold text-lg">{selectedDoc.nombre} {selectedDoc.apellido}</h3>
                  <p className="text-sm text-slate-500">🟢 Disponible — 🔵 Cátedra asignada — Clic para marcar disponibilidad</p>
                </div>
                <button onClick={guardar} disabled={guardando}
                  className="px-6 py-2 bg-amber-500 text-slate-900 rounded-lg font-medium disabled:opacity-50">
                  {guardando ? '⏳...' : '💾 Guardar disponibilidad'}
                </button>
              </div>
              {/* Cátedras asignadas resumen */}
              {asigDocente.length > 0 && (
                <div className="flex flex-wrap gap-2 mb-4 p-3 bg-blue-50 rounded-lg border border-blue-200">
                  <span className="text-xs text-blue-600 font-medium py-1">Cátedras asignadas:</span>
                  {asigDocente.map(a => (
                    <span key={a.id} className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs">
                      {a.cat_codigo} • {a.dia || 'Pend.'} {a.hora_inicio || ''}
                    </span>
                  ))}
                </div>
              )}
              <div className="bg-white rounded-xl border overflow-auto">
                <table className="w-full text-sm">
                  <thead><tr className="bg-slate-800 text-white">
                    <th className="p-2 border-r w-20">Hora</th>
                    {DIAS.map(d => <th key={d} className="p-2 border-r">{d}</th>)}
                  </tr></thead>
                  <tbody>
                    {HORAS.map(hora => (
                      <tr key={hora} className="border-b">
                        <td className="p-2 border-r bg-slate-50 font-medium text-center text-xs">{hora}</td>
                        {DIAS.map(dia => {
                          const disp = isDisponible(dia, hora);
                          const asig = asigEnCelda(dia, hora);
                          return (
                            <td key={dia} className="p-0.5 border-r text-center cursor-pointer select-none"
                              onClick={() => !asig && toggleCelda(dia, hora)}>
                              {asig ? (
                                <div className="rounded py-1.5 bg-blue-500 text-white text-[10px] font-bold px-1">
                                  {asig.cat_codigo}
                                </div>
                              ) : (
                                <div className={`rounded py-1.5 transition-all ${disp ? 'bg-emerald-400 text-white font-bold' : 'bg-slate-100 text-slate-300 hover:bg-slate-200'}`}>
                                  {disp ? '✓' : ''}
                                </div>
                              )}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ==================== EXPORTAR VIEW (v6.0 con desglose) ====================
function ExportarView({ cuatrimestre, cuatrimestres }) {
  const [descargando, setDescargando] = useState(false);
  const descargar = async () => {
    setDescargando(true);
    try {
      const cuatId = cuatrimestre !== 'todos' ? cuatrimestre : '';
      const url = `${API_URL}/api/exportar/horarios${cuatId ? `?cuatrimestre_id=${cuatId}` : ''}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error('Error al generar');
      const blob = await res.blob();
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      const cuatNombre = cuatrimestres.find(c => c.id.toString() === cuatrimestre.toString())?.nombre || 'Todos';
      a.download = `IEA_Horarios_${cuatNombre.replace(/ /g, '_')}.xlsx`;
      a.click();
    } catch (e) { alert('Error: ' + e.message); }
    setDescargando(false);
  };
  return (
    <div className="p-8">
      <h2 className="text-2xl font-bold text-slate-800 mb-6">Exportar</h2>
      <div className="bg-white rounded-xl border p-6 max-w-xl">
        <h3 className="font-semibold mb-2">📊 Exportar Horarios (v6.0)</h3>
        <p className="text-sm text-slate-500 mb-4">
          Excel con una solapa por sede. Incluye columnas de inscriptos total, virtuales y presenciales.
          Cátedras ordenadas por código. Múltiples docentes en filas separadas.
        </p>
        {cuatrimestre !== 'todos'
          ? <p className="text-sm text-amber-600 font-medium mb-4">📅 Se exportará: {cuatrimestres.find(c => c.id.toString() === cuatrimestre.toString())?.nombre}</p>
          : <p className="text-sm text-slate-400 mb-4">💡 Seleccioná un cuatrimestre en el menú para filtrar.</p>}
        <button onClick={descargar} disabled={descargando}
          className="w-full py-3 bg-amber-500 text-slate-900 rounded-lg font-bold disabled:opacity-50 hover:bg-amber-400">
          {descargando ? '⏳ Generando...' : '📥 Descargar Excel'}
        </button>
      </div>
    </div>
  );
}

// ==================== APP PRINCIPAL ====================
export default function App() {
  const [autenticado, setAutenticado] = useState(() => localStorage.getItem('iea_auth') === 'true');
  const [activeView, setActiveView] = useState('dashboard');
  const [cuatrimestre, setCuatrimestre] = useState('todos');
  const [catedras, setCatedras] = useState([]);
  const [cursos, setCursos] = useState([]);
  const [docentes, setDocentes] = useState([]);
  const [sedes, setSedes] = useState([]);
  const [cuatrimestres, setCuatrimestres] = useState([]);
  const [solapamientos, setSolapamientos] = useState([]);
  const [necesitanDocente, setNecesitanDocente] = useState([]);
  const [solapCarrerasCount, setSolapCarrerasCount] = useState(0);
  const [loading, setLoading] = useState(true);

  const cargarDatos = useCallback(async () => {
    const cuatId = cuatrimestre !== 'todos' ? cuatrimestre : null;
    const qParam = cuatId ? `?cuatrimestre_id=${cuatId}` : '';
    try { setSedes(await apiFetch('/api/sedes')); } catch (e) { console.error(e); }
    try { setCuatrimestres(await apiFetch('/api/cuatrimestres')); } catch (e) { console.error(e); }
    try { setCatedras(await apiFetch(`/api/catedras${qParam}`)); } catch (e) { console.error(e); }
    try { setCursos(await apiFetch('/api/cursos')); } catch (e) { console.error(e); }
    try { setDocentes(await apiFetch(`/api/docentes${qParam}`)); } catch (e) { console.error(e); }
    try { setSolapamientos(await apiFetch(`/api/horarios/solapamientos${qParam}`)); } catch (e) { console.error(e); }
    try { setNecesitanDocente(await apiFetch(`/api/catedras/necesitan-docente${qParam}`)); } catch (e) { console.error(e); }
    try { const sc = await apiFetch(`/api/solapamientos-carreras${qParam}`); setSolapCarrerasCount(sc.total || 0); } catch (e) { console.error(e); }
    setLoading(false);
  }, [cuatrimestre]);

  useEffect(() => { if (autenticado) cargarDatos(); }, [cargarDatos, autenticado]);

  if (!autenticado) return <LoginScreen onLogin={() => setAutenticado(true)} />;
  if (loading) return <div className="flex items-center justify-center min-h-screen"><p className="text-xl">⏳ Cargando sistema...</p></div>;

  return (
    <div className="flex min-h-screen bg-slate-100">
      <Sidebar activeView={activeView} setActiveView={setActiveView} cuatrimestre={cuatrimestre}
        setCuatrimestre={setCuatrimestre} sedes={sedes} cuatrimestres={cuatrimestres}
        solapamientosCount={solapamientos.length} necesitanDocenteCount={necesitanDocente.length} solapCarrerasCount={solapCarrerasCount} />
      <main className="flex-1 overflow-auto">
        {activeView === 'dashboard' && <DashboardView cuatrimestre={cuatrimestre} setActiveView={setActiveView} />}
        {activeView === 'catedras' && <CatedrasView catedras={catedras} docentes={docentes} sedes={sedes} cuatrimestre={cuatrimestre} cuatrimestres={cuatrimestres} recargar={cargarDatos} />}
        {activeView === 'cursos' && <CursosView cursos={cursos} sedes={sedes} recargar={cargarDatos} />}
        {activeView === 'inscriptos_curso' && <InscriptosPorCursoView cuatrimestre={cuatrimestre} />}
        {activeView === 'docentes' && <DocentesView docentes={docentes} sedes={sedes} cuatrimestre={cuatrimestre} recargar={cargarDatos} />}
        {activeView === 'decisiones' && <DecisionesView catedras={catedras} cuatrimestre={cuatrimestre} recargar={cargarDatos} />}
        {activeView === 'necesitan_docente' && <NecesitanDocenteView cuatrimestre={cuatrimestre} cuatrimestres={cuatrimestres} />}
        {activeView === 'asincronicas' && <AsincronicasView cuatrimestre={cuatrimestre} />}
        {activeView === 'disponibilidad' && <DisponibilidadView docentes={docentes} catedras={catedras} sedes={sedes} cuatrimestre={cuatrimestre} cuatrimestres={cuatrimestres} recargar={cargarDatos} />}
        {activeView === 'docentes_dia' && <DocentesDiaView catedras={catedras} />}
        {activeView === 'sugerencias' && <SugerenciasArmadoView cuatrimestre={cuatrimestre} />}
        {activeView === 'calendario' && <CalendarioView catedras={catedras} docentes={docentes} sedes={sedes} cuatrimestre={cuatrimestre} />}
        {activeView === 'plan_carrera' && <PlanCarreraView cuatrimestre={cuatrimestre} />}
        {activeView === 'solapamientos' && <SolapamientosView solapamientos={solapamientos} cuatrimestre={cuatrimestre} tab="horarios" />}
        {activeView === 'solap_carreras' && <SolapamientosView solapamientos={solapamientos} cuatrimestre={cuatrimestre} tab="carreras" />}
        {activeView === 'bce_bea' && <BceBeaView catedras={catedras} docentes={docentes} sedes={sedes} cuatrimestre={cuatrimestre} cuatrimestres={cuatrimestres} recargar={cargarDatos} />}
        {activeView === 'control_insc' && <ControlInscripcionesView cuatrimestre={cuatrimestre} />}
        {activeView === 'edi_alumnos' && <EdiAlumnosView cuatrimestre={cuatrimestre} />}
        {activeView === 'importar' && <ImportarView recargar={cargarDatos} cuatrimestres={cuatrimestres} cuatrimestre={cuatrimestre} />}
        {activeView === 'exportar' && <ExportarView cuatrimestre={cuatrimestre} cuatrimestres={cuatrimestres} />}
      </main>
    </div>
  );
}
