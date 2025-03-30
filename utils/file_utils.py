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

def create_chapter_directory(manga_title, chapter_number, chapter_title=None, force_new=False):
    """Crea un directorio para un capítulo específico de un manga.
    
    Args:
        manga_title: Título del manga
        chapter_number: Número del capítulo
        chapter_title: Título del capítulo (opcional)
        force_new: Si es True, crea un nuevo directorio sin preguntar
        
    Returns:
        str: Ruta al directorio del capítulo
    """
    manga_dir = create_manga_directory(manga_title)
    
    # Sanitizar número de capítulo para nombre de directorio
    # Solo convertir a entero si es un número entero (sin parte decimal)
    if isinstance(chapter_number, float) and chapter_number.is_integer():
        chapter_number = int(chapter_number)
    
    # Crear directorio para el capítulo
    chapter_dir_name = f"capitulo_{chapter_number}"
    chapter_dir = os.path.join(manga_dir, chapter_dir_name)
    
    # Verificar si el directorio ya existe
    if os.path.exists(chapter_dir):
        # Verificar si hay contenido en el directorio
        has_content = len(os.listdir(chapter_dir)) > 0
        
        if has_content and not force_new:
            # Preguntar al usuario qué hacer
            action = input(f"El directorio para {manga_title} - Capítulo {chapter_number} ya existe. ¿Qué deseas hacer?\n"
                          f"1. Usar el directorio existente\n"
                          f"2. Sobreescribir (eliminar contenido actual)\n"
                          f"Selecciona una opción (1/2): ")
            
            if action == "2":
                # Eliminar archivos existentes (excepto meta.json para preservar metadatos)
                for item in os.listdir(chapter_dir):
                    if item != "meta.json":
                        item_path = os.path.join(chapter_dir, item)
                        if os.path.isfile(item_path):
                            os.remove(item_path)
                print(f"Contenido del directorio {chapter_dir} eliminado para sobreescribir.")
            else:
                print(f"Usando directorio existente: {chapter_dir}")
    else:
        # Crear directorio si no existe
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
