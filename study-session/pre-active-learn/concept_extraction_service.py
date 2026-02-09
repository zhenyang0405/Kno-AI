"""
Material Concept Extraction Service

Extracts and identifies key concepts from PDF materials using Gemini AI.
Saves concepts to material_concepts table for tracking student understanding.
"""
import logging
from typing import Optional, List, Dict
import json
import psycopg2
from google import genai
from google.genai import types

from config import (
    GEMINI_API_KEY,
    GEMINI_THINKING_MODEL,
    DB_HOST,
    DB_NAME,
    DB_USER,
    DB_PASS,
    DB_PORT
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_db_connection():
    """Create database connection"""
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        port=DB_PORT
    )


def check_concepts_exist(material_id: int) -> bool:
    """
    Check if concepts already extracted for a material
    
    Args:
        material_id: ID of the material
        
    Returns:
        True if concepts exist, False otherwise
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT COUNT(*) FROM material_concepts WHERE material_id = %s",
            (material_id,)
        )
        count = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return count > 0
        
    except Exception as e:
        logger.error(f"Error checking concepts existence: {e}")
        if conn:
            conn.close()
        return False


def extract_material_concepts(material_id: int, cache_name: Optional[str] = None) -> List[Dict]:
    """
    Extract concepts from a material using Gemini AI
    
    Args:
        material_id: ID of the material
        cache_name: Optional Gemini cache name to use
        
    Returns:
        List of extracted concepts
        
    Raises:
        ValueError: If material not found
        Exception: For database or API errors
    """
    conn = None
    try:
        # Check if concepts already extracted
        if check_concepts_exist(material_id):
            logger.info(f"Concepts already extracted for material {material_id}, skipping")
            return get_material_concepts(material_id)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get material info
        cursor.execute(
            "SELECT original_filename FROM materials WHERE id = %s",
            (material_id,)
        )
        result = cursor.fetchone()
        
        if not result:
            raise ValueError(f"Material {material_id} not found")
        
        filename = result[0]
        logger.info(f"Extracting concepts from material: {filename}")
        
        # Prepare Gemini prompt
        prompt = """Analyze this educational material and extract all major concepts.

For each concept, provide:
1. concept_id: A short, kebab-case identifier (e.g., "python-functions", "calculus-derivatives")
2. concept_name: Clear, descriptive name
3. description: Brief explanation of the concept (2-3 sentences)
4. page_start: First page where concept appears
5. page_end: Last page where concept is discussed
6. prerequisite_concepts: List of concept_ids that should be understood first (empty array if none)

Return the result as a valid JSON array with this exact structure:
[
  {
    "concept_id": "string",
    "concept_name": "string", 
    "description": "string",
    "page_start": number,
    "page_end": number,
    "prerequisite_concepts": ["concept_id1", "concept_id2"]
  }
]

Extract 5-15 major concepts. Focus on key learning objectives and important topics."""

        # Call Gemini API
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        config_params = {
            "temperature": 0.3,  # Lower temperature for more consistent extraction
            "response_mime_type": "application/json"
        }
        
        # Use cache if available
        if cache_name:
            config_params["cached_content"] = cache_name
            logger.info(f"Using cached content: {cache_name}")
        
        response = client.models.generate_content(
            model=GEMINI_THINKING_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(**config_params)
        )
        
        # Parse response
        concepts_json = response.text
        logger.debug(f"Gemini response: {concepts_json[:200]}...")
        
        concepts = json.loads(concepts_json)
        logger.info(f"Extracted {len(concepts)} concepts")
        
        # Save concepts to database
        for concept in concepts:
            cursor.execute(
                """
                INSERT INTO material_concepts 
                (material_id, concept_id, concept_name, description, page_start, page_end, prerequisite_concepts)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (material_id, concept_id) DO NOTHING
                """,
                (
                    material_id,
                    concept['concept_id'],
                    concept['concept_name'],
                    concept.get('description', ''),
                    concept['page_start'],
                    concept['page_end'],
                    json.dumps(concept.get('prerequisite_concepts', []))
                )
            )
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"Successfully saved {len(concepts)} concepts for material {material_id}")
        return concepts
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Gemini response as JSON: {e}")
        if conn:
            conn.rollback()
            conn.close()
        raise Exception(f"Invalid JSON response from Gemini: {e}")
    except Exception as e:
        logger.error(f"Error extracting concepts: {e}")
        if conn:
            conn.rollback()
            conn.close()
        raise


def get_material_concepts(material_id: int) -> List[Dict]:
    """
    Get all concepts for a material from database
    
    Args:
        material_id: ID of the material
        
    Returns:
        List of concepts
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """
            SELECT id, concept_id, concept_name, description, user_understanding,
                   page_start, page_end, prerequisite_concepts
            FROM material_concepts
            WHERE material_id = %s
            ORDER BY page_start, concept_id
            """,
            (material_id,)
        )
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        concepts = []
        for row in rows:
            concepts.append({
                'id': row[0],
                'concept_id': row[1],
                'concept_name': row[2],
                'description': row[3],
                'user_understanding': row[4],
                'page_start': row[5],
                'page_end': row[6],
                'prerequisite_concepts': row[7] if row[7] else []
            })
        
        return concepts
        
    except Exception as e:
        logger.error(f"Error getting concepts: {e}")
        if conn:
            conn.close()
        return []


def update_concept_understanding(concept_id: int, user_understanding: str) -> bool:
    """
    Update user's understanding level for a specific concept
    
    Args:
        concept_id: Database ID of the concept (not concept_id field)
        user_understanding: Text describing user's understanding level
                          (e.g., "struggling", "partial", "confident", "mastered")
        
    Returns:
        True if successful, False otherwise
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """
            UPDATE material_concepts 
            SET user_understanding = %s
            WHERE id = %s
            """,
            (user_understanding, concept_id)
        )
        
        updated = cursor.rowcount > 0
        conn.commit()
        cursor.close()
        conn.close()
        
        if updated:
            logger.info(f"Updated understanding for concept {concept_id}: {user_understanding}")
        else:
            logger.warning(f"Concept {concept_id} not found")
        
        return updated
        
    except Exception as e:
        logger.error(f"Error updating concept understanding: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False


def update_multiple_concepts_understanding(updates: List[Dict]) -> Dict[str, int]:
    """
    Update understanding for multiple concepts in a batch
    
    Args:
        updates: List of dicts with 'concept_id' (DB id) and 'user_understanding'
                 Example: [{'concept_id': 1, 'user_understanding': 'mastered'}, ...]
        
    Returns:
        Dict with counts: {'updated': int, 'failed': int}
    """
    updated_count = 0
    failed_count = 0
    
    for update in updates:
        concept_id = update.get('concept_id')
        user_understanding = update.get('user_understanding')
        
        if not concept_id or not user_understanding:
            failed_count += 1
            continue
        
        if update_concept_understanding(concept_id, user_understanding):
            updated_count += 1
        else:
            failed_count += 1
    
    logger.info(f"Batch update complete: {updated_count} updated, {failed_count} failed")
    return {'updated': updated_count, 'failed': failed_count}
