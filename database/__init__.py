# database/__init__.py
# ============================================================================
# UAT TOOLKIT DATABASE PACKAGE
# ============================================================================
# Provides database access for UAT cycle management.
# Connects to the shared client_product_database.db.

from .db_manager import UATDatabase, get_database_path

__all__ = ['UATDatabase', 'get_database_path']
