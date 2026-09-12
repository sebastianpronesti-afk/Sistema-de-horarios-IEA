import React, { createContext, useContext, useEffect, useState } from 'react';

const InstitutionContext = createContext(null);

export function useInstitution() {
  const value = useContext(InstitutionContext);
  if (!value) throw new Error('Falta el perfil institucional');
  return value;
}

export function InstitutionProvider({ children }) {
  const [profile, setProfile] = useState(null);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    setError(false);
    async function load() {
      try {
        const response = await fetch('/api/institucion', { signal: controller.signal });
        if (!response.ok) throw new Error('No se pudo cargar el perfil');
        const data = await response.json();
        if (data.schema_version !== 1 || typeof data.titulo !== 'string' || !data.titulo.trim() ||
            !['minimo_inscriptos_apertura', 'alumnos_por_docente', 'duracion_clase_minutos']
              .every(key => Number.isInteger(data[key]) && data[key] > 0)) {
          throw new Error('Perfil institucional incompatible');
        }
        if (active) {
          document.title = data.titulo;
          setProfile(data);
        }
      } catch (e) {
        if (active) setError(true);
      } finally {
        clearTimeout(timeout);
      }
    }
    load();
    return () => { active = false; clearTimeout(timeout); controller.abort(); };
  }, [attempt]);

  if (error) return (
    <div className="min-h-screen flex items-center justify-center p-8">
      <div role="alert" className="text-center">
        <p>No se pudo cargar la configuración del sistema.</p>
        <button className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg"
          onClick={() => setAttempt(value => value + 1)}>Reintentar</button>
      </div>
    </div>
  );
  if (!profile) return <div role="status" className="min-h-screen flex items-center justify-center">Cargando sistema…</div>;
  return <InstitutionContext.Provider value={profile}>{children}</InstitutionContext.Provider>;
}
