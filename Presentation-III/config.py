import os
from dotenv import load_dotenv

# Load .env file if available
load_dotenv(override=True)

class Config:
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = int(os.getenv('DB_PORT', 3306))
    DB_USER = os.getenv('DB_USER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')
    DB_NAME = os.getenv('DB_NAME', 'ScholarshipDB')
    
    SECRET_KEY = os.getenv('SECRET_KEY', 'scholarship-mgmt-secret-2026')
    DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() in ('true', '1', 't')
    PORT = int(os.getenv('PORT', 5000))
    
    @classmethod
    def get_db_config(cls, include_db=True):
        load_dotenv(override=True)
        host = os.getenv('DB_HOST', cls.DB_HOST)
        port = int(os.getenv('DB_PORT', cls.DB_PORT))
        user = os.getenv('DB_USER', cls.DB_USER)
        password = os.getenv('DB_PASSWORD', cls.DB_PASSWORD)
        db_name = os.getenv('DB_NAME', cls.DB_NAME)

        cfg = {
            'host': host,
            'port': port,
            'user': user,
            'password': password,
            'autocommit': True
        }
        if include_db:
            cfg['database'] = cls.DB_NAME
        return cfg

