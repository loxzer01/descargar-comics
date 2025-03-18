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



# Importar utilidades goto
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
        
        # Verificar si existe un archivo capitulos.json para esta URL
        json_filename = "capitulos.json"
        if os.path.exists(json_filename):
            try:
                with open(json_filename, 'r', encoding='utf-8') as f:
                    chapters_data = json.load(f)
                
                # Verificar si ya tenemos datos para esta URL
                if url in chapters_data and chapters_data[url]:
                    print(f"Usando datos guardados para el manga {manga_slug}")
                    return chapters_data[url]
            except Exception as e:
                print(f"Error al cargar datos guardados: {str(e)}")
        
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
            await page.goto(url, wait_until="networkidle", timeout=60000)
            await page.wait_for_timeout(2000)  # Espera 2 segundos tras cargar
            print("Página cargada completamente")
            
            # Obtener información del manga
            manga_title = await page.evaluate("() => { const el = document.querySelector('h2.element-subtitle, h2.widget-title'); return el ? el.innerText.trim() : null; }")
            
            if not manga_title:
                manga_title = manga_slug.replace('-', ' ').title()
            
            print(f"Título del manga: {manga_title}")
            
            # Método optimizado: Extraer directamente los capítulos del DOM usando el selector específico
            print("Extrayendo capítulos directamente del DOM...")
            chapters_data = await page.evaluate("""
                () => {
                    // solicitar todos los capitulos
                    try {
                    const btnOnClickX = Number(document.querySelector("ul>pag").textContent.split(" / ")[1])
                    for(let xy=0; xy<btnOnClickX;xy++) {
                        document.querySelector("ul>pag").click()
                    }
                    } catch {
                        console.log("Error")
                    }


                    // Obtener la lista de capítulos usando el selector específico (div>ul)[2]
                    const chapterList = document.querySelectorAll("div>ul")[2];

                    if (!chapterList) return [];
                    
                    // Obtener todos los elementos li que contienen los capítulos
                    const chapterItems = chapterList.querySelectorAll("li");
                    const chapters = [];
                    
                    // Extraer información de cada capítulo
                    for (const item of chapterItems) {
                        // Buscar el enlace y el elemento em dentro del li
                        const link = item.querySelector("a");
                        const em = link ? link.querySelector("em") : null;
                        
                        if (link && em) {
                            // Extraer URL y título del capítulo
                            const href = link.getAttribute("href");
                            const title = em.textContent.trim();
                            
                            // Extraer número de capítulo del texto o de la URL
                            let chapterNum = null;
                            const numMatch = item.textContent.match(/#(\d+(?:\.\d+)?)/);
                            if (numMatch) {
                                chapterNum = numMatch[1];
                            } else {
                                // Intentar extraer de la URL
                                const urlMatch = href.match(/(\d+(?:\.\d+)?)-/);
                                if (urlMatch) {
                                    chapterNum = urlMatch[1];
                                }
                            }
                            
                            if (chapterNum && href) {
                                chapters.push({
                                    number: chapterNum,
                                    url: href,
                                    title: title
                                });
                            }
                        }
                    }
                    
                    return chapters;
                }
            """)
            
            chapters = []
            
            if chapters_data and len(chapters_data) > 0:
                print(f"Se encontraron {len(chapters_data)} capítulos en el DOM")
                
                for chapter in chapters_data:
                    chapter_num = chapter.get('number', '')
                    chapter_url = chapter.get('url', '')
                    chapter_title = chapter.get('title', f"Capítulo {chapter_num}")
                    
                    if chapter_num and chapter_url:
                        try:
                            chapter_num_float = float(chapter_num)
                        except ValueError:
                            chapter_num_float = 0
                            
                        chapters.append({
                            'number': chapter_num_float,
                            'url': chapter_url,
                            'title': chapter_title
                        })
            
            # Método 1: Si no se encontraron capítulos con el método optimizado, extraer datos de capítulos desde el JavaScript
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
