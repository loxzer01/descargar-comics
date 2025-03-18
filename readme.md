# Vesion Local
## Instalación
1. Clona el repositorio o descarga los archivos del proyecto.
2. Instala las dependencias necesarias. Puedes hacerlo utilizando `pip`:
```bash
pip install -r requirements.txt
```

## Uso
1. Ejecuta el script principal:
```bash
python main.py # para descargar las imagenes
python strapi_upload.py # para subir las imagenes a strapi
```


# Scraping de Mangas

Este es un script para descargar capítulos de mangas desde diferentes sitios web de lectura en español.

## Características

- Soporte para múltiples sitios (actualmente funciona con Olympus, M440.in e Inmanga)
- Descarga automática de imágenes de capítulos
- Opción para generar solo metadatos sin descargar imágenes
- Organización automática en carpetas por manga y capítulo
- Generación de archivos meta.json con información del manga y capítulo
- Descarga de capítulos consecutivos
- Descarga de rangos específicos de capítulos
- Soporte para sitios que utilizan JavaScript para cargar contenido (mediante Playwright)

## Requisitos

- Python 3.6 o superior
- Bibliotecas requeridas:
  - requests
  - beautifulsoup4
  - playwright
  - re (estándar)
  - urllib.parse (estándar)
  - json (estándar)
  - os (estándar)
  - asyncio (estándar)

## Instalación

1. Clona este repositorio o descarga los archivos del proyecto
2. Instala las dependencias:

```bash
pip install requests beautifulsoup4 playwright
```

3. Instala los navegadores necesarios para Playwright:
```bash
python -m playwright install
 ```
## Uso

1. Ejecuta el script principal:

```bash
python main.py
```

2. Sigue las instrucciones en la consola:
   - Selecciona el sitio de origen del manga (1-4)
   - Proporciona la URL del capítulo que deseas descargar
   - Elige si deseas descargar las imágenes o solo generar el archivo meta.json


## Estructura del Proyecto

```
scrapping-scan/
├── main.py                # Script principal
├── scrapers/              # Módulos específicos para cada sitio
│   ├── m440.py            # Scraper para M440.in
│   ├── m440_scraper.py    # Implementación de scraping para M440.in
│   ├── inmanga_scraper.py # Scraper para Inmanga
│   └── ...
├── utils/                 # Utilidades comunes
│   ├── file_utils.py      # Funciones para manejo de archivos
│   ├── http_utils.py      # Funciones para peticiones HTTP
│   └── ...
├── images/                # Directorio donde se guardan los mangas
│   ├── [nombre_manga]/
│   │   ├── capitulo_[número]/
│   │   │   ├── 001.jpg
│   │   │   ├── 002.jpg
│   │   │   ├── ...
│   │   │   └── meta.json
└── readme.md              # Este archivo
```

## Formato de meta.json

El archivo `meta.json` contiene la siguiente información:

```json
{
  "manga_title": "Nombre del manga",
  "chapter_number": X,
  "image_count": 25,
  "images": [
    {
      "url": "https://ejemplo.com/imagen.jpg",
      "number": 1,
      "filename": "001.jpg"
    },
    // más imágenes...
  ],
  "urls": [
    "https://ejemplo.com/imagen1.jpg",
    "https://ejemplo.com/imagen2.jpg",
    // más URLs...
  ]
}
```


## Sitios Soportados

1. Olympus (olympusbiblioteca.com) - Totalmente implementado
   - Descarga de capítulos individuales
   - Descarga de capítulos consecutivos
2. M440.in - Totalmente implementado
   - Descarga de capítulos individuales
   - Descarga de rangos específicos de capítulos
   - Soporte para contenido cargado con JavaScript (mediante Playwright)
3. Inmanga - Totalmente implementado
   - Descarga de capítulos individuales
   - Descarga de capítulos consecutivos
4. TMO - Pendiente de implementar


## Características Avanzadas

- Descarga de rangos de capítulos : Para M440.in, puedes especificar un rango de capítulos a descargar (ejemplo: 1-10)
- Descarga de capítulos consecutivos : Para Olympus e Inmanga, puedes descargar automáticamente un número específico de capítulos consecutivos
- Soporte para JavaScript : Utiliza Playwright para sitios que cargan el contenido dinámicamente con JavaScript


## Contribuir

Si deseas contribuir a este proyecto, puedes implementar el soporte para los sitios pendientes o mejorar las funcionalidades existentes