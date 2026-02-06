# 📊 Dashboard SaaS Industrial

Plataforma multi-tenant de monitoreo industrial en tiempo real, diseñada para visualizar métricas de producción, calcular KPIs (OEE) y gestionar paradas de línea de manera eficiente y escalable.

---

## 🏗️ Arquitectura del Sistema

El sistema utiliza una arquitectura **Multi-Tenant con Bases de Datos Aisladas** para garantizar la seguridad y separación de datos entre clientes.

### Estructura de Base de Datos
1.  **DB Global (`camet_global`):**
    *   Gestiona la autenticación centralizada, tenants (clientes), usuarios y permisos.
    *   Almacena el catálogo maestro de widgets (`WIDGET_CATALOG`) y templates de dashboard.
2.  **DB Cliente (`dashboard_client_{id}`):**
    *   Base de datos independiente para cada cliente.
    *   Contiene la configuración específica de planta (`PRODUCTION_LINE`, `AREA`, `PRODUCT`).
    *   Almacena datos masivos de sensores (`DETECTION_LINE_X`) particionados mensualmente.

### Diagrama de Flujo de Datos
```mermaid
graph TD
    User[Usuario] -->|Login| Auth[Auth Service (JWT)]
    Auth -->|Valida| GlobalDB[(DB Global)]
    User -->|Consulta Datas| API[FastAPI Backend]
    API -->|Lee Config| Cache[In-Memory Metadata Cache]
    API -->|Query Optimizado| ClientDB[(DB Cliente)]
    ClientDB -->|Raw Data| PartitionManager[Partition Manager]
    Cache -.->|Enriquece Data| API
    API -->|JSON/HTML| Frontend[Dashboard UI]
```

---

## 🛠️ Stack Tecnológico

Seleccionado para maximizar rendimiento en entornos con recursos limitados (hosting cPanel compartido).

### Backend
*   **Lenguaje:** Python 3.11+
*   **API Framework:** **FastAPI** (Alto rendimiento, Async I/O).
*   **SSR Framework:** **Flask** (Renderizado de templates Jinja2).
*   **ORM:** **SQLAlchemy 2.0** (Asyncio, prevención de inyección SQL).
*   **Base de Datos:** **MySQL 8.0** (InnoDB, Particionamiento).
*   **Validación:** **Pydantic v2** (Schemas robustos y serialización).
*   **Task Runner:** **APScheduler** (Tareas en segundo plano: cálculo de paradas, mantenimiento de particiones).

### Frontend
*   **Templating:** **Jinja2** (Renderizado servidor).
*   **Interactividad:** **HTMX** (AJAX declarativo sin complexidad de SPA).
*   **Lógica UI:** **Alpine.js** (Micro-interacciones cliente).
*   **Estilos:** **Tailwind CSS** (Utility-first CSS).
*   **Gráficos:** **Chart.js** (Visualización de datos).

### Seguridad
*   **Hashing:** **Argon2** (Resistente a ataques GPU).
*   **Auth:** **JWT** (Access + Refresh Tokens con rotación).
*   **Protección:** Rate Limiting, CSRF, Headers OWASP.

---

## 🚀 Estrategias de Implementación Clave

### 1. Application-Side Joins & Caching
En lugar de realizar costosos `JOIN` en la base de datos entre tablas masivas de detecciones y tablas de configuración, implementamos:
*   **Metadata Cache:** Carga toda la configuración (Productos, Áreas, Líneas) en memoria al inicio.
*   **Enriquecimiento en Python:** Los IDs de las detecciones se cruzan con el caché en la capa de aplicación.
*   **Ventaja:** Reduce drásticamente la carga de CPU en MySQL y permite respuestas en milisegundos.

### 2. Particionamiento Mensual Automático
Las tablas de detecciones (`DETECTION_LINE_X`) crecen en millones de registros por año.
*   **Estrategia:** Particionamiento `RANGE` por mes.
*   **Partition Manager:** Clase automatizada que crea particiones futuras y elimina las antiguas (retención).
*   **Query Pruning:** El `DetectionQueryBuilder` inyecta hints SQL para que MySQL lea *solo* las particiones necesarias según el filtro de fecha.

### 3. Configuración sobre Código (Configuration-Driven)
El sistema actúa como un motor genérico.
*   **UI Dinámica:** Los filtros y widgets se renderizan leyendo la configuración de la base de datos del cliente.
*   **Escalabilidad:** Agregar un nuevo cliente no requiere cambios en el código, solo configuración de base de datos.

---

## ⚠️ Limitaciones y Restricciones

El diseño respeta las restricciones de un entorno de hosting compartido (cPanel):
*   **Sin Redis:** El caché es en memoria (`MetadataCache` implementado con `asyncio.Lock`).
*   **Sin Docker en Prod:** Despliegue tradicional basado en entorno virtual Python.
*   **Recursos Finitos:** Optimización agresiva de consultas y uso de memoria.
*   **MySQL 8.0:** Uso de características estándar disponibles en la mayoría de hostings.

---

## ✅ Funcionalidades Implementadas

### Backend Core
- [x] Arquitectura Multi-tenant completa con separación de bases de datos
- [x] Sistema de Autenticación JWT con refresh tokens
- [x] Autorización basada en roles (RBAC): SUPER_ADMIN, ADMIN, MANAGER, OPERATOR, VIEWER
- [x] Gestión completa de Usuarios y Tenants
- [x] Sistema de auditoría automática (AUDIT_LOG, USER_LOGIN, USER_QUERY)

### Gestión de Datos y Performance
- [x] **PartitionManager:** Gestión automática de particiones mensuales en MySQL
- [x] **DetectionService:** Ingesta y consulta optimizada de detecciones
- [x] **QueryBuilder Dinámico:** Construcción de SQL con hints de partición
- [x] **MetadataCache:** Sistema de caché en memoria thread-safe con asyncio.Lock
- [x] **Application-Side Joins:** Enriquecimiento de datos en Python

### Motor de Paradas (Downtime Engine)
- [x] Detección automática de paradas por gap analysis
- [x] Cálculo incremental basado en último detection_id procesado
- [x] Soporte para paradas manuales con justificación
- [x] APScheduler para cálculo automático cada 15 minutos
- [x] Persistencia en tablas DOWNTIME_EVENTS_X

### Métricas y OEE
- [x] Cálculo completo de OEE (Disponibilidad × Rendimiento × Calidad)
- [x] Agregaciones por hora, turno, día, semana y mes
- [x] Análisis de pérdidas de tiempo operativo
- [x] Comparaciones entre líneas y períodos

### Motor de Widgets y Dashboards
- [x] Sistema de widgets dinámico basado en WIDGET_CATALOG
- [x] 10+ tipos de widgets: KPI cards, gráficos (línea, barras, pie), tablas
- [x] Validación automática de parámetros con JSON Schema
- [x] Dashboard templates personalizados por rol
- [x] Sistema de filtros dinámicos configurables

### API REST (FastAPI)
- [x] `/api/v1/auth/*`: Login, Logout, Refresh, Change Password
- [x] `/api/v1/users/*`: CRUD completo de usuarios
- [x] `/api/v1/tenants/*`: Gestión de tenants (activate/deactivate)
- [x] `/api/v1/production/*`: Líneas, áreas, productos, turnos
- [x] `/api/v1/data/detections/*`: Consultas con filtros avanzados
- [x] `/api/v1/data/production/*`: Resúmenes y agregaciones
- [x] `/api/v1/downtime/*`: Gestión y cálculo de paradas
- [x] `/api/v1/metrics/*`: KPIs, OEE y comparaciones
- [x] `/api/v1/dashboard/*`: Widgets y layouts dinámicos
- [x] `/api/v1/system/*`: Health checks, versión, estadísticas

### Frontend SSR (Flask + HTMX)
- [x] Sistema de autenticación con sesiones
- [x] Dashboard principal con widgets dinámicos
- [x] Panel de filtros con validación en tiempo real
- [x] Visualización con Chart.js (gráficos interactivos)
- [x] Diseño responsive con Tailwind CSS
- [x] Modo oscuro por defecto
- [x] Componentes reutilizables (sidebar, header, cards)
- [x] HTMX para actualizaciones parciales sin recargar página
- [x] Alpine.js para lógica reactiva del cliente

### Seguridad (OWASP Compliant)
- [x] Hashing Argon2 (resistente a ataques GPU)
- [x] Rate limiting por IP y endpoint
- [x] Protección CSRF con Flask-WTF
- [x] Security headers (X-Frame-Options, CSP, etc.)
- [x] Sanitización de inputs con validación Pydantic
- [x] Prevención de SQL Injection (ORM parametrizado)
- [x] XSS protection en templates Jinja2

### Background Tasks
- [x] APScheduler configurado para tareas programadas
- [x] Cálculo automático de paradas cada 15 minutos
- [x] Mantenimiento de particiones (creación y limpieza)
- [x] Gestión de logs con rotación automática

### Scripts de Utilidad
- [x] `init_db.py`: Inicialización de bases de datos
- [x] `create_tenant.py`: Creación de nuevos tenants
- [x] `create_user.py`: Gestión de usuarios por CLI
- [x] `seed_data.py`: Datos de prueba
- [x] `seed_filters.py`: Población de filtros dinámicos
- [x] `seed_widget_catalog.py`: Catálogo de widgets
- [x] `test_*.py`: Suite de pruebas de integración

---

## 🔮 Roadmap Futuro

### Mejoras Pendientes
- [ ] Retención de datos históricos con archivado automático
- [ ] Autenticación de dos factores (2FA/TOTP)
- [ ] Exportación avanzada de reportes en PDF
- [ ] Sistema de alertas y notificaciones por email
- [ ] Soporte multi-planta para comparaciones globales
- [ ] WebSocket para actualizaciones en tiempo real
- [ ] Machine Learning para predicción de paradas
- [ ] API pública con rate limiting por API key

### Optimizaciones Futuras
- [ ] Implementar Redis para caché distribuido (si disponible)
- [ ] Lazy loading de widgets pesados
- [ ] Compresión de datos históricos
- [ ] Query caching con TTL configurable

---

**Estado del Proyecto:** ✅ Producción
**Última Actualización:** 30 Enero 2026
**Versión:** 1.0.0
