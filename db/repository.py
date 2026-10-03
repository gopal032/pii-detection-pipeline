import os

# Replace 'YOUR_PASSWORD' with the password you set during installation
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "Redstone")

DB_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://postgres:{DB_PASSWORD}@localhost:5432/pii_db",
)