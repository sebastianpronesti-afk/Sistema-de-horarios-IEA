export function choosePeriod(periods,saved,today=new Date()){
  if(periods.some(p=>String(p.id)===saved))return saved;
  const active=periods.filter(p=>p.activo);
  if(active.length===1)return String(active[0].id);
  const current=periods.find(p=>Number(p.anio)===today.getFullYear()&&Number(p.numero)===(today.getMonth()<6?1:2));
  if(current)return String(current.id);
  // Do not silently choose an unrelated academic period.
  return periods.length===1?String(periods[0].id):'';
}
