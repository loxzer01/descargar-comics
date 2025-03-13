import re
import time
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from utils.http_utils import create_session, get_page_content
from utils.file_utils import (
    create_chapter_directory, save_metadata, download_image, sanitize_filename
)

def get_m440_chapters(url):
    """
    Obtiene la lista de capítulos de un manga en m440.in.
    
    Args:
        url: URL principal del manga en m440.in (ejemplo: https://m440.in/manga/the-return-of-the-disasterclass-hero)
        
    Returns:
        list: Lista de capítulos con su número, URL y título,
              o None si no se pudieron obtener
    """
    try:
        # Verificar que la URL sea la principal del manga
        if '/capitulo/' in url or re.search(r'/\d+-[a-zA-Z0-9]+(?:/\d+)?$', url):
            base_match = re.search(r'(https://m440\.in/manga/[^/]+)', url)
            if base_match:
                url = base_match.group(1)
            else:
                print("La URL proporcionada parece ser de un capítulo específico. Por favor, usa la URL principal del manga.")
                return None
        
        # Extraer el slug del manga
        manga_slug = url.split("/")[-1]
        print(f"Procesando manga: {manga_slug}")
        
        # Crear sesión HTTP
        session = create_session()
        
        # Obtener la página principal del manga
        print(f"Obteniendo página principal desde {url}...")
        soup, response = get_page_content(session, url)
        if not soup:
            print("No se pudo acceder a la página del manga.")
            return None
        
        # Obtener el título del manga
        manga_title = None
        title_tag = soup.select_one("h2.widget-title")
        if title_tag:
            manga_title = title_tag.text.strip()
            print(f"Título del manga: {manga_title}")
        else:
            manga_title = manga_slug.replace('-', ' ').title()
            print(f"Título no encontrado, usando por defecto: {manga_title}")
        
        # Buscar la lista de capítulos
        chapter_list = soup.select_one("ul.chaptersul")
        if not chapter_list:
            print("No se encontró la lista de capítulos en la página.")
            return None
        
        chapters = []
        chapter_items = chapter_list.select("li")
        print(f"Se encontraron {len(chapter_items)} elementos de capítulos.")
        
        for item in chapter_items:
            try:
                # Encontrar el enlace del capítulo
                link = item.select_one("a")
                if not link or not link.get('href'):
                    continue
                
                chapter_url = urljoin(url, link['href'])
                
                # Extraer el número del capítulo desde la URL o el texto
                number_text = link.text.strip()
                number_match = re.search(r'Cap[^\d]*(\d+(?:\.\d+)?)', number_text, re.IGNORECASE)
                if number_match:
                    chapter_number = float(number_match.group(1))
                    if chapter_number.is_integer():
                        chapter_number = int(chapter_number)
                else:
                    # Intentar desde la URL
                    url_match = re.search(r'/(\d+(?:\.\d+)?)-', chapter_url)
                    if url_match:
                        chapter_number = float(url_match.group(1))
                        if chapter_number.is_integer():
                            chapter_number = int(chapter_number)
                    else:
                        print(f"No se pudo determinar el número del capítulo para: {chapter_url}")
                        continue
                
                # Título del capítulo
                chapter_title = number_text.strip() if number_text else f"Capítulo {chapter_number}"
                
                chapters.append({
                    'number': chapter_number,
                    'url': chapter_url,
                    'title': chapter_title
                })
            except Exception as e:
                print(f"Error al procesar un capítulo: {str(e)}")
                continue
        
        # Ordenar capítulos por número (de menor a mayor)
        chapters.sort(key=lambda x: x['number'])
        print(f"Total de capítulos encontrados: {len(chapters)}")
        
        if chapters:
            min_chap = min(chapters, key=lambda x: x['number'])['number']
            max_chap = max(chapters, key=lambda x: x['number'])['number']
            print(f"Rango de capítulos: {min_chap} - {max_chap}")
        
        return chapters if chapters else None
        
    except Exception as e:
        print(f"Error al obtener la lista de capítulos: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

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
        if not url.startswith("https://m440.in"):
            print("La URL no pertenece a m440.in")
            return None

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
        manga_title = soup.select_one("h2.widget-title").text.strip() if soup and soup.select_one("h2.widget-title") else manga_slug.replace('-', ' ').title()
        print(f"Manga: {manga_title}")
        
        # Obtener página del capítulo
        soup, response = get_page_content(session, url)
        if not soup:
            print(f"No se pudo acceder al capítulo: {url}")
            return None
            
        chapter_title = f"Capítulo {chapter_number}"
        title_tag = soup.select_one("h1 b")
        if title_tag:
            chapter_title = title_tag.text.strip()
        print(f"Título del capítulo: {chapter_title}")
        
        # Extraer imágenes
        images = []
        image_tags = soup.select("div#all img")
        
        if not image_tags:
            print("No se encontraron imágenes directamente. Buscando en scripts...")
            script_tags = soup.find_all("script")
            for script in script_tags:
                if script.string and "pages = [" in script.string:
                    match = re.search(r'var pages = (\[.*?\]);', script.string, re.DOTALL)
                    if match:
                        pages_json = match.group(1)
                        pages_data = json.loads(pages_json)
                        for page in pages_data:
                            img_url = page.get('page_image')
                            if img_url:
                                full_url = urljoin("https://s1.m440.in/uploads/manga/", f"{manga_slug}/chapters/{chapter_match.group(0)[1:]}/{img_url}")
                                images.append(full_url)
                        break
        
        if not images and image_tags:
            for img in image_tags:
                src = img.get('data-src') or img.get('src')
                if src and src != "https://m440.in/images/loading.gif":
                    images.append(urljoin(url, src))
        
        if not images:
            print("No se encontraron imágenes en el capítulo.")
            return None
            
        print(f"Se encontraron {len(images)} imágenes.")
        
        # Construir información del capítulo
        chapter_info = {
            'manga_title': manga_title,
            'chapter_number': chapter_number,
            'chapter_title': chapter_title,
            'source_url': url,
            'images': images,
            'downloaded_at': time.strftime("%Y-%m-%d %H:%M:%S"),
            'page_count': len(images)
        }
        
        # Buscar navegación
        next_link = soup.find("a", onclick="return nextChap();")
        prev_link = soup.find("a", onclick="return prevChap();")
        if next_link and next_link.get('href'):
            chapter_info['next_chapter_url'] = urljoin(url, next_link['href'])
        if prev_link and prev_link.get('href'):
            chapter_info['prev_chapter_url'] = urljoin(url, prev_link['href'])
        
        # Descargar imágenes
        if download_images:
            print("Descargando imágenes...")
            chapter_dir = create_chapter_directory(manga_title, chapter_number, chapter_title)
            save_metadata(chapter_dir, chapter_info)
            
            for i, img_url in enumerate(images, 1):
                img_filename = f"{i:03d}.jpg"
                img_path = f"{chapter_dir}/{img_filename}"
                print(f"Descargando imagen {i}/{len(images)}: {img_url}")
                success = download_image(session, img_url, img_path)
                if not success:
                    print(f"Error al descargar la imagen {i}")
                time.sleep(0.5)
                
            print(f"Capítulo descargado en: {chapter_dir}")
        
        return chapter_info
        
    except Exception as e:
        print(f"Error al descargar el capítulo: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

# Ejemplo de uso
if __name__ == "__main__":
    manga_url = "https://m440.in/manga/the-return-of-the-disasterclass-hero"
    chapters = get_m440_chapters(manga_url)
    
    if chapters:
        print("\nCapítulos encontrados:")
        for chapter in chapters[:5]:  # Mostrar los primeros 5 como ejemplo
            print(f"- {chapter['title']}: {chapter['url']}")
        if len(chapters) > 5:
            print(f"...y {len(chapters) - 5} capítulos más.")
        
        # Descargar el primer capítulo como ejemplo
        first_chapter = chapters[0]
        print(f"\nDescargando {first_chapter['title']}...")
        chapter_info = scrape_m440(first_chapter['url'], download_images=True)