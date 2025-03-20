import os
from typing import Dict, List, Optional, Union, Any
from dotenv import load_dotenv
import aiohttp
import asyncio
import re
from .upload import ImageUploader

# Load environment variables
load_dotenv('.env.local')

# Get Strapi configuration from environment variables
STRAPI_URL = os.getenv('STRAPI_URL')
STRAPI_TOKEN = os.getenv('STRAPI_TOKEN')

if not STRAPI_URL or not STRAPI_TOKEN:
    raise ValueError("STRAPI_URL and STRAPI_TOKEN must be set in .env.local")

class ComicManager:
    def __init__(self):
        self.headers = {
            'Authorization': f'Bearer {STRAPI_TOKEN}',
            'Content-Type': 'application/json',
        }
        
    async def find_similar_comics(self, title: str) -> List[Dict]:
        """Find comics with similar titles"""
        async with aiohttp.ClientSession() as session:
            try:
                # Get all comics
                async with session.get(
                    f"{STRAPI_URL}/api/comics?populate[episodesAll][fields][0]=id&populate[episodesAll][fields][1]=episode&popula&fields[1]=title",
                    headers=self.headers,
                    
                ) as response:
                    if response.status != 200:
                        print(f"Error getting comics: {response.status}")
                        return []
                    
                    data = await response.json()
                    if not data.get('data'):
                        return []
                    
                    # Process each comic and calculate similarity
                    similar_comics = []
                    title_lower = title.lower()
                    
                    for comic in data['data']:
                        comic_title = comic['title']
                        
                        if not comic_title:
                            continue
                            
                        # Calculate similarity (basic contains check for now)
                        comic_title_lower = comic_title.lower()
                        if (title_lower in comic_title_lower or 
                            comic_title_lower in title_lower or
                            len(set(title_lower.split()) & set(comic_title_lower.split())) > 0):
                            similar_comics.append({
                                'id': comic['id'],
                                'title': comic_title,
                                'documentId': comic['documentId'],
                                'similarity': 'Potential match'
                            })
                    
                    return similar_comics
            except Exception as e:
                print(f"Error finding similar comics: {str(e)}")
                return []
                
    async def get_all_comics(self) -> List[Dict]:
        """Get all comics from Strapi"""
        async with aiohttp.ClientSession() as session:
            try:
                # Get all comics
                async with session.get(
                    f"{STRAPI_URL}/api/comics?populate[episodesAll][fields][0]=id&populate[episodesAll][fields][1]=episode&fields[0]=id&fields[1]=title&fields[2]=documentId&sort=title:asc",
                    headers=self.headers,
                    
                ) as response:
                    if response.status != 200:
                        print(f"Error getting all comics: {response.status}")
                        return []
                    
                    data = await response.json()
                    if not data.get('data'):
                        return []
                    
                    # Format comics list
                    all_comics = []
                    for comic in data['data']:
                        if not comic.get('title'):
                            continue
                            
                        all_comics.append({
                            'id': comic['id'],
                            'title': comic['title'],
                            'documentId': comic.get('documentId', str(comic['id']))
                        })
                    
                    return all_comics
            except Exception as e:
                print(f"Error getting all comics: {str(e)}")
                return []

    async def get_comic_by_document_id(self, document_id: str) -> Optional[Dict]:
        """Get a comic by its document_id or find similar comics if not found"""
        async with aiohttp.ClientSession() as session:
            try:
                # First try exact document_id match
                async with session.get(
                    f"{STRAPI_URL}/api/comics?filters[documentId][$eq]={document_id}",
                    headers=self.headers,
                    
                ) as response:
                    if response.status != 200:
                        print(f"Error getting comic: {response.status}")
                        return None
                    
                    data = await response.json()
                    if data.get('data'):
                        return data['data'][0]
                    
                    # If not found, try snake case as fallback
                    async with session.get(
                        f"{STRAPI_URL}/api/comics?filters[document_id][$eq]={document_id}",
                        headers=self.headers,
                        
                    ) as fallback_response:
                        fallback_data = await fallback_response.json()
                        if fallback_data.get('data'):
                            return fallback_data['data'][0]
                        
                    # If still not found, return None to trigger similar comics search
                    return None
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                print(f"Network error when getting comic: {str(e)}")
                return None
            except Exception as e:
                print(f"Unexpected error when getting comic: {str(e)}")
                return None

    
    async def update_comic(self, comic_id: str, comic_data: Dict) -> Dict:
        """Update an existing comic with normalized data"""
        normalized_data = await self._normalize_comic_data(comic_data, comic_data.get('documentId', ''))
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.put(
                    f"{STRAPI_URL}/api/comics/{comic_id}",
                    json={"data": normalized_data},  # Wrap in data field
                    headers=self.headers,
                    
                ) as response:
                    response_data = await response.json()
                    if response.status not in (200, 201):
                        print(f"Error updating comic: {response.status}")
                        print(f"Response: {response_data}")
                    return response_data
            except Exception as e:
                print(f"Error updating comic: {str(e)}")
                return {"error": str(e)}

    async def _normalize_comic_data(self, comic_data: Dict, documentId: str) -> Dict:
        # Normalize comic data to match Strapi expectations
        # subir imagenes;
        uploadImage = ImageUploader()
        # print(f"Subiendo {comic_data['image_count']} imagenes")
        imagen = await uploadImage.upload_images(comic_data['images'], comic_data['episode'])
        
        # Process the image response to ensure it's in the correct format
        processed_images = []
        for img in imagen:
            if isinstance(img, dict) and 'id' in img:
                processed_images.append(img)
            elif isinstance(img, list) and len(img) > 0:
                for item in img:
                    if isinstance(item, dict) and 'id' in item:
                        processed_images.append(item)
        
        normalized = {
            'episode': comic_data['episode'],
            'images': {
                'data': processed_images
            },
            'isImageInURL': False,
            'views': 0,
            'connect': [
                {
                    '__component': 'comic.comic',
                    'documentId': documentId
                }
            ]
        }        
        return normalized
        """Generate a safe document ID from title"""
        # Remove special chars, convert spaces to underscores, make lowercase
        doc_id = re.sub(r'[^\w\s]', '', title)
        doc_id = re.sub(r'\s+', '_', doc_id)
        return doc_id.lower()

    async def extract_comic_id(self, response: Dict) -> Optional[int]:
        """Extract comic ID from various response formats"""
        if not response:
            return None
            
        # Check for error
        if 'error' in response:
            print(f"Error in response: {response['error']}")
            return None
            
        # Different possible structures based on Strapi response format
        try:
            # Direct ID
            if 'id' in response:
                return response['id']
                
            # Nested in data object
            if 'data' in response:
                data = response['data']
                
                # Single object
                if isinstance(data, dict) and 'id' in data:
                    return data['id']
                    
                # Array with first element
                if isinstance(data, list) and len(data) > 0 and 'id' in data[0]:
                    return data[0]['id']
                    
                # Nested attributes
                if isinstance(data, dict) and 'attributes' in data:
                    if 'id' in data:
                        return data['id']
            
            print(f"Could not extract comic ID from response structure: {response}")
            return None
        except Exception as e:
            print(f"Error extracting comic ID: {str(e)}")
            return None
    
    async def get_comic_by_id(self, comic_id: int) -> Optional[Dict]:
        """Get a comic directly by its numeric ID"""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    f"{STRAPI_URL}/api/comics?filters[id][$eq]={comic_id}",
                    headers=self.headers,
                ) as response:
                    if response.status != 200:
                        print(f"Error getting comic by ID: {response.status}")
                        return None
                    
                    data = await response.json()
                    if not data.get('data'):
                        return None
                    
                    return data['data']
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                print(f"Network error when getting comic by ID: {str(e)}")
                return None
            except Exception as e:
                print(f"Unexpected error when getting comic by ID: {str(e)}")
                return None
    



class EpisodeManager:
    def __init__(self):
        self.headers = {
            'Authorization': f'Bearer {STRAPI_TOKEN}',
            'Content-Type': 'application/json',
        }

    async def get_comic_episodes(self, comic_id: str) -> List[int]:
        """Get all episode numbers for a comic"""
        print(f"Getting episodes for comic ID: {comic_id}")
        
        async with aiohttp.ClientSession() as session:
            try:
                # First try the camelCase field name
                url = f"{STRAPI_URL}/api/episodes?filters[comic][id][$eq]={comic_id}&fields[0]=episode"
                async with session.get(url, headers=self.headers, ) as response:
                    if response.status != 200:
                        print(f"Error getting episodes: {response.status}")
                        return []
                        
                    data = await response.json()
                    episodes = []
                    
                    if not data.get('data'):
                        print("No episode data found")
                        return []
                    
                    # Handle different response structures
                    for item in data['data']:
                        # Structure 1: {id, attributes: {episode: number}}
                        if 'attributes' in item and 'episode' in item['attributes']:
                            episode_num = item['attributes']['episode']
                            if episode_num is not None:
                                episodes.append(episode_num)
                        # Structure 2: {episode: number}
                        elif 'episode' in item:
                            episode_num = item['episode']
                            if episode_num is not None:
                                episodes.append(episode_num)
                    
                    print(f"Found episodes: {episodes}")
                    return episodes
            except Exception as e:
                print(f"Error retrieving episodes: {str(e)}")
                return []

    async def get_episode_by_number(self, comic_id: str, episode_number: int) -> Optional[Dict]:
        """Get an episode by its number with error handling"""
        print(f"Looking for episode {episode_number} for comic ID: {comic_id}")
        
        async with aiohttp.ClientSession() as session:
            try:
                url = f"{STRAPI_URL}/api/comics?filters[documentId][$eq]={comic_id}&filters[episodesAll][episode][$eq]={episode_number}&fields[0]=title&populate[episodesAll][fields][0]=id&populate[episodesAll][fields][1]=episode"
                #/api/comics?filters[documentId][$eq]={comic_id}&filters[episodeAll][episode][$eq]={episode_number}"
                async with session.get(url, headers=self.headers, ) as response:
                    if response.status != 200:
                        print(f"Error retrieving episode: {response.status}")
                        return None
                        
                    data = await response.json()
                    if not data.get('data') or not data['data']:
                        print(f"Episode {episode_number} not found")
                        return None
                    
                    episode = data['data'][0]['episodesAll'][0]
                    episode_id = self._extract_episode_id(episode)
                    if episode_id:
                        print(f"Found episode with ID: {episode_id}")
                        # Add the ID to a predictable location
                        if 'id' not in episode:
                            episode['id'] = episode_id
                        return episode
                    
                    print(f"Could not extract episode ID")
                    return None
            except Exception as e:
                print(f"Error retrieving episode: {str(e)}")
                return None

    def _extract_episode_id(self, episode: Dict) -> Optional[int]:
        """Extract episode ID from various possible structures"""
        if not episode:
            return None
            
        # Direct ID
        if 'id' in episode:
            return episode['id']
            
        # Nested ID
        if 'attributes' in episode and 'id' in episode['attributes']:
            return episode['attributes']['id']
            
        return None

    async def _prepare_episode_data(self, episode_data: Dict, comic_id: str) -> Dict:
        """Prepare and normalize episode data for creation/update"""
        # Create a copy to avoid modifying the original
        normalized = {
            'images': [],
            'isImageInURL': False,
            'views': 0,
            'reactions': {
                'like': 0,
                'love': 0,
                'angry': 0,
                'sad': 0,
                'funny': 0,
                'surprised': 0,
            },
            'episode': episode_data['episode'],
            'comic': {
                'connect': [comic_id]
            },
            "locale": "es"
        }

        

        # Subir imágenes
        uploadImage = ImageUploader()

        if 'images' in episode_data and isinstance(episode_data['images'], list):
            uploaded_images = await uploadImage.upload_images(episode_data['images'], str(episode_data['episode']), as_media=True, retries=3)
            
            # Verificar si hubo un error crítico durante la subida de imágenes
            if uploaded_images is None:
                print(f"ERROR CRÍTICO: Falló la subida de imágenes para el episodio {episode_data['episode']}")
                print(f"Deteniendo el proceso de subida del episodio.")
                return {"error": "Falló la subida de imágenes para el episodio"}
    
            # Extraer los IDs de las imágenes subidas
            image_ids = []
            for img in uploaded_images:
                # Strapi puede devolver diferentes estructuras de respuesta
                if isinstance(img, list):
                    # Si es una lista, extraer el ID del primer elemento
                    if len(img) > 0 and isinstance(img[0], dict) and 'id' in img[0]:
                        image_ids.append(img[0]['id'])
                elif isinstance(img, dict):
                    # Si es un diccionario, verificar si tiene un ID directamente
                    if 'id' in img:
                        image_ids.append(img['id'])
                    # O si tiene datos anidados
                    elif 'data' in img and isinstance(img['data'], list) and len(img['data']) > 0:
                        for item in img['data']:
                            if isinstance(item, dict) and 'id' in item:
                                image_ids.append(item['id'])
            
            # Verificar si se obtuvieron IDs de imágenes
            if not image_ids:
                print(f"ERROR CRÍTICO: No se obtuvieron IDs de imágenes para el episodio {episode_data['episode']}")
                print(f"Deteniendo el proceso de subida del episodio.")
                return {"error": "No se obtuvieron IDs de imágenes para el episodio"}
            
            print(image_ids)
            # Asociar las imágenes al campo 'images'
            normalized['images'] = image_ids

        return normalized
        
    async def create_or_update_episode(self, document_id: str, episode_data: Dict) -> Dict:
        """Create or update an episode for a comic"""
        # First, prepare the episode data

        # Check if episode already exists
        episode_number = episode_data.get('episode', 0)
        if not episode_number and episode_number != 0:  # Allow episode 0
            print(f"Error: Episode data missing episode number: {normalized_data}")
            return {"error": "Missing episode number"}
        
        
            
        existing_episode = await self.get_episode_by_number(document_id, episode_number)

        if existing_episode:
            return print(f"Capitulo ya existente")

        normalized_data = await self._prepare_episode_data(episode_data, document_id)
        # Ensure episode number is set in normalized data
        normalized_data['episode'] = episode_number
        
        # Flatten the images data if it's a nested array
        if 'images' in normalized_data and 'data' in normalized_data['images']:
            images_data = normalized_data['images']['data']
            if isinstance(images_data, list) and len(images_data) > 0 and isinstance(images_data[0], list):
                # It's a nested array, flatten it
                flattened_images = [img for sublist in images_data for img in sublist]
                normalized_data['images']['data'] = flattened_images
        
        async with aiohttp.ClientSession() as session:
            try:
                if existing_episode:
                    # Update existing episode
                    episode_id = self._extract_episode_id(existing_episode)
                    if not episode_id:
                        print(f"Error: Could not extract episode ID from {existing_episode}")
                        return {"error": "Could not extract episode ID"}
                        
                    print(f"Updating episode {episode_number} with ID {episode_id}")
                    async with session.put(
                        f"{STRAPI_URL}/api/episodes/{episode_id}",
                        json={"data": normalized_data},
                        headers=self.headers,
                        
                    ) as response:
                        response_data = await response.json()
                        if response.status not in (200, 201):
                            print(f"Error updating episode: {response.status}")
                            print(f"Response: {response_data}")
                        return response_data
                else:
                    # Create new episode
                    print(f"Creating new episode {episode_number} for comic {document_id}")
                    async with session.post(
                        f"{STRAPI_URL}/api/episodes",
                        json={"data": normalized_data},
                        headers=self.headers,
                        
                    ) as response:
                        response_data = await response.json()
                        if response.status not in (200, 201):
                            print(f"Error creating episode: {response.status}")
                            print(f"Response: {response_data}")
                        return response_data
            except Exception as e:
                print(f"Error creating/updating episode: {str(e)}")
                return {"error": str(e)}

async def save_comic_and_episodes(comic_data: Dict, episodes: List[Dict]) -> Dict:
    """Save a comic and its episodes to Strapi"""
    # Initialize managers
    comic_manager = ComicManager()
    episode_manager = EpisodeManager()
    
    comic_id = None
    choice_idx = None
    if not comic_id:
        print(f"'{comic_data['title']}'. Buscando cómics similares...")
        # Try to find similar comics
        similar_comics = await comic_manager.find_similar_comics(comic_data['title'])
        
        if similar_comics:
            print("\nCómics similares encontrados:")
            for i, similar in enumerate(similar_comics, 1):
                print(f"{i}. {similar['title']} (ID: {similar['id']})")
            
            while True:
                try:
                    choice = input("\nSeleccione el número del cómic correcto (0 para cancelar, -1 para ver todos los cómics): ")
                    if choice == '0':
                        return {"error": "Selección cancelada por el usuario"}
                    if choice == '-1':
                        # Opción para mostrar todos los cómics disponibles
                        print("\nObteniendo lista completa de cómics...")
                        all_comics = await comic_manager.get_all_comics()
                        
                        if not all_comics:
                            print("No se encontraron cómics en la base de datos.")
                            return {"error": "No se encontraron cómics en la base de datos"}
                        
                        print("\nLista completa de cómics disponibles:")
                        # Mostrar todos los cómics en formato paginado
                        page_size = 20
                        total_comics = len(all_comics)
                        total_pages = (total_comics + page_size - 1) // page_size
                        current_page = 1
                        
                        while True:
                            start_idx = (current_page - 1) * page_size
                            end_idx = min(start_idx + page_size, total_comics)
                            
                            print(f"\nPágina {current_page}/{total_pages} - Mostrando cómics {start_idx+1}-{end_idx} de {total_comics}\n")
                            
                            for i, comic in enumerate(all_comics[start_idx:end_idx], start_idx + 1):
                                print(f"{i}. {comic['title']} (ID: {comic['id']})")
                            
                            nav = input("\nSeleccione un número de cómic, 'n' para siguiente página, 'p' para página anterior, 'q' para cancelar: ")
                            
                            if nav.lower() == 'q':
                                return {"error": "Selección cancelada por el usuario"}
                            elif nav.lower() == 'n' and current_page < total_pages:
                                current_page += 1
                            elif nav.lower() == 'p' and current_page > 1:
                                current_page -= 1
                            else:
                                try:
                                    selection = int(nav)
                                    if 1 <= selection <= total_comics:
                                        comic_id = all_comics[selection-1]['id']
                                        print(f"Seleccionado cómic con ID: {comic_id}")
                                        # Actualizar similar_comics para mantener consistencia
                                        similar_comics = [all_comics[selection-1]]
                                        choice_idx = 0  # Solo hay un elemento
                                        break
                                    else:
                                        print("Selección inválida. Intente de nuevo.")
                                except ValueError:
                                    if nav.lower() not in ['n', 'p', 'q']:
                                        print("Por favor, ingrese un número válido o una opción de navegación.")
                        break
                    
                    choice_idx = int(choice) - 1
                    if 0 <= choice_idx < len(similar_comics):
                        comic_id = similar_comics[choice_idx]['id']
                        print(f"Seleccionado cómic con ID: {comic_id}")
                        break
                    print("Selección inválida. Intente de nuevo.")
                except ValueError:
                    print("Por favor, ingrese un número válido.")
        
        if not comic_id:
            print("No se encontraron cómics similares o se canceló la selección.")
            return {"error": "No se encontraron cómics similares o se canceló la selección."}

    # Create or update episodes
    print(f"Procesando {len(episodes)} episodios para el cómic ID: {comic_id}")
    
    # Get the document ID from similar_comics if available, otherwise use the comic_id
    document_id = similar_comics[choice_idx]['documentId'] if similar_comics else str(comic_id)
    
    for episode in episodes:
        # Ensure episode has an episode number
        if 'episode' not in episode:
            # If episode number is missing, set it to 0 (which is valid)
            episode['episode'] = 0
            
        print(f"Procesando episodio {episode.get('episode', 'desconocido')}")
        result = await episode_manager.create_or_update_episode(document_id, episode)
        
        # Verificar si hubo un error en la creación/actualización del episodio
        if isinstance(result, dict) and 'error' in result:
            print(f"\nERROR CRÍTICO: Falló la subida del episodio {episode.get('episode', 'desconocido')}: {result['error']}")
            print(f"Deteniendo el proceso de subida de episodios.\n")
            return {"error": f"Falló la subida del episodio {episode.get('episode', 'desconocido')}"}

    # Return a success response with the comic ID
    return {"id": comic_id, "documentId": document_id, "status": "success"}

# Example usage
async def main():

    return "hola";

if __name__ == "__main__":
    asyncio.run(main())