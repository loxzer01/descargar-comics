#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Web scrapping de paginas de leer capitulos de mangas

# Options a mostrar en consola para que el usuario ponga el numero de la opcion
# - Olympus = 1
# - M440.in = 2
# - TMO = 3
# - Imanga = 4

import os
import json
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse, urljoin
import sys
import time

# Importar módulos específicos para cada sitio
from scrapers.m440 import get_m440_chapters as m440_get_chapters_impl
from scrapers.m440_scraper import scrape_m440 as m440_scrape_chapter_impl
from scrapers.m440 import process_chapter_links as m440_process_chapter_links_impl

# Importar utilidades comunes
from utils.file_utils import create_directories, sanitize_filename, create_manga_directory
from utils.file_utils import create_chapter_directory, save_metadata, download_image

# Crear directorio para guardar imágenes si no existe
def create_directories():
    if not os.path.exists("images"):
        os.makedirs("images")

# Función principal para iniciar el proceso
def main():
    create_directories()
    
    print("=== Scraper de Mangas ===")
    print("Selecciona una opción:")
    print("1. Olympus")
    print("2. M440.in")
    print("3. Inmanga")
    print("4. TMO")
    
    option = input("Ingresa el número de la opción: ")
    
    if option == "1":
        url = input("Ingresa la URL del capítulo de Olympus: ")
        download_option = input("¿Deseas descargar las imágenes? (s/n): ").lower()
        download_images = download_option == 's' or download_option == 'si'
        
        # Opción para descargar capítulos consecutivos
        consecutive_option = input("¿Deseas descargar capítulos consecutivos? (s/n): ").lower()
        if consecutive_option == 's' or consecutive_option == 'si':
            num_chapters = input("¿Cuántos capítulos adicionales quieres descargar? (número o 'todos'): ")
            scrape_olympus_consecutive(url, download_images, num_chapters)
        else:
            scrape_olympus(url, download_images)
    elif option == "2":
        url = input("Ingresa la URL del manga en M440.in (URL principal del manga, no de un capítulo específico): ")
        download_option = input("¿Deseas descargar las imágenes? (s/n): ").lower()
        download_images = download_option == 's' or download_option == 'si'
        
        # Obtener lista de capítulos disponibles
        print("Obteniendo lista de capítulos disponibles...")
        chapters = m440_get_chapters_impl(url)
        
        if not chapters:
            print("No se pudo obtener la lista de capítulos. Verifica la URL e intenta nuevamente.")
            return
        
        print(f"Se encontraron {len(chapters)} capítulos disponibles.")
        print(f"Rango disponible: {chapters[0]['number']} - {chapters[-1]['number']}")
        
        # Solicitar rango de capítulos
        range_option = input("Ingresa el rango de capítulos a descargar (ejemplo: 1-10, o 'todos' para descargar todos): ").lower()
        
        start_chapter = 0
        end_chapter = float('inf')
        
        if range_option != 'todos':
            try:
                if '-' in range_option:
                    start_chapter, end_chapter = map(int, range_option.split('-'))
                else:
                    # Si solo se ingresa un número, descargar desde ese capítulo hasta el final
                    start_chapter = int(range_option)
            except ValueError:
                print("Formato de rango incorrecto. Se descargarán todos los capítulos.")
                start_chapter = 0
                end_chapter = float('inf')
        
        # Filtrar capítulos según el rango especificado
        filtered_chapters = [chapter for chapter in chapters if start_chapter <= chapter['number'] <= end_chapter]
        
        if not filtered_chapters:
            print("No hay capítulos en el rango especificado.")
            return
        
        print(f"Se descargarán {len(filtered_chapters)} capítulos.")
        
        # Descargar capítulos
        for idx, chapter in enumerate(filtered_chapters):
            print(f"\n=== Procesando capítulo {chapter['number']} ({idx+1}/{len(filtered_chapters)}): {chapter['url']} ===")
            
            # Añadir una pequeña pausa para no sobrecargar el servidor
            if idx > 0:
                time.sleep(1.5)
            
            m440_scrape_chapter_impl(chapter['url'], download_images)
    elif option == "3":
        url = input("Ingresa la URL del capítulo de Inmanga: ")
        download_option = input("¿Deseas descargar las imágenes? (s/n): ").lower()
        download_images = download_option == 's' or download_option == 'si'
        
        # Opción para descargar capítulos consecutivos
        consecutive_option = input("¿Deseas descargar capítulos consecutivos? (s/n): ").lower()
        if consecutive_option == 's' or consecutive_option == 'si':
            num_chapters = input("¿Cuántos capítulos adicionales quieres descargar? (número o 'todos'): ")
            from scrapers.inmanga_scraper import scrape_inmanga_consecutive
            scrape_inmanga_consecutive(url, download_images, num_chapters)
        else:
            from scrapers.inmanga_scraper import scrape_inmanga
            scrape_inmanga(url, download_images)
    elif option == "4":
        url = input("Ingresa la URL del capítulo de TMO: ")
        # Función para TMO (pendiente de implementar)
        print("Funcionalidad no implementada aún")
    else:
        print("Opción no válida")

"""
    funcionalidad especifica para leer el manga de Olympus
    y scrapearlo. 
"""
def scrape_olympus(url, download_images=True):
    try:
        # Verificar que la URL sea de Olympus
        parsed_url = urlparse(url)
        # if "olympusbiblioteca.com" not in parsed_url.netloc:
        #     print("URL no válida para Olympus")
        #     return
        
        # Obtener el contenido de la página
        response = requests.get(url)
        if response.status_code != 200:
            print(f"Error al acceder a la URL: {response.status_code}")
            return
        
        # Parsear el HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Inicializar variables
        manga_title = "Manga Desconocido"
        chapter_number = 0
        
        # Extraer título del manga - intentar diferentes métodos
        title_element = soup.select_one("h1.text-slate-500.hover\\:text-slate-400")
        if title_element:
            manga_title = title_element.text.strip()
        else:
            # Intentar con otro selector alternativo
            title_element = soup.select_one("div.flex-center a h1")
            if title_element:
                manga_title = title_element.text.strip()
            else:
                title_element = soup.select_one("h1")
                if title_element:
                    manga_title = title_element.text.strip()
        
        # Eliminar el punto final del título si existe
        manga_title = manga_title.rstrip('.')
        
        # Buscar el número de capítulo
        chapter_element = soup.select_one("div.flex-center.gap-4 b.text-xs.md\\:text-base")
        if chapter_element:
            chapter_text = chapter_element.text.strip()
            # Extraer solo los dígitos y convertir a entero
            try:
                chapter_number = int(re.search(r'\d+', chapter_text).group())
            except (AttributeError, ValueError):
                print("No se pudo convertir el número de capítulo a entero. Usando 0 como valor predeterminado.")
        
        # Extraer URLs de capítulos anterior y siguiente para navegación
        prev_chapter_url = None
        next_chapter_url = None
        
        # Buscar enlaces de capítulos anterior y siguiente
        chapter_links = soup.select("div.flex-center.gap-4 a[href]")
        
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        # Si encontramos al menos 2 enlaces, asumimos que son el anterior y siguiente
        if len(chapter_links) >= 2:
            # El primer enlace suele ser el capítulo anterior
            if 'href' in chapter_links[0].attrs:
                prev_chapter_url = urljoin(base_url, chapter_links[0]['href'])
            
            # El último enlace suele ser el capítulo siguiente
            if 'href' in chapter_links[-1].attrs:
                next_chapter_url = urljoin(base_url, chapter_links[-1]['href'])
        
        # Extraer imágenes
        image_elements = soup.select("section div.relative.rounded-none img")
        
        if not image_elements:
            print("No se encontraron imágenes en la página")
            return
        
        # Intentar extraer información adicional desde las descripciones de las imágenes
        for img in image_elements:
            alt_text = img.get('alt', '')
            # El formato esperado es "Título > Capitulo X > Page Y"
            if '>' in alt_text:
                parts = alt_text.split('>')
                if len(parts) >= 2:
                    # Extraer título del manga
                    potential_title = parts[0].strip()
                    if potential_title and potential_title != manga_title:
                        manga_title = potential_title.rstrip('.')
                    
                    # Extraer número de capítulo
                    if len(parts) >= 2 and "capitulo" in parts[1].lower():
                        chapter_match = re.search(r'capitulo\s+(\d+)', parts[1].lower())
                        if chapter_match and chapter_number == 0:
                            chapter_number = int(chapter_match.group(1))
                # Solo necesitamos verificar una imagen, ya que todas deberían tener la misma información
                break
        
        print(f"Manga: {manga_title}")
        print(f"Capítulo: {chapter_number}")
        print(f"Encontradas {len(image_elements)} imágenes")
        
        if prev_chapter_url:
            print(f"Capítulo anterior disponible: {prev_chapter_url}")
        if next_chapter_url:
            print(f"Capítulo siguiente disponible: {next_chapter_url}")
        
        # Procesar y guardar las imágenes
        save_images(manga_title, chapter_number, image_elements, download_images)
        
        # Devolver información útil para navegación entre capítulos
        return {
            "manga_title": manga_title,
            "chapter_number": chapter_number,
            "next_chapter_url": next_chapter_url,
            "prev_chapter_url": prev_chapter_url
        }
        
    except Exception as e:
        print(f"Error al scrapear Olympus: {str(e)}")
        return None

"""
    Función para descargar capítulos consecutivos
"""
def scrape_olympus_consecutive(initial_url, download_images=True, num_chapters='todos'):
    current_url = initial_url
    chapters_downloaded = 0
    max_chapters = float('inf') if num_chapters == 'todos' else int(num_chapters)
    
    # Descargar el capítulo inicial
    print(f"\n=== Procesando capítulo inicial: {current_url} ===")
    chapter_info = scrape_olympus(current_url, download_images)
    
    if not chapter_info:
        print("No se pudo obtener información del capítulo.")
        return
    
    chapters_downloaded += 1
    
    # Verificar si hay capítulo siguiente
    if not chapter_info.get('next_chapter_url'):
        print("No hay capítulo siguiente disponible.")
        print(f"\n=== Proceso completado. Se descargaron {chapters_downloaded} capítulos. ===")
        return
    
    # Descargar capítulos consecutivos
    while chapters_downloaded < max_chapters and chapter_info and chapter_info.get('next_chapter_url'):
        current_url = chapter_info['next_chapter_url']
        print(f"\n=== Procesando capítulo siguiente ({chapters_downloaded + 1}/{max_chapters if max_chapters != float('inf') else 'todos'}): {current_url} ===")
        
        # Añadir una pequeña pausa para no sobrecargar el servidor
        time.sleep(1.5)
        
        chapter_info = scrape_olympus(current_url, download_images)
        
        if not chapter_info:
            print("Error al procesar el capítulo. Deteniendo.")
            break
        
        chapters_downloaded += 1
        
        if not chapter_info.get('next_chapter_url'):
            print("No hay más capítulos disponibles.")
            break
    
    print(f"\n=== Proceso completado. Se descargaron {chapters_downloaded} capítulos. ===")

"""
    funcionalidad especifica para leer el manga de M440.in
    y scrapearlo. 
"""
def scrape_m440(url, download_images=True):
    """
    Descarga un capítulo específico de manga de m440.in.
    
    Args:
        url: URL del capítulo
        download_images: Si es True, descarga las imágenes del capítulo
        
    Returns:
        dict: Información del capítulo descargado, o None si hubo un error
    """
    return m440_scrape_chapter_impl(url, download_images)

"""
    Función para obtener la lista de todos los capítulos disponibles de un manga en M440.in
"""
def get_m440_chapters(url):
    """
    Obtiene la lista de capítulos de un manga en m440.in.
    
    Args:
        url: URL principal del manga en m440.in
        
    Returns:
        list: Lista de capítulos con su número, URL y título
    """
    return m440_get_chapters_impl(url)

# Función para crear metadatos y guardar imágenes
def save_images(manga_title, chapter_number, image_elements, download_images=True):
    # Crear directorio específico para este manga/capítulo
    chapter_dir = create_chapter_directory(manga_title, chapter_number)
    
    # Crear lista para almacenar información de imágenes
    images_info = []
    image_urls = []
    
    # Procesar cada imagen
    for index, img in enumerate(image_elements):
        try:
            # Obtener URL de la imagen
            img_url = None
            if isinstance(img, dict) and 'src' in img:
                img_url = img['src']
            elif hasattr(img, 'get'):
                img_url = img.get('src', '')
                
                # Si hay un data-src, usarlo en lugar de src (a menudo el src es un placeholder)
                data_src = img.get('data-src', '')
                if data_src and (data_src.endswith('.jpg') or data_src.endswith('.png') or data_src.endswith('.webp')):
                    img_url = data_src
            
            if not img_url:
                print(f"No se pudo obtener URL para la imagen {index+1}")
                continue
                
            # Asegurar que es una URL absoluta
            if not img_url.startswith(('http://', 'https://')):
                # Intentar construir una URL absoluta razonable
                img_url = urljoin("https://m440.in", img_url)
            
            # Filtrar imágenes que no sean de contenido (como íconos, logos, etc.)
            if (img_url.endswith('.jpg') or img_url.endswith('.png') or img_url.endswith('.webp') or 
                '/uploads/' in img_url.lower() or '/images/' in img_url.lower()):
                
                # Nombre de archivo para esta imagen
                filename = f"{index+1:03d}.jpg"  # Formato: 001.jpg, 002.jpg, etc.
                
                # si filename tiene un parentesis es una imagen de anuncios
                if '(' in img_url:
                    print(f"Saltando imagen {index+1} porque parece ser un anuncio")
                    continue

                filepath = os.path.join(chapter_dir, filename)
                
                # Añadir a la lista de imágenes
                image_urls.append(img_url)
                images_info.append({
                    'url': img_url,
                    'number': index + 1,
                    'filename': filename
                })
                
                # Descargar imagen solo si se ha solicitado
                if download_images:
                    download_image(requests.Session(), img_url, filepath)
                    print(f"Guardada imagen {index+1}/{len(image_elements)}")
        except Exception as e:
            print(f"Error al procesar imagen {index+1}: {str(e)}")
    
    # Crear y guardar archivo de metadatos
    metadata = {
        'manga_title': manga_title,
        'chapter_number': chapter_number,
        'image_count': len(images_info),
        'images': images_info,
        'urls': image_urls
    }
    
    save_metadata(chapter_dir, metadata)
    
    if download_images:
        print(f"Proceso completado. Imágenes guardadas en: {chapter_dir}")
    
    return {
        'chapter_dir': chapter_dir,
        'images': images_info,
        'count': len(images_info)
    }

"""
    Función para descargar capítulos consecutivos de M440.in
"""
def scrape_m440_consecutive(initial_url, download_images=True, num_chapters='todos'):
    # Extraer la URL base del manga
    base_match = re.search(r'(https://m440\.in/manga/[^/]+)', initial_url)
    if not base_match:
        print("La URL proporcionada no parece ser de M440.in o no se pudo extraer la URL base.")
        return
    
    manga_base_url = base_match.group(1)
    
    # Obtener todos los capítulos disponibles
    chapters = m440_get_chapters_impl(manga_base_url)
    if not chapters:
        print("No se pudieron obtener los capítulos del manga.")
        return
    
    # Encontrar el índice del capítulo inicial en la lista
    start_index = -1
    for i, chapter in enumerate(chapters):
        if chapter['url'] == initial_url:
            start_index = i
            break
    
    if start_index == -1:
        print(f"No se pudo encontrar el capítulo inicial en la lista de capítulos.")
        # Intentar usar el primer capítulo como alternativa
        if chapters:
            start_index = 0
            print(f"Comenzando desde el primer capítulo disponible: {chapters[0]['title']}")
        else:
            return
    
    # Determinar cuántos capítulos descargar
    if num_chapters == 'todos':
        end_index = len(chapters)
    else:
        try:
            end_index = start_index + int(num_chapters)
            end_index = min(end_index, len(chapters))
        except ValueError:
            print("Número de capítulos no válido, descargando solo el capítulo inicial.")
            end_index = start_index + 1
    
    # Descargar capítulos en secuencia
    for i in range(start_index, end_index):
        print(f"\nDescargando capítulo {i-start_index+1} de {end_index-start_index}...")
        m440_scrape_chapter_impl(chapters[i]['url'], download_images)

# Función para procesar los enlaces de capítulos y convertirlos en una lista estructurada
def process_chapter_links(chapter_links, base_url):
    """
    Procesa enlaces a capítulos y extrae información relevante.
    Esta función ahora está en el módulo scrapers.m440
    
    Args:
        chapter_links: Lista de elementos <a> a procesar
        base_url: URL base para resolver URLs relativas
        
    Returns:
        list: Lista de información de capítulos
    """
    return m440_process_chapter_links_impl(chapter_links, base_url)

if __name__ == "__main__":
    main()