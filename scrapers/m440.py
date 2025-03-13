#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Módulo especializado para el scraping de manga desde m440.in utilizando Playwright
para manejar el contenido cargado por JavaScript.
"""

import re
import json
import time
import os
import asyncio
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError

# Importar utilidades
from utils.file_utils import create_chapter_directory, save_metadata, download_image, sanitize_filename
from utils.http_utils import create_session

async def get_chapters(url):
    """
    Obtiene la lista de capítulos de un manga en m440.in utilizando Playwright.
    
    Args:
        url: URL principal del manga en m440.in (ejemplo: https://m440.in/manga/the-return-of-the-disasterclass-hero)
        
    Returns:
        list: Lista de capítulos con su número, URL y título, ordenados por número
    """
    try:
        # Verificar que la URL sea la principal del manga
        if '/capitulo/' in url or re.search(r'/\d+-[a-zA-Z0-9]+(?:/\d+)?$', url):
            base_match = re.search(r'(https://m440\.in/manga/[^/]+)', url)
            if base_match:
                url = base_match.group(1)
                print(f"URL ajustada a: {url}")
            else:
                print("La URL proporcionada parece ser de un capítulo específico. Por favor, usa la URL principal del manga.")
                return None
        
        # Extraer el slug del manga
        manga_slug = url.split("/")[-1]
        print(f"Procesando manga: {manga_slug}")
        
        print(f"Iniciando navegador para acceder a {url}...")
        async with async_playwright() as p:
            # Iniciar navegador en modo headless
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            
            page = await context.new_page()
            print(f"Navegando a {url}...")
            await page.goto(url, wait_until="networkidle")
            print("Página cargada completamente")
            
            # Esperar a que el contenido JavaScript se cargue completamente
            try:
                await page.wait_for_selector("div.manga-detail", timeout=10000)
            except TimeoutError:
                print("No se encontró el selector 'div.manga-detail' en la página. Intentando con otro selector...")
                try:
                    await page.wait_for_selector("div.#LdlOI", timeout=10000)
                except TimeoutError:
                    print("No se encontró el selector 'div.chapter-list' en la página. Intentando con otro selector...")
                    try:
                        await page.wait_for_selector("div.chapter-item", timeout=10000)
                    except TimeoutError:
                        print("No se encontró el selector 'div.chapter-item' en la página. No se pudo cargar la página correctamente.")
                        return None
            
            # Obtener información del manga
            manga_title = await page.evaluate("() => { const el = document.querySelector('h2.element-subtitle, h2.widget-title'); return el ? el.innerText.trim() : null; }")
            
            if not manga_title:
                manga_title = manga_slug.replace('-', ' ').title()
            
            print(f"Título del manga: {manga_title}")
            
            # Método 1: Extraer datos de capítulos desde el JavaScript
            print("Extrayendo datos de capítulos desde JavaScript...")
            chapters_js_data = await page.evaluate("""
                () => {
                    // Buscar todas las variables globales que pueden contener datos de capítulos
                    let chaptersData = null;
                    
                    // Verificar variable específica que sabemos que contiene capítulos
                    if (typeof WAJSyPTQroOZxNtmGUsbCW !== 'undefined') {
                        return WAJSyPTQroOZxNtmGUsbCW;
                    }
                    
                    // Buscar en otras variables globales que podrían contener datos de capítulos
                    for (const key in window) {
                        try {
                            if (window[key] && typeof window[key] === 'object') {
                                // Buscar objetos que tengan una propiedad 'data' con un array
                                if (window[key].data && Array.isArray(window[key].data) && 
                                    window[key].data.length > 0 && 
                                    (window[key].data[0].number || window[key].data[0].slug)) {
                                    return window[key];
                                }
                                
                                // Buscar arrays directamente que parezcan tener información de capítulos
                                if (Array.isArray(window[key]) && window[key].length > 0) {
                                    const firstItem = window[key][0];
                                    if (firstItem && typeof firstItem === 'object' && 
                                        (firstItem.number || firstItem.slug || firstItem.id)) {
                                        return { data: window[key] };
                                    }
                                }
                            }
                        } catch (e) {
                            // Ignorar errores al acceder a propiedades
                            continue;
                        }
                    }
                    
                    return null;
                }
            """)
            
            chapters = []
            
            if chapters_js_data and isinstance(chapters_js_data, dict):
                chapters_data = chapters_js_data.get('data', []) if 'data' in chapters_js_data else []
                
                if chapters_data and len(chapters_data) > 0:
                    print(f"Se encontraron {len(chapters_data)} capítulos en los datos de JavaScript")
                    
                    for chapter in chapters_data:
                        chapter_num = chapter.get('number', '')
                        chapter_slug = chapter.get('slug', '')
                        chapter_name = chapter.get('name', f"Capítulo {chapter_num}")
                        
                        if chapter_num and chapter_slug:
                            chapter_url = f"{url}/{chapter_slug}"
                            try:
                                chapter_num_float = float(chapter_num)
                            except ValueError:
                                chapter_num_float = 0
                                
                            chapters.append({
                                'number': chapter_num_float,
                                'url': chapter_url,
                                'title': chapter_name
                            })
            
            # Método 2: Si no se encontraron capítulos, intentar extraerlos de los enlaces en la página
            if not chapters:
                print("Extrayendo enlaces de capítulos directamente desde la página...")
                chapters_html = await page.evaluate("""
                    () => {
                        // Buscar enlaces de capítulos con diferentes selectores
                        const selectors = [
                            'a[href*="/capitulo/"]', 
                            'a[href*="-mvow1"]',
                            '.chapters-container a',
                            '.chapter-list a',
                            'li.chapter a',
                            '.episodes-list a'
                        ];
                        
                        let results = [];
                        
                        // Probar cada selector
                        for (const selector of selectors) {
                            const links = Array.from(document.querySelectorAll(selector));
                            if (links.length > 0) {
                                console.log(`Encontrados ${links.length} enlaces con selector: ${selector}`);
                                
                                // Convertir enlaces a objetos simples
                                const linkObjects = links.map(link => ({
                                    href: link.href,
                                    text: link.innerText.trim()
                                }));
                                
                                results = results.concat(linkObjects);
                            }
                        }
                        
                        // Eliminar duplicados
                        const uniqueLinks = {};
                        for (const link of results) {
                            if (!uniqueLinks[link.href]) {
                                uniqueLinks[link.href] = link;
                            }
                        }
                        
                        return Object.values(uniqueLinks);
                    }
                """)
                
                if chapters_html:
                    print(f"Se encontraron {len(chapters_html)} posibles enlaces a capítulos")
                    
                    for link in chapters_html:
                        href = link.get('href', '')
                        text = link.get('text', '')
                        
                        if not href:
                            continue
                            
                        # Intentar extraer el número de capítulo de la URL o del texto
                        chapter_num = None
                        
                        # Patrón para extraer el número de capítulo de la URL
                        num_match = re.search(r'/capitulo/(\d+(?:\.\d+)?)', href)
                        if num_match:
                            try:
                                chapter_num = float(num_match.group(1))
                            except ValueError:
                                pass
                        
                        # Si no se pudo extraer el número de la URL, intentar del texto
                        if chapter_num is None and text:
                            num_match = re.search(r'(?:Capítulo|Cap[ií]tulo|Cap|Chapter|Chap|Ch|#)\s*(\d+(?:\.\d+)?)', text, re.IGNORECASE)
                            if num_match:
                                try:
                                    chapter_num = float(num_match.group(1))
                                except ValueError:
                                    pass
                        
                        # Si aún no se tiene el número, extraerlo del final de la URL
                        if chapter_num is None:
                            num_match = re.search(r'(\d+(?:\.\d+)?)-[^/]+/?$', href)
                            if num_match:
                                try:
                                    chapter_num = float(num_match.group(1))
                                except ValueError:
                                    pass
                        
                        # Si no se pudo extraer un número de capítulo, asignar uno arbitrario
                        if chapter_num is None:
                            # Asignar un número negativo para que quede al final de la lista
                            chapter_num = -1 * (len(chapters) + 1)
                        
                        # Si no se tiene título, usar un título genérico
                        if not text:
                            text = f"Capítulo {chapter_num}"
                        
                        chapters.append({
                            'number': chapter_num,
                            'url': href,
                            'title': text
                        })
            
            # Método 3: Buscar en el HTML completo de la página
            if not chapters:
                print("Analizando HTML completo para encontrar referencias a capítulos...")
                page_html = await page.content()
                
                # Buscar URLs de capítulos en el HTML
                chapter_urls = re.findall(r'["\']((?:https?:)?//[^"\']+/capitulo/[^"\']+)["\']', page_html)
                chapter_urls += re.findall(r'["\']((?:https?:)?//[^"\']+/\d+(?:\.\d+)?-[^"\']+)["\']', page_html)
                
                # Procesar URLs encontradas
                if chapter_urls:
                    print(f"Se encontraron {len(chapter_urls)} URLs de capítulos en el HTML")
                    
                    for url_match in chapter_urls:
                        # Convertir a URL completa si es necesario
                        if url_match.startswith('//'):
                            url_match = 'https:' + url_match
                        elif not url_match.startswith(('http://', 'https://')):
                            url_match = urljoin(url, url_match)
                        
                        # Extraer número de capítulo
                        num_match = re.search(r'/capitulo/(\d+(?:\.\d+)?)', url_match)
                        if not num_match:
                            num_match = re.search(r'/(\d+(?:\.\d+)?)-', url_match)
                        
                        if num_match:
                            try:
                                chapter_num = float(num_match.group(1))
                                chapters.append({
                                    'number': chapter_num,
                                    'url': url_match,
                                    'title': f"Capítulo {chapter_num}"
                                })
                            except ValueError:
                                continue
            
            # Método 4: Si seguimos sin capítulos, tomar una captura de pantalla de la página para diagnóstico
            if not chapters:
                print("No se encontraron capítulos. Tomando captura de pantalla para diagnóstico...")
                debug_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "debug")
                os.makedirs(debug_dir, exist_ok=True)
                
                screenshot_path = os.path.join(debug_dir, f"manga_{manga_slug}.png")
                await page.screenshot(path=screenshot_path)
                print(f"Captura guardada en: {screenshot_path}")
                
                html_path = os.path.join(debug_dir, f"manga_{manga_slug}.html")
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(await page.content())
                print(f"HTML guardado en: {html_path}")
            
            # Cerrar navegador
            await browser.close()
            
            if chapters:
                # Eliminar duplicados basados en la URL
                unique_chapters = []
                seen_urls = set()
                
                for chapter in chapters:
                    if chapter['url'] not in seen_urls:
                        seen_urls.add(chapter['url'])
                        unique_chapters.append(chapter)
                
                # Ordenar por número de capítulo
                unique_chapters.sort(key=lambda x: x['number'])
                print(f"Se encontraron un total de {len(unique_chapters)} capítulos únicos")
                return unique_chapters
            else:
                print("No se encontraron capítulos para este manga")
                return []
                
    except Exception as e:
        print(f"Error al obtener la lista de capítulos: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

async def scrape_chapter(chapter_url, output_directory, download_images=True):
    """
    Extrae las imágenes de un capítulo específico utilizando Playwright para manejar el contenido JavaScript.
    
    Args:
        chapter_url: URL del capítulo a descargar
        output_directory: Directorio donde se guardarán las imágenes y metadatos
        download_images: Si es True, descarga las imágenes; si es False, solo devuelve la metadata
        
    Returns:
        dict: Diccionario con información del capítulo (título, número, imágenes, etc.)
    """
    try:
        # Extraer información del capítulo de la URL
        chapter_num_match = re.search(r'/capitulo/(\d+(?:\.\d+)?)', chapter_url)
        if not chapter_num_match:
            # Intentar otro patrón común
            chapter_num_match = re.search(r'/(\d+(?:\.\d+)?)-', chapter_url)
            
        chapter_num = chapter_num_match.group(1) if chapter_num_match else "desconocido"
        
        print(f"Iniciando descarga del capítulo {chapter_num} desde {chapter_url}")
        
        # Crear directorio para el capítulo
        chapter_dir = create_chapter_directory(output_directory, chapter_num)
        if not chapter_dir and download_images:
            print(f"No se pudo crear el directorio para el capítulo {chapter_num}")
            return None
            
        # Iniciar Playwright para navegar a la página del capítulo
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            
            page = await context.new_page()
            print(f"Navegando a la página del capítulo: {chapter_url}")
            
            # Navegar a la página y esperar a que se cargue completamente
            await page.goto(chapter_url, wait_until="networkidle")
            print("Página del capítulo cargada completamente")
            
            # Esperar a que las imágenes se carguen usando varios selectores posibles
            selectors_to_try = [
                "div.reader-content", 
                "div.chapter-content", 
                ".reader img", 
                ".img-container img",
                ".chapter-container img",
                "div.image-container"
            ]
            
            selector_found = False
            for selector in selectors_to_try:
                try:
                    await page.wait_for_selector(selector, timeout=5000)
                    print(f"Selector encontrado: {selector}")
                    selector_found = True
                    break
                except TimeoutError:
                    continue
                    
            if not selector_found:
                print("No se encontraron selectores específicos para las imágenes. Esperando tiempo adicional...")
                await page.wait_for_timeout(5000)  # Esperar 5 segundos adicionales
            
            # Obtener título del capítulo
            chapter_title = await page.evaluate("""
                () => {
                    const selectors = [
                        'h1.reader-title', 
                        'h2.chapter-title', 
                        '.chapter-heading h1',
                        'title'
                    ];
                    
                    for (const selector of selectors) {
                        const el = document.querySelector(selector);
                        if (el) {
                            return el.innerText.trim() || el.textContent.trim();
                        }
                    }
                    
                    // Si no se encuentra, extraer del título de la página
                    return document.title;
                }
            """)
            
            # Método 1: Extraer datos de imágenes desde JavaScript
            print("Buscando variables de JavaScript con URLs de imágenes...")
            images_js_data = await page.evaluate("""
                () => {
                    // Buscar variables que contengan URLs de imágenes
                    const imageVariables = [];
                    
                    // Buscar en variables globales específicas conocidas
                    const knownVars = [
                        'chapter_images', 'chapterImages', 'CHAPTER_IMAGES', 
                        'READER_IMAGES', 'readerImages', 'chapter_data'
                    ];
                    
                    for (const varName of knownVars) {
                        if (typeof window[varName] !== 'undefined') {
                            imageVariables.push({
                                name: varName,
                                data: window[varName]
                            });
                        }
                    }
                    
                    // Buscar en todas las variables globales
                    for (const key in window) {
                        try {
                            if (window[key] && typeof window[key] === 'object') {
                                // Buscar arrays que contengan objetos con URLs de imágenes
                                if (Array.isArray(window[key]) && window[key].length > 0) {
                                    const firstItem = window[key][0];
                                    
                                    // Verificar si es un array de URLs o objetos con URLs
                                    if (typeof firstItem === 'string' && 
                                        (firstItem.endsWith('.jpg') || firstItem.endsWith('.png') || 
                                         firstItem.endsWith('.webp') || firstItem.endsWith('.jpeg'))) {
                                        imageVariables.push({
                                            name: key,
                                            data: window[key]
                                        });
                                    } 
                                    else if (typeof firstItem === 'object' && 
                                             (firstItem.url || firstItem.src || firstItem.image)) {
                                        imageVariables.push({
                                            name: key,
                                            data: window[key]
                                        });
                                    }
                                } 
                                // Buscar objetos que contengan un array de imágenes
                                else if (window[key].images && Array.isArray(window[key].images)) {
                                    imageVariables.push({
                                        name: key,
                                        data: window[key].images
                                    });
                                }
                            }
                        } catch (e) {
                            // Ignorar errores al acceder a propiedades
                            continue;
                        }
                    }
                    
                    return imageVariables;
                }
            """)
            
            images = []
            
            # Procesar datos de JavaScript si se encontraron
            if images_js_data and len(images_js_data) > 0:
                print(f"Se encontraron {len(images_js_data)} posibles fuentes de datos de imágenes")
                
                for source in images_js_data:
                    js_data = source.get('data', [])
                    source_name = source.get('name', 'unknown')
                    
                    print(f"Procesando datos de imágenes de la fuente: {source_name}")
                    
                    # Si es un array de strings (URLs directas)
                    if all(isinstance(item, str) for item in js_data):
                        for i, url in enumerate(js_data):
                            images.append({
                                'index': i + 1,
                                'url': url
                            })
                    # Si es un array de objetos con URLs
                    elif all(isinstance(item, dict) for item in js_data):
                        for i, item in enumerate(js_data):
                            img_url = item.get('url', item.get('src', item.get('image', '')))
                            if img_url:
                                images.append({
                                    'index': i + 1,
                                    'url': img_url
                                })
                
                if images:
                    print(f"Se encontraron {len(images)} imágenes a través de datos de JavaScript")
            
            # Método 2: Si no se encontraron imágenes en JavaScript, extraerlas del DOM
            if not images:
                print("Extrayendo imágenes directamente del DOM...")
                images_html = await page.evaluate("""
                    () => {
                        // Buscar imágenes con diferentes selectores
                        const selectors = [
                            '.reader-content img', 
                            '.chapter-content img',
                            '.reader img',
                            '.page-break img',
                            '.wp-manga-chapter-img',
                            '.chapter-container img',
                            '.manga-container img'
                        ];
                        
                        let allImages = [];
                        
                        // Probar cada selector
                        for (const selector of selectors) {
                            const imgs = Array.from(document.querySelectorAll(selector));
                            if (imgs.length > 0) {
                                console.log(`Encontradas ${imgs.length} imágenes con selector: ${selector}`);
                                
                                const imageData = imgs.map((img, index) => ({
                                    index: index + 1,
                                    url: img.src || img.dataset.src || img.dataset.lazySrc
                                }));
                                
                                allImages = allImages.concat(imageData);
                            }
                        }
                        
                        // Filtrar imágenes válidas y eliminar duplicados
                        const validImages = allImages.filter(img => 
                            img.url && 
                            !img.url.includes('data:image') && 
                            !img.url.includes('blank.gif') &&
                            !img.url.includes('loading.gif')
                        );
                        
                        // Eliminar duplicados por URL
                        const uniqueImages = [];
                        const seenUrls = new Set();
                        
                        for (const img of validImages) {
                            if (!seenUrls.has(img.url)) {
                                seenUrls.add(img.url);
                                uniqueImages.push(img);
                            }
                        }
                        
                        return uniqueImages;
                    }
                """)
                
                if images_html:
                    print(f"Se encontraron {len(images_html)} imágenes en el DOM")
                    images = images_html
            
            # Método 3: Buscar en el HTML completo de la página
            if not images:
                print("Analizando HTML completo para encontrar URLs de imágenes...")
                html_content = await page.content()
                
                # Patrones comunes para URLs de imágenes
                img_patterns = [
                    r'["\'](https?://[^"\']+\.(?:jpg|jpeg|png|webp)(?:\?[^"\']*)?)["\']',
                    r'data-src=["\']([^"\']+\.(?:jpg|jpeg|png|webp)(?:\?[^"\']*)?)["\']',
                    r'data-lazy-src=["\']([^"\']+\.(?:jpg|jpeg|png|webp)(?:\?[^"\']*)?)["\']'
                ]
                
                all_urls = set()
                for pattern in img_patterns:
                    matches = re.findall(pattern, html_content)
                    for match in matches:
                        # Filtrar imágenes no deseadas (íconos, logos, etc.)
                        if not any(skip in match for skip in ['avatar', 'banner', 'logo', 'icon', 'thumb']):
                            all_urls.add(match)
                
                if all_urls:
                    print(f"Se encontraron {len(all_urls)} URLs de imágenes en el HTML")
                    
                    # Convertir a formato de lista de imágenes
                    images = [{'index': i+1, 'url': url} for i, url in enumerate(all_urls)]
            
            # Método 4: Tomar capturas de pantalla si no se encontraron imágenes
            if not images:
                print("No se encontraron imágenes. Tomando captura de pantalla para diagnóstico...")
                debug_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "debug")
                os.makedirs(debug_dir, exist_ok=True)
                
                screenshot_path = os.path.join(debug_dir, f"chapter_{chapter_num}.png")
                await page.screenshot(path=screenshot_path)
                print(f"Captura guardada en: {screenshot_path}")
                
                html_path = os.path.join(debug_dir, f"chapter_{chapter_num}.html")
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(await page.content())
                print(f"HTML guardado en: {html_path}")
            
            # Cerrar navegador
            await browser.close()
            
            if not images:
                print("No se pudieron encontrar imágenes para este capítulo")
                return None
            
            print(f"Se encontraron {len(images)} imágenes en total")
            
            # Metadata del capítulo
            chapter_info = {
                'title': chapter_title or f"Capítulo {chapter_num}",
                'number': chapter_num,
                'images': []
            }
            
            # Descargar imágenes si se ha solicitado
            if download_images:
                print(f"Descargando {len(images)} imágenes...")
                
                # Crear session HTTP para descargas
                session = await create_session()
                
                for i, img in enumerate(images):
                    img_url = img['url']
                    img_index = img['index']
                    filename = f"{i+1:03d}.jpg"  # Formato 001.jpg, 002.jpg, etc.
                    
                    # Guardar la info de la imagen
                    chapter_info['images'].append({
                        'index': img_index,
                        'filename': filename,
                        'url': img_url
                    })
                    
                    # Descargar imagen
                    filepath = os.path.join(chapter_dir, filename)
                    success = await download_image(session, img_url, filepath)
                    
                    if success:
                        print(f"Descargada imagen {i+1}/{len(images)}: {filename}")
                    else:
                        print(f"Error al descargar imagen {i+1}/{len(images)}: {img_url}")
                
                # Cerrar la sesión HTTP
                await session.close()
                
                # Guardar metadata del capítulo
                metadata_path = os.path.join(chapter_dir, "metadata.json")
                save_metadata(metadata_path, chapter_info)
                print(f"Metadata guardada en: {metadata_path}")
            else:
                # Solo registrar URLs sin descargar
                for i, img in enumerate(images):
                    img_url = img['url']
                    img_index = img['index']
                    filename = f"{i+1:03d}.jpg"
                    
                    chapter_info['images'].append({
                        'index': img_index,
                        'filename': filename,
                        'url': img_url
                    })
            
            return chapter_info
            
    except Exception as e:
        print(f"Error al descargar el capítulo: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


# Función para procesar enlaces de capítulos
def process_chapter_links(chapter_links, base_url):
    """
    Procesa enlaces a capítulos y extrae información relevante.
    
    Args:
        chapter_links: Lista de elementos <a> a procesar
        base_url: URL base para resolver URLs relativas
        
    Returns:
        list: Lista de información de capítulos
    """
    chapters = []
    
    for link in chapter_links:
        try:
            # Obtener URL y texto del enlace
            href = link.get('href')
            if not href:
                continue
                
            # Resolver URL relativa si es necesario
            chapter_url = urljoin(base_url, href)
            
            # Obtener texto del enlace
            text = link.get_text().strip()
            
            # Extraer número de capítulo
            chapter_num = None
            
            # Intentar extraer de la URL
            num_match = re.search(r'/capitulo/(\d+(?:\.\d+)?)', chapter_url)
            if not num_match:
                num_match = re.search(r'/(\d+(?:\.\d+)?)-', chapter_url)
                
            if num_match:
                try:
                    chapter_num = float(num_match.group(1))
                    if chapter_num.is_integer():
                        chapter_num = int(chapter_num)
                except ValueError:
                    pass
            
            # Si no se encontró en la URL, buscar en el texto
            if chapter_num is None and text:
                num_match = re.search(r'(?:Capítulo|Cap[ií]tulo|Cap|Chapter|Chap|Ch|#)\s*(\d+(?:\.\d+)?)', text, re.IGNORECASE)
                if num_match:
                    try:
                        chapter_num = float(num_match.group(1))
                        if chapter_num.is_integer():
                            chapter_num = int(chapter_num)
                    except ValueError:
                        pass
            
            # Si aún no se tiene número, asignar uno arbitrario
            if chapter_num is None:
                chapter_num = -1 * (len(chapters) + 1)
            
            # Título del capítulo
            chapter_title = text if text else f"Capítulo {chapter_num}"
            
            chapters.append({
                'number': chapter_num,
                'url': chapter_url,
                'title': chapter_title
            })
            
        except Exception as e:
            print(f"Error al procesar enlace de capítulo: {str(e)}")
            continue
    
    # Ordenar capítulos por número
    if chapters:
        chapters.sort(key=lambda x: x['number'])
    
    return chapters


# Funciones de utilidad para ejecutar código asíncrono
def get_m440_chapters(url):
    """Wrapper síncrono para get_chapters"""
    return asyncio.run(get_chapters(url))

def scrape_m440(chapter_url, output_directory, download_images=True):
    """Wrapper síncrono para scrape_chapter"""
    return asyncio.run(scrape_chapter(chapter_url, output_directory, download_images))