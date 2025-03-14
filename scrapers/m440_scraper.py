import re
import time
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from utils.http_utils import create_session, get_page_content
from utils.file_utils import (
    create_chapter_directory, save_metadata, download_image
)

def scrape_m440(url, download_images=True):
    """
    Descarga un capítulo específico de m440.in
    
    Args:
        url: URL del capítulo a descargar
        download_images: Si es True, descarga las imágenes del capítulo
        
    Returns:
        dict: Información del capítulo descargado, o None si hubo un error
    """
    try:
        # Verificar dominio
        # if not url.startswith("https://m440.in"):
        #     print("La URL no pertenece a m440.in")
        #     return None

        # Extraer información de la URL
        manga_match = re.search(r'manga/([^/]+)', url)
        chapter_match = re.search(r'/(\d+(?:\.\d+)?)-[^/]+', url)
        
        if not manga_match or not chapter_match:
            print("No se pudo extraer información del manga o capítulo de la URL")
            return None
            
        manga_slug = manga_match.group(1)
        chapter_number = float(chapter_match.group(1))
        if chapter_number.is_integer():
            chapter_number = int(chapter_number)
            
        manga_base_url = f"https://m440.in/manga/{manga_slug}"
        print(f"Extrayendo capítulo {chapter_number} de {manga_slug}...")
        
        # Crear sesión
        session = create_session()
        
        # Obtener título del manga
        soup, _ = get_page_content(session, manga_base_url)
        manga_name = soup.select_one("h2.widget-title").text.strip() if soup and soup.select_one("h2.widget-title") else manga_slug.replace('-', ' ').title()
        print(f"Manga: {manga_name}")
        
        # Obtener página del capítulo
        soup, response = get_page_content(session, url)
        if not soup:
            print(f"No se pudo acceder al capítulo: {url}")
            return None
            
        chapter_name = f"Capítulo {chapter_number}"
        title_tag = soup.select_one("h1 b")
        if title_tag:
            chapter_name = title_tag.text.strip()
        print(f"Título del capítulo: {chapter_name}")
        
        # Extraer imágenes
        image_urls = []
        image_tags = soup.select("div#all img")
        
        if not image_urls and image_tags:
            for img in image_tags:
                src = img.get('data-src') or img.get('src')
                if src and src != "https://m440.in/images/loading.gif":
                    image_urls.append(urljoin(url, src))
        
        if not image_urls:
            print("No se encontraron imágenes en el capítulo.")
            return None
            
        total_images = len(image_urls)
        print(f"Se encontraron {total_images} imágenes.")
        
        # Preparar la información detallada de cada imagen
        images = []
        for i, img_url in enumerate(image_urls, 1):
            # Determinar la extensión del archivo
            extension = "jpg"  # Por defecto
            if ".webp" in img_url.lower():
                extension = "webp"
            elif ".png" in img_url.lower():
                extension = "png"
            elif ".jpeg" in img_url.lower() or ".jpg" in img_url.lower():
                extension = "jpg"
                
            # Crear el nombre del archivo con formato adecuado
            filename = f"{i-1:02d}.{extension}"
            
            # Crear la descripción de la imagen
            description = f"{manga_name} > {chapter_name} > Page {i:02d}"
            
            # Añadir la información de la imagen
            images.append({
                "url": img_url,
                "number": i,
                "filename": filename,
                "description": description
            })
        
        # Construir información del capítulo con la nueva estructura
        chapter_info = {
            'manga_name': manga_name,
            'chapter_name': chapter_name,
            'chapter_number': chapter_number,
            'total_images': total_images,
            'images': images
        }
        
        # Añadir información adicional que podría ser útil
        chapter_info['source_url'] = url
        chapter_info['downloaded_at'] = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # Buscar navegación
        next_link = soup.find("a", onclick="return nextChap();")
        prev_link = soup.find("a", onclick="return prevChap();")
        if next_link and next_link.get('href'):
            chapter_info['next_chapter_url'] = urljoin(url, next_link['href'])
        if prev_link and prev_link.get('href'):
            chapter_info['prev_chapter_url'] = urljoin(url, prev_link['href'])
        
        # Crear directorio y guardar metadatos siempre
        chapter_dir = create_chapter_directory(manga_name, chapter_number, chapter_name)
        save_metadata(chapter_dir, chapter_info)
        
        # Descargar imágenes solo si se solicita
        if download_images:
            print("Descargando imágenes...")
            
            for image_info in images:
                img_url = image_info['url']
                img_filename = image_info['filename']
                img_path = f"{chapter_dir}/{img_filename}"
                
                print(f"Descargando imagen {image_info['number']}/{total_images}: {img_url}")
                success = download_image(session, img_url, img_path)
                
                if not success:
                    print(f"Error al descargar la imagen {image_info['number']}")
                    
                time.sleep(0.5)
                
            print(f"Capítulo descargado en: {chapter_dir}")
        else:
            print(f"Metadatos guardados en: {chapter_dir}")
        
        return chapter_info
        
    except Exception as e:
        print(f"Error al descargar el capítulo: {str(e)}")
        import traceback
        traceback.print_exc()
        return None
