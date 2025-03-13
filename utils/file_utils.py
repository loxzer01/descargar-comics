#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Utilidades para operaciones de archivos y directorios.
"""

import os
import json
import sys
import re

def create_directories():
    """Crea el directorio principal para guardar imágenes si no existe."""
    if not os.path.exists('images'):
        os.mkdir('images')
    return os.path.abspath('images')

def sanitize_filename(filename):
    """Sanitiza el nombre de un archivo eliminando caracteres no válidos."""
    # Eliminar caracteres no permitidos en nombres de archivo
    sanitized = re.sub(r'[\\/*?:"<>|]', "", filename)
    # Reemplazar espacios y puntos con guiones bajos
    sanitized = re.sub(r'[\s.]+', "_", sanitized)
    return sanitized

def create_manga_directory(manga_title):
    """Crea un directorio para un manga específico."""
    images_dir = create_directories()
    manga_dir = os.path.join(images_dir, sanitize_filename(manga_title))
    
    if not os.path.exists(manga_dir):
        os.mkdir(manga_dir)
    
    return manga_dir

def create_chapter_directory(manga_title, chapter_number, chapter_title=None):
    """Crea un directorio para un capítulo específico de un manga."""
    manga_dir = create_manga_directory(manga_title)
    
    # Sanitizar número de capítulo para nombre de directorio
    if isinstance(chapter_number, float) and chapter_number.is_integer():
        chapter_number = int(chapter_number)
    
    # Crear directorio para el capítulo
    chapter_dir_name = f"capitulo_{chapter_number}"
    chapter_dir = os.path.join(manga_dir, chapter_dir_name)
    
    if not os.path.exists(chapter_dir):
        os.mkdir(chapter_dir)
    
    return chapter_dir

def save_metadata(directory, metadata):
    """Guarda la metadata en un archivo JSON."""
    meta_file = os.path.join(directory, 'meta.json')
    with open(meta_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=4)

def download_image(session, url, file_path, headers=None):
    """Descarga una imagen desde una URL y la guarda en el archivo especificado."""
    try:
        if headers is None:
            headers = {}
        
        response = session.get(url, headers=headers, stream=True)
        if response.status_code == 200:
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            return True
        else:
            print(f"Error al descargar imagen: {response.status_code}")
            return False
    except Exception as e:
        print(f"Error al descargar imagen: {str(e)}")
        return False
