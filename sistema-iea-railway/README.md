# Sistema Horarios IEA - Railway Edition

Sistema de planificación de horarios para instituciones educativas.

## Estructura

```
sistema-iea-railway/
├── backend/          # API en Python (FastAPI)
├── frontend/         # Interfaz web (React)
└── README.md
```

## Despliegue en Railway

Ver el documento **Tutorial-Railway-IEA.pdf** para instrucciones paso a paso.

## Servicios necesarios en Railway

1. **PostgreSQL** - Base de datos (añadir desde Railway)
2. **Backend** - API Python/FastAPI
3. **Frontend** - React (servido con serve)

## Variables de entorno

El backend necesita:
- `DATABASE_URL` (se configura automáticamente al vincular PostgreSQL)

El frontend necesita:
- `REACT_APP_API_URL` (URL del backend desplegado)
