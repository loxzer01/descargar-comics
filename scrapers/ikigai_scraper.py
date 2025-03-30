#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Scraper para el sitio web Ikigai

import os
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import time

# Importar utilidades comunes
from utils.file_utils import create_directories, sanitize_filename, create_manga_directory
from utils.file_utils import create_chapter_directory, save_metadata, download_image

def scrape_ikigai(url, download_images=True):
    """
    Descarga un capítulo específico de manga de Ikigai.
    
    Args:
        url: URL del capítulo
        download_images: Si es True, descarga las imágenes del capítulo
        
    Returns:
        dict: Información del capítulo descargado, o None si hubo un error
    """
    try:
        # Verificar que la URL sea de Ikigai
        parsed_url = urlparse(url)
        
        # Obtener el dominio base para configurar los headers correctamente
        base_domain = parsed_url.netloc
        base_url = f"{parsed_url.scheme}://{base_domain}"
        
        # Obtener el contenido de la página con headers específicos para simular un navegador real
        # y manejar correctamente las solicitudes CORS
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Origin': base_url,
            'Referer': base_url + '/',
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
        session = requests.Session()
        session.headers.update(headers)
        
        # Intentar obtener la página con reintentos y delays para evitar bloqueos
        max_retries = 3
        retry_delay = 2
        
        for retry in range(max_retries):
            try:
                # Primero, visitar la página principal para obtener cookies
                print(f"Visitando la página principal de {base_url} para obtener cookies...")
                session.get(base_url, timeout=10)
                
                # Luego intentar acceder a la URL del capítulo
                print(f"Intentando acceder a {url} (intento {retry+1}/{max_retries})...")
                response = session.get(url, timeout=10)
                
                if response.status_code == 200:
                    print("Acceso exitoso a la página.")
                    break
                elif response.status_code == 403:
                    print(f"Error 403 Forbidden al acceder a la URL (intento {retry+1}/{max_retries})")
                    if retry < max_retries - 1:
                        wait_time = retry_delay * (retry + 1)
                        print(f"Esperando {wait_time} segundos antes de reintentar...")
                        time.sleep(wait_time)
                else:
                    print(f"Error al acceder a la URL: {response.status_code} (intento {retry+1}/{max_retries})")
                    if retry < max_retries - 1:
                        wait_time = retry_delay * (retry + 1)
                        print(f"Esperando {wait_time} segundos antes de reintentar...")
                        time.sleep(wait_time)
            except Exception as e:
                print(f"Error de conexión (intento {retry+1}/{max_retries}): {str(e)}")
                if retry < max_retries - 1:
                    wait_time = retry_delay * (retry + 1)
                    print(f"Esperando {wait_time} segundos antes de reintentar...")
                    time.sleep(wait_time)
        
        # Verificar si después de los reintentos se pudo acceder a la página
        if not hasattr(response, 'status_code') or response.status_code != 200:
            print(f"Error al acceder a la URL después de {max_retries} intentos.")
            return
            
        # Guardar la respuesta en un archivo temporal
        # with open('ikigaiResponse.html', 'w', encoding='utf-8') as f:
        #     f.write(response.text)
        
        # Intentar extraer el contenido usando BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Si no encontramos las imágenes, podríamos necesitar cargar el contenido dinámicamente
        # En una implementación futura, se podría considerar usar selenium para renderizar JavaScript
        
        # Inicializar variables
        manga_title = "Manga Desconocido"
        chapter_number = 0
        
        # Extraer título del manga
        title_element = soup.select_one("ul.flex-center.gap-2.text-xs.font-medium.pt-4 a")
        if title_element:
            manga_title = title_element.text.strip()
        
        # Buscar el número de capítulo
        chapter_element = soup.select_one("ul.flex-center.gap-2.text-xs.font-medium.pt-4 li:nth-child(2)")
        if chapter_element:
            chapter_text = chapter_element.text.strip()
            # Extraer números, incluyendo decimales
            try:
                # Buscar patrones como '2.5' o '6.05' o simplemente '5'
                match = re.search(r'\d+(?:\.\d+)?', chapter_text)
                if match:
                    chapter_number = float(match.group())
                    # Convertir a entero si es un número entero
                    if chapter_number.is_integer():
                        chapter_number = int(chapter_number)
                    print(f"Capítulo: {chapter_number}")
            except (AttributeError, ValueError):
                print("No se pudo convertir el número de capítulo. Usando 0 como valor predeterminado.")
        
        # Extraer URLs de capítulos anterior y siguiente para navegación
        prev_chapter_url = None
        next_chapter_url = None
        
        # Buscar enlaces de capítulos anterior y siguiente
        # Primero intentamos con los enlaces de navegación específicos
        nav_links = soup.select("div.flex.justify-between.items-center a[href]")
        
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        # Verificar si encontramos los enlaces de navegación
        if len(nav_links) >= 2:
            # El primer enlace suele ser el capítulo anterior
            if 'href' in nav_links[0].attrs:
                prev_chapter_url = urljoin(base_url, nav_links[0]['href'])
            
            # El último enlace suele ser el capítulo siguiente
            if 'href' in nav_links[-1].attrs:
                next_chapter_url = urljoin(base_url, nav_links[-1]['href'])
        
        # Si no encontramos los enlaces con el selector anterior, intentamos con otro
        if not next_chapter_url:
            nav_links = soup.select("ul.flex-center.gap-2.text-xs.font-medium.pt-2.pb-4 a[href]")
            
            if len(nav_links) >= 2:
                # El primer enlace suele ser el capítulo anterior
                if 'href' in nav_links[0].attrs:
                    prev_chapter_url = urljoin(base_url, nav_links[0]['href'])
                
                # El segundo enlace suele ser el capítulo siguiente
                if 'href' in nav_links[1].attrs:
                    next_chapter_url = urljoin(base_url, nav_links[1]['href'])
        
        # Verificar que las URLs de navegación sean diferentes a la URL actual
        if prev_chapter_url == url:
            prev_chapter_url = None
        if next_chapter_url == url:
            next_chapter_url = None
        
        # Extraer imágenes - usando múltiples selectores para ser más robustos
        # Intentar diferentes estrategias para encontrar las imágenes
        image_elements = []
        
        # Estrategia 1: Buscar divs con clase w-full que contienen imágenes
        image_containers = soup.select("div.w-full")
        for container in image_containers:
            # Buscar la etiqueta img dentro del contenedor
            img_tag = container.select_one("div.img img") or container.select_one("img")
            if img_tag and img_tag.get('src'):
                # Verificar que la URL de la imagen sea de un archivo de imagen
                src = img_tag.get('src')
                if any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']):
                    image_elements.append(img_tag)
                    print(f"Encontrada imagen (estrategia 1): {src}")
        
        # Estrategia 2: Buscar todas las imágenes en la página que parezcan ser del manga
        if not image_elements:
            all_images = soup.select("img[src]")
            for img in all_images:
                src = img.get('src')
                # Filtrar imágenes que parecen ser del contenido del manga
                # Excluir imágenes pequeñas, iconos, logos, etc.
                if src and any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']):
                    # Excluir imágenes de publicidad o navegación
                    if not any(ad_term in src.lower() for ad_term in ['ad', 'banner', 'logo', 'icon', 'btn']):
                        image_elements.append(img)
                        print(f"Encontrada imagen (estrategia 2): {src}")
        
        # Estrategia 3: Buscar en atributos data-src o lazy-load
        if not image_elements:
            lazy_images = soup.select("img[data-src], img[data-lazy-src], img[data-original]")
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
        
        if not image_elements:
            print("No se encontraron imágenes en la página usando ninguna estrategia")
            return
        
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
            "next_chapter_url": next_chapter_url,
            "prev_chapter_url": prev_chapter_url,
            **result
        }
        
    except Exception as e:
        print(f"Error al scrapear Ikigai: {str(e)}")
        return None

def scrape_ikigai_consecutive(initial_url, download_images=True, num_chapters='todos'):
    """
    Descarga capítulos consecutivos de un manga de Ikigai.
    
    Args:
        initial_url: URL del capítulo inicial
        download_images: Si es True, descarga las imágenes de los capítulos
        num_chapters: Número de capítulos a descargar o 'todos' para descargar todos los disponibles
    """
    current_url = initial_url
    chapters_downloaded = 0
    max_chapters = float('inf') if num_chapters == 'todos' else int(num_chapters)
    
    # Para evitar bucles infinitos, mantenemos un registro de URLs visitadas
    visited_urls = set([current_url])
    
    # Descargar el capítulo inicial
    print(f"\n=== Procesando capítulo inicial: {current_url} ===")
    chapter_info = scrape_ikigai(current_url, download_images)
    
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
        next_url = chapter_info['next_chapter_url']
        
        # Verificar si la URL del siguiente capítulo ya ha sido visitada (evitar bucles)
        if next_url in visited_urls:
            print(f"URL del siguiente capítulo ({next_url}) ya fue procesada. Evitando bucle infinito.")
            break
        
        # Actualizar la URL actual y añadirla a las visitadas
        current_url = next_url
        visited_urls.add(current_url)
        
        print(f"\n=== Procesando capítulo siguiente ({chapters_downloaded + 1}/{max_chapters if max_chapters != float('inf') else 'todos'}): {current_url} ===")
        
        # Añadir una pequeña pausa para no sobrecargar el servidor
        time.sleep(1.5)
        
        chapter_info = scrape_ikigai(current_url, download_images)
        
        if not chapter_info:
            print("Error al procesar el capítulo. Deteniendo.")
            break
        
        chapters_downloaded += 1
        
        if not chapter_info.get('next_chapter_url'):
            print("No hay más capítulos disponibles.")
            break
    
    print(f"\n=== Proceso completado. Se descargaron {chapters_downloaded} capítulos. ===")