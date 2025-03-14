#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Módulo especializado para el scraping de manga desde intomanga.com
"""

import re
import time
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from utils.http_utils import create_session, get_page_content
from utils.file_utils import (
    create_chapter_directory, save_metadata, download_image, sanitize_filename
)

def get_inmanga_chapters(url):
    """
    Obtiene la lista de capítulos de un manga en intomanga.com
    
    Args:
        url: URL principal del manga
        
    Returns:
        list: Lista de capítulos con su número, URL y título,
              o None si no se pudieron obtener
    """
    try:
        # Crear sesión HTTP
        session = create_session()
        
        # Obtener la página del manga
        print(f"Obteniendo información del manga desde {url}...")
        soup, _ = get_page_content(session, url)
        
        if not soup:
            print("No se pudo acceder a la página del manga.")
            return None
            
        # Extraer el título del manga
        manga_title = None
        title_tag = soup.select_one("a.blue")
        if title_tag:
            manga_title = title_tag.text.strip()
            print(f"Manga encontrado: {manga_title}")
        
        # Buscar todos los enlaces a capítulos
        chapters = []
        chapter_options = soup.select("select.ChapterListClass option")
        
        if not chapter_options:
            print("No se encontraron enlaces a capítulos en la página.")
            return None
            
        print(f"Se encontraron {len(chapter_options)} posibles enlaces a capítulos.")
        
        # Extraer información base del manga
        manga_id = None
        manga_friendly_name = None
        
        # Intentar obtener el ID del manga y su nombre amigable
        manga_id_input = soup.select_one("input#MangaIdentification")
        if manga_id_input:
            manga_id = manga_id_input.get('value')
            
        manga_friendly_name_input = soup.select_one("input#FriendlyMangaName")
        if manga_friendly_name_input:
            manga_friendly_name = manga_friendly_name_input.get('value')
        
        # Procesar cada opción de capítulo
        for option in chapter_options:
            chapter_id = option.get('value')
            chapter_num_text = option.text.strip()
            
            try:
                # Convertir el número de capítulo a float o int según corresponda
                chapter_num = float(chapter_num_text)
                if chapter_num.is_integer():
                    chapter_num = int(chapter_num)
            except ValueError:
                # Si no se puede convertir, usar un contador
                chapter_num = 0
            
            # Construir la URL del capítulo
            chapter_url = f"/ver/manga/{manga_friendly_name}/{chapter_num_text}/{chapter_id}"
            chapter_url = urljoin(url, chapter_url)
            
            # Añadir a la lista de capítulos
            chapters.append({
                'number': chapter_num,
                'url': chapter_url,
                'title': f"Capítulo {chapter_num_text}",
                'id': chapter_id
            })
            
        # Ordenar por número de capítulo
        chapters.sort(key=lambda x: x['number'])
        
        print(f"Total de capítulos procesados: {len(chapters)}")
        return chapters
        
    except Exception as e:
        print(f"Error al obtener la lista de capítulos: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def scrape_inmanga(url, download_images=True):
    """
    Descarga un capítulo específico de intomanga.com
    
    Args:
        url: URL del capítulo a descargar
        download_images: Si es True, descarga las imágenes del capítulo
        
    Returns:
        dict: Información del capítulo descargado, o None si hubo un error
    """
    try:
        # Crear sesión HTTP
        session = create_session()
        
        # Obtener la página del capítulo
        print(f"Descargando contenido de {url}...")
        soup, _ = get_page_content(session, url)
        
        if not soup:
            print("No se pudo acceder a la página del capítulo.")
            return None
            
        # Extraer información del manga y capítulo
        manga_title = None
        chapter_number = None
        
        # Obtener título del manga
        manga_title_tag = soup.select_one("a.blue:nth-child(1)")
        print(manga_title_tag)
        if manga_title_tag:
            manga_title = manga_title_tag.get("textContext").strip()
        
        # Si no encontramos el título, intentar extraerlo de los inputs ocultos
        if not manga_title:
            manga_name_input = soup.select_one("input#MangaName")
            print(manga_name_input)

            if manga_name_input:
                manga_title = manga_name_input.get('value')
        
        # Obtener número del capítulo
        # chapter_number = soup.select_one("#select2-ChapList-container")
        chapter_number_input = soup.select_one("input#ChapterNumber")
        if chapter_number:
            chapter_number_text = chapter_number.get('title')
            try:
                chapter_number = int(chapter_number_text.replace(',', ''))
                if chapter_number.is_integer():
                    chapter_number = int(chapter_number)
            except ValueError:
                chapter_number = 0
        
        # Si no se encontró el número del capítulo, intentar extraerlo de la URL
        if not chapter_number:
            match = re.search(r'/([\d,\.]+)/', url)
            if match:
                try:
                    chapter_number_text = match.group(1).replace(',', '.')
                    chapter_number = int(chapter_number_text.replace(',', ''))
                    if chapter_number.is_integer():
                        chapter_number = int(chapter_number)
                except ValueError:
                    pass
        
        print(f"Manga: {manga_title}")
        print(f"Capítulo: {chapter_number}")
        
        # Buscar imágenes del capítulo
        images = []
        
        # Buscar contenedor de imágenes
        img_containers = soup.select("div.PagesContainer img.ImageContainer")
        
        for img in img_containers:
            src = img.get('src')
            if src and not src.endswith('loading-gear.gif'):
                # Si la imagen ya está cargada, usar su URL directamente
                if not src.startswith(('http://', 'https://')):
                    src = urljoin(url, src)
                images.append(src)
            else:
                # Si la imagen no está cargada, construir la URL basada en los atributos
                img_id = img.get('id')
                page_number = img.get('data-pagenumber')
                manga_friendly_name = None
                
                # Obtener el nombre amigable del manga
                friendly_name_input = soup.select_one("input#FriendlyMangaName")
                if friendly_name_input:
                    manga_friendly_name = friendly_name_input.get('value')
                
                if img_id and page_number and manga_friendly_name and chapter_number:
                    # Construir la URL de la imagen según el patrón observado
                    img_url = f"https://pack-yak.intomanga.com/images/manga/{manga_friendly_name}/chapter/{chapter_number}/page/{page_number}/{img_id}"
                    images.append(img_url)
        
        if not images:
            print("No se encontraron imágenes en el capítulo.")
            return None
            
        print(f"Se encontraron {len(images)} imágenes.")
        
        # Información del capítulo
        chapter_info = {
            'manga_title': manga_title,
            'chapter_number': chapter_number,
            'chapter_title': f"Capítulo {chapter_number}",
            'source_url': url,
            'images': images,
            'downloaded_at': time.strftime("%Y-%m-%d %H:%M:%S"),
            'page_count': len(images)
        }
        
        # Buscar enlaces a capítulos anterior y siguiente
        # En InManga, los botones de navegación usan JavaScript
        # Intentaremos extraer los IDs de capítulos de la lista desplegable
        chapter_select = soup.select_one("select.ChapterListClass")
        if chapter_select:
            options = chapter_select.select("option")
            current_index = None
            
            # Encontrar el índice del capítulo actual
            chapter_id_input = soup.select_one("input#ChapterIdentification")
            if chapter_id_input:
                current_chapter_id = chapter_id_input.get('value')
                for i, option in enumerate(options):
                    if option.get('value') == current_chapter_id:
                        current_index = i
                        break
            
            if current_index is not None:
                # Capítulo anterior (índice mayor porque la lista está en orden inverso)
                if current_index < len(options) - 1:
                    prev_option = options[current_index + 1]
                    prev_chapter_num = prev_option.text.strip()
                    prev_chapter_id = prev_option.get('value')
                    manga_friendly_name = None
                    
                    friendly_name_input = soup.select_one("input#FriendlyMangaName")
                    if friendly_name_input:
                        manga_friendly_name = friendly_name_input.get('value')
                    
                    if manga_friendly_name:
                        prev_url = f"/ver/manga/{manga_friendly_name}/{prev_chapter_num}/{prev_chapter_id}"
                        chapter_info['prev_chapter_url'] = urljoin(url, prev_url)
                
                # Capítulo siguiente (índice menor porque la lista está en orden inverso)
                if current_index > 0:
                    next_option = options[current_index - 1]
                    next_chapter_num = next_option.text.strip()
                    next_chapter_id = next_option.get('value')
                    manga_friendly_name = None
                    
                    friendly_name_input = soup.select_one("input#FriendlyMangaName")
                    if friendly_name_input:
                        manga_friendly_name = friendly_name_input.get('value')
                    
                    if manga_friendly_name:
                        next_url = f"/ver/manga/{manga_friendly_name}/{next_chapter_num}/{next_chapter_id}"
                        chapter_info['next_chapter_url'] = urljoin(url, next_url)
        
        # Descargar imágenes si se solicitó
        if download_images:
            print("Descargando imágenes...")
            chapter_dir = create_chapter_directory(manga_title, chapter_number, chapter_info['chapter_title'])
            save_metadata(chapter_dir, chapter_info)
            
            # Descargar cada imagen
            for i, img_url in enumerate(images, 1):
                img_filename = f"{i:03d}.jpg"
                img_path = f"{chapter_dir}/{img_filename}"
                
                print(f"Descargando imagen {i}/{len(images)}: {img_url}")
                success = download_image(session, img_url, img_path)
                
                if not success:
                    print(f"Error al descargar la imagen {i}")
                
                # Pequeña pausa para evitar sobrecarga del servidor
                time.sleep(0.5)
                
            print(f"Capítulo descargado en: {chapter_dir}")
            
        return chapter_info
            
    except Exception as e:
        print(f"Error al descargar el capítulo: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def scrape_inmanga_consecutive(initial_url, download_images=True, num_chapters='todos'):
    """
    Descarga capítulos consecutivos de intomanga.com
    
    Args:
        initial_url: URL del capítulo inicial
        download_images: Si es True, descarga las imágenes de los capítulos
        num_chapters: Número de capítulos a descargar o 'todos' para descargar todos
        
    Returns:
        int: Número de capítulos descargados
    """
    current_url = initial_url
    chapters_downloaded = 0
    max_chapters = float('inf') if num_chapters == 'todos' else int(num_chapters)
    
    # Descargar el capítulo inicial
    print(f"\n=== Procesando capítulo inicial: {current_url} ===")
    chapter_info = scrape_inmanga(current_url, download_images)
    
    if not chapter_info:
        print("No se pudo obtener información del capítulo.")
        return chapters_downloaded
    
    chapters_downloaded += 1
    
    # Verificar si hay capítulo siguiente
    if not chapter_info.get('next_chapter_url'):
        print("No hay capítulo siguiente disponible.")
        print(f"\n=== Proceso completado. Se descargaron {chapters_downloaded} capítulos. ===")
        return chapters_downloaded
    
    # Descargar capítulos consecutivos
    while chapters_downloaded < max_chapters and chapter_info and chapter_info.get('next_chapter_url'):
        current_url = chapter_info['next_chapter_url']
        print(f"\n=== Procesando capítulo siguiente ({chapters_downloaded + 1}/{max_chapters if max_chapters != float('inf') else 'todos'}): {current_url} ===")
        
        # Añadir una pequeña pausa para no sobrecargar el servidor
        time.sleep(1.5)
        
        chapter_info = scrape_inmanga(current_url, download_images)
        
        if not chapter_info:
            print("Error al procesar el capítulo. Deteniendo.")
            break
        
        chapters_downloaded += 1
        
        if not chapter_info.get('next_chapter_url'):
            print("No hay más capítulos disponibles.")
            break
    
    print(f"\n=== Proceso completado. Se descargaron {chapters_downloaded} capítulos. ===")
    return chapters_downloaded