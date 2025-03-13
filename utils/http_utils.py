#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Utilidades para operaciones HTTP y manejo de sesiones web.
"""

import requests
from bs4 import BeautifulSoup
import re
import time
import random

def create_session():
    """Crea una sesión HTTP con cabeceras que simulan un navegador moderno."""
    session = requests.Session()
    
    # Establecer cabeceras por defecto para la sesión
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
        'Connection': 'keep-alive',
        'Pragma': 'no-cache',
        'Cache-Control': 'no-cache',
    }
    
    session.headers.update(headers)
    return session

def get_page_content(session, url, timeout=30, retry_count=3):
    """
    Obtiene el contenido de una página web con manejo de errores y reintentos.
    
    Args:
        session: Sesión HTTP a utilizar
        url: URL de la página a obtener
        timeout: Tiempo de espera máximo en segundos
        retry_count: Número de reintentos si ocurre un error
    
    Returns:
        tuple: (soup, response) donde soup es un objeto BeautifulSoup y response es la respuesta HTTP
               o (None, None) si ocurre un error
    """
    current_try = 0
    
    while current_try < retry_count:
        try:
            response = session.get(url, timeout=timeout)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                return soup, response
            else:
                print(f"Error al acceder a {url}: Código {response.status_code}")
                
            # Esperar antes de reintentar
            if current_try < retry_count - 1:
                sleep_time = 2 * (current_try + 1) + random.uniform(0, 1)
                time.sleep(sleep_time)
                
        except requests.exceptions.RequestException as e:
            print(f"Error de conexión al acceder a {url}: {str(e)}")
        
        current_try += 1
    
    return None, None

def extract_urls_from_html(soup, pattern, base_url=None):
    """
    Extrae URLs de un objeto BeautifulSoup que coinciden con un patrón.
    
    Args:
        soup: Objeto BeautifulSoup a analizar
        pattern: Expresión regular o string para filtrar URLs
        base_url: URL base para resolver URLs relativas
    
    Returns:
        list: Lista de URLs encontradas
    """
    urls = []
    
    # Encontrar todos los enlaces
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        
        # Resolver URL relativa si es necesario
        if base_url and not href.startswith(('http://', 'https://')):
            from urllib.parse import urljoin
            href = urljoin(base_url, href)
        
        # Filtrar por patrón
        if isinstance(pattern, str):
            if pattern in href:
                urls.append(href)
        else:  # Asumimos que es un patrón regex
            if pattern.search(href):
                urls.append(href)
    
    return urls

def get_json_api(session, url, api_headers=None):
    """
    Realiza una solicitud a una API JSON.
    
    Args:
        session: Sesión HTTP a utilizar
        url: URL de la API
        api_headers: Cabeceras adicionales específicas para la API
    
    Returns:
        dict: Datos JSON devueltos por la API o None si ocurre un error
    """
    try:
        headers = {}
        if api_headers:
            headers.update(api_headers)
        
        # Añadir cabeceras típicas para solicitudes API
        if 'Accept' not in headers:
            headers['Accept'] = 'application/json'
        if 'X-Requested-With' not in headers:
            headers['X-Requested-With'] = 'XMLHttpRequest'
        
        response = session.get(url, headers=headers)
        
        if response.status_code == 200:
            try:
                return response.json()
            except ValueError:
                print("La respuesta no contiene JSON válido")
                return None
        else:
            print(f"Error al acceder a la API: {response.status_code}")
            return None
    
    except Exception as e:
        print(f"Error al realizar solicitud API: {str(e)}")
        return None
