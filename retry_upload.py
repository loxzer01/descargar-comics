#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script para reintentar la subida de mangas que fallaron durante el proceso inicial.

Este script verifica las imágenes ya subidas en Strapi y reintenta crear
episodios utilizando las referencias de imágenes existentes en lugar de volver a subirlas.
"""

import os
import json
import asyncio
import aiohttp
from typing import List, Dict, Optional, Any
from dotenv import load_dotenv
import sys
from pathlib import Path

# Importar módulos de Strapi
from strapi.save import ComicManager, EpisodeManager
from strapi.upload import ImageUploader

# Cargar variables de entorno
load_dotenv('.env.local')

# Obtener configuración de Strapi desde variables de entorno
STRAPI_URL = os.getenv('STRAPI_URL')
STRAPI_TOKEN = os.getenv('STRAPI_TOKEN')

if not STRAPI_URL or not STRAPI_TOKEN:
    raise ValueError("STRAPI_URL y STRAPI_TOKEN deben estar configurados en .env.local")


class RetryUploader:
    def __init__(self):
        self.headers = {
            'Authorization': f'Bearer {STRAPI_TOKEN}',
            'Content-Type': 'application/json',
        }
        self.comic_manager = ComicManager()
        self.episode_manager = EpisodeManager()
        self.image_uploader = ImageUploader()
    
    async def find_uploaded_images(self, image_urls: List[str]) -> Dict[str, int]:
        """
        Busca imágenes ya subidas en Strapi por URL para evitar volver a subirlas.
        
        Args:
            image_urls: Lista de URLs de imágenes a buscar
            
        Returns:
            Diccionario que mapea URLs de imágenes a IDs de Strapi
        """
        print(f"Buscando {len(image_urls)} imágenes ya subidas en Strapi...")
        url_to_id_map = {}
        
        async with aiohttp.ClientSession() as session:
            for url in image_urls:
                # Extraer nombre de archivo de la URL para buscar coincidencias
                filename = os.path.basename(url)
                search_query = f"{STRAPI_URL}/api/upload/files?filters[name][$contains]={filename}"
                
                try:
                    async with session.get(search_query, headers=self.headers) as response:
                        if response.status != 200:
                            print(f"Error al buscar imagen {filename}: {response.status}")
                            continue
                        
                        data = await response.json()
                        if not data or len(data) == 0:
                            continue
                        
                        # Buscar coincidencia exacta o similar
                        for file_data in data:
                            if 'url' in file_data and (file_data['url'] == url or filename in file_data['url']):
                                url_to_id_map[url] = file_data['id']
                                print(f"Imagen encontrada: {filename} -> ID: {file_data['id']}")
                                break
                except Exception as e:
                    print(f"Error al buscar imagen {filename}: {str(e)}")
        
        print(f"Se encontraron {len(url_to_id_map)} imágenes ya subidas")
        return url_to_id_map
    
    async def prepare_episode_with_existing_images(self, episode_data: Dict, comic_id: str) -> Dict:
        """
        Prepara los datos del episodio utilizando imágenes existentes cuando sea posible.
        
        Args:
            episode_data: Datos del episodio a preparar
            comic_id: ID del cómic al que pertenece el episodio
            
        Returns:
            Datos normalizados del episodio
        """
        # Crear una copia para evitar modificar el original
        normalized = {
            'images': [],
            'isImageInURL': False,
            'views': 0,
            'episode': episode_data['episode'],
            'comic': {
                'connect': [comic_id]
            },
            "locale": "es"
        }
        
        if 'images' in episode_data and isinstance(episode_data['images'], list):
            # Buscar imágenes ya subidas
            image_urls = [img['url'] if isinstance(img, dict) else img for img in episode_data['images']]
            existing_images = await self.find_uploaded_images(image_urls)
            
            # Preparar lista de imágenes para subir (las que no existen)
            images_to_upload = []
            for img in episode_data['images']:
                url = img['url'] if isinstance(img, dict) else img
                if url not in existing_images:
                    images_to_upload.append(img)
            
            # Obtener IDs de imágenes existentes
            image_ids = list(existing_images.values())
            
            # Subir imágenes faltantes si es necesario
            if images_to_upload:
                print(f"Subiendo {len(images_to_upload)} imágenes faltantes...")
                uploaded_images = await self.image_uploader.upload_images(
                    images_to_upload, 
                    str(episode_data['episode']), 
                    as_media=True, 
                    retries=3
                )
                
                # Verificar si hubo un error crítico durante la subida
                if uploaded_images is None:
                    print(f"ERROR CRÍTICO: Falló la subida de imágenes para el episodio {episode_data['episode']}")
                    return {"error": "Falló la subida de imágenes para el episodio"}
                
                # Extraer IDs de las imágenes recién subidas
                for img in uploaded_images:
                    if isinstance(img, list) and len(img) > 0 and isinstance(img[0], dict) and 'id' in img[0]:
                        image_ids.append(img[0]['id'])
                    elif isinstance(img, dict):
                        if 'id' in img:
                            image_ids.append(img['id'])
                        elif 'data' in img and isinstance(img['data'], list) and len(img['data']) > 0:
                            for item in img['data']:
                                if isinstance(item, dict) and 'id' in item:
                                    image_ids.append(item['id'])
            
            # Verificar si se obtuvieron IDs de imágenes
            if not image_ids:
                print(f"ERROR: No se obtuvieron IDs de imágenes para el episodio {episode_data['episode']}")
                return {"error": "No se obtuvieron IDs de imágenes para el episodio"}
            
            print(f"Total de IDs de imágenes obtenidos: {len(image_ids)}")
            normalized['images'] = image_ids
        
        return normalized
    
    async def retry_create_episode(self, document_id: str, episode_data: Dict) -> Dict:
        """
        Reintenta crear un episodio utilizando imágenes existentes cuando sea posible.
        
        Args:
            document_id: ID del documento del cómic
            episode_data: Datos del episodio a crear
            
        Returns:
            Resultado de la creación del episodio
        """
        episode_number = episode_data.get('episode', 0)
        if not episode_number and episode_number != 0:  # Permitir episodio 0
            print(f"Error: Datos del episodio sin número de episodio")
            return {"error": "Falta el número de episodio"}
        
        # Verificar si el episodio ya existe
        existing_episode = await self.episode_manager.get_episode_by_number(document_id, episode_number)
        if existing_episode:
            print(f"El episodio {episode_number} ya existe, omitiendo...")
            return {"status": "existing", "message": f"El episodio {episode_number} ya existe"}
        
        # Preparar datos del episodio con imágenes existentes
        normalized_data = await self.prepare_episode_with_existing_images(episode_data, document_id)
        if "error" in normalized_data:
            return normalized_data
        
        # Asegurar que el número de episodio esté establecido
        normalized_data['episode'] = episode_number
        
        # Crear el episodio
        async with aiohttp.ClientSession() as session:
            try:
                print(f"Creando episodio {episode_number}...")
                async with session.post(
                    f"{STRAPI_URL}/api/episodes",
                    json={"data": normalized_data},
                    headers=self.headers
                ) as response:
                    if response.status not in (200, 201):
                        error_text = await response.text()
                        print(f"Error al crear episodio {episode_number}: {response.status}\n{error_text}")
                        return {"error": f"Error al crear episodio: {response.status}"}
                    
                    result = await response.json()
                    print(f"Episodio {episode_number} creado exitosamente")
                    return result
            except Exception as e:
                print(f"Error al crear episodio {episode_number}: {str(e)}")
                return {"error": f"Error al crear episodio: {str(e)}"}


async def retry_upload_manga(manga_dir: str, failed_episodes: List[int] = None):
    """
    Reintenta subir un manga y sus capítulos fallidos desde un directorio existente.
    
    Args:
        manga_dir: Ruta al directorio del manga
        failed_episodes: Lista opcional de números de episodios que fallaron
    """
    manga_name = os.path.basename(manga_dir)
    print(f"\nReintentando subida del manga: {manga_name}")
    
    # Buscar todos los directorios de capítulos
    chapter_dirs = [d for d in os.listdir(manga_dir) 
                   if os.path.isdir(os.path.join(manga_dir, d)) and d.startswith("capitulo_")]
    
    if not chapter_dirs:
        print(f"No se encontraron capítulos para {manga_name}")
        return
    
    # Ordenar capítulos por número
    chapter_dirs.sort(key=lambda x: float(x.split('_')[1]) if x.split('_')[1].replace('.', '', 1).isdigit() else 0)
    
    print(f"Se encontraron {len(chapter_dirs)} capítulos")
    
    # Datos del cómic para Strapi
    comic_data = {
        'title': manga_name.replace('_', ' '),
        'document_id': manga_name.lower(),  # Usar el nombre del directorio como document_id
        'author': 'Desconocido',
        'genres': 'Manga',
        'isCompleted': False,
        'likes': 0,
        'favorite': 0,
        'description': manga_name.replace('_', ' ')
    }
    
    # Verificar si el cómic ya existe
    comic_manager = ComicManager()
    existing_comic = await comic_manager.get_comic_by_document_id(comic_data['document_id'])
    
    if not existing_comic:
        print(f"El cómic {manga_name} no existe en Strapi. Creándolo primero...")
        try:
            result = await comic_manager.create_or_update_comic(comic_data)
            if isinstance(result, dict) and 'error' in result:
                print(f"Error al crear el cómic: {result['error']}")
                return
            existing_comic = result
            print(f"Cómic {manga_name} creado exitosamente")
        except Exception as e:
            print(f"Error al crear el cómic: {str(e)}")
            return
    
    comic_id = existing_comic['id']
    print(f"Usando cómic existente con ID: {comic_id}")
    
    # Lista para almacenar datos de episodios
    episodes = []
    
    # Procesar cada capítulo
    for chapter_dir_name in chapter_dirs:
        chapter_dir = os.path.join(manga_dir, chapter_dir_name)
        meta_file = os.path.join(chapter_dir, 'meta.json')
        
        if not os.path.exists(meta_file):
            print(f"No se encontró meta.json en {chapter_dir}")
            continue
        
        # Cargar metadatos del capítulo
        try:
            with open(meta_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            # Extraer información del capítulo
            chapter_number = metadata.get('chapter_number')
            if chapter_number is None:
                # Intentar extraer del nombre del directorio
                try:
                    chapter_number = float(chapter_dir_name.split('_')[1])
                    if chapter_number.is_integer():
                        chapter_number = int(chapter_number)
                except:
                    print(f"No se pudo determinar el número de capítulo para {chapter_dir}")
                    continue
            
            # Crear datos del episodio
            episode_data = {
                'episode': chapter_number,
                'images': metadata.get('images', []),
            }
            episodes.append(episode_data)
            print(f"  - Capítulo {chapter_number} procesado")
            
        except Exception as e:
            print(f"Error al procesar {meta_file}: {str(e)}")
    
    if not episodes:
        print(f"No se pudieron procesar capítulos para {manga_name}")
        return
    
    # Ordenar episodios por número
    episodes.sort(key=lambda x: x['episode'])
    
    # Verificar episodios existentes en Strapi y filtrar solo los que necesitan reintento
    retry_uploader = RetryUploader()
    
    # Si se especificaron episodios fallidos, filtrar solo esos
    if failed_episodes:
        print(f"Filtrando solo los episodios fallidos: {failed_episodes}")
        episodes = [ep for ep in episodes if ep['episode'] in failed_episodes]
    
    if not episodes:
        print(f"No hay episodios para reintentar en {manga_name}")
        return
    
    # Reintentar crear cada episodio
    results = []
    for episode_data in episodes:
        print(f"\nReintentando subida del episodio {episode_data['episode']}...")
        result = await retry_uploader.retry_create_episode(comic_id, episode_data)
        results.append({
            'episode': episode_data['episode'],
            'result': result
        })
        
        # Pausa breve entre episodios para no sobrecargar la API
        await asyncio.sleep(1)
    
    # Mostrar resumen de resultados
    print(f"\nResumen de resultados para {manga_name}:")
    success_count = 0
    existing_count = 0
    error_count = 0
    
    for result_data in results:
        episode_num = result_data['episode']
        result = result_data['result']
        
        if isinstance(result, dict) and 'error' in result:
            print(f"  - Episodio {episode_num}: ERROR - {result['error']}")
            error_count += 1
        elif isinstance(result, dict) and result.get('status') == 'existing':
            print(f"  - Episodio {episode_num}: Ya existía")
            existing_count += 1
        else:
            print(f"  - Episodio {episode_num}: Subido exitosamente")
            success_count += 1
    
    print(f"\nTotal: {len(results)} episodios procesados")
    print(f"  - {success_count} subidos exitosamente")
    print(f"  - {existing_count} ya existían")
    print(f"  - {error_count} con errores")


async def main():
    """Función principal que maneja los argumentos de línea de comandos."""
    # Verificar argumentos
    if len(sys.argv) < 2:
        print("Uso: python retry_upload.py <directorio_manga> [episodio1,episodio2,...]")
        print("Ejemplo: python retry_upload.py images/Mi_Manga 1,2,5")
        return
    
    # Obtener ruta del manga
    manga_path = sys.argv[1]
    if not os.path.exists(manga_path):
        print(f"Error: El directorio {manga_path} no existe")
        return
    
    # Obtener lista de episodios fallidos (opcional)
    failed_episodes = None
    if len(sys.argv) > 2 and sys.argv[2]:
        try:
            failed_episodes = [int(ep.strip()) for ep in sys.argv[2].split(',')]
            print(f"Reintentando episodios específicos: {failed_episodes}")
        except ValueError:
            print("Error: Los números de episodio deben ser enteros separados por comas")
            return
    
    # Ejecutar el reintento de subida
    await retry_upload_manga(manga_path, failed_episodes)


if __name__ == "__main__":
    asyncio.run(main())