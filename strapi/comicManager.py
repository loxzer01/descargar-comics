import os
import asyncio
import aiohttp
import re
from typing import Dict, List, Optional, Union

class ComicManager:
    def __init__(self, strapi_url: str, strapi_token: str):
        self.strapi_url = strapi_url
        self.headers = {
            'Authorization': f'Bearer {strapi_token}',
            'Content-Type': 'application/json',
        }
        
    async def get_comic_by_document_id(self, document_id: str) -> Optional[Dict]:
        """Get a comic by its document_id"""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    f"{self.strapi_url}/api/comics?filters[documentId][$eq]={document_id}",
                    headers=self.headers,
                    timeout=30  # Add timeout
                ) as response:
                    if response.status != 200:
                        print(f"Error getting comic: {response.status}")
                        return None
                    
                    data = await response.json()
                    if not data.get('data'):
                        # Try with snake case as fallback
                        async with session.get(
                            f"{self.strapi_url}/api/comics?filters[document_id][$eq]={document_id}",
                            headers=self.headers,
                            timeout=30
                        ) as fallback_response:
                            fallback_data = await fallback_response.json()
                            return fallback_data['data'][0] if fallback_data.get('data') else None
                    
                    return data['data'][0] if data['data'] else None
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                print(f"Network error when getting comic: {str(e)}")
                return None
            except Exception as e:
                print(f"Unexpected error when getting comic: {str(e)}")
                return None

    async def create_comic(self, comic_data: Dict) -> Dict:
        """Create a new comic with normalized data"""
        # Normalize data fields
        normalized_data = self._normalize_comic_data(comic_data)
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{self.strapi_url}/api/comics",
                    json={"data": normalized_data},  # Wrap in data field as required by Strapi
                    headers=self.headers,
                    timeout=30
                ) as response:
                    response_data = await response.json()
                    if response.status not in (200, 201):
                        print(f"Error creating comic: {response.status}")
                        print(f"Response: {response_data}")
                    return response_data
            except Exception as e:
                print(f"Error creating comic: {str(e)}")
                return {"error": str(e)}

    async def update_comic(self, comic_id: int, comic_data: Dict) -> Dict:
        """Update an existing comic with normalized data"""
        normalized_data = self._normalize_comic_data(comic_data)
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.put(
                    f"{self.strapi_url}/api/comics/{comic_id}",
                    json={"data": normalized_data},  # Wrap in data field
                    headers=self.headers,
                    timeout=30
                ) as response:
                    response_data = await response.json()
                    if response.status not in (200, 201):
                        print(f"Error updating comic: {response.status}")
                        print(f"Response: {response_data}")
                    return response_data
            except Exception as e:
                print(f"Error updating comic: {str(e)}")
                return {"error": str(e)}

    def _normalize_comic_data(self, comic_data: Dict) -> Dict:
        """Normalize comic data to match Strapi expectations"""
        normalized = comic_data.copy()
        
        # Ensure required fields
        normalized.setdefault('title', '')
        normalized.setdefault('description', normalized['title'])
        
        # Convert document_id/documentId
        if 'document_id' in normalized and 'documentId' not in normalized:
            normalized['documentId'] = normalized.pop('document_id')
        if 'documentId' not in normalized:
            normalized['documentId'] = self._generate_document_id(normalized['title'])
        
        # Handle genres - ensure it's a list
        if 'genres' in normalized and isinstance(normalized['genres'], str):
            normalized['genres'] = [g.strip() for g in normalized['genres'].split(',')]
        
        # Ensure boolean fields are actually booleans
        for bool_field in ['isCompleted', 'isImageInURL']:
            if bool_field in normalized and not isinstance(normalized[bool_field], bool):
                normalized[bool_field] = bool(normalized[bool_field])
        
        return normalized
    
    def _generate_document_id(self, title: str) -> str:
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

    async def create_or_update_comic(self, comic_data: Dict) -> Dict:
        """Create or update a comic and return the response with ID clearly accessible"""
        document_id = comic_data.get('documentId') or comic_data.get('document_id') or self._generate_document_id(comic_data['title'])
        existing_comic = await self.get_comic_by_document_id(document_id)

        response = None
        if existing_comic:
            comic_id = await self.extract_comic_id(existing_comic)
            if comic_id:
                response = await self.update_comic(comic_id, comic_data)
                response['extracted_id'] = comic_id  # Add clear ID field
                return response

        response = await self.create_comic(comic_data)
        if response:
            comic_id = await self.extract_comic_id(response)
            if comic_id:
                response['extracted_id'] = comic_id
        return response