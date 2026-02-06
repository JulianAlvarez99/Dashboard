# Estructura de CSS del Dashboard

Esta carpeta contiene todos los archivos CSS del proyecto, organizados por responsabilidad para mantener el código limpio y mantenible.

## Archivos

### 📄 main.css
**Propósito:** Estilos globales y utilidades generales

**Contenido:**
- Utilidades generales (x-cloak, etc.)
- Indicadores HTMX (loading states)
- Animaciones globales (spinner, shimmer, pulse)
- Transiciones
- Scrollbar personalizado
- Toast notifications
- Focus states
- Utilidades responsive

**Cuándo usar:**
- Estilos que se aplican a toda la aplicación
- Animaciones reutilizables
- Configuraciones globales

---

### 📄 components.css
**Propósito:** Componentes reutilizables de la UI

**Contenido:**
- **Sidebar:** Navegación lateral con estilos para items activos
- **Header:** Barra superior con acciones y breadcrumbs
- **Botones:** Estilos para diferentes tipos de botones (primary, secondary, danger, etc.)
- **Formularios:** Inputs, selects, textareas, labels
- **Toggle switches:** Interruptores on/off
- **Alerts:** Mensajes de error, éxito, advertencia, info
- **Cards:** Tarjetas con header y contenido

**Cuándo usar:**
- Componentes que se reutilizan en múltiples páginas
- Elementos de UI consistentes en toda la aplicación

---

### 📄 login.css
**Propósito:** Estilos específicos de la página de login

**Contenido:**
- Layout del login (contenedor centrado)
- Branding (logo, título, subtítulo)
- Tarjeta de login
- Campos de formulario con iconos
- Botón de submit con estados loading
- Mensajes flash
- Footer y dev hints

**Cuándo usar:**
- Solo en la página de autenticación
- Estilos únicos del login que no se usan en otros lugares

---

### 📄 dashboard.css
**Propósito:** Estilos del dashboard principal

**Contenido:**
- **Layout:** Estructura principal del dashboard
- **Panel de filtros:** Container y header de filtros
- **Filtros individuales:** Daterange, dropdown, multiselect, toggle, text, select buttons, number
- **Grid de widgets:** Configuración responsive del grid
- **Widgets:** Cards de widgets con loading states
- **Estados vacíos:** Mensajes cuando no hay datos
- **Error alerts:** Alertas de configuración
- **Responsive:** Ajustes para móviles

**Cuándo usar:**
- En la página principal del dashboard
- Componentes específicos de visualización de datos

---

## Convenciones de Nomenclatura

### Clases de Componentes
```css
.component-name { }           /* Componente base */
.component-name-element { }   /* Elemento dentro del componente */
.component-name.modifier { }  /* Modificador del componente */
```

### Ejemplos
```css
/* Sidebar */
.sidebar { }
.sidebar-header { }
.sidebar-nav { }
.sidebar-nav-item { }
.sidebar-nav-item.active { }

/* Filtros */
.filter-item { }
.filter-label { }
.filter-select { }
.filter-daterange { }
.filter-daterange-container { }
```

---

## Soporte de Modo Oscuro

Todos los estilos incluyen soporte para modo oscuro mediante la clase `.dark`:

```css
.component {
    background-color: white;
}

.dark .component {
    background-color: #1f2937;
}
```

---

## Uso en HTML

### Importar CSS en las plantillas

**base.html** (plantilla base):
```html
<link rel="stylesheet" href="{{ url_for('static', filename='css/main.css') }}">
<link rel="stylesheet" href="{{ url_for('static', filename='css/components.css') }}">
```

**login.html** (página de login):
```html
<link rel="stylesheet" href="{{ url_for('static', filename='css/main.css') }}">
<link rel="stylesheet" href="{{ url_for('static', filename='css/login.css') }}">
```

**dashboard/index.html** (dashboard principal):
```html
{% block extra_head %}
<link rel="stylesheet" href="{{ url_for('static', filename='css/dashboard.css') }}">
{% endblock %}
```

---

## Ventajas de esta Estructura

✅ **Separación de responsabilidades:** Cada archivo tiene un propósito claro
✅ **Mantenibilidad:** Es fácil encontrar y modificar estilos específicos
✅ **Reutilización:** Los componentes pueden usarse en cualquier parte
✅ **Performance:** Solo cargar los CSS necesarios por página
✅ **Escalabilidad:** Agregar nuevos estilos es simple y organizado
✅ **DRY:** No repetir código de estilos

---

## Migración desde Tailwind Inline

Hemos migrado de clases Tailwind inline a CSS custom por las siguientes razones:

1. **Mejor organización:** Estilos centralizados en lugar de dispersos en HTML
2. **Nombres semánticos:** `.sidebar-nav-item` es más claro que `flex items-center px-4 py-3...`
3. **Mantenimiento:** Cambiar un estilo en un solo lugar en vez de buscar en todos los HTML
4. **Reusabilidad:** Componentes con nombres claros que pueden reutilizarse
5. **Menos HTML:** Templates más limpios y legibles

---

## Compatibilidad

- ✅ Tailwind CSS (CDN) sigue disponible para utilidades adicionales
- ✅ Dark mode con clase `.dark` en el elemento `<html>`
- ✅ Responsive design con media queries
- ✅ Compatible con Alpine.js y HTMX

---

## Guía de Estilo

### Colores Principales
- **Primary:** `#3b82f6` (azul)
- **Secondary:** `#64748b` (gris)
- **Success:** `#10b981` (verde)
- **Danger:** `#ef4444` (rojo)
- **Warning:** `#f59e0b` (amarillo)
- **Info:** `#3b82f6` (azul)

### Espaciado
- Padding interno de componentes: `1.5rem` (24px)
- Gap entre elementos: `1rem` (16px)
- Border radius: `0.5rem` (8px)

### Tipografía
- Font base: Sistema (inherit)
- Títulos: `font-weight: 600`
- Labels: `font-size: 0.875rem` (14px)

---

## Troubleshooting

### Los estilos no se aplican
1. Verificar que el archivo CSS está en `/app/static/css/`
2. Comprobar que la ruta en el `<link>` es correcta
3. Limpiar caché del navegador (Ctrl+F5)
4. Verificar que Flask está sirviendo archivos estáticos

### Conflictos con Tailwind
- Las clases custom tienen prioridad sobre Tailwind
- Usar clases custom para componentes principales
- Tailwind para utilidades puntuales (ej: `mt-4`, `flex`, etc.)

### Modo oscuro no funciona
- Verificar que el `<html>` tiene la clase `dark`
- Usar Alpine.js para toggle: `@click="darkMode = !darkMode; $el.closest('html').classList.toggle('dark')"`

---

## Próximos Pasos

Para continuar mejorando:

1. ✅ Separar estilos de widgets específicos
2. ✅ Crear variables CSS para colores y spacing
3. ✅ Documentar patrones de diseño comunes
4. ✅ Agregar ejemplos de uso en Storybook
5. ✅ Optimizar para producción (minificación)
