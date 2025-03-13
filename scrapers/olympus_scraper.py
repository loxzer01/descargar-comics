#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Módulo especializado para el scraping de manga desde olympusscanlation.com
"""

import re
import time
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from utils.http_utils import create_session, get_page_content
from utils.file_utils import (
    create_chapter_directory, save_metadata, download_image, sanitize_filename
)

def get_olympus_chapters(url):
    """
    Obtiene la lista de capítulos de un manga en olympusscanlation.com
    
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
        title_tag = soup.select_one("h1.entry-title")
        if title_tag:
            manga_title = title_tag.text.strip()
            print(f"Manga encontrado: {manga_title}")
        
        # Buscar todos los enlaces a capítulos
        chapters = []
        chapter_links = soup.select("div.ch-list a")
        
        if not chapter_links:
            # Intentar con otros selectores si el primero no funciona
            chapter_links = soup.select("div.chapters a, div.chapter-list a, li.wp-manga-chapter a")
            
        if not chapter_links:
            print("No se encontraron enlaces a capítulos en la página.")
            return None
            
        print(f"Se encontraron {len(chapter_links)} posibles enlaces a capítulos.")
        
        # Procesar cada enlace
        for link in chapter_links:
            href = link.get('href', '')
            if not href:
                continue
                
            # Convertir a URL absoluta si es necesario
            if not href.startswith(('http://', 'https://')):
                href = urljoin(url, href)
                
            # Extraer número y título del capítulo
            chapter_title = link.text.strip()
            chapter_num = 0
            
            # Intentar extraer el número del capítulo del texto
            match = re.search(r'cap(?:í|i)tulo\s+(\d+(?:\.\d+)?)', chapter_title, re.IGNORECASE)
            if not match:
                match = re.search(r'chapter\s+(\d+(?:\.\d+)?)', chapter_title, re.IGNORECASE)
                
            if match:
                try:
                    chapter_num = float(match.group(1))
                    # Convertir a entero si es posible
                    if chapter_num.is_integer():
                        chapter_num = int(chapter_num)
                except ValueError:
                    pass
            else:
                # Si no encontramos el patrón en el texto, intentar extraerlo de la URL
                url_match = re.search(r'[/-](\d+(?:\.\d+)?)(?:[/-]|$)', href)
                if url_match:
                    try:
                        chapter_num = float(url_match.group(1))
                        if chapter_num.is_integer():
                            chapter_num = int(chapter_num)
                    except ValueError:
                        pass
            
            # Añadir a la lista de capítulos
            chapters.append({
                'number': float(chapter_num),
                'url': href,
                'title': chapter_title
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

def scrape_olympus(url, download_images=True):
    """
    Descarga un capítulo específico de olympusscanlation.com
    
    Args:
        url: URL del capítulo a descargar
        download_images: Si es True, descarga las imágenes del capítulo
        
    Returns:
        dict: Información del capítulo descargado, o None si hubo un error
    """
    try:
        # Verificar que la URL pertenezca a olympusscanlation.com
        if not "olympusscanlation.com" in url:
            print("La URL proporcionada no pertenece a olympusscanlation.com")
            return None

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
        chapter_title = None
        
        # Obtener título del manga
        manga_title_tag = soup.select_one("h1.entry-title, div.series-title h1")
        if manga_title_tag:
            manga_title = manga_title_tag.text.strip()
            
        # Si no encontramos el título, intentar extraerlo de la navegación
        if not manga_title:
            breadcrumbs = soup.select("nav.breadcrumb a, div.breadcrumbs a")
            if len(breadcrumbs) >= 2:
                manga_title = breadcrumbs[1].text.strip()
                
        if not manga_title:
            # Último recurso: extraer de la URL
            match = re.search(r'com/([^/]+)/', url)
            if match:
                manga_title = match.group(1).replace('-', ' ').title()
                
        # Obtener título y número del capítulo
        chapter_title_tag = soup.select_one("div.chapter-title h1, h2.entry-title")
        if chapter_title_tag:
            chapter_title = chapter_title_tag.text.strip()
            
        # Extraer número del capítulo
        chapter_number = 0
        if chapter_title:
            match = re.search(r'cap(?:í|i)tulo\s+(\d+(?:\.\d+)?)', chapter_title, re.IGNORECASE)
            if not match:
                match = re.search(r'chapter\s+(\d+(?:\.\d+)?)', chapter_title, re.IGNORECASE)
                
            if match:
                try:
                    chapter_number = float(match.group(1))
                    if chapter_number.is_integer():
                        chapter_number = int(chapter_number)
                except ValueError:
                    pass
                    
        if chapter_number == 0:
            # Intentar extraer de la URL
            match = re.search(r'[/-](\d+(?:\.\d+)?)(?:[/-]|$)', url)
            if match:
                try:
                    chapter_number = float(match.group(1))
                    if chapter_number.is_integer():
                        chapter_number = int(chapter_number)
                except ValueError:
                    pass
                    
        print(f"Manga: {manga_title}")
        print(f"Capítulo: {chapter_number} - {chapter_title}")
        
        # Buscar imágenes del capítulo
        images = []
        
        # Método 1: Buscar directamente las imágenes en la página
        img_containers = soup.select("div.reading-content img, div.entry-content img")
        for img in img_containers:
            src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
            if src:
                if not src.startswith(('http://', 'https://')):
                    src = urljoin(url, src)
                images.append(src)
                
        # Método 2: Buscar en scripts (común en sitios que cargan imágenes con JS)
        if not images:
            scripts = soup.find_all("script")
            for script in scripts:
                if script.string and ('var images' in script.string or 'chapter_images' in script.string):
                    # Buscar datos de imágenes en scripts
                    img_matches = re.findall(r'[\'"]([^"\']+\.(?:jpg|jpeg|png|webp))[\'"]', script.string)
                    for img_url in img_matches:
                        if not img_url.startswith(('http://', 'https://')):
                            img_url = urljoin(url, img_url)
                        images.append(img_url)
                        
        if not images:
            print("No se encontraron imágenes en el capítulo.")
            return None
            
        print(f"Se encontraron {len(images)} imágenes.")
        
        # Información del capítulo
        chapter_info = {
            'manga_title': manga_title,
            'chapter_number': chapter_number,
            'chapter_title': chapter_title,
            'source_url': url,
            'images': images,
            'downloaded_at': time.strftime("%Y-%m-%d %H:%M:%S"),
            'page_count': len(images)
        }
        
        # Buscar enlaces a capítulos anterior y siguiente
        nav_links = soup.select("div.chapter-navigation a, div.nav-links a")
        for link in nav_links:
            href = link.get('href', '')
            if not href:
                continue
                
            link_text = link.text.strip().lower()
            if 'siguiente' in link_text or 'next' in link_text:
                chapter_info['next_chapter_url'] = urljoin(url, href)
            elif 'anterior' in link_text or 'prev' in link_text:
                chapter_info['prev_chapter_url'] = urljoin(url, href)
        
        # Descargar imágenes si se solicitó
        if download_images:
            print("Descargando imágenes...")
            chapter_dir = create_chapter_directory(manga_title, chapter_number, chapter_title)
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
