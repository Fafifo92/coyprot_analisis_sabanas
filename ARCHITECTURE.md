# Arquitectura del Sistema - Analizador de Llamadas Pro v3.0

Este documento detalla la arquitectura de la plataforma, diseñada como un sistema SaaS Multitenant (multi-inquilino) utilizando **FastAPI** (Python). Responde a la necesidad de evolucionar un script/aplicación local a una arquitectura web robusta, escalable y profesional.

## 1. Visión General de la Arquitectura Web

La aplicación ha sido transformada de un programa de escritorio a una **API Web RESTful (FastAPI)**. Elegir FastAPI (en lugar de Django o C#) permite aprovechar el ecosistema de datos de Python (Pandas, Folium, ReportLab) de forma nativa, ofreciendo un rendimiento asíncrono excepcional.

*   **Frontend:** Interfaz web utilizando Alpine.js y TailwindCSS, interactuando con la API REST.
*   **Backend:** FastAPI manejando la lógica de enrutamiento y autenticación JWT.
*   **Base de Datos:** Relacional (SQLite en desarrollo, PostgreSQL recomendado para producción) manejada vía **SQLAlchemy (ORM)**.
*   **Procesamiento Asíncrono:** **Celery + Redis** para manejar cargas pesadas en segundo plano.

## 2. Plataforma Multitenancy y Sistema de Tokens

El sistema está diseñado para soportar múltiples clientes (inquilinos) de forma segura:

*   **Aislamiento de Datos:** Cada proyecto (`Project`) está vinculado estrictamente a un `owner_id` (Usuario). Todas las consultas en los endpoints (`src/api/routers/projects.py`) filtran por el usuario autenticado, asegurando que nadie pueda ver proyectos ajenos.
*   **Sistema de Cuentas y Tokens:**
    *   **Usuarios Administradores:** Pueden crear y gestionar cuentas de suscripción y auditar el sistema. No consumen tokens.
    *   **Usuarios de Suscripción:** Poseen un saldo (`tokens_balance`). Cada vez que crean un proyecto de análisis, se descuenta un token. Esto permite la asignación manual de uso sin requerir una pasarela de pago.
*   **Gestión por Proyectos:** El flujo de trabajo se divide en "Proyectos". Dentro de un proyecto, un usuario puede subir múltiples archivos Excel/CSV (`ProjectFile`), mapear las columnas a través de la web (reemplazando el diálogo de escritorio) y generar el informe.

## 3. Colas de Procesamiento (Workers)

El análisis de grandes archivos Excel y la generación de informes PDF son tareas intensivas que bloquearían un servidor web tradicional. Para resolver esto, implementamos un patrón de **Cola de Tareas (Task Queue)**:

*   **Celery y Redis:** El trabajo pesado se delega a `src/api/worker/tasks.py`. Cuando un usuario hace clic en "Analizar" o "Generar PDF", la API no realiza el trabajo directamente. En su lugar, pone un mensaje en Redis.
*   **Workers en Segundo Plano:** Un proceso *worker* de Celery recoge el mensaje y realiza el procesamiento (Pandas, geocodificación, ReportLab).
*   **Estado no bloqueante:** El usuario puede seguir navegando, revisando otros proyectos o subiendo archivos mientras su informe se genera en la cola. El estado del proyecto cambia dinámicamente (`QUEUED`, `PROCESSING`, `COMPLETED`).
*   **Fallback Local:** Para entornos de desarrollo en Windows sin Redis, el sistema puede degradar elegantemente usando `threading.Thread` (`CELERY_ENABLED=False`).

## 4. Aplicación de Principios SOLID y Patrones de Diseño

El código base se estructura separando responsabilidades para garantizar mantenibilidad y escalabilidad.

### Single Responsibility Principle (SRP)
*   **Routers (`src/api/routers/`)**: Solo manejan peticiones HTTP (validación de entrada y formato de salida). No contienen lógica de base de datos ni de negocio.
*   **Services (`src/services/`, `src/api/services/`)**: Contienen la lógica de negocio pura (ej. `data_processing_service.py` procesa los dataframes, `security.py` maneja JWT).
*   **Repositories (`src/api/repositories/`)**: Encapsulan toda la lógica de acceso a datos (SQLAlchemy).

### Patrón Repositorio (Repository Pattern)
Implementado en `src/api/repositories/` (ej. `ProjectRepository`, `UserRepository`).
*   Aísla la capa de negocio de la capa de persistencia.
*   Si en el futuro cambiamos de SQLAlchemy a otro ORM, o modificamos la estructura de la tabla, solo modificamos el repositorio; los *routers* y *services* permanecen intactos.

### Inversión de Dependencias (Dependency Injection)
FastAPI utiliza inyección de dependencias intensivamente.
*   Las sesiones de base de datos (`AsyncSession`) y la validación del usuario actual (`get_current_user`) se inyectan en las rutas mediante `Depends()`. Esto facilita enormemente las pruebas unitarias al permitir inyectar bases de datos en memoria (mocking).

## 5. Próximos Pasos Recomendados (Roadmap Arquitectónico)

1.  **Migración a PostgreSQL:** Cambiar SQLite por PostgreSQL para soporte robusto de concurrencia en un entorno Multitenant de producción.
2.  **Despliegue Contenerizado (Docker):** Usar `docker-compose.yml` para desplegar la API, el Worker de Celery, y Redis como microservicios aislados.
3.  **Almacenamiento en la Nube (S3):** Modificar el almacenamiento de `uploads/` local para usar un servicio de objetos como AWS S3 o MinIO, permitiendo escalabilidad horizontal de los nodos de FastAPI.