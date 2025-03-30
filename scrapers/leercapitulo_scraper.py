#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Módulo especializado para el scraping de manga desde leercapitulo.co
"""

import re
import time
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from utils.http_utils import create_session, get_page_content
from utils.file_utils import (
    create_chapter_directory, save_metadata, download_image, sanitize_filename
)

def get_leercapitulo_chapters(url):
    """
    Obtiene la lista de capítulos de un manga en leercapitulo.co
    
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
        title_tag = soup.select_one("h1")
        if title_tag:
            manga_title = title_tag.text.strip()
            # Eliminar "En línea" del título si existe
            manga_title = re.sub(r'\s+En\s+[lL]ínea$', '', manga_title)
            print(f"Manga encontrado: {manga_title}")
        
        # Buscar todos los enlaces a capítulos
        chapters = []
        chapter_links = soup.select("div.chapter-list a, div.chapters a")
        
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
                url_match = re.search(r'[/-](\d+(?:\.\d+)?)[/-]', href)
                if url_match:
                    try:
                        chapter_num = float(url_match.group(1))
                        # Solo convertir a entero si es un número entero y no tiene parte decimal
                        if chapter_num.is_integer():
                            chapter_num = int(chapter_num)
                    except ValueError:
                        pass
            
            # Añadir a la lista de capítulos
            chapters.append({
                'number': float(chapter_num) if chapter_num else 0,
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

def scrape_leercapitulo(url, download_images=True):
    """
    Descarga un capítulo específico de leercapitulo.co
    
    Args:
        url: URL del capítulo a descargar
        download_images: Si es True, descarga las imágenes del capítulo
        
    Returns:
        dict: Información del capítulo descargado, o None si hubo un error
    """
    try:
        # Verificar que la URL pertenezca a leercapitulo.co
        if not "leercapitulo.co" in url:
            print("La URL proporcionada no pertenece a leercapitulo.co")
            return None

        # Obtener el contenido de la página con headers específicos para simular un navegador real
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Referer': 'https://leercapitulo.co/',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'Connection': 'keep-alive',
            'DNT': '1',
            'Pragma': 'no-cache'
        }
        
        # Crear una sesión para mantener cookies y otros estados
        session = create_session()
        session.headers.update(headers)
        
        # Obtener la página del capítulo con múltiples intentos para asegurar la carga completa
        print(f"Descargando contenido de {url}...")
        soup, response = get_page_content(session, url)
        
        if not soup:
            print("No se pudo acceder a la página del capítulo.")
            return None
            
        # Verificar si la página tiene el elemento array_data que indica carga progresiva
        array_data_element = soup.select_one("p#array_data")
        if array_data_element:
            print("Detectada página con carga progresiva de imágenes.")
            
            # Realizar múltiples intentos para asegurar que todas las imágenes se carguen
            max_attempts = 3
            for attempt in range(1, max_attempts + 1):
                print(f"Intento {attempt}/{max_attempts} para obtener todas las imágenes...")
                
                # Verificar cuántas imágenes están cargadas actualmente
                img_containers = soup.select("div.comic_wraCon a[name] img")
                print(f"Imágenes encontradas: {len(img_containers)}")
                
                # Si ya tenemos un número razonable de imágenes, podemos continuar
                if len(img_containers) > 5:
                    print("Se encontró un número suficiente de imágenes.")
                    break
                    
                # Esperar un tiempo para que se carguen más imágenes
                wait_time = 2 * attempt  # Aumentar el tiempo de espera en cada intento
                print(f"Esperando {wait_time} segundos para la carga de imágenes...")
                time.sleep(wait_time)
                
                # Volver a cargar la página
                soup, response = get_page_content(session, url)
                if not soup:
                    print("Error al recargar la página.")
                    break
            
        # Extraer información del manga y capítulo
        manga_title = None
        chapter_title = None
        chapter_number = 0
        
        # Obtener título del manga - intentar diferentes selectores
        manga_title_tag = soup.select_one("h1.text-center.text-bold")
        if manga_title_tag:
            manga_title = manga_title_tag.text.strip()
            # Eliminar "En línea" del título si existe
            manga_title = re.sub(r'\s+En\s+[lL]ínea$', '', manga_title)
            
        # Si no encontramos el título, intentar extraerlo de los enlaces
        if not manga_title:
            manga_link = soup.select_one("div.container_title h2.chapter-title a[title]")
            if manga_link:
                manga_title = manga_link.text.strip()
                
        # Si aún no encontramos el título, intentar con otros selectores
        if not manga_title:
            manga_link = soup.select_one("a.manga-name")
            if manga_link:
                manga_title = manga_link.text.strip()
                
        # Último intento: buscar cualquier h1 o h2 que pueda contener el título
        if not manga_title:
            for heading in soup.select("h1, h2"):
                if heading.text and not re.search(r'cap(?:í|i)tulo|chapter', heading.text, re.IGNORECASE):
                    manga_title = heading.text.strip()
                    break
                    
        # Si aún no tenemos título, usar un valor por defecto
        if not manga_title:
            manga_title = "Manga Desconocido"
                
        # Obtener título y número del capítulo
        chapter_title_tag = soup.select_one("h2.chapter-title")
        if chapter_title_tag:
            chapter_title = chapter_title_tag.text.strip()
            
        # Extraer número del capítulo
        if chapter_title:
            match = re.search(r'cap(?:í|i)tulo\s+(\d+(?:\.\d+)?)', chapter_title, re.IGNORECASE)
            if not match:
                match = re.search(r'chapter\s+(\d+(?:\.\d+)?)', chapter_title, re.IGNORECASE)
                
            if match:
                try:
                    chapter_number = float(match.group(1))
                    # Solo convertir a entero si es un número entero y no tiene parte decimal
                    if chapter_number.is_integer():
                        chapter_number = int(chapter_number)
                except ValueError:
                    pass
                    
        if chapter_number == 0:
            # Intentar extraer de la URL
            match = re.search(r'[/-](\d+(?:\.\d+)?)[/-]', url)
            if match:
                try:
                    chapter_number = float(match.group(1))
                    # Solo convertir a entero si es un número entero y no tiene parte decimal
                    if chapter_number.is_integer():
                        chapter_number = int(chapter_number)
                except ValueError:
                    pass
                    
        print(f"Manga: {manga_title}")
        print(f"Capítulo: {chapter_number} - {chapter_title}")
        
        # Extraer URLs de capítulos anterior y siguiente para navegación
        prev_chapter_url = None
        next_chapter_url = None
        
        # Buscar enlaces a capítulos anterior y siguiente
        # Intentar varios selectores para encontrar el enlace al siguiente capítulo
        
        # Primer intento: selector específico usado anteriormente
        next_link = soup.select_one("a.loadAllImgPage.pull-right.next")
        
        # Segundo intento: buscar por texto y clase
        if not next_link or 'href' not in next_link.attrs:
            next_links = soup.select("a.pull-right")
            for link in next_links:
                if 'Próximo' in link.text and 'href' in link.attrs:
                    next_link = link
                    break
        
        # Tercer intento: buscar cualquier enlace con texto 'Próximo' o 'Siguiente'
        if not next_link or 'href' not in next_link.attrs:
            for link in soup.find_all('a'):
                if ('Próximo' in link.text or 'Siguiente' in link.text) and 'href' in link.attrs:
                    next_link = link
                    break
        
        # Buscar enlace al capítulo anterior
        prev_link = soup.select_one("a.loadAllImgPage.pull-left.prev")
        
        # Segundo intento para capítulo anterior
        if not prev_link or 'href' not in prev_link.attrs:
            prev_links = soup.select("a.pull-left")
            for link in prev_links:
                if 'Anterior' in link.text and 'href' in link.attrs:
                    prev_link = link
                    break
        
        # Tercer intento para capítulo anterior
        if not prev_link or 'href' not in prev_link.attrs:
            for link in soup.find_all('a'):
                if 'Anterior' in link.text and 'href' in link.attrs:
                    prev_link = link
                    break
        
        # Procesar enlace al siguiente capítulo
        if next_link and 'href' in next_link.attrs:
            next_url = next_link['href']
            # Asegurarse de que la URL sea absoluta
            if not next_url.startswith(('http://', 'https://')):
                next_url = urljoin(url, next_url)
            
            # Verificar que la URL tenga el formato correcto
            if '/leer/' in next_url:
                next_chapter_url = next_url
                print(f"URL del siguiente capítulo: {next_url}")
            else:
                print(f"URL del siguiente capítulo no válida: {next_url}")
        else:
            print("No se encontró enlace al siguiente capítulo.")
            
        # Procesar enlace al capítulo anterior
        if prev_link and 'href' in prev_link.attrs:
            prev_url = prev_link['href']
            # Asegurarse de que la URL sea absoluta
            if not prev_url.startswith(('http://', 'https://')):
                prev_url = urljoin(url, prev_url)
            
            # Verificar que la URL tenga el formato correcto
            if '/leer/' in prev_url:
                prev_chapter_url = prev_url
                print(f"URL del capítulo anterior: {prev_url}")
        
        # Verificar que las URLs de navegación sean diferentes a la URL actual
        if prev_chapter_url == url:
            prev_chapter_url = None
        if next_chapter_url == url:
            next_chapter_url = None
        
        # Buscar imágenes del capítulo - usando múltiples estrategias como en ikigai_scraper
        image_elements = []
        
        # Estrategia 0: Buscar en el elemento array_data que contiene las URLs codificadas
        # Este elemento contiene todas las imágenes que se cargarán progresivamente
        array_data_element = soup.select_one("p#array_data")
        if array_data_element and array_data_element.string:
            print("Encontrado elemento array_data que contiene las URLs de imágenes codificadas")
            # Intentar extraer las imágenes ya cargadas en la página
            img_containers = soup.select("div.comic_wraCon a[name] img")
            
            # Verificar si todas las imágenes ya están cargadas
            if img_containers:
                print(f"Se encontraron {len(img_containers)} imágenes ya cargadas en la página")
                # Esperar un momento para asegurar que todas las imágenes se hayan cargado
                time.sleep(2)
                
                # Volver a obtener la página para asegurarnos de tener todas las imágenes
                print("Recargando la página para obtener todas las imágenes...")
                soup, _ = get_page_content(session, url)
                
                # Buscar nuevamente las imágenes después de la recarga
                img_containers = soup.select("div.comic_wraCon a[name] img")
                
                for img in img_containers:
                    if img.get('src'):
                        src = img.get('src')
                        if any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']):
                            image_elements.append(img)
                            print(f"Encontrada imagen cargada: {src}")
        
        # Estrategia 1: Buscar directamente las imágenes en la página con selectores específicos
        if not image_elements:
            img_containers = soup.select("div.comic_wraCon a[name] img")
            for img in img_containers:
                if img.get('src'):
                    src = img.get('src')
                    if any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']):
                        image_elements.append(img)
                        print(f"Encontrada imagen (estrategia 1): {src}")
        
        # Estrategia 2: Buscar con selectores más amplios
        if not image_elements:
            img_containers = soup.select("div.chapter-content-inner img, div.comic_wraCon img, div.chapter-content img")
            for img in img_containers:
                if img.get('src'):
                    src = img.get('src')
                    if any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']):
                        # Filtrar imágenes que no son del manga (como íconos, logos, etc.)
                        if not any(ad_term in src.lower() for ad_term in ['ad', 'banner', 'logo', 'icon', 'btn']):
                            image_elements.append(img)
                            print(f"Encontrada imagen (estrategia 2): {src}")
        
        # Estrategia 3: Buscar en atributos data-src o lazy-load
        if not image_elements:
            lazy_images = soup.select("img[data-src], img[data-lazy-src], img[data-original], img.lazy")
            for img in lazy_images:
                src = img.get('data-src') or img.get('data-lazy-src') or img.get('data-original')
                if src and any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']):
                    # Crear un nuevo tag img con el src correcto
                    img['src'] = src
                    image_elements.append(img)
                    print(f"Encontrada imagen (estrategia 3): {src}")
        
        # Estrategia 4: Buscar en estilos de fondo
        if not image_elements:
            bg_elements = soup.select("[style*='background-image']")
            for el in bg_elements:
                style = el.get('style', '')
                # Extraer URL de la imagen del estilo
                match = re.search(r'background-image:\s*url\([\'"](.*?)[\'"]\)', style)
                if match:
                    src = match.group(1)
                    if any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']):
                        # Crear un elemento img simulado
                        img = {'src': src}
                        image_elements.append(img)
                        print(f"Encontrada imagen (estrategia 4): {src}")
        
        # Estrategia 5: Buscar en scripts para contenido cargado dinámicamente
        if not image_elements:
            scripts = soup.select("script")
            for script in scripts:
                script_content = script.string
                if script_content:
                    # Buscar URLs de imágenes en el contenido del script
                    img_urls = re.findall(r'https?://[^\s\'"]+\.(jpg|jpeg|png|webp|gif)', script_content, re.IGNORECASE)
                    for url in img_urls:
                        # Crear un elemento img simulado
                        img = {'src': url[0]}
                        image_elements.append(img)
                        print(f"Encontrada imagen (estrategia 5): {url[0]}")
        
        # Estrategia 6: Último recurso - buscar todas las imágenes en la página
        if not image_elements:
            all_images = soup.find_all('img')
            for img in all_images:
                # Verificar varios atributos donde podría estar la URL
                for attr in ['src', 'data-src', 'data-original', 'data-lazy-src']:
                    if img.get(attr):
                        src = img.get(attr)
                        # Filtrar imágenes pequeñas o de navegación
                        if any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']):
                            if not any(term in src.lower() for term in ['logo', 'icon', 'banner', 'button', 'btn']):
                                image_elements.append(img)
                                print(f"Encontrada imagen (estrategia 6): {src}")
                                break
        
        if not image_elements:
            print("No se encontraron imágenes en la página usando ninguna estrategia")
            return None
        
        print(f"Manga: {manga_title}")
        print(f"Capítulo: {chapter_number}")
        print(f"Encontradas {len(image_elements)} imágenes")
        
        if prev_chapter_url:
            print(f"Capítulo anterior disponible: {prev_chapter_url}")
        if next_chapter_url:
            print(f"Capítulo siguiente disponible: {next_chapter_url}")
        
        # Procesar y guardar las imágenes
        from main import save_images
        result = save_images(manga_title, chapter_number, image_elements, download_images)
        
        # Devolver información útil para navegación entre capítulos
        return {
            "manga_title": manga_title,
            "chapter_number": chapter_number,
            "chapter_title": chapter_title,
            "next_chapter_url": next_chapter_url,
            "prev_chapter_url": prev_chapter_url,
            "source_url": url,
            "downloaded_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            **result
        }
            
    except Exception as e:
        print(f"Error al descargar el capítulo: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def scrape_leercapitulo_consecutive(url, download_images=True, num_chapters='1'):
    """
    Descarga capítulos consecutivos de leercapitulo.co
    
    Args:
        url: URL del primer capítulo a descargar
        download_images: Si es True, descarga las imágenes de los capítulos
        num_chapters: Número de capítulos a descargar o 'todos' para descargar todos
        
    Returns:
        list: Lista de información de capítulos descargados
    """
    # Asegurarse de que la URL tenga el formato correcto
    if url.endswith('/'):
        url = url[:-1]  # Eliminar la barra final si existe
    try:
        # Convertir num_chapters a entero si es posible
        max_chapters = float('inf')  # Valor por defecto para 'todos'
        if num_chapters.lower() != 'todos':
            try:
                max_chapters = int(num_chapters)
            except ValueError:
                print(f"Valor no válido para número de capítulos: {num_chapters}. Usando 1.")
                max_chapters = 1
        
        # Lista para almacenar información de capítulos descargados
        downloaded_chapters = []
        
        # URL del capítulo actual
        current_url = url
        chapters_downloaded = 0
        
        while current_url and chapters_downloaded < max_chapters:
            print(f"\n=== Procesando capítulo {chapters_downloaded + 1}/{max_chapters if max_chapters != float('inf') else '?'} ===\n")
            
            # Descargar el capítulo actual
            chapter_info = scrape_leercapitulo(current_url, download_images)
            
            if not chapter_info:
                print("No se pudo descargar el capítulo. Deteniendo el proceso.")
                break
                
            # Añadir a la lista de capítulos descargados
            downloaded_chapters.append(chapter_info)
            chapters_downloaded += 1
            
            # Verificar si hay un capítulo siguiente
            if 'next_chapter_url' in chapter_info:
                current_url = chapter_info['next_chapter_url']
                print(f"Siguiente capítulo: {current_url}")
                
                # Pequeña pausa para evitar sobrecarga del servidor
                time.sleep(1.5)
            else:
                print("No hay más capítulos disponibles.")
                break
        
        print(f"\n=== Proceso completado. Se descargaron {chapters_downloaded} capítulos. ===\n")
        return downloaded_chapters
        
    except Exception as e:
        print(f"Error al descargar capítulos consecutivos: {str(e)}")
        import traceback
        traceback.print_exc()
        return None