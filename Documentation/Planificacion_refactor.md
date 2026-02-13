# Planificación Arquitectónica V2.0 — Camet Analytics

**Descripción:** Esta es la hoja de ruta detallada para la refactorización completa del SaaS de monitoreo industrial. El objetivo principal es lograr una arquitectura altamente escalable, basada en plugins (Registry Pattern), con control estricto de memoria (Data Scoping) y un intermediario inteligente de datos (Data Broker). Todo optimizado para un entorno de hosting compartido en cPanel.

---

## 🏗️ Nuevos Paradigmas Arquitectónicos

Antes de iniciar con las etapas de desarrollo, el sistema se regirá por tres principios inquebrantables:

1. **Registry Pattern (Cero Acoplamiento):** Eliminación total de diccionarios de mapeo gigantes o sentencias condicionales largas para definir qué filtro o widget usar. La base de datos almacenará el nombre exacto de la clase o función a instanciar, y el sistema la cargará dinámicamente mediante reflexión/introspección.
2. **Data Scoping (Eficiencia de Memoria):** Los widgets son consumidores estrictos. Exigirán exactamente qué columnas del DataFrame Maestro o qué datos externos necesitan. Nunca se enviará un DataFrame completo si un widget solo grafica dos variables.
3. **Data Broker (Aislamiento de Fuentes):** Ningún widget sabrá cómo ir a buscar sus datos. Una capa intermedia (el Orquestador de Datos) leerá el origen del widget (interno de MySQL o externo de una API) y le entregará la información ya recolectada.

---

## 📦 ETAPA 1: Fundaciones Core, Autenticación y Caché (La Infraestructura Base)

**Objetivo:** Establecer la base dual del proyecto garantizando que las consultas repetitivas no golpeen la base de datos de cPanel.

* **Fase 1.1: Setup Dual-Server**
* Configurar el punto de entrada principal para lanzar FastAPI (Motor de Datos) y Flask (Renderizado SSR) como hilos/procesos independientes compatibles con WSGI/ASGI.


* **Fase 1.2: DatabaseManager Optimizado**
* Implementar el gestor de base de datos multi-tenant utilizando una estrategia sin pooling (`NullPool`) para evitar agotar las conexiones limitadas de cPanel.


* **Fase 1.3: Autenticación y Seguridad**
* Replicar el sistema de login seguro usando Argon2.
* Implementar control de sesión híbrido (Server-side en Flask, validación JWT en FastAPI).


* **Fase 1.4: Metadata Cache Singleton**
* Desarrollar el servicio que, al iniciar la aplicación o al detectar un inicio de sesión de un tenant nuevo, cargue toda la configuración estática en memoria RAM (Líneas, Áreas, Productos, Turnos).



---

## 🎛️ ETAPA 2: Motor de Filtros Dinámicos (Patrón Registry)

**Objetivo:** Simplificar la creación y renderizado de filtros. Cada filtro será un módulo independiente.

* **Fase 2.1: Interfaz Base de Filtros (`BaseFilter`)**
* Definir la estructura obligatoria para todo filtro, incluyendo los métodos de validación de entrada del usuario, la recolección de opciones estáticas, y la generación de fragmentos de SQL.


* **Fase 2.2: Implementación de Filtros Concretos**
* Crear clases independientes para cada tipo (Ej: `FiltroFechas`, `FiltroDropdownMulti`, `FiltroToggle`).


* **Fase 2.3: Inyección desde Caché**
* Conectar las clases de los filtros dinámicos (como la lista de productos o líneas) directamente con el `MetadataCache` para que sus opciones de selección se generen en microsegundos sin consultas a MySQL.


* **Fase 2.4: Auto-Registro de Filtros**
* Configurar el motor para que lea la tabla `Filters` y, utilizando el nombre de la clase allí guardado, instancie dinámicamente el filtro correspondiente para el usuario actual.



---

## ⚙️ ETAPA 3: Extracción de Datos Internos (El Data Lake Local)

**Objetivo:** Aislar la obtención y cruzamiento de los datos nativos de la planta de producción.

* **Fase 3.1: Constructor de Consultas Dinámico (Query Builder)**
* Desarrollar el generador de sentencias SQL que consolide todos los fragmentos creados por los filtros activados por el usuario.
* Mantener el soporte automatizado para el ruteo de particiones mensuales.


* **Fase 3.2: Extracción y Conversión**
* Ejecutar la consulta en las tablas de detecciones de la línea seleccionada y convertir la respuesta cruda en un DataFrame base de Pandas de alta velocidad.


* **Fase 3.3: Application-Side Joins (Enriquecimiento)**
* Tomar el DataFrame base y cruzarlo en memoria (Python-side) con el `MetadataCache` para inyectar nombres legibles, códigos de producto, áreas y pesos, formando así el "DataFrame Maestro".



---

## 🌐 ETAPA 4: Data Broker y APIs Externas (El Orquestador de Fuentes)

**Objetivo:** Crear una capa intermedia inteligente que controle de dónde proviene la información, permitiendo combinar datos de los sensores de la planta con APIs de terceros.

* **Fase 4.1: Archivo de Configuración Externo (`external_apis.yml`)**
* Crear el manifiesto YAML que define las URLs base, los métodos HTTP admitidos, los tiempos máximos de espera (timeouts) y los nombres de las variables de entorno que guardan los tokens de seguridad para cada API externa (ERP, Clima, Cotizaciones, etc.).


* **Fase 4.2: Cliente HTTP Asíncrono (`ExternalAPIService`)**
* Implementar un servicio centralizado basado en un cliente no bloqueante que consuma las APIs del archivo YAML, con un manejo estricto de errores para evitar que una caída externa cuelgue el dashboard interno.


* **Fase 4.3: Implementación del Data Broker**
* Construir el enrutador lógico que determine el proveedor de datos.
* Establecer la lógica de evaluación: Si un widget indica fuente "interna", se le asigna el DataFrame Maestro. Si indica fuente "externa", dispara la solicitud asíncrona a la API correspondiente.



---

## 📊 ETAPA 5: Motor de Widgets Independientes (Data Scoping y Registry)

**Objetivo:** Transformar los widgets en componentes tontos pero altamente eficientes, ignorantes del origen general de los datos.

* **Fase 5.1: Interfaz Base de Widgets (`BaseWidget`)**
* Definir la clase madre que obligue a especificar la fuente de datos (`source_type = 'internal' | 'external'`).
* Obligar la implementación del método de requerimientos (ej. `required_columns` para datos internos o `required_api_id` para externos).


* **Fase 5.2: Procesador de Formato (`process_data`)**
* Establecer el método donde ocurre la magia algorítmica. Este método recibe datos recortados (Data Scoping) y debe devolver únicamente la estructura JSON (diccionario) formateada lista para Chart.js o el renderizador HTML.


* **Fase 5.3: Creación del Catálogo y Auto-Registro**
* Implementar las clases concretas de cada widget (KPIs, Líneas, Barras) e instruir al motor para que las invoque dinámicamente según lo indicado en la tabla `Widget_catalog`.



---

## 🎼 ETAPA 6: El Orquestador Principal (Dashboard Execution Workflow)

**Objetivo:** Construir la "gran vía" que une todas las etapas anteriores en una única solicitud de red eficiente al presionar "Aplicar Filtros".

* **Fase 6.1: Recepción y Validación**
* El endpoint maestro recibe el diccionario de opciones elegidas por el usuario.
* Valida las selecciones utilizando las reglas del Motor de Filtros (Etapa 2).


* **Fase 6.2: Construcción del Contexto de Datos**
* Dispara el Query Builder y enriquece los datos internos (Etapa 3) para crear el DataFrame Maestro.


* **Fase 6.3: Ruteo del Data Broker**
* Lee la configuración del layout del usuario para saber qué widgets se van a renderizar.
* Pasa la lista de widgets al Data Broker (Etapa 4) para que recolecte, paralelamente si es posible, la información externa necesaria y recorte el DataFrame Maestro según el requerimiento exacto de cada widget interno.


* **Fase 6.4: Ejecución y Ensamblaje**
* Invoca el método `process_data` de cada widget instanciado con su fragmento de información correspondiente.
* Empaqueta todas las respuestas de los widgets en un único gran diccionario JSON estructurado y lo retorna a la capa de presentación.



---

## 🖥️ ETAPA 7: Capa de Presentación (Frontend Dinámico con Flask y HTMX)

**Objetivo:** Mantener el frontend ligero (Driven Configuration). El navegador renderiza exactamente lo que el backend ordena.

* **Fase 7.1: Renderizado Inicial y Panel de Filtros**
* Al hacer Login, Flask consulta al backend por la configuración base y utiliza plantillas Jinja2 para pintar la estructura general.
* Utilizar Alpine.js para gestionar el estado local del formulario de filtros y preconfigurar fechas.


* **Fase 7.2: Ciclo de Interactividad HTMX**
* Configurar el formulario principal para interceptar el botón "Aplicar Filtros" enviando una petición asíncrona POST vía HTMX al orquestador (Etapa 6).


* **Fase 7.3: Inyección de Partials y Chart.js**
* Procesar la respuesta del backend, que entregará fragmentos HTML (partials) con las tarjetas KPI y lienzos `<canvas>` con sus atributos `x-data` actualizados.
* Hacer que Alpine.js reaccione a los nuevos fragmentos y dibuje (o redibuje) los gráficos con la librería Chart.js de forma suave y sin parpadeos completos de pantalla.



---

## 🛡️ ETAPA 8: Tareas en Segundo Plano, Seguridad y Despliegue

**Objetivo:** Finalizar la arquitectura de grado de producción asegurando el mantenimiento continuo de la aplicación sin intervención humana.

* **Fase 8.1: Trabajos en Segundo Plano (APScheduler)**
* Codificar la lógica de "Gap Analysis" (algoritmo de paradas) y mantenimientos de base de datos (particionamiento mensual) en tareas asíncronas aisladas de los hilos web principales.


* **Fase 8.2: Capas de Seguridad Crítica**
* Configurar e inyectar validaciones CSRF nativas.
* Aplicar Rate Limiting inteligente y sanitización de encabezados usando los estándares OWASP.


* **Fase 8.3: Optimización para Entorno de Hosting (cPanel)**
* Configurar el script adaptador `passenger_wsgi.py` para enganchar correctamente el hilo de Flask y FastAPI con Apache/LiteSpeed.
* Establecer una estricta política de recolección de basura (Garbage Collection) en la capa de datos de Pandas para evitar que los workers agoten el límite de RAM del hosting compartido tras consultas masivas.