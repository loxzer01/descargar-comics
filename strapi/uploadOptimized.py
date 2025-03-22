import os
import cloudinary
from cloudinary.uploader import upload
from cloudinary.utils import cloudinary_url
import cloudinary.utils
from dotenv import load_dotenv
# Configurar Cloudinary con tus credenciales
load_dotenv('.env.local')

# Reemplaza con tus valores reales
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_NAME'),
    api_key=os.getenv('CLOUDINARY_KEY'),
    api_secret=os.getenv('CLOUDINARY_SECRET')
)

def get_optimized_url(public_id):
    """
    Genera la URL optimizada para una imagen dada su public ID en Cloudinary.
    
    Transformaciones:
    - Ancho: 800 píxeles, recorte: 'scale'
    - Calidad: 'auto:best'
    - Formato: 'auto'
    """
    transformation = [
        {'quality': 'auto'},
        {'fetch_format': 'webp'},  # Forzar formato WebP
        {'width': 800, 'crop': 'limit'},
    ]
    url, options  = cloudinary_url(public_id, format='webp', transformation=[
        {'quality': 'auto'}
    ])
    return url

def upload_and_get_optimized_url(external_url):
    """
    Sube una imagen desde una URL externa a Cloudinary y devuelve la URL optimizada.
    """
    try:
        # Subir la imagen a Cloudinary
        upload_result = cloudinary.uploader.upload(external_url)
        public_id = upload_result['public_id']
        # Generar y devolver la URL optimizada
        return get_optimized_url(public_id)
    except Exception as e:
        print(f"Error al subir la imagen: {e}")
        return None

def main():
    """
    Función principal que permite al usuario ingresar una URL de imagen para optimizarla.
    """
    print("Ingrese la URL de la imagen que desea optimizar:")
    external_url = input().strip()
    
    # Subir y optimizar la imagen
    optimized_url = upload_and_get_optimized_url(external_url)
    
    if optimized_url:
        print(f"URL optimizada: {optimized_url}")
    else:
        print("No se pudo optimizar la imagen.")

if __name__ == "__main__":
    main()