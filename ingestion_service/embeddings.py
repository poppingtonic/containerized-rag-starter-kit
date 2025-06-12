"""Embedding generation for the ingestion service."""

import time
from openai import OpenAI
from config import OPENAI_API_KEY, RATE_LIMIT_DELAY

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)


def create_embedding(text):
    """Create embeddings using OpenAI with rate limiting.
    
    Args:
        text: Text to create embedding for
        
    Returns:
        List of embedding values
    """
    try:
        response = client.embeddings.create(
            input=text,
            model="text-embedding-ada-002"
        )
        # Add small delay to avoid hitting API rate limits
        time.sleep(RATE_LIMIT_DELAY)
        return response.data[0].embedding
    except Exception as e:
        print(f"Error creating embedding: {e}")
        time.sleep(1)  # Wait longer on errors
        # Return a default embedding if we can't get a real one
        # This is not ideal but prevents total failure
        return [0.0] * 1536


def create_embeddings_batch(texts):
    """Create embeddings for a batch of texts.
    
    Args:
        texts: List of text strings
        
    Returns:
        List of embedding lists
    """
    embeddings = []
    for text in texts:
        try:
            embedding = create_embedding(text)
            embeddings.append(embedding)
        except Exception as e:
            print(f"Error creating embedding for text batch: {e}")
            # Add default embedding for this text
            embeddings.append([0.0] * 1536)
    
    return embeddings