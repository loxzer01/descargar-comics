#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script de prueba para subir mangas existentes a Strapi.

Este script escanea los directorios de imágenes existentes, lee los metadatos
de los archivos meta.json y sube los capítulos de manga a la API de Strapi.
"""

import os
import json
import asyncio
import aiohttp
from dotenv import load_dotenv
import sys
from pathlib import Path

# Importar módulos de Strapi
from strapi.save import ComicManager, EpisodeManager, save_comic_and_episodes

# Cargar variables de entorno
load_dotenv('.env.local')

# Obtener configuración de Strapi desde variables de entorno
STRAPI_URL = os.getenv('STRAPI_URL')
STRAPI_TOKEN = os.getenv('STRAPI_TOKEN')
STRAPI_URL_API = os.getenv('STRAPI_URL_API')
STRAPI_TOKEN_API = os.getenv('STRAPI_TOKEN_API')

if not STRAPI_URL or not STRAPI_TOKEN:
    raise ValueError("STRAPI_URL y STRAPI_TOKEN deben estar configurados en .env.local")
    
if not STRAPI_URL_API or not STRAPI_TOKEN_API:
    raise ValueError("STRAPI_URL_API y STRAPI_TOKEN_API deben estar configurados en .env.local")
    
print(f"\nConfiguración cargada:")
print(f"- Servidor local: {STRAPI_URL}")
print(f"- Servidor API: {STRAPI_URL_API}")
print(f"\nLas imágenes se distribuirán entre ambos servidores para optimizar la velocidad de carga.")
print(f"El sistema alternará automáticamente entre servidores para cada imagen.\n")

async def upload_manga_from_directory(manga_dir):
    """
    Sube un manga y sus capítulos desde un directorio existente.
    
    Args:
        manga_dir: Ruta al directorio del manga
    """
    manga_name = os.path.basename(manga_dir)
    print(f"\nProcesando manga: {manga_name}")
    
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
        'author': 'Desconocido',  # Podría extraerse de meta.json si estuviera disponible
        'genres': 'Manga',        # Podría extraerse de meta.json si estuviera disponible
        'isCompleted': False,
        'likes': 0,
        'favorite': 0,
        'description': manga_name.replace('_', ' ')  # Descripción básica
    }
    
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

    # preguntar a el usuario si quiere subir todos los capitulos o un rango de capitulos 0-33
    print(f"\n¿Qué capítulos deseas subir de {manga_name}?")
    print(f"\nEjemplo: {episodes[0]['episode']}-{episodes[-1]['episode']} para subir los capítulos del {episodes[0]['episode']} al {episodes[-1]['episode']}")
    print("Opciones:")
    print("0. Subir todos los capítulos")
    print(f"1. Subir un rango de capítulos ({episodes[0]['episode']}-{episodes[-1]['episode']})")
    print("2. Subir un capítulo específico")
    print("3. Salir")
    option = input("Opción: ")
    if option == "0":
        # Subir todos los capítulos
        print(f"\nSubiendo todos los capítulos de {manga_name}...")
    elif option == "1":
        # Subir un rango de capítulos
        print(f"\n¿Qué rango de capítulos deseas subir de {manga_name}?")
        print(f"Ejemplo: 0-33 para subir los capítulos del {episodes[0]['episode']} al {episodes[33]['episode'] if len(episodes) > 33 else episodes[-1]['episode']}")
        range_str = input("Rango: ")
        try:
            start, end = map(int, range_str.split('-'))
            if start < 0 or end > len(episodes):
                print("Rango no válido")
                return
            episodes = episodes[start:end]
            print(f"\nSubiendo capítulos del {episodes[0]['episode']} al {episodes[-1]['episode']} de {manga_name}...")
        except:
            print("Rango no válido")
            return
    elif option == "2":
        # Subir un capítulo específico
        print(f"\n¿Qué capítulo deseas subir de {manga_name}?")
        print("Ejemplo: 33 para subir el capítulo 33, o 2.5 para subir el capítulo 2.5")
        chapter_input = input("Capítulo: ")
        try:
            # Convertir a float para manejar números decimales
            chapter_number = float(chapter_input)
            
            # Buscar el episodio con ese número de capítulo
            episode_index = None
            for i, ep in enumerate(episodes):
                if ep['episode'] == chapter_number:
                    episode_index = i
                    break
                    
            if episode_index is None:
                print(f"No se encontró el capítulo {chapter_number}")
                return
                
            episodes = [episodes[episode_index]]
            print(f"\nSubiendo capítulo {chapter_number} de {manga_name}...")
        except:
            print("Capítulo no válido")
            return
    elif option == "3":
        # Salir
        print("Saliendo...")
        return
    else:
        print("Opción no válida")
        return
    
    # Guardar en Strapi
    try:
        print(f"Guardando {manga_name} con {len(episodes)} capítulos en Strapi...")
        result = await save_comic_and_episodes(comic_data, episodes)
        
        # Verificar si hubo un error en el resultado
        if isinstance(result, dict) and 'error' in result:
            print(f"\nERROR: No se pudo completar la subida de {manga_name}: {result['error']}")
            print(f"La subida del manga se ha detenido debido a errores.\n")
            return None
            
        print(f"Manga {manga_name} guardado exitosamente en Strapi")
        return result
    except Exception as e:
        print(f"\nERROR CRÍTICO al guardar en Strapi: {str(e)}")
        print(f"La subida del manga se ha detenido debido a un error crítico.\n")
        return None

async def main():
    """
    Función principal que escanea el directorio de imágenes y sube los mangas a Strapi.
    """
    # Directorio base de imágenes
    images_dir = os.path.abspath('images')
    
    if not os.path.exists(images_dir):
        print(f"El directorio {images_dir} no existe")
        return
    
    # Listar todos los directorios de manga
    manga_dirs = [os.path.join(images_dir, d) for d in os.listdir(images_dir) 
                 if os.path.isdir(os.path.join(images_dir, d))]

    if not manga_dirs:
        print("No se encontraron mangas en el directorio de imágenes")
        return
    
    print(f"Se encontraron {len(manga_dirs)} mangas")
    
    # Preguntar al usuario qué manga subir
    print("\nMangas disponibles:")
    for i, manga_dir in enumerate(manga_dirs):
        print(f"{i+1}. {os.path.basename(manga_dir)}")
    
    print("\nOpciones:")
    print("0. Subir todos los mangas")
    for i, manga_dir in enumerate(manga_dirs):
        print(f"{i+1}. Subir {os.path.basename(manga_dir)}")
    
    try:
        option = int(input("\nSelecciona una opción: "))
        
        if option == 0:
            # Subir todos los mangas
            for manga_dir in manga_dirs:
                await upload_manga_from_directory(manga_dir)
        elif 1 <= option <= len(manga_dirs):
            # Subir un manga específico
            await upload_manga_from_directory(manga_dirs[option-1])
        else:
            print("Opción no válida")
    except ValueError:
        print("Por favor, ingresa un número válido")
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())