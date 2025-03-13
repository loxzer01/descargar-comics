# Scraping de Mangas

Este es un script para descargar capítulos de mangas desde diferentes sitios web de lectura en español.

## Características

- Soporte para múltiples sitios (actualmente funciona con Olympus)
- Descarga automática de imágenes de capítulos
- Opción para generar solo metadatos sin descargar imágenes
- Organización automática en carpetas por manga y capítulo
- Generación de archivos meta.json con información del manga y capítulo

## Requisitos

- Python 3.6 o superior
- Bibliotecas requeridas:
  - requests
  - beautifulsoup4
  - re (estándar)
  - urllib.parse (estándar)
  - json (estándar)
  - os (estándar)

## Instalación

1. Clona este repositorio o descarga los archivos del proyecto
2. Instala las dependencias:

```bash
pip install requests beautifulsoup4
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
├── main.py         # Script principal
├── images/         # Directorio donde se guardan los mangas
│   ├── [nombre_manga]/
│   │   ├── capitulo_[número]/
│   │   │   ├── 00.webp
│   │   │   ├── 01.webp
│   │   │   ├── ...
│   │   │   └── meta.json
└── readme.md       # Este archivo
```

## Formato de meta.json

El archivo `meta.json` contiene la siguiente información:

```json
{
  "manga_name": "Nombre del manga",
  "chapter_name": "Capítulo X",
  "chapter_number": X,
  "total_images": 25,
  "images": [
    {
      "url": "https://ejemplo.com/imagen.webp",
      "number": 1,
      "filename": "00.webp",
      "description": "Descripción de la imagen"
    },
    // más imágenes...
  ]
}
```

## Sitios Soportados

1. Olympus (olympusbiblioteca.com) - Totalmente implementado
2. M440.in - Pendiente de implementar
3. TMO - Pendiente de implementar
4. Imanga - Pendiente de implementar

## Contribuir

Si deseas contribuir a este proyecto, puedes implementar el soporte para los sitios pendientes o mejorar las funcionalidades existentes.