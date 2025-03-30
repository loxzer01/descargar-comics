import os
import re
import aiohttp
import asyncio
import json
from typing import List, Dict
from dotenv import load_dotenv
# Comentado temporalmente para deshabilitar el optimizador
# from .uploadOptimized import upload_and_get_optimized_url
# Cargar variables de entorno
load_dotenv('.env.local')

# Configuración de Strapi desde variables de entorno
STRAPI_URL = os.getenv('STRAPI_URL')
STRAPI_TOKEN = os.getenv('STRAPI_TOKEN')
STRAPI_URL_API = os.getenv('STRAPI_URL_API')
STRAPI_TOKEN_API = os.getenv('STRAPI_TOKEN_API')

if not STRAPI_URL or not STRAPI_TOKEN:
    raise ValueError("Las variables STRAPI_URL y STRAPI_TOKEN deben estar configuradas en .env.local")
    
if not STRAPI_URL_API or not STRAPI_TOKEN_API:
    raise ValueError("Las variables STRAPI_URL_API y STRAPI_TOKEN_API deben estar configuradas en .env.local")
class ImageUploader:
    def __init__(self):
        # Configurar headers para ambos servidores
        self.headers_local = {
            'Authorization': f'Bearer {STRAPI_TOKEN}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        self.headers_api = {
            'Authorization': f'Bearer {STRAPI_TOKEN_API}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        self.base_path = 'comic'
        # Priorizar el servidor local (0) sobre el API (1)
        self.server_index = 0
        # Contador de fallos consecutivos del servidor local
        self.local_failures = 0
        # Máximo de fallos consecutivos antes de intentar con el API
        self.max_local_failures = 3

    async def upload_image(self, url: str, path: str = "comic", as_media: bool = False, filename: str = None, retries: int = 3, recursion_level: int = 0) -> Dict:
        # Limitar la recursión para evitar el error de profundidad máxima
        if recursion_level >= 3:
            print(f"ADVERTENCIA: Se alcanzó el límite de recursión para {url}. Devolviendo error.")
            return {'url': url, 'error': 'Límite de recursión alcanzado'}
            
        # Seleccionar servidor basado en el índice actual
        # Priorizar el servidor local (0) y solo usar API (1) como respaldo
        if self.server_index == 0:
            strapi_url = STRAPI_URL
            auth_token = STRAPI_TOKEN
            headers = self.headers_local
            server_name = "local"
        else:
            strapi_url = STRAPI_URL_API
            auth_token = STRAPI_TOKEN_API
            headers = self.headers_api
            server_name = "API"
        
        # Ya no alternamos automáticamente, mantenemos el servidor local como prioridad
        # Solo cambiaremos si hay fallos consecutivos
        
        for attempt in range(retries):
            try:
                async with aiohttp.ClientSession() as session:
                    if as_media:
                        # Descargar la imagen primero
                        print(f"Descargando imagen desde: {url}")
                        async with session.get(url) as response:
                            if response.status != 200:
                                raise ValueError(f"Error al descargar la imagen desde {url} (Estado: {response.status})")
                            
                            content_type = response.headers.get('Content-Type', '')
                            if not content_type.startswith('image/'):
                                raise ValueError(f"La URL {url} no corresponde a una imagen (Content-Type: {content_type})")
                            
                            image_data = await response.read()
                            
                            # Subir la imagen a Strapi
                            form_data = aiohttp.FormData()
                            filename = filename if filename else "image.webp"
                            if not filename.endswith('.webp'):
                                filename = filename.split('.')[0] + '.webp'
                            
                            form_data.add_field('files',
                                              image_data,
                                              filename=filename,
                                              content_type=content_type)
                            
                            print(f"Subiendo imagen a servidor Strapi {server_name}: {filename} en {path}")
                            upload_url = f"{strapi_url}/api/upload"
                            
                            async with session.post(
                                upload_url,
                                data=form_data,
                                headers={'Authorization': f'Bearer {auth_token}'}
                            ) as upload_response:
                                print(f"Estado de la respuesta de subida ({server_name}): {upload_response.status}")
                                if upload_response.status not in (200, 201):
                                    response_text = await upload_response.text()
                                    # Si falla, manejar según el servidor actual
                                    if attempt == retries - 1:
                                        if server_name == "local":
                                            # Si el servidor local falla, incrementar contador de fallos
                                            self.local_failures += 1
                                            print(f"Error al subir a servidor local (fallo {self.local_failures}/{self.max_local_failures}), intentando con el servidor API...")
                                            # Cambiar al servidor API solo si hay suficientes fallos consecutivos
                                            if self.local_failures >= self.max_local_failures:
                                                self.server_index = 1
                                                print(f"Cambiando temporalmente al servidor API después de {self.local_failures} fallos consecutivos del servidor local")
                                            else:
                                                # Mantener el servidor local para la próxima imagen
                                                self.server_index = 0
                                        else:
                                            # Si el API falla, volver a intentar con el servidor local
                                            print(f"Error al subir a servidor API, volviendo al servidor local...")
                                            self.server_index = 0
                                        # Reintentar con el servidor seleccionado, incrementando el nivel de recursión
                                        return await self.upload_image(url, path, as_media, filename, 1, recursion_level + 1)
                                    raise ValueError(f"Error al subir la imagen a Strapi {server_name} (Estado {upload_response.status}): {response_text}")
                                try:
                                    result = await upload_response.json()
                                    print(f"Imagen subida exitosamente al servidor {server_name}")
                                    # Si la subida al servidor local fue exitosa, resetear el contador de fallos
                                    if server_name == "local":
                                        if self.local_failures > 0:
                                            print(f"Reseteando contador de fallos del servidor local después de una subida exitosa")
                                            self.local_failures = 0
                                    # Si estábamos usando el API pero el local ya funciona, volver al local
                                    elif server_name == "API" and self.local_failures >= self.max_local_failures:
                                        print("Intentando volver al servidor local para la próxima imagen...")
                                        self.server_index = 0
                                        self.local_failures = 0
                                    return result
                                except Exception as e:
                                    print(f"Error al parsear la respuesta JSON: {e}")
                                    return {'url': url, 'error': str(e)}
                    else:
                        return {'url': url}
            except Exception as e:
                print(f"Intento {attempt + 1} fallido para {url} en servidor {server_name}: {str(e)}")
                if attempt < retries - 1:
                    print("Reintentando...")
                    await asyncio.sleep(1)
                else:
                    # Si se agotan los intentos con este servidor, intentar con el otro
                    if server_name == "local":
                        # Si el servidor local falla, incrementar contador de fallos
                        self.local_failures += 1
                        print(f"Intentando con el servidor API después de {self.local_failures} fallos del servidor local...")
                        # Cambiar al servidor API solo si hay suficientes fallos consecutivos
                        if self.local_failures >= self.max_local_failures:
                            self.server_index = 1
                            print(f"Cambiando temporalmente al servidor API después de {self.local_failures} fallos consecutivos del servidor local")
                        else:
                            # Mantener el servidor local para la próxima imagen a pesar del fallo actual
                            self.server_index = 0
                        # Reintentar con el servidor seleccionado, incrementando el nivel de recursión
                        return await self.upload_image(url, path, as_media, filename, 1, recursion_level + 1)
                    elif server_name == "API":
                        print("Intentando con el servidor local...")
                        self.server_index = 0
                        # Resetear el contador de fallos al volver al servidor local
                        self.local_failures = 0
                        # Reintentar con el servidor seleccionado, incrementando el nivel de recursión
                        return await self.upload_image(url, path, as_media, filename, 1, recursion_level + 1)
                    else:
                        print("Se agotaron los intentos en ambos servidores.")
                        return {'url': url, 'error': str(e)}

    async def get_image_size(self, url: str) -> int:
        """Obtiene el tamaño de una imagen en bytes desde su URL."""
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    print(f"Error al descargar la imagen para obtener tamaño: {url}")
                    return None
                image_data = await response.read()
                return len(image_data)

    async def upload_images(self, images: List[Dict], path: str = "comic", as_media: bool = False, retries: int = 3) -> List[Dict]:
        """Sube múltiples imágenes a Strapi, sin usar el optimizador.

        Args:
            images: Lista de diccionarios con 'url' y 'filename'.
            path: Ruta en Strapi donde se almacenarán las imágenes.
            as_media: Si True, sube las imágenes como archivos multimedia.
            retries: Número de intentos por imagen.
            
        Returns:
            List[Dict]: Lista de resultados o None si hubo un error crítico que detuvo el proceso.
        """
        # Patrones de URL a ignorar
        skip_patterns = [
            'recluta-Limpiador.webp',
            'donadores-discord-agosto.webp',
            'z_02.webp',
            'z_01.webp',
            'x.webp',
            'z.webp'
        ]
        
        results = []
        # Contador para las imágenes procesadas (para identificar las primeras dos)
        image_count = 0
        # Contador de errores en las primeras dos imágenes
        first_images_errors = 0
        
        for image in images:
            image_count += 1
            print(f"Procesando imagen {image_count}/{len(images)}: {image['filename']}")
            url_to_upload = image['url']
            
            # Verificar si la URL contiene alguno de los patrones a ignorar
            should_skip = False
            for pattern in skip_patterns:
                if pattern in url_to_upload:
                    print(f"Omitiendo imagen con patrón ignorado: {pattern} en {url_to_upload}")
                    should_skip = True
                    break
                    
            if should_skip:
                continue  # Saltar esta imagen y continuar con la siguiente
            
            # Comentado temporalmente para deshabilitar el optimizador
            # optimized_url = upload_and_get_optimized_url(original_url)
            # 
            # if not optimized_url:
            #     print(f"ERROR CRÍTICO: No se pudo optimizar la imagen {original_url}")
            #     print(f"Deteniendo la subida del capítulo debido a un error crítico.")
            #     return None  # Detener todo el proceso si no se puede optimizar
            # 
            # # Obtener el tamaño de la imagen original
            # original_size = await self.get_image_size(original_url)
            # if original_size is None:
            #     print(f"ERROR CRÍTICO: No se pudo obtener el tamaño de la imagen original {original_url}")
            #     print(f"Deteniendo la subida del capítulo debido a un error crítico.")
            #     return None  # Detener todo el proceso si no se puede obtener el tamaño
            # 
            # # Obtener el tamaño de la imagen optimizada
            # optimized_size = await self.get_image_size(optimized_url)
            # if optimized_size is None:
            #     print(f"ERROR CRÍTICO: No se pudo obtener el tamaño de la imagen optimizada {optimized_url}")
            #     print(f"Deteniendo la subida del capítulo debido a un error crítico.")
            #     return None  # Detener todo el proceso si no se puede obtener el tamaño
            # 
            # # Decidir cuál imagen subir
            # if optimized_size < original_size:
            #     url_to_upload = optimized_url
            #     print(f"La imagen optimizada es más ligera: {optimized_size} vs {original_size}")
            # else:
            #     url_to_upload = original_url
            #     print(f"La imagen original es más ligera o igual: {original_size} vs {optimized_size}")
            
            filename = image['filename']
            try:
                result = await self.upload_image(url_to_upload, path, as_media, filename, retries)
                if 'error' in result:
                    # Si es una de las primeras dos imágenes, permitir que falle y continuar
                    if image_count <= 2:
                        first_images_errors += 1
                        print(f"ADVERTENCIA: Falló la subida de la imagen {image_count} (posible anuncio): {filename}")
                        print(f"Omitiendo esta imagen y continuando con las siguientes...")
                        continue
                    else:
                        # Para el resto de imágenes, mantener el comportamiento original
                        print(f"ERROR CRÍTICO: Falló la subida de la imagen {filename}: {result['error']}")
                        # Si ya tenemos suficientes imágenes (más de 2), podemos continuar a pesar del error
                        if len(results) > 2:
                            print(f"Ya se han subido {len(results)} imágenes, continuando a pesar del error...")
                            continue
                        else:
                            print(f"Deteniendo la subida del capítulo debido a un error crítico.")
                            return None  # Detener el proceso solo si no hay suficientes imágenes
                results.append(result)
            except Exception as e:
                # Si es una de las primeras dos imágenes, permitir que falle y continuar
                if image_count <= 2:
                    first_images_errors += 1
                    print(f"ADVERTENCIA: Error al subir la imagen {image_count} (posible anuncio) {url_to_upload}: {str(e)}")
                    print(f"Omitiendo esta imagen y continuando con las siguientes...")
                    continue
                else:
                    # Para el resto de imágenes, ser más estricto pero aún permitir continuar si ya tenemos suficientes
                    print(f"ERROR: Error al subir {url_to_upload}: {str(e)}")
                    # Si ya tenemos suficientes imágenes (más de 2), podemos continuar a pesar del error
                    if len(results) > 2:
                        print(f"Ya se han subido {len(results)} imágenes, continuando a pesar del error...")
                        continue
                    else:
                        print(f"Deteniendo la subida del capítulo debido a un error crítico.")
                        return None  # Detener el proceso solo si no hay suficientes imágenes
        return results
        
# Función principal
async def main():
    # Directorio base de imágenes
    images_dir = os.path.abspath('images')

    if not os.path.exists(images_dir):
        print(f"El directorio {images_dir} no existe")
        return
    
    # Obtener la lista de comics disponibles
    comics = [d for d in os.listdir(images_dir) if os.path.isdir(os.path.join(images_dir, d))]
    if not comics:
        print("No se encontraron comics en el directorio 'images'")
        return
    
    # Mostrar los comics disponibles al usuario
    print("Comics disponibles:")
    for i, comic in enumerate(comics, 1):
        print(f"{i}. {comic}")
    
    # Pedir al usuario que seleccione un comic por número
    try:
        option = int(input("\nSelecciona el número del comic a subir (0 para cancelar): "))
        
        if option == 0:
            print("Operación cancelada")
            return
        elif 1 <= option <= len(comics):
            comic_choice = comics[option - 1]
            manga_path = os.path.join(images_dir, comic_choice)
            print(f"Has seleccionado: {comic_choice}")
        else:
            print("Opción no válida")
            return
    except ValueError:
        print("Por favor, ingresa un número válido")
        return
    
    # Obtener los capítulos disponibles para el comic seleccionado
    chapter_dirs = [d for d in os.listdir(manga_path) if os.path.isdir(os.path.join(manga_path, d)) and re.match(r'capitulo_\d+', d)]
    chapters_available = []
    for d in chapter_dirs:
        match = re.search(r'\d+', d)
        if match:
            chapters_available.append(int(match.group()))
    chapters_available.sort()

    if not chapters_available:
        print(f"No se encontraron capítulos para el comic '{comic_choice}'")
        return
    
    # Mostrar los capítulos disponibles
    print(f"Capítulos disponibles para {comic_choice}: {chapters_available}")
    
    # Pedir al usuario que ingrese el rango de capítulos
    range_input = input("Ingrese el rango de capítulos a subir (ej. 1-5 o 3): ")
    
    # Parsear el input del usuario
    if '-' in range_input:
        try:
            start, end = map(int, range_input.split('-'))
            if start > end:
                print("El inicio del rango debe ser menor o igual que el fin")
                return
            chapters_to_upload = [c for c in chapters_available if start <= c <= end]
        except ValueError:
            print("Rango inválido. Asegúrese de ingresar números enteros separados por '-'")
            return
    else:
        try:
            chapter = int(range_input)
            if chapter in chapters_available:
                chapters_to_upload = [chapter]
            else:
                print(f"El capítulo {chapter} no está disponible para el comic '{comic_choice}'")
                return
        except ValueError:
            print("Input inválido. Debe ingresar un número entero o un rango (ej. 1-5)")
            return
    
    if not chapters_to_upload:
        print("No hay capítulos para subir en el rango especificado")
        return
    
    # Inicializar el uploader
    uploader = ImageUploader()
    
    # Crear las carpetas en Strapi y subir los capítulos
    for chapter_number in chapters_to_upload:
        path = f"{uploader.base_path}/{comic_choice}/{chapter_number}"
        folder = None
        try:
            # folder_response = await uploader.create_folder(path)
            # folder = folder_response['data']['currentFolder']
            print(f"Carpeta {path} creada en Strapi")
        except Exception as e:
            print(f"Error al crear la carpeta {path} en Strapi: {str(e)}")
            continue  # Saltar este capítulo si no se pudo crear la carpeta

        # Solo proceder si la carpeta se creó correctamente
        # if folder is None:
        #     print(f"No se pudo obtener información de la carpeta {path}, omitiendo la subida.")
        #     continue

        chapter_path = os.path.join(manga_path, f"capitulo_{chapter_number}")
        meta_file = os.path.join(chapter_path, 'meta.json')
        if os.path.exists(meta_file):
            with open(meta_file, 'r') as f:
                meta_data = json.load(f)
            
            images = meta_data.get('images', [])
            if not images:
                print(f"No se encontraron imágenes en {meta_file}")
                continue
            
            # Usar la ruta de la carpeta creada
            upload_path = path
            print(f"Subiendo imágenes para {comic_choice} capítulo {chapter_number} a {upload_path}")
            
            # Subir las imágenes con reintentos
            results = await uploader.upload_images(images, upload_path, as_media=True, retries=3)
            if results is None:
                print(f"\nERROR: Se detuvo la subida del capítulo {chapter_number} debido a errores en la subida de imágenes.")
                print(f"Pasando al siguiente capítulo...\n")
                continue  # Saltar al siguiente capítulo
            print(results);
        
if __name__ == "__main__":
    asyncio.run(main())