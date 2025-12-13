"""Утилита для проверки подключения к Weaviate."""

import time
from src.vdb.client import get_weaviate_client
from src.vdb.config import WEAVIATE_URL


def wait_for_weaviate(timeout: int = 60, check_interval: float = 2.0) -> bool:
    start_time = time.time()
    
    print(f"Ожидание подключения к Weaviate по адресу: {WEAVIATE_URL}")
    print(f"Таймаут: {timeout} секунд")
    
    while time.time() - start_time < timeout:
        try:
            client = get_weaviate_client()
            
            # Проверяем готовность через метод is_ready()
            if client.is_ready():
                elapsed_time = time.time() - start_time
                print(f"✓ Weaviate подключен успешно за {elapsed_time:.2f} секунд")
                client.close()
                return True
            
            client.close()
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            remaining_time = timeout - elapsed_time
            
            if remaining_time > 0:
                print(f"⏳ Ожидание... ({elapsed_time:.1f}s / {timeout}s) - {str(e)[:50]}")
                time.sleep(check_interval)
            else:
                break
    
    print(f"✗ Не удалось подключиться к Weaviate за {timeout} секунд")
    return False

