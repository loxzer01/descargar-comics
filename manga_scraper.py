#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Módulo principal para la descarga de manga de diversos sitios web.
Este script proporciona una interfaz de usuario para seleccionar 
sitios, mangas y capítulos para descargar.
"""

import os
import sys
import importlib
import re
from urllib.parse import urlparse

from config.sites import SUPPORTED_SITES, identify_site, print_supported_sites, get_site_id_by_number
from utils.file_utils import create_directories

def main():
    """Función principal del programa."""
    # Mostrar cabecera
    print("=" * 50)
    print("MANGA SCRAPER - DESCARGADOR DE MANGA")
    print("=" * 50)
    
    # Asegurarse de que exista el directorio de imágenes
    images_dir = create_directories()
    print(f"Directorio de descarga: {images_dir}")
    
    while True:
        # Mostrar menú principal
        print("\nMENU PRINCIPAL:")
        print("1. Descargar manga por URL")
        print("2. Ver sitios soportados")
        print("3. Salir")
        
        option = input("\nSelecciona una opción (1-3): ").strip()
        
        if option == "1":
            download_by_url()
        elif option == "2":
            print_supported_sites()
        elif option == "3":
            print("\n¡Gracias por usar Manga Scraper!")
            sys.exit(0)
        else:
            print("Opción no válida. Inténtalo de nuevo.")

def download_by_url():
    """Descarga manga a partir de una URL proporcionada por el usuario."""
    while True:
        url = input("\nIntroduce la URL del manga o capítulo (o 'q' para volver): ").strip()
        
        if url.lower() == 'q':
            return
            
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            
        # Identificar el sitio
        site_config = identify_site(url)
        
        if not site_config:
            print("La URL proporcionada no pertenece a ningún sitio soportado.")
            print_supported_sites()
            continue
            
        print(f"Sitio detectado: {site_config['name']}")
        
        # Determinar si es una URL de manga o capítulo
        is_chapter_url = is_chapter(url, site_config)
        
        if is_chapter_url:
            download_single_chapter(url, site_config)
        else:
            download_manga_chapters(url, site_config)
            
        # Preguntar si desea descargar otro manga
        again = input("\n¿Deseas descargar otro manga? (s/n): ").strip().lower()
        if again != 's':
            break

def is_chapter(url, site_config):
    """
    Determina si una URL es de un capítulo específico o de la página principal del manga.
    
    Args:
        url: URL a verificar
        site_config: Configuración del sitio
        
    Returns:
        bool: True si es una URL de capítulo, False si es una URL de manga
    """
    domain = site_config['domain']
    
    # Patrones comunes para URLs de capítulos
    chapter_patterns = [
        r'/capitulo/',
        r'/chapter/',
        r'/chap(ter)?-\d+',
        r'/c\d+',
        r'/\d+-[a-zA-Z0-9]+'
    ]
    
    for pattern in chapter_patterns:
        if re.search(pattern, url):
            return True
            
    return False

def download_single_chapter(url, site_config):
    """
    Descarga un único capítulo desde una URL de capítulo.
    
    Args:
        url: URL del capítulo a descargar
        site_config: Configuración del sitio
    """
    print(f"\nDescargando capítulo desde: {url}")
    
    # Importar dinámicamente la función de scraping
    module_name = site_config['scraper_module']
    func_name = site_config['scrape_func']
    
    try:
        module = importlib.import_module(module_name)
        scrape_func = getattr(module, func_name)
        
        # Ejecutar la función de scraping
        chapter_info = scrape_func(url, download_images=True)
        
        if chapter_info:
            print(f"\nCapítulo descargado exitosamente:")
            print(f"Manga: {chapter_info['manga_title']}")
            print(f"Capítulo: {chapter_info['chapter_number']} - {chapter_info['chapter_title']}")
            print(f"Páginas: {chapter_info['page_count']}")
        else:
            print("No se pudo descargar el capítulo. Verifica la URL e intenta nuevamente.")
            
    except ImportError:
        print(f"Error: No se pudo importar el módulo {module_name}")
    except AttributeError:
        print(f"Error: La función {func_name} no existe en el módulo {module_name}")
    except Exception as e:
        print(f"Error al descargar el capítulo: {str(e)}")

def download_manga_chapters(url, site_config):
    """
    Obtiene la lista de capítulos de un manga y permite al usuario seleccionar 
    cuáles descargar.
    
    Args:
        url: URL de la página principal del manga
        site_config: Configuración del sitio
    """
    print(f"\nObteniendo lista de capítulos desde: {url}")
    
    # Importar dinámicamente las funciones
    module_name = site_config['scraper_module']
    get_chapters_func_name = site_config['get_chapters_func']
    scrape_func_name = site_config['scrape_func']
    
    try:
        module = importlib.import_module(module_name)
        get_chapters_func = getattr(module, get_chapters_func_name)
        scrape_func = getattr(module, scrape_func_name)
        
        # Obtener la lista de capítulos
        chapters = get_chapters_func(url)
        
        if not chapters:
            print("No se pudieron obtener los capítulos del manga.")
            return
            
        # Mostrar los capítulos disponibles
        print(f"\nSe encontraron {len(chapters)} capítulos:")
        
        # Mostrar los primeros y últimos 5 capítulos si hay muchos
        if len(chapters) > 10:
            # Primeros 5
            print("\nPrimeros 5 capítulos:")
            for i, chapter in enumerate(chapters[:5], 1):
                print(f"{i}. Capítulo {chapter['number']}: {chapter['title']} - {chapter['url']}")
                
            # Últimos 5
            print("\nÚltimos 5 capítulos:")
            for i, chapter in enumerate(chapters[-5:], len(chapters)-4):
                print(f"{i}. Capítulo {chapter['number']}: {chapter['title']} - {chapter['url']}")
        else:
            # Mostrar todos los capítulos
            for i, chapter in enumerate(chapters, 1):
                print(f"{i}. Capítulo {chapter['number']}: {chapter['title']} - {chapter['url']}")
                
        # Solicitar al usuario los capítulos a descargar
        while True:
            selection = input("\nSelecciona los capítulos a descargar (ej: 1,3,5-10 o 'todos'): ").strip().lower()
            
            if selection == 'q':
                return
                
            if selection == 'todos':
                selected_chapters = chapters
                break
                
            try:
                selected_indices = []
                parts = selection.split(',')
                
                for part in parts:
                    if '-' in part:
                        # Rango de capítulos
                        start, end = map(int, part.split('-'))
                        if start < 1 or end > len(chapters):
                            raise ValueError("Índice fuera de rango")
                        selected_indices.extend(range(start-1, end))
                    else:
                        # Capítulo individual
                        idx = int(part) - 1
                        if idx < 0 or idx >= len(chapters):
                            raise ValueError("Índice fuera de rango")
                        selected_indices.append(idx)
                
                selected_chapters = [chapters[i] for i in selected_indices]
                break
                
            except (ValueError, IndexError):
                print("Selección no válida. Intenta de nuevo.")
                
        # Descargar los capítulos seleccionados
        if not selected_chapters:
            print("No se seleccionaron capítulos para descargar.")
            return
            
        print(f"\nSe van a descargar {len(selected_chapters)} capítulos...")
        
        for i, chapter in enumerate(selected_chapters, 1):
            print(f"\n[{i}/{len(selected_chapters)}] Descargando Capítulo {chapter['number']}: {chapter['title']}")
            chapter_info = scrape_func(chapter['url'], download_images=True)
            
            if chapter_info:
                print(f"Capítulo {chapter['number']} descargado exitosamente ({chapter_info['page_count']} páginas)")
            else:
                print(f"Error al descargar el capítulo {chapter['number']}")
                
        print("\nDescarga completada.")
            
    except ImportError:
        print(f"Error: No se pudo importar el módulo {module_name}")
    except AttributeError:
        print(f"Error: Una de las funciones requeridas no existe en el módulo {module_name}")
    except Exception as e:
        print(f"Error al procesar los capítulos: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
